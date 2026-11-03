"""P0: immutable market snapshots and persisted analysis runs."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quotes", sa.JSON(), nullable=False),
    )
    op.create_index("ix_market_snapshots_fetched_at", "market_snapshots", ["fetched_at"])
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "snapshot_id", sa.String(36), sa.ForeignKey("market_snapshots.id"), nullable=False
        ),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
    )
    op.create_index("ix_analysis_runs_created_at", "analysis_runs", ["created_at"])
    op.create_index("ix_analysis_runs_symbol", "analysis_runs", ["symbol"])


def downgrade():
    op.drop_table("analysis_runs")
    op.drop_table("market_snapshots")
