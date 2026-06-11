"""add project scoping to chat sessions

Revision ID: 017_add_chat_session_project_id
Revises: 016_add_gpt_image_2
Create Date: 2026-06-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "017_add_chat_session_project_id"
down_revision = "016_add_gpt_image_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])
    op.create_foreign_key(
        "fk_chat_sessions_project_id_projects",
        "chat_sessions",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_sessions_project_id_projects", "chat_sessions", type_="foreignkey")
    op.drop_index("ix_chat_sessions_project_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "project_id")
