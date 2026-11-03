"""P3 immutable dataset manifests and durable experiment queue."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quant_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_quant_datasets_mode", "quant_datasets", ["mode"])
    op.create_table(
        "quant_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("quant_datasets.id"), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(500)),
    )
    op.create_index("ix_quant_runs_mode", "quant_runs", ["mode"])
    op.create_index("ix_quant_runs_status", "quant_runs", ["status"])


def downgrade():
    op.drop_table("quant_runs")
    op.drop_table("quant_datasets")
