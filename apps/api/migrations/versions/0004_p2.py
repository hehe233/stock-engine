"""P2 research snapshots, collection requests, position lots and frozen job evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "research_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("query_date", sa.Date(), nullable=False),
        sa.Column("data_date", sa.Date()),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_research_snapshots_key", "research_snapshots", ["key"])
    op.create_index("ix_research_snapshots_observed_at", "research_snapshots", ["observed_at"])
    op.create_table(
        "data_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(160), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.String(500)),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("research_snapshots.id")),
    )
    op.create_index("ix_data_requests_key", "data_requests", ["key"])
    op.create_index("ix_data_requests_status", "data_requests", ["status"])
    op.create_table(
        "position_lots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("asset_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("cost_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("acquired_on", sa.Date(), nullable=False),
        sa.Column("settlement", sa.String(10), nullable=False),
        sa.Column("note", sa.String(300), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_position_lots_mode", "position_lots", ["mode"])
    op.create_index("ix_position_lots_symbol", "position_lots", ["symbol"])
    with op.batch_alter_table("research_jobs") as batch:
        batch.add_column(sa.Column("context", sa.JSON(), nullable=False, server_default="{}"))


def downgrade():
    with op.batch_alter_table("research_jobs") as batch:
        batch.drop_column("context")
    op.drop_table("position_lots")
    op.drop_table("data_requests")
    op.drop_table("research_snapshots")
