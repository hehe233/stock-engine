"""固定参数滚动训练。校准器只看校准区，不用测试集优化阈值或挑选模型。"""

import importlib.metadata
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from app.quant.backtest import simulate
from app.quant.features import FEATURE_VERSION, FEATURES, build_features, time_folds

ENGINE_VERSION = "walk-forward-v1"


def metrics(labels, probability):
    y, p = np.asarray(labels), np.clip(np.asarray(probability), 1e-6, 1 - 1e-6)
    bins = []
    for i in range(10):
        selected = (p >= i / 10) & (p < (i + 1) / 10)
        if selected.any():
            bins.append(
                {
                    "lower": i / 10,
                    "upper": (i + 1) / 10,
                    "count": int(selected.sum()),
                    "predicted": float(p[selected].mean()),
                    "observed": float(y[selected].mean()),
                }
            )
    return {
        "count": len(y),
        "positives": int(y.sum()),
        "event_rate": float(y.mean()),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "auc": float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
        "ece": sum(b["count"] * abs(b["predicted"] - b["observed"]) for b in bins) / len(y),
        "bins": bins,
    }


def train_experiment(bars, params, details, progress=lambda _: None):
    frame = build_features(bars, params.horizon, params.event_return, details["adjustment"])
    samples = frame[frame.feature_valid & frame.label_valid].copy()
    samples = samples.dropna(subset=FEATURES[:-1])
    predictions, folds, models, skipped = [], [], [], []
    attempted = 0
    for number, train, calibration, test in time_folds(samples, params):
        attempted += 1
        progress(f"训练第 {number + 1} 折")
        if (
            len(train) < 100
            or len(calibration) < 30
            or len(test) < 10
            or any(
                part.label.value_counts().reindex([0, 1], fill_value=0).min() < 5
                for part in (train, calibration)
            )
        ):
            skipped.append(
                {
                    "fold": number + 1,
                    "reason": "训练/校准样本不足或任一类别少于 5 个",
                    "train": len(train),
                    "calibration": len(calibration),
                    "test": len(test),
                }
            )
            continue
        model = lgb.LGBMClassifier(
            n_estimators=80,
            max_depth=3,
            num_leaves=7,
            learning_rate=0.05,
            min_child_samples=20,
            reg_lambda=1,
            random_state=params.seed,
            n_jobs=1,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        )
        model.fit(train[FEATURES], train.label)
        margins = model.booster_.predict(calibration[FEATURES], raw_score=True).reshape(-1, 1)
        calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=params.seed)
        calibrator.fit(margins, calibration.label)
        raw = model.booster_.predict(test[FEATURES])
        probability = calibrator.predict_proba(
            model.booster_.predict(test[FEATURES], raw_score=True).reshape(-1, 1)
        )[:, 1]
        output = test[["symbol", "date", "label_end", "label", "future_return"]].copy()
        output["probability"], output["raw_probability"], output["fold"] = (
            probability,
            raw,
            number + 1,
        )
        output["baseline_probability"] = float(calibration.label.mean())
        predictions.append(output)
        folds.append(
            {
                "fold": number + 1,
                "train_start": train.date.min(),
                "train_end": train.date.max(),
                "train_label_end": train.label_end.max(),
                "calibration_start": calibration.date.min(),
                "calibration_end": calibration.date.max(),
                "calibration_label_end": calibration.label_end.max(),
                "test_start": test.date.min(),
                "test_end": test.date.max(),
                "train_count": len(train),
                "calibration_count": len(calibration),
                "metrics": metrics(test.label, probability),
                "raw_metrics": metrics(test.label, raw),
            }
        )
        models.append(
            {
                "fold": number + 1,
                "lightgbm_text": model.booster_.model_to_string(),
                "sigmoid_coef": calibrator.coef_.tolist(),
                "sigmoid_intercept": calibrator.intercept_.tolist(),
                "features": FEATURES,
                "importance": dict(
                    zip(
                        FEATURES,
                        model.booster_.feature_importance(importance_type="gain").tolist(),
                        strict=True,
                    )
                ),
            }
        )
    for number in range(attempted, params.folds):
        skipped.append(
            {"fold": number + 1, "reason": "连续日期长度不足以形成完整的训练、校准、测试窗口"}
        )
    if not predictions:
        raise ValueError(
            "没有可评估的滚动分区：需更多连续日线，且每个训练/校准区各至少 5 个正例和负例。"
            "可减少窗口，或补充非精选历史证券数据。"
        )
    predicted = pd.concat(predictions, ignore_index=True).sort_values(["date", "symbol"])
    monthly = []
    for month, group in predicted.groupby(predicted.date.str[:7]):
        monthly.append({"month": month, **metrics(group.label, group.probability)})
    progress("计算样本外误差与成交模拟")
    result = {
        "engine_version": ENGINE_VERSION,
        "feature_version": FEATURE_VERSION,
        "target": "未来 5 个数据集交易日收盘涨幅 ≥20%",
        "research_only": True,
        "evaluation_end": predicted.label_end.max(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ("lightgbm", "scikit-learn", "pandas", "duckdb", "pyarrow")
        },
        "feature_names": FEATURES,
        "input_rows": len(bars),
        "usable_samples": len(samples),
        "excluded_rows": len(bars) - len(samples),
        "folds": folds,
        "skipped_folds": skipped,
        "requested_folds": params.folds,
        "metrics": metrics(predicted.label, predicted.probability),
        "raw_metrics": metrics(predicted.label, predicted.raw_probability),
        "baseline_metrics": metrics(predicted.label, predicted.baseline_probability),
        "monthly_errors": monthly,
        "importance": models[-1]["importance"],
        "backtest": simulate(bars, predicted, params, details["adjustment"]),
        "warnings": [
            *details["warnings"],
            "校准可能变差，请同时比较原始预测和校准区发生率基准。",
            "标签窗口有重叠，样本并非独立；不报告未经相关性修正的置信区间。",
            "本次结果仅对应冻结的数据、固定参数和测试日期，不是当前股票的可部署概率。",
            "多次查看测试结果后再改参数会产生选择偏差，应保留额外未查看的最终验证区。",
        ],
    }
    # 确保报告没有 numpy 标量或 NaN，前端和数据库都接收标准 JSON。
    json.dumps(result, allow_nan=False)
    return result, predicted, models
