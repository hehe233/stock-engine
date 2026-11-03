import math
from datetime import UTC, datetime, timedelta

from app.shared.time import SHANGHAI


def number(value) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def source_time(value) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (float, int)):
            parsed = datetime.fromtimestamp(value / 1000 if value > 1e12 else value, UTC)
        else:
            text = str(value)
            # 只有时分秒时无法确认交易日期，不能拼接当前日期冒充可靠时间戳。
            if len(text) < 16:
                return None
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=SHANGHAI)
        if parsed > datetime.now(UTC) + timedelta(minutes=5):
            return None
        return parsed.astimezone(UTC)
    except (ValueError, TypeError, OSError, OverflowError):
        return None
