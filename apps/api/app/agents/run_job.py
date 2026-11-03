import argparse
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver

from app.agents.assistant import build_assistant_graph
from app.agents.models import create_chat_model
from app.agents.research import build_research_graph
from app.core.config import get_settings
from app.db import AnalysisRun, MarketSnapshot, ModelConfiguration, ResearchJob, build_database
from app.jobs.service import event, finish_failed
from app.model_settings.service import apply_configuration
from app.schemas import AnalysisReport
from app.shared.time import as_utc, utc_now


@contextmanager
def checkpoint_store(settings):
    # 业务报告与图检查点分开存储。换 PostgreSQL 时，检查点也可独立配置 PostgreSQL。
    if settings.checkpoint_postgres_url:
        with PostgresSaver.from_conn_string(
            settings.checkpoint_postgres_url.get_secret_value()
        ) as saver:
            saver.setup()
            yield saver
    else:
        with SqliteSaver.from_conn_string(settings.checkpoint_sqlite_path) as saver:
            yield saver


def execute_job(sessions, settings, job_id: str, owner: str, model_factory=create_chat_model):
    with sessions() as session:
        job = session.get(ResearchJob, job_id)
        if job is None or job.lease_owner != owner or job.status != "running":
            return
        snapshot = session.get(MarketSnapshot, job.snapshot_id)
        quote = next(row for row in snapshot.quotes if row["symbol"] == job.symbol)
        mode, name = job.mode, job.model_name
        # 已提交任务始终读取自己的配置版本，更换页面默认模型不改变恢复语义。
        if job.model_config_id:
            settings = apply_configuration(
                settings, session.get(ModelConfiguration, job.model_config_id)
            )
        initial = {
            "quote": quote,
            "trace": [],
            "source": snapshot.source,
            "is_demo": snapshot.source == "demo",
            "model_name": name,
            "research_context": job.context,
            "as_of": quote.get("quote_time")
            or (
                as_utc(snapshot.as_of).isoformat()
                if snapshot.source == "demo" and snapshot.as_of
                else None
            ),
        }
    with checkpoint_store(settings) as saver:
        graph = (
            build_research_graph(saver)
            if mode == "rules"
            else build_assistant_graph(
                model_factory(settings, mode, name),
                saver,
                settings.max_tool_rounds,
                stream_output=True,
            )
        )
        config = {"configurable": {"thread_id": job_id}, "recursion_limit": 30}
        saved = graph.get_state(config)
        # 有检查点时传 None 表示恢复；重新传 initial 会覆盖已完成节点的状态。
        if not saved.values or saved.next:
            for channel, update in graph.stream(
                None if saved.values else initial, config, stream_mode=["updates", "custom"]
            ):
                with sessions() as session:
                    current = session.get(ResearchJob, job_id)
                    if (
                        current.cancel_requested
                        or current.lease_owner != owner
                        or current.status != "running"
                    ):
                        raise ValueError("任务已取消或执行租约失效")
                    if channel == "custom":
                        event(
                            session,
                            job_id,
                            update["kind"],
                            attempt=current.attempts,
                            **update["payload"],
                        )
                    else:
                        for node, values in update.items():
                            if not isinstance(values, dict):
                                continue
                            trace = values.get("trace", [])
                            step = trace[-1] if trace else {}
                            event(
                                session,
                                job_id,
                                "node",
                                node=node,
                                attempt=current.attempts,
                                message=step.get("title", f"节点 {node} 已完成"),
                                detail=step.get("detail", ""),
                            )
                            preview = {
                                key: values[key]
                                for key in ("heat_score", "factors", "risks", "summary", "insight")
                                if key in values
                            }
                            if preview:
                                event(
                                    session,
                                    job_id,
                                    "report.patch",
                                    patch=preview,
                                    attempt=current.attempts,
                                )
                    current.updated_at = utc_now()
                    session.commit()
        result = graph.get_state(config).values
    with sessions() as session:
        job = session.get(ResearchJob, job_id)
        if job.lease_owner != owner or job.status != "running" or job.cancel_requested:
            return
        snapshot = session.get(MarketSnapshot, job.snapshot_id)
        report = AnalysisReport(
            id=job.id,
            snapshot_id=snapshot.id,
            symbol=job.symbol,
            name=quote["name"],
            created_at=utc_now(),
            as_of=quote.get("quote_time")
            or (snapshot.as_of if snapshot.source == "demo" else None),
            source=snapshot.source,
            is_demo=snapshot.source == "demo",
            asset_type=snapshot.asset_type,
            analysis_mode=mode,
            model_name=name,
            heat_score=result["heat_score"],
            summary=result["summary"],
            factors=result["factors"],
            risks=result["risks"],
            trace=result["trace"],
            insight=result.get("insight"),
            evidence=result.get("evidence", {}),
            research_context=result.get("research_context", {}),
        )
        if report.as_of:
            report.as_of = as_utc(report.as_of)
        # 报告 ID 与任务 ID 一致；恢复不会生成第二份报告。
        session.add(
            AnalysisRun(
                id=job.id,
                snapshot_id=snapshot.id,
                symbol=job.symbol,
                created_at=report.created_at,
                report=report.model_dump(mode="json"),
            )
        )
        session.flush()
        job.status, job.report_id, job.updated_at = "succeeded", report.id, utc_now()
        job.lease_until = None
        event(session, job.id, "succeeded", report_id=report.id, message="报告已保存")
        session.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    parser.add_argument("owner")
    args = parser.parse_args()
    settings = get_settings()
    engine, sessions = build_database(settings.database_url)
    try:
        execute_job(sessions, settings, args.job_id, args.owner)
    except Exception as exc:
        # 不保存第三方异常原文，避免响应体或 URL 里的密钥进入报告与事件流。
        finish_failed(
            sessions,
            args.job_id,
            args.owner,
            f"执行失败（{type(exc).__name__}）；请检查模型连接、工具调用能力或数据。可从检查点重试。",
        )
    finally:
        engine.dispose()
