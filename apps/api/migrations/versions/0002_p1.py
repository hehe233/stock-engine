"""P1: market metadata, durable jobs, events and shared service state."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("market_snapshots") as batch:
        batch.alter_column("as_of", existing_type=sa.DateTime(timezone=True), nullable=True)
        batch.add_column(
            sa.Column("asset_type", sa.String(10), nullable=False, server_default="stock")
        )
        batch.add_column(sa.Column("details", sa.JSON(), nullable=False, server_default="{}"))
        batch.create_index("ix_market_snapshots_asset_type", ["asset_type"])
    op.create_table(
        "research_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id", sa.String(36), sa.ForeignKey("market_snapshots.id"), nullable=False
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("model_name", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(500)),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("analysis_runs.id")),
    )
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("research_jobs.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_table(
        "service_states",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
    )


def downgrade():
    op.drop_table("service_states")
    op.drop_table("job_events")
    op.drop_table("research_jobs")
    with op.batch_alter_table("market_snapshots") as batch:
        batch.drop_index("ix_market_snapshots_asset_type")
        batch.drop_column("details")
        batch.drop_column("asset_type")
        # 未知源时间不能无损转回 NOT NULL，因此保留可空时间列。
