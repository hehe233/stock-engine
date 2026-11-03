"""Named model profiles; keep immutable configurations and existing job bindings."""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    profiles = op.create_table(
        "model_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column(
            "configuration_id",
            sa.String(36),
            sa.ForeignKey("model_configurations.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    states = sa.table(
        "service_states", sa.column("key", sa.String()), sa.column("value", sa.JSON())
    )
    connection = op.get_bind()
    active = connection.execute(
        sa.select(states.c.value).where(states.c.key == "model_settings")
    ).scalar_one_or_none()
    if active and active.get("id"):
        profile_id = str(uuid4())
        connection.execute(
            profiles.insert().values(
                id=profile_id,
                name="默认配置",
                configuration_id=active["id"],
                created_at=datetime.now(UTC),
            )
        )
        connection.execute(
            states.update()
            .where(states.c.key == "model_settings")
            .values(value={**active, "profile_id": profile_id})
        )


def downgrade():
    # 保留当前配置版本，降级后单配置接口仍能读取；不删除任何任务凭证版本。
    op.drop_table("model_profiles")
