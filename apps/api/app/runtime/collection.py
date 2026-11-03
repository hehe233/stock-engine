import time

from app.db import ServiceState
from app.market.calendar import market_session
from app.market.service import set_service_state
from app.providers.base import ProviderError
from app.providers.runner import run_collector
from app.research.collection import process_one, schedule_research
from app.shared.time import as_utc, utc_now


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


class CollectionScheduler:
    """Two existing collection lanes; never increase task/process concurrency."""

    def __init__(self, sessions, settings, market, pool):
        self.sessions, self.settings, self.market, self.pool = sessions, settings, market, pool
        self.next_collection, self.collection = 0, None
        self.next_research, self.research_collection = 0, None

    def tick(self):
        sessions, settings, market, pool = self.sessions, self.settings, self.market, self.pool
        with sessions() as session:
            request = session.get(ServiceState, "refresh_request")
            manual = request is not None and request.value.get("pending", False)
            calendar = session.get(ServiceState, "calendar")
            calendar_dates = calendar.value.get("dates", []) if calendar else []
        due = time.monotonic() >= self.next_collection
        if settings.scheduler_enabled and time.monotonic() >= self.next_research:
            schedule_research(sessions, settings, calendar_dates)
            self.next_research = time.monotonic() + settings.refresh_interval_seconds
        if self.research_collection is None or self.research_collection.done():
            self.research_collection = pool.submit(process_one, sessions, settings)
        # 首次启动和手动刷新允许休市读取；后续已确认休市时无需重复抓全市场。
        trading = market_session(utc_now(), calendar_dates)["code"] not in {
            "closed",
            "break",
        }
        if (self.collection is None or self.collection.done()) and (
            manual
            or (settings.scheduler_enabled and due and (self.next_collection == 0 or trading))
        ):
            set_service_state(sessions, "refresh_request", {"pending": False})
            self.collection = pool.submit(collect_market, sessions, settings, market)
            self.next_collection = time.monotonic() + settings.refresh_interval_seconds
