"""独立 worker：采集与模型任务均不占用 API 请求线程，可重启后恢复入库任务。"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.db import QuantRun, ResearchJob, ServiceState, build_database
from app.providers.base import ProviderError
from app.providers.demo import DemoQuoteProvider
from app.providers.public import PublicQuoteProvider
from app.providers.runner import run_collector
from app.quant.service import claim_experiment, fail_experiment, recover_experiments
from app.services.calendar import market_session
from app.services.jobs import claim_job, finish_failed, recover_expired_jobs
from app.services.market import MarketService, set_service_state
from app.services.research_data import process_one, recover_requests, schedule_research
from app.shared.time import as_utc, utc_now


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


def collect_market(sessions, settings, market):
    if settings.market_provider == "public":
        with sessions() as session:
            calendar = session.get(ServiceState, "calendar")
            needs_calendar = (
                calendar is None
                or (utc_now() - as_utc(calendar.updated_at)).total_seconds() > 86400
            )
        if needs_calendar:
            try:
                data = run_collector("calendar", "sina", settings.provider_timeout_seconds)
                set_service_state(sessions, "calendar", data)
            except Exception:
                pass  # 保留旧日历，状态接口会明确显示范围是否覆盖今日。
    for asset_type in ("stock", "etf", "index"):
        set_service_state(sessions, f"collection:{asset_type}", {"status": "running"})
        try:
            result = market.refresh(asset_type)
            set_service_state(
                sessions,
                f"collection:{asset_type}",
                {
                    "status": "ok",
                    "source": result.source,
                    "count": result.universe_count,
                    "snapshot_id": result.snapshot_id,
                },
            )
        except Exception as exc:
            set_service_state(
                sessions,
                f"collection:{asset_type}",
                {
                    "status": "failed",
                    # ProviderError 只含适配器生成的安全描述，不能透传其他异常原文。
                    "message": (
                        str(exc)
                        if isinstance(exc, ProviderError)
                        else f"公开行情采集失败（{type(exc).__name__}），保留旧数据"
                    ),
                },
            )


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
    child, active, started = None, None, 0
    next_collection, collection = 0, None
    next_research, research_collection = 0, None
    quant_child, quant_id, quant_started = None, None, 0
    try:
        with single_worker(), ThreadPoolExecutor(max_workers=2) as pool:
            recover_requests(sessions)
            recover_experiments(sessions)
            while True:
                set_service_state(sessions, "worker", {"pid": os.getpid(), "status": "ready"})
                recover_expired_jobs(sessions, settings.job_max_attempts)
                if quant_child:
                    with sessions() as session:
                        cancelled = session.get(QuantRun, quant_id).cancel_requested
                    expired = time.monotonic() - quant_started > settings.quant_timeout_seconds
                    if cancelled or expired:
                        quant_child.kill()
                        quant_child.wait()
                        fail_experiment(
                            sessions,
                            quant_id,
                            "实验已取消" if cancelled else "实验执行超时",
                            cancelled,
                        )
                    if quant_child.poll() is not None:
                        fail_experiment(sessions, quant_id, "实验进程中断")
                        quant_child, quant_id = None, None
                if quant_child is None:
                    quant_id = claim_experiment(sessions, settings)
                    if quant_id:
                        quant_child = subprocess.Popen(
                            [sys.executable, "-m", "app.quant.run", quant_id],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                        quant_started = time.monotonic()
                with sessions() as session:
                    request = session.get(ServiceState, "refresh_request")
                    manual = request is not None and request.value.get("pending", False)
                    calendar = session.get(ServiceState, "calendar")
                    calendar_dates = calendar.value.get("dates", []) if calendar else []
                due = time.monotonic() >= next_collection
                if settings.scheduler_enabled and time.monotonic() >= next_research:
                    schedule_research(sessions, settings, calendar_dates)
                    next_research = time.monotonic() + settings.refresh_interval_seconds
                if research_collection is None or research_collection.done():
                    research_collection = pool.submit(process_one, sessions, settings)
                # 首次启动和手动刷新允许休市读取；后续已确认休市时无需重复抓全市场。
                trading = market_session(utc_now(), calendar_dates)["code"] not in {
                    "closed",
                    "break",
                }
                if (collection is None or collection.done()) and (
                    manual
                    or (settings.scheduler_enabled and due and (next_collection == 0 or trading))
                ):
                    set_service_state(sessions, "refresh_request", {"pending": False})
                    collection = pool.submit(collect_market, sessions, settings, market)
                    next_collection = time.monotonic() + settings.refresh_interval_seconds
                if child:
                    with sessions() as session:
                        job = session.get(ResearchJob, active[0])
                        cancelled = job.cancel_requested
                    expired = time.monotonic() - started > settings.job_timeout_seconds
                    if cancelled or expired:
                        child.kill()
                        child.wait()
                        finish_failed(
                            sessions,
                            *active,
                            "任务已取消" if cancelled else "任务执行超时",
                            cancelled,
                        )
                    if child.poll() is not None:
                        finish_failed(sessions, *active, "执行进程中断，检查点已保留")
                        child, active = None, None
                if child is None:
                    active = claim_job(sessions, settings)
                    if active:
                        child = subprocess.Popen(
                            [sys.executable, "-m", "app.agents.run_job", *active],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                        started = time.monotonic()
                time.sleep(1)
    finally:
        if quant_child and quant_child.poll() is None:
            quant_child.kill()
            quant_child.wait()
        if child and child.poll() is None:
            child.kill()
            child.wait()
        engine.dispose()


if __name__ == "__main__":
    run()
