"""add workflow template metadata

Revision ID: 018_add_workflow_templates
Revises: 017_add_chat_session_project_id
Create Date: 2026-06-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "018_add_workflow_templates"
down_revision = "017_add_chat_session_project_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_profiles",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("workflow_profiles", sa.Column("template_category", sa.String(length=50), nullable=True))
    op.add_column("workflow_profiles", sa.Column("template_icon", sa.String(length=50), nullable=True))
    op.add_column("workflow_profiles", sa.Column("template_tags", sa.JSON(), nullable=True))
    op.create_index("ix_workflow_profiles_is_template", "workflow_profiles", ["is_template"])
    op.create_index("ix_workflow_profiles_template_category", "workflow_profiles", ["template_category"])
    op.alter_column("workflow_profiles", "is_template", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_workflow_profiles_template_category", table_name="workflow_profiles")
    op.drop_index("ix_workflow_profiles_is_template", table_name="workflow_profiles")
    op.drop_column("workflow_profiles", "template_tags")
    op.drop_column("workflow_profiles", "template_icon")
    op.drop_column("workflow_profiles", "template_category")
    op.drop_column("workflow_profiles", "is_template")
