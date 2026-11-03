from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.shared.time import utc_now


class Base(DeclarativeBase):
    pass


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source: Mapped[str] = mapped_column(String(50))
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset_type: Mapped[str] = mapped_column(String(10), default="stock", index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # 单机 P1 按证券类别保存不可变 JSON 批次；长期归档时再拆分证券主表和行情明细。
    quotes: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("market_snapshots.id"))
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # 保存完整报告及其行情快照引用，使以后刷新行情也不会改变历史分析依据。
    report: Mapped[dict[str, Any]] = mapped_column(JSON)


class ModelConfiguration(Base):
    """不可变模型配置版本，仅后端可读。密钥属于服务端数据库敏感数据。"""

    __tablename__ = "model_configurations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)


class ModelProfile(Base):
    """可管理的配置名称和当前版本指针；编辑不修改旧任务引用的不可变版本。"""

    __tablename__ = "model_profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    configuration_id: Mapped[str] = mapped_column(ForeignKey("model_configurations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("market_snapshots.id"))
    symbol: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))
    model_name: Mapped[str | None] = mapped_column(String(200))
    model_config_id: Mapped[str | None] = mapped_column(ForeignKey("model_configurations.id"))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(String(500))
    report_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"))
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ResearchSnapshot(Base):
    """研究数据和行情分别存批次；披露日期、观察时间不能互相冒充。"""

    __tablename__ = "research_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))
    query_date: Mapped[date] = mapped_column(Date)
    data_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(100))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DataRequest(Base):
    """独立于模型任务的数据采集队列；单 worker 启动时恢复中断的请求。"""

    __tablename__ = "data_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(160), index=True)
    mode: Mapped[str] = mapped_column(String(10))
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    error: Mapped[str | None] = mapped_column(String(500))
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("research_snapshots.id"))


class PositionLot(Base):
    """持仓快照中的一笔剩余持仓，不是券商成交账本。"""

    __tablename__ = "position_lots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(80))
    asset_type: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    acquired_on: Mapped[date] = mapped_column(Date)
    settlement: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(300), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuantDataset(Base):
    """文件只保存不可变数值数据；数据库保存可审计元数据，不接受客户端文件路径。"""

    __tablename__ = "quant_datasets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(200))
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class QuantRun(Base):
    __tablename__ = "quant_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("quant_datasets.id"))
    mode: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("research_jobs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class ServiceState(Base):
    """API 和独立 worker 共享采集状态、交易日历与心跳，不保存模型推理内容。"""

    __tablename__ = "service_states"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)


def build_database(database_url: str):
    kwargs = {}
    if database_url.startswith("sqlite"):
        # FastAPI 同步路由在线程池执行，定时任务也有独立线程。
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    engine = create_engine(database_url, pool_pre_ping=True, **kwargs)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            # SQLite 默认不执行外键约束，必须开启才能保护快照引用关系。
            connection.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(bind=engine, expire_on_commit=False)
