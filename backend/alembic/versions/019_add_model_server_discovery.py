"""add model server discovery

Revision ID: 019_add_model_server_discovery
Revises: 018_add_workflow_templates
Create Date: 2026-06-05 00:25:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "019_add_model_server_discovery"
down_revision = "018_add_workflow_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    settings_columns = {col["name"] for col in inspector.get_columns("settings")}
    if "model_servers" not in settings_columns:
        op.add_column("settings", sa.Column("model_servers", sa.JSON(), nullable=True))
        conn.execute(sa.text("UPDATE settings SET model_servers = '[]' WHERE model_servers IS NULL"))

    local_model_columns = {col["name"] for col in inspector.get_columns("local_models")}
    if "server_id" not in local_model_columns:
        op.add_column("local_models", sa.Column("server_id", sa.String(), nullable=True))
        op.create_index("ix_local_models_server_id", "local_models", ["server_id"], unique=False)
    if "auto_discovered" not in local_model_columns:
        op.add_column(
            "local_models",
            sa.Column("auto_discovered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    local_model_columns = {col["name"] for col in inspector.get_columns("local_models")}
    indexes = {idx["name"] for idx in inspector.get_indexes("local_models")}

    if "auto_discovered" in local_model_columns:
        op.drop_column("local_models", "auto_discovered")
    if "server_id" in local_model_columns:
        if "ix_local_models_server_id" in indexes:
            op.drop_index("ix_local_models_server_id", table_name="local_models")
        op.drop_column("local_models", "server_id")

    settings_columns = {col["name"] for col in inspector.get_columns("settings")}
    if "model_servers" in settings_columns:
        op.drop_column("settings", "model_servers")
