from datetime import datetime, time
from zoneinfo import ZoneInfo


def market_session(now: datetime, dates: list[str]) -> dict:
    local = now.astimezone(ZoneInfo("Asia/Shanghai"))
    day = local.date().isoformat()
    if local.weekday() >= 5:
        return {"code": "closed", "label": "周末休市", "calendar_verified": False}
    # 日历的范围外不能用“周一至周五”猜测节假日。
    if not dates or not (min(dates) <= day <= max(dates)):
        return {"code": "unknown", "label": "交易日历未覆盖今日", "calendar_verified": False}
    if day not in dates:
        return {"code": "closed", "label": "非交易日", "calendar_verified": True}
    clock = local.time().replace(tzinfo=None)
    if time(9, 15) <= clock < time(9, 30):
        code, label = "auction", "集合竞价"
    elif time(9, 30) <= clock <= time(11, 30) or time(13) <= clock < time(15):
        code, label = "trading", "盘中交易"
    elif time(11, 30) < clock < time(13):
        code, label = "break", "午间休市"
    else:
        code, label = "closed", "盘前 / 盘后"
    return {"code": code, "label": label, "calendar_verified": True}
