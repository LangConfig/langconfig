"""create pii_profiles table

Revision ID: 015_pii_profiles
Revises: 014_sync_tool_enums
Create Date: 2026-06-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "015_pii_profiles"
down_revision = "014_sync_tool_enums"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pii_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("blocklist", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("allowlist", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("custom_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled_builtin_types", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pii_profiles_id", "pii_profiles", ["id"])
    op.create_index("ix_pii_profiles_project_id", "pii_profiles", ["project_id"])
    op.create_index("ix_pii_profiles_name", "pii_profiles", ["name"])


def downgrade() -> None:
    op.drop_index("ix_pii_profiles_name", table_name="pii_profiles")
    op.drop_index("ix_pii_profiles_project_id", table_name="pii_profiles")
    op.drop_index("ix_pii_profiles_id", table_name="pii_profiles")
    op.drop_table("pii_profiles")
