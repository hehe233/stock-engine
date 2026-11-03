from threading import Lock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import MarketSnapshot, ServiceState
from app.providers.base import QuoteProvider
from app.schemas import MarketResponse
from app.shared.time import as_utc, utc_now


class MarketService:
    def __init__(self, sessions: sessionmaker, provider: QuoteProvider, interval: int, mode="demo"):
        self.sessions = sessions
        self.provider = provider
        self.interval = interval
        self.mode = mode
        self._refresh_lock = Lock()

    def refresh(self, asset_type: str = "stock") -> MarketResponse:
        # P1 的独立 worker 执行采集；进程内锁补充保护直接调用，多实例仍需分布式锁。
        with self._refresh_lock, self.sessions() as session:
            batch = self.provider.fetch_quotes(asset_type)
            if not batch.quotes:
                raise ValueError("行情源返回空数据，保留上一个有效快照")
            if len({quote.symbol for quote in batch.quotes}) != len(batch.quotes):
                raise ValueError("行情源包含重复股票代码")
            previous = self.latest_row(session, asset_type)
            old_symbols = {item["symbol"] for item in previous.quotes} if previous else set()
            missing = sorted(old_symbols - {quote.symbol for quote in batch.quotes})
            snapshot = MarketSnapshot(
                id=str(uuid4()),
                source=batch.source,
                as_of=as_utc(batch.as_of) if batch.as_of else None,
                asset_type=asset_type,
                details={**batch.details, "missing_from_previous": missing},
                fetched_at=utc_now(),
                quotes=[quote.model_dump(mode="json") for quote in batch.quotes],
            )
            session.add(snapshot)
            session.commit()
            return self.serialize(snapshot)

    def latest_row(self, session: Session, asset_type="stock") -> MarketSnapshot | None:
        source_filter = (
            MarketSnapshot.source == "demo"
            if self.mode == "demo"
            else MarketSnapshot.source != "demo"
        )
        return session.scalar(
            select(MarketSnapshot)
            .where(MarketSnapshot.asset_type == asset_type, source_filter)
            .order_by(MarketSnapshot.fetched_at.desc())
            .limit(1)
        )

    def latest(
        self,
        session: Session,
        asset_type="stock",
        page=1,
        page_size=100,
        search="",
        sort_by="change_pct",
        descending=True,
    ) -> MarketResponse | None:
        snapshot = self.latest_row(session, asset_type)
        if snapshot is None:
            return None
        response = self.serialize(snapshot)
        keyword = search.strip().lower()
        rows = [
            quote
            for quote in response.quotes
            if keyword in f"{quote.symbol} {quote.name} {quote.sector}".lower()
        ]
        present = [quote for quote in rows if getattr(quote, sort_by) is not None]
        missing = [quote for quote in rows if getattr(quote, sort_by) is None]
        present.sort(key=lambda quote: getattr(quote, sort_by), reverse=descending)
        response.total = len(rows)
        response.page, response.page_size = page, page_size
        response.quotes = (present + missing)[(page - 1) * page_size : page * page_size]
        return response

    def serialize(self, snapshot: MarketSnapshot) -> MarketResponse:
        fetched_at = as_utc(snapshot.fetched_at)
        details = snapshot.details or {}
        warnings = list(details.get("warnings", []))
        if snapshot.source != "demo":
            warnings += [
                "免费公开行情没有延迟或可用性保证，来源可能限流、缺页或变更。",
                "全量覆盖尚未与交易所证券名录核验，返回数量不等于全市场数量。",
            ]
            if details.get("source_time_known_count", 0) < len(snapshot.quotes):
                warnings.append("部分或全部源时间未知，采集成功不代表行情实时。")
        return MarketResponse(
            snapshot_id=snapshot.id,
            source=snapshot.source,
            is_demo=snapshot.source == "demo",
            asset_type=snapshot.asset_type,
            as_of=as_utc(snapshot.as_of) if snapshot.as_of else None,
            fetched_at=fetched_at,
            # stale 表示采集任务是否落后，不代表演示数据具有实时性。
            stale=(utc_now() - fetched_at).total_seconds() > self.interval * 2,
            refresh_interval_seconds=self.interval,
            quotes=snapshot.quotes,
            total=len(snapshot.quotes),
            universe_count=len(snapshot.quotes),
            source_time_known_count=details.get("source_time_known_count", 0),
            missing_from_previous=details.get("missing_from_previous", []),
            rejected_count=details.get("rejected_count", 0),
            warnings=warnings,
        )


def set_service_state(sessions, key: str, value: dict):
    with sessions() as session:
        row = session.get(ServiceState, key)
        if row is None:
            session.add(ServiceState(key=key, value=value, updated_at=utc_now()))
        else:
            row.value, row.updated_at = value, utc_now()
        session.commit()
