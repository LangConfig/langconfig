# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add skills system tables

Revision ID: 006_skills_system
Revises: 005_workflow_debug_mode
Create Date: 2025-12-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_skills_system'
down_revision = '005_workflow_debug_mode'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create skills and skill_executions tables."""

    conn = op.get_bind()

    # Check if skills table already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'skills')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'skills',
            sa.Column('id', sa.Integer(), nullable=False),

            # Identity
            sa.Column('skill_id', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('version', sa.String(length=20), nullable=False, server_default='1.0.0'),
            sa.Column('author', sa.String(length=100), nullable=True),

            # Source tracking
            sa.Column('source_type', sa.String(length=20), nullable=False),  # builtin, personal, project
            sa.Column('source_path', sa.String(length=500), nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=True),

            # Matching metadata
            sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('triggers', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('allowed_tools', sa.JSON(), nullable=True),
            sa.Column('required_context', sa.JSON(), nullable=False, server_default='[]'),

            # Content
            sa.Column('instructions', sa.Text(), nullable=False),
            sa.Column('examples', sa.Text(), nullable=True),

            # Usage metrics
            sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('avg_success_rate', sa.Float(), nullable=False, server_default='1.0'),

            # File tracking
            sa.Column('file_modified_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('indexed_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('skill_id', name='uq_skills_skill_id'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL')
        )
    else:
        print("Note: skills table already exists, skipping creation")

    # Check if skill_executions table already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'skill_executions')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'skill_executions',
            sa.Column('id', sa.Integer(), nullable=False),

            # Skill reference
            sa.Column('skill_id', sa.Integer(), nullable=False),

            # Execution context
            sa.Column('agent_id', sa.String(length=100), nullable=True),
            sa.Column('workflow_id', sa.Integer(), nullable=True),
            sa.Column('task_id', sa.Integer(), nullable=True),

            # Invocation details
            sa.Column('invocation_type', sa.String(length=20), nullable=False),  # automatic, explicit
            sa.Column('trigger_context', sa.JSON(), nullable=True),
            sa.Column('match_score', sa.Float(), nullable=True),
            sa.Column('match_reason', sa.String(length=200), nullable=True),

            # Results
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('execution_time_ms', sa.Integer(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),

            # Timestamp
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['workflow_id'], ['workflow_profiles.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL')
        )
    else:
        print("Note: skill_executions table already exists, skipping creation")

    # Create indexes for skills table
    _create_index_if_not_exists(conn, 'ix_skills_id', 'skills', ['id'])
    _create_index_if_not_exists(conn, 'ix_skills_skill_id', 'skills', ['skill_id'])
    _create_index_if_not_exists(conn, 'ix_skills_source_type', 'skills', ['source_type'])
    _create_index_if_not_exists(conn, 'ix_skills_project_id', 'skills', ['project_id'])

    # Create indexes for skill_executions table
    _create_index_if_not_exists(conn, 'ix_skill_executions_id', 'skill_executions', ['id'])
    _create_index_if_not_exists(conn, 'ix_skill_executions_skill_id', 'skill_executions', ['skill_id'])
    _create_index_if_not_exists(conn, 'ix_skill_executions_workflow_id', 'skill_executions', ['workflow_id'])
    _create_index_if_not_exists(conn, 'ix_skill_executions_task_id', 'skill_executions', ['task_id'])


def _create_index_if_not_exists(conn, index_name: str, table_name: str, columns: list):
    """Helper to create index only if it doesn't exist."""
    result = conn.execute(sa.text(
        f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}')"
    ))
    if not result.scalar():
        op.create_index(op.f(index_name), table_name, columns, unique=False)


def downgrade() -> None:
    """Remove skills system tables."""

    # Drop indexes for skill_executions
    op.drop_index(op.f('ix_skill_executions_task_id'), table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_workflow_id'), table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_skill_id'), table_name='skill_executions')
    op.drop_index(op.f('ix_skill_executions_id'), table_name='skill_executions')

    # Drop indexes for skills
    op.drop_index(op.f('ix_skills_project_id'), table_name='skills')
    op.drop_index(op.f('ix_skills_source_type'), table_name='skills')
    op.drop_index(op.f('ix_skills_skill_id'), table_name='skills')
    op.drop_index(op.f('ix_skills_id'), table_name='skills')

    # Drop tables (order matters due to foreign keys)
    op.drop_table('skill_executions')
    op.drop_table('skills')
