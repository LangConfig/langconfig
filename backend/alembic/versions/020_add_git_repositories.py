"""add git_repositories table

Revision ID: 020_add_git_repositories
Revises: 019_add_model_server_discovery
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "020_add_git_repositories"
down_revision = "019_add_model_server_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create git_repositories table.

    Tracks git repositories cloned locally for a project. Files from
    these repos can be browsed read-only in the UI and selectively
    ingested into the project knowledge base for RAG search.
    """
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'git_repositories')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            "git_repositories",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("clone_url", sa.String(500), nullable=False),
            sa.Column("repo_name", sa.String(255), nullable=False),
            sa.Column("local_path", sa.String(500), nullable=True),
            sa.Column("branch", sa.String(100), nullable=False, server_default="main"),
            sa.Column(
                "sync_status",
                sa.String(20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("last_commit_hash", sa.String(40), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("indexed_files_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "clone_url", name="uq_project_clone_url"),
        )
    else:
        print("Note: git_repositories table already exists, skipping creation")

    # Index on project_id for fast lookup
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_git_repositories_project_id')"
    ))
    if not result.scalar():
        op.create_index(
            "ix_git_repositories_project_id",
            "git_repositories",
            ["project_id"],
            unique=False,
        )


def downgrade() -> None:
    """Remove git_repositories table."""
    op.drop_index("ix_git_repositories_project_id", table_name="git_repositories")
    op.drop_table("git_repositories")
