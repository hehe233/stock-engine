"""特征函数不读取模型、数据库或网络；时序规则在此集中定义。"""

import numpy as np
import pandas as pd

FEATURES = [
    "return_1",
    "return_5",
    "return_20",
    "volatility_20",
    "range_pct",
    "ma_distance",
    "volume_ratio",
]
FEATURE_VERSION = "daily-v1"


def build_features(bars, horizon=5, event_return=0.2, adjustment="raw"):
    frame = bars.sort_values(["symbol", "date"]).copy()
    days = sorted(frame.date.unique())
    day_index = {day: i for i, day in enumerate(days)}
    frame["day_index"] = frame.date.map(day_index)
    parts = []
    for _, group in frame.groupby("symbol", sort=True):
        group = group.copy()
        close = group.close
        daily = close.pct_change(fill_method=None)
        group["return_1"] = daily
        group["return_5"] = close / close.shift(5) - 1
        group["return_20"] = close / close.shift(20) - 1
        group["volatility_20"] = daily.rolling(20).std()
        group["range_pct"] = (group.high - group.low) / close
        group["ma_distance"] = close / close.rolling(20).mean() - 1
        volume = group.volume.replace(0, np.nan)
        group["volume_ratio"] = volume / volume.rolling(5).mean()
        group["label_end"] = group.date.shift(-horizon)
        group["future_return"] = close.shift(-horizon) / close - 1
        group["label"] = (group.future_return >= event_return - 1e-12).astype(int)
        # 如果缺了证券日线，不把「下一条记录」误称为下一交易日。
        contiguous_past = group.day_index - group.day_index.shift(20) == 20
        contiguous_future = group.day_index.shift(-horizon) - group.day_index == horizon
        # 日线信号最早在下一交易日开盘前可用；晚到数据不进入历史预测。
        next_days = group.day_index.map(lambda i: days[i + 1] if i + 1 < len(days) else None)
        next_open = pd.to_datetime(next_days, utc=True) + pd.Timedelta(hours=1, minutes=30)
        # 连同回看窗口中的历史数据一起检查；只检查信号当日会漏掉迟到的旧日线。
        available_ns = group.available_at.map(
            lambda value: value.value if pd.notna(value) else np.nan
        )
        latest_visible = pd.to_datetime(available_ns.rolling(21, min_periods=1).max(), utc=True)
        visible = latest_visible.isna() | (latest_visible <= next_open)
        group["feature_valid"] = contiguous_past & visible
        group["label_valid"] = contiguous_future & group.future_return.notna()
        # 标签也有可见时间：迟到的未来收盘不能提前用于拟合校准器。
        assumed_close_time = pd.to_datetime(group.date, utc=True) + pd.Timedelta(hours=8)
        group["label_available_at"] = group.available_at.fillna(assumed_close_time).shift(-horizon)
        if adjustment == "raw":
            corporate_action = (group.prev_close / close.shift(1) - 1).abs() > 0.001
            group["feature_valid"] &= ~corporate_action.rolling(21, min_periods=1).max().astype(
                bool
            )
            future_action = pd.Series(False, index=group.index)
            for step in range(1, horizon + 1):
                future_action |= corporate_action.shift(-step, fill_value=False)
            group["label_valid"] &= ~future_action
        parts.append(group)
    result = pd.concat(parts, ignore_index=True)
    result[FEATURES] = result[FEATURES].replace([np.inf, -np.inf], np.nan)
    return result


def time_folds(samples, params):
    """按日期整组切分，purge 的是标签结束日，而不是只切特征行。"""
    days = sorted(samples.date.unique())
    for number in range(params.folds):
        start = number * params.test_days
        calibration_start = start + params.train_days
        test_start = calibration_start + params.calibration_days
        end = test_start + params.test_days
        if end > len(days):
            break
        train = samples[
            (samples.date >= days[start])
            & (samples.date < days[calibration_start])
            & (samples.label_end < days[calibration_start])
            & (
                samples.label_available_at
                < pd.Timestamp(days[calibration_start], tz="UTC")
                + pd.Timedelta(hours=1, minutes=30)
            )
        ]
        calibration = samples[
            (samples.date >= days[calibration_start])
            & (samples.date < days[test_start])
            & (samples.label_end < days[test_start])
            & (
                samples.label_available_at
                < pd.Timestamp(days[test_start], tz="UTC") + pd.Timedelta(hours=1, minutes=30)
            )
        ]
        test = samples[(samples.date >= days[test_start]) & (samples.date <= days[end - 1])]
        yield number, train, calibration, test
