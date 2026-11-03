"""Single-worker entry point; scheduling, process mechanics and state are separate."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.db import build_database
from app.jobs.service import recover_expired_jobs
from app.market.service import MarketService, set_service_state
from app.providers.demo import DemoQuoteProvider
from app.providers.public import PublicQuoteProvider
from app.quant.service import recover_experiments
from app.research.collection import recover_requests
from app.runtime.agent_slot import AgentSlot
from app.runtime.collection import CollectionScheduler
from app.runtime.quant_slot import QuantSlot


@contextmanager
def single_worker():
    # 本版单机 worker，使用操作系统文件锁；进程退出自动释放，避免遗留锁文件阻塞重启。
    file = Path(".worker.lock").open("a+b")
    file.write(b"0")
    file.flush()
    file.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        file.close()


def run():
    settings = get_settings()
    engine, sessions = build_database(settings.database_url)
    provider = (
        DemoQuoteProvider()
        if settings.market_provider == "demo"
        else PublicQuoteProvider(settings.public_source, settings.provider_timeout_seconds)
    )
    market = MarketService(
        sessions, provider, settings.refresh_interval_seconds, settings.market_provider
    )
    agent = AgentSlot(sessions, settings)
    quant = QuantSlot(sessions, settings)
    try:
        with single_worker(), ThreadPoolExecutor(max_workers=2) as pool:
            # Recovery must occur only after acquiring the single-worker lock.
            recover_requests(sessions)
            recover_experiments(sessions)
            collections = CollectionScheduler(sessions, settings, market, pool)
            try:
                while True:
                    set_service_state(sessions, "worker", {"pid": os.getpid(), "status": "ready"})
                    recover_expired_jobs(sessions, settings.job_max_attempts)
                    quant.tick()
                    collections.tick()
                    agent.tick()
                    time.sleep(1)
            finally:
                try:
                    quant.close()
                finally:
                    agent.close()
    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run()
