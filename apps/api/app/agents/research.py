from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas import Factor, Quote, TraceStep


class ResearchState(TypedDict, total=False):
    """类似前端 store 的状态类型。节点返回局部更新，由 LangGraph 合并进状态。"""

    quote: dict
    factors: list[dict]
    heat_score: float
    risks: list[str]
    summary: str
    trace: list[dict]
    is_demo: bool
    source: str
    as_of: str | None
    model_name: str | None
    messages: list
    rounds: int
    evidence: dict
    insight: dict
    research_context: dict


def append_trace(state: ResearchState, node: str, title: str, detail: str) -> list[dict]:
    step = TraceStep(node=node, title=title, detail=detail)
    # 本图是串行图，显式返回新数组。未来并行分支需要给状态字段配置 reducer。
    return [*state.get("trace", []), step.model_dump()]


def validate_quote(state: ResearchState) -> dict:
    quote = Quote.model_validate(state["quote"])
    return {
        "quote": quote.model_dump(mode="json"),
        "trace": append_trace(state, "validate", "校验行情", "验证字段、数值范围和数据类型"),
    }


def calculate_factors(state: ResearchState) -> dict:
    quote = Quote.model_validate(state["quote"])

    def factor(name: str, value: float | None, cap: float, weight: int, note: str) -> Factor:
        return Factor(
            name=name,
            value=value,
            points=round(min(max(value / cap, 0), 1) * weight, 2) if value is not None else None,
            max_points=weight,
            explanation=note,
        )

    # 教学规则刻意保持透明：正向强度截断到 [0, 1] 后乘权重。
    # 它只衡量样本活跃程度，未经过收益验证，不能解释为涨停或盈利概率。
    factors = [
        factor("涨幅强度", quote.change_pct, 10, 30, "正涨幅 / 10 × 30，上限 30 分"),
        factor("换手活跃", quote.turnover_pct, 20, 25, "换手率 / 20 × 25，上限 25 分"),
        factor("量比强度", quote.volume_ratio, 5, 25, "量比 / 5 × 25，上限 25 分"),
        factor("成交规模", quote.amount_yuan, 1_000_000_000, 20, "成交额 / 10 亿 × 20"),
    ]
    return {
        "factors": [item.model_dump() for item in factors],
        "heat_score": round(sum(item.points for item in factors), 2)
        if quote.asset_type == "stock"
        and quote.price is not None
        and all(item.points is not None for item in factors)
        else None,
        "trace": append_trace(state, "factors", "计算因子", "计算四项规则因子及各自分数贡献"),
    }


def check_risks(state: ResearchState) -> dict:
    quote = Quote.model_validate(state["quote"])
    risks = (
        ["当前为虚构演示样本，不能用于真实交易判断。"]
        if state.get("is_demo", True)
        else ["免费公开行情的延迟与完整性没有保证；无源时间的行情不能确认实时性。"]
    )
    if state.get("heat_score") is None:
        risks.append("字段不完整或标的不是股票，不计算股票规则热度总分。")
    if quote.turnover_pct is not None and quote.turnover_pct >= 20:
        risks.append("样本换手率达到 20%：高活跃也可能伴随较大分歧。")
    if quote.change_pct is not None and quote.change_pct >= 9:
        risks.append("样本当日涨幅较大：当前分数不反映追高后的可成交性与回撤。")
    if quote.amount_yuan is not None and quote.amount_yuan < 100_000_000:
        risks.append("样本成交额较低：需额外核验流动性。")
    risks.append("逐笔盘口和经校准的历史回测尚未接入；研究资料不能直接转成连板概率。")
    context = state.get("research_context", {})
    for kind, evidence in context.items():
        if evidence.get("available") is False:
            risks.append(f"{kind}：提交时无可用研究证据。")
    if context.get("portfolio", {}).get("items"):
        for row in context["portfolio"]["items"]:
            risks.extend(row["conditions"])
    return {
        "risks": risks,
        "trace": append_trace(state, "risk", "检查边界", "检查高换手、追高及流动性条件"),
    }


def write_summary(state: ResearchState) -> dict:
    quote = Quote.model_validate(state["quote"])
    score = state["heat_score"]
    if score is None:
        return {
            "summary": (
                f"{quote.name}的股票规则热度分不可用。"
                "请结合已有行情和缺失字段阅读，不能推断连板概率。"
            ),
            "trace": append_trace(state, "report", "生成报告", "保留缺失信息，不伪造总分"),
        }
    intensity = "较高" if score >= 70 else "中等" if score >= 40 else "较低"
    return {
        "summary": (
            f"{quote.name}的规则热度分为 {score:.2f}/100，样本活跃程度{intensity}。"
            "分数由涨幅、换手率、量比和成交额计算；这是规则分析，不是 AI 概率预测或买卖指令。"
        ),
        "trace": append_trace(state, "report", "生成报告", "汇总得分、因子解释和数据局限"),
    }


def build_research_graph(checkpointer=None):
    """规则模式不依赖模型密钥；传入 checkpointer 后也可由任务进程持久化执行。"""
    graph = StateGraph(ResearchState)
    graph.add_node("validate", validate_quote)
    graph.add_node("factors", calculate_factors)
    graph.add_node("risk", check_risks)
    graph.add_node("report", write_summary)
    graph.add_edge(START, "validate")
    graph.add_edge("validate", "factors")
    graph.add_edge("factors", "risk")
    graph.add_edge("risk", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)
