"""十个完整年度的观察目录；这是人工选择的研究对象，不是经统计认证的妖股榜。"""

HISTORY_CASES = [
    {
        "id": f"{year}-{symbol}",
        "year": year,
        "symbol": symbol,
        "name": name,
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
        "selection": "人工观察目录；是否强势、是否失败由日线窗口统计展示，不预填收益",
    }
    for year, symbol, name in [
        (2016, "000935.SZ", "四川双马"),
        (2017, "600903.SH", "贵州燃气"),
        (2018, "600776.SH", "东方通信"),
        (2019, "600776.SH", "东方通信"),
        (2020, "002400.SZ", "省广集团"),
        (2021, "002432.SZ", "九安医疗"),
        (2022, "000957.SZ", "中通客车"),
        (2023, "002855.SZ", "捷荣技术"),
        (2024, "000062.SZ", "深圳华强"),
        (2025, "300476.SZ", "胜宏科技"),
    ]
]


def history_case(case_id):
    return next((row for row in HISTORY_CASES if row["id"] == case_id), None)
