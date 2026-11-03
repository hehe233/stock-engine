import re


def normalize_symbol(raw: str, asset_type: str) -> str:
    raw = raw.strip().upper()
    if re.fullmatch(r"(SH|SZ|BJ)\d{6}", raw):
        return f"{raw[2:]}.{raw[:2]}"
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", raw):
        return raw
    if not re.fullmatch(r"\d{6}", raw):
        raise ValueError("无效代码")
    if asset_type == "stock":
        exchange = (
            "BJ" if raw.startswith(("4", "8", "92")) else "SH" if raw.startswith("6") else "SZ"
        )
    elif asset_type == "etf":
        exchange = "SH" if raw.startswith("5") else "SZ"
    else:
        # 指数与股票的代码可能相同；无交易所信息时拒绝猜测。
        raise ValueError("指数代码缺少交易所")
    return f"{raw}.{exchange}"
