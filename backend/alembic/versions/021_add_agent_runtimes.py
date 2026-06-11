"""add agent runtime columns

Revision ID: 021_add_agent_runtimes
Revises: 020_add_git_repositories
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "021_add_agent_runtimes"
down_revision = "020_add_git_repositories"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(sa.text(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.columns "
        "  WHERE table_name = :table AND column_name = :column"
        ")"
    ), {"table": table, "column": column})
    return bool(result.scalar())


def upgrade() -> None:
    """Add AgentRuntime columns.

    Supports pluggable execution runtimes (langgraph, google_adk,
    anthropic_agents, ...) behind the AgentRuntime abstraction
    (core/runtimes/). Existing rows default to 'langgraph', the only
    runtime implemented today, so behavior is unchanged.
    """
    conn = op.get_bind()

    # deep_agent_templates: which runtime executes this agent + runtime-native refs
    if not _column_exists(conn, "deep_agent_templates", "runtime"):
        op.add_column(
            "deep_agent_templates",
            sa.Column("runtime", sa.String(32), nullable=False, server_default="langgraph"),
        )
        op.create_index(
            "ix_deep_agent_templates_runtime",
            "deep_agent_templates",
            ["runtime"],
        )

    if not _column_exists(conn, "deep_agent_templates", "external_refs"):
        op.add_column(
            "deep_agent_templates",
            sa.Column("external_refs", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        )

    # chat_sessions: runtime binding + runtime-native session handle
    if not _column_exists(conn, "chat_sessions", "runtime"):
        op.add_column(
            "chat_sessions",
            sa.Column("runtime", sa.String(32), nullable=False, server_default="langgraph"),
        )

    if not _column_exists(conn, "chat_sessions", "external_session_ref"):
        op.add_column(
            "chat_sessions",
            sa.Column("external_session_ref", sa.String(255), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "chat_sessions", "external_session_ref"):
        op.drop_column("chat_sessions", "external_session_ref")

    if _column_exists(conn, "chat_sessions", "runtime"):
        op.drop_column("chat_sessions", "runtime")

    if _column_exists(conn, "deep_agent_templates", "external_refs"):
        op.drop_column("deep_agent_templates", "external_refs")

    if _column_exists(conn, "deep_agent_templates", "runtime"):
        op.drop_index("ix_deep_agent_templates_runtime", table_name="deep_agent_templates")
        op.drop_column("deep_agent_templates", "runtime")
