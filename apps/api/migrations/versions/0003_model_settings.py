"""Persist UI model settings and bind jobs to immutable configuration versions."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "model_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
    )
    with op.batch_alter_table("research_jobs") as batch:
        batch.add_column(sa.Column("model_config_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_research_jobs_model_config", "model_configurations", ["model_config_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("research_jobs") as batch:
        batch.drop_constraint("fk_research_jobs_model_config", type_="foreignkey")
        batch.drop_column("model_config_id")
    op.execute(sa.text("DELETE FROM service_states WHERE key = 'model_settings'"))
    op.drop_table("model_configurations")
