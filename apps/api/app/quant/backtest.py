"""保守的日线撮合模拟。概率标签和可交易收益分别计算，不假定涨停排队可成交。"""

from collections import Counter

import pandas as pd


def simulate(bars, predictions, params, adjustment):
    if adjustment != "raw":
        return {"enabled": False, "reason": "前复权精选案例缺可执行原始价格，交易模拟停用。"}
    days = sorted(bars.date.unique())
    index = {day: i for i, day in enumerate(days)}
    prices = {(r["date"], r["symbol"]): r for r in bars.to_dict("records")}
    signals = {}
    for row in predictions.sort_values(
        ["date", "probability", "symbol"], ascending=[True, False, True]
    ).to_dict("records"):
        i = index[row["date"]]
        if i + 1 < len(days) and row["probability"] >= params.probability_threshold:
            signals.setdefault(days[i + 1], []).append(row)
    cash, holdings, trades, curve = float(params.initial_cash), {}, [], []
    rejected, valuation_complete = Counter(), True
    start = min(predictions.date)
    # 测试结束后只管理已有仓位，不产生新预测；最多延续 20 个数据集交易日。
    last = min(len(days) - 1, index[max(predictions.date)] + params.horizon + 21)

    def blocked(row, side, quantity=100):
        if row is None:
            return "missing_bar"
        symbol = row["symbol"]
        supported = (
            symbol.startswith("DEMO")
            or (symbol.endswith(".SH") and symbol.startswith(("600", "601", "603", "605")))
            or (
                symbol.endswith(".SZ")
                and symbol.startswith(("000", "001", "002", "003", "300", "301"))
            )
        )
        if not supported:
            return "unsupported_trading_lot_rules"
        if row["date"] < "2016-01-01":
            return "unsupported_fee_period"
        if any(
            pd.isna(row.get(k))
            for k in ("tradable", "volume", "prev_close", "upper_limit", "lower_limit")
        ):
            return "unknown_trading_rules"
        if not row["tradable"] or row["volume"] <= 0:
            return "suspended"
        # 即使不是一字板，触及开盘限制仍拒绝；日线无法判断队列优先级。
        if side == "buy" and row["open"] >= row["upper_limit"] - 0.005:
            return "limit_up"
        if side == "sell" and row["open"] <= row["lower_limit"] + 0.005:
            return "limit_down"
        if quantity > row["volume"] * params.participation:
            return "participation_limit"
        return None

    for day in days[index[start] + 1 : last + 1]:
        for symbol, lot in list(holdings.items()):
            row = prices.get((day, symbol))
            if (
                row is not None
                and pd.notna(row["prev_close"])
                and abs(row["prev_close"] / lot["last_close"] - 1) > 0.001
            ):
                lot["corporate_action_unknown"] = True
            if lot.get("corporate_action_unknown"):
                valuation_complete = False
                rejected["corporate_action_unresolved"] += 1
                continue
            if row is not None:
                lot["last_close"] = row["close"]
            if index[day] < lot["exit_index"]:
                continue
            reason = blocked(row, "sell", lot["quantity"])
            if reason:
                rejected[reason] += 1
                continue
            price = row["open"] * (1 - params.slippage_bps / 10000)
            if price < row["low"] or price <= row["lower_limit"]:
                rejected["sell_price_outside_bar"] += 1
                continue
            gross = price * lot["quantity"]
            commission = max(5.0, gross * params.commission_bps / 10000)
            tax_rate = 0.0005 if day >= "2023-08-28" else 0.001
            tax = gross * tax_rate
            cash += gross - commission - tax
            trades.append(
                {
                    "symbol": symbol,
                    "signal_date": lot["signal_date"],
                    "buy_date": lot["buy_date"],
                    "sell_date": day,
                    "quantity": lot["quantity"],
                    "buy_price": lot["price"],
                    "sell_price": price,
                    "gross_pnl": gross - lot["notional"],
                    "fees": commission + tax + lot["fee"],
                    "net_pnl": gross - commission - tax - lot["notional"] - lot["fee"],
                }
            )
            del holdings[symbol]
        for signal in signals.get(day, []):
            symbol = signal["symbol"]
            if symbol in holdings:
                rejected["already_held"] += 1
                continue
            if len(holdings) >= params.max_positions:
                rejected["position_limit"] += 1
                continue
            row = prices.get((day, symbol))
            reason = blocked(row, "buy")
            if reason:
                rejected[reason] += 1
                continue
            price = row["open"] * (1 + params.slippage_bps / 10000)
            if price > row["high"] or price >= row["upper_limit"]:
                rejected["buy_price_outside_bar"] += 1
                continue
            budget = min(cash, params.initial_cash / params.max_positions)
            quantity = (
                int(
                    min(
                        (budget - 5) / (price * (1 + params.commission_bps / 10000)),
                        row["volume"] * params.participation,
                    )
                    // 100
                )
                * 100
            )
            if quantity < 100:
                rejected["insufficient_cash_or_volume"] += 1
                continue
            notional = price * quantity
            fee = max(5.0, notional * params.commission_bps / 10000)
            cash -= notional + fee
            holdings[symbol] = {
                "signal_date": signal["date"],
                "buy_date": day,
                "exit_index": index[day] + params.horizon,
                "price": price,
                "quantity": quantity,
                "notional": notional,
                "fee": fee,
                "last_close": row["close"],
            }
        # 缺当日收盘只能沿用上次估值，并显式标记，不伪装成完全可核验净值。
        stale = any((day, symbol) not in prices for symbol in holdings)
        if stale:
            valuation_complete = False
        equity = cash + sum(lot["quantity"] * lot["last_close"] for lot in holdings.values())
        curve.append(
            {"date": day, "equity": round(equity, 2), "cash": round(cash, 2), "stale": stale}
        )
    peak, drawdown = params.initial_cash, 0
    for point in curve:
        peak = max(peak, point["equity"])
        drawdown = min(drawdown, point["equity"] / peak - 1)
    attribution = {}
    for trade in trades:
        bucket = attribution.setdefault(
            trade["symbol"],
            {"symbol": trade["symbol"], "trades": 0, "gross_pnl": 0, "fees": 0, "net_pnl": 0},
        )
        bucket["trades"] += 1
        for key in ("gross_pnl", "fees", "net_pnl"):
            bucket[key] += trade[key]
    return {
        "enabled": True,
        "curve": curve,
        "trades": trades,
        "rejected": dict(rejected),
        "attribution": list(attribution.values()),
        "open_positions": [{"symbol": s, **v} for s, v in holdings.items()],
        "valuation_complete": valuation_complete,
        "trade_count": len(trades),
        "ending_cash": round(cash, 2),
        "return_pct": round((curve[-1]["equity"] / params.initial_cash - 1) * 100, 4)
        if curve and valuation_complete
        else None,
        "max_drawdown_pct": round(drawdown * 100, 4) if valuation_complete else None,
        "fees": sum(t["fees"] for t in trades) + sum(lot["fee"] for lot in holdings.values()),
        "warnings": [
            "买入后持有 5 个数据集交易日再尝试开盘卖出，区别于收盘到收盘的事件标签。",
            "收益包含未平仓按最后收盘价的参考估值；遇缺价或未处理除权时总收益留空。",
            "成交量为整日量，参与率只是事后容量约束，不能证明开盘时可成交。交易日历未独立核验。",
            "交易模拟只支持 2016 年起沪深主板/创业板 100 股规则；科创板、北交所、ETF 等拒绝成交。",
            "佣金双边最低 5 元；卖出印花税在 2023-08-28 前 0.1%、之后 0.05%；未另计过户费。",
        ],
    }
