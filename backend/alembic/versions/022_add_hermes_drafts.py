"""add hermes drafts

Revision ID: 022_add_hermes_drafts
Revises: 021_add_agent_runtimes
Create Date: 2026-06-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "022_add_hermes_drafts"
down_revision = "021_add_agent_runtimes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hermes_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=True),
        sa.Column("source_session_id", sa.String(length=100), nullable=True),
        sa.Column("codex_run_id", sa.String(length=100), nullable=True),
        sa.Column("apply_result", sa.JSON(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hermes_drafts_project_id", "hermes_drafts", ["project_id"])
    op.create_index("ix_hermes_drafts_artifact_type", "hermes_drafts", ["artifact_type"])
    op.create_index("ix_hermes_drafts_status", "hermes_drafts", ["status"])
    op.create_index("ix_hermes_drafts_source_session_id", "hermes_drafts", ["source_session_id"])
    op.create_index("ix_hermes_drafts_codex_run_id", "hermes_drafts", ["codex_run_id"])


def downgrade() -> None:
    op.drop_index("ix_hermes_drafts_codex_run_id", table_name="hermes_drafts")
    op.drop_index("ix_hermes_drafts_source_session_id", table_name="hermes_drafts")
    op.drop_index("ix_hermes_drafts_status", table_name="hermes_drafts")
    op.drop_index("ix_hermes_drafts_artifact_type", table_name="hermes_drafts")
    op.drop_index("ix_hermes_drafts_project_id", table_name="hermes_drafts")
    op.drop_table("hermes_drafts")
