# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add workspace_files table for file metadata tracking

Revision ID: 004_workspace_files
Revises: 003_session_documents
Create Date: 2025-01-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_workspace_files'
down_revision = '003_session_documents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workspace_files table for tracking agent-created file metadata."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if workspace_files table already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'workspace_files')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'workspace_files',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(length=255), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),

            # Source tracking
            sa.Column('agent_label', sa.String(length=255), nullable=True),
            sa.Column('agent_type', sa.String(length=100), nullable=True),
            sa.Column('node_id', sa.String(length=100), nullable=True),

            # Workflow context
            sa.Column('workflow_id', sa.Integer(), nullable=True),
            sa.Column('workflow_name', sa.String(length=255), nullable=True),
            sa.Column('task_id', sa.Integer(), nullable=True),
            sa.Column('project_id', sa.Integer(), nullable=True),
            sa.Column('execution_id', sa.String(length=100), nullable=True),

            # Content metadata
            sa.Column('original_query', sa.Text(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('content_type', sa.String(length=50), nullable=True),
            sa.Column('tags', sa.JSON(), nullable=True),

            # File info
            sa.Column('size_bytes', sa.Integer(), nullable=True),
            sa.Column('mime_type', sa.String(length=100), nullable=True),
            sa.Column('extension', sa.String(length=20), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=True),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('file_path', name='uq_workspace_files_file_path'),
            sa.ForeignKeyConstraint(['workflow_id'], ['workflow_profiles.id'],
                                   ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'],
                                   ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id'],
                                   ondelete='SET NULL')
        )
    else:
        print("Note: workspace_files table already exists, skipping creation")

    # Create indexes for efficient lookups
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_workspace_files_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_workspace_files_id'),
            'workspace_files',
            ['id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_workspace_files_workflow_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_workspace_files_workflow_id'),
            'workspace_files',
            ['workflow_id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_workspace_files_task_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_workspace_files_task_id'),
            'workspace_files',
            ['task_id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_workspace_files_project_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_workspace_files_project_id'),
            'workspace_files',
            ['project_id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_workspace_files_agent_label')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_workspace_files_agent_label'),
            'workspace_files',
            ['agent_label'],
            unique=False
        )


def downgrade() -> None:
    """Remove workspace_files table."""

    # Drop indexes
    op.drop_index(op.f('ix_workspace_files_agent_label'), table_name='workspace_files')
    op.drop_index(op.f('ix_workspace_files_project_id'), table_name='workspace_files')
    op.drop_index(op.f('ix_workspace_files_task_id'), table_name='workspace_files')
    op.drop_index(op.f('ix_workspace_files_workflow_id'), table_name='workspace_files')
    op.drop_index(op.f('ix_workspace_files_id'), table_name='workspace_files')

    # Drop table
    op.drop_table('workspace_files')
