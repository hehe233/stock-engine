from datetime import UTC, datetime
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    # SQLite 会丢失时区信息；数据库中的时间约定统一为 UTC，API 始终返回时区。
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
