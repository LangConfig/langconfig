# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add file_versions table for version tracking

Revision ID: 011_file_versions
Revises: 010_workflow_output_path
Create Date: 2025-01-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_file_versions'
down_revision = '010_workflow_output_path'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create file_versions table for tracking file edit history."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if table already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'file_versions'
        )
        """
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'file_versions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workspace_file_id', sa.Integer(), sa.ForeignKey('workspace_files.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('version_number', sa.Integer(), nullable=False),
            sa.Column('content_hash', sa.String(64), nullable=True),

            # Content snapshot
            sa.Column('content_snapshot', sa.Text(), nullable=True),

            # Edit tracking
            sa.Column('operation', sa.String(50), nullable=False),
            sa.Column('old_string', sa.Text(), nullable=True),
            sa.Column('new_string', sa.Text(), nullable=True),

            # Agent context
            sa.Column('agent_label', sa.String(255), nullable=True),
            sa.Column('agent_type', sa.String(100), nullable=True),
            sa.Column('node_id', sa.String(100), nullable=True),
            sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True),
            sa.Column('execution_id', sa.String(100), nullable=True),

            # Change summary
            sa.Column('change_summary', sa.String(500), nullable=True),
            sa.Column('lines_added', sa.Integer(), nullable=True),
            sa.Column('lines_removed', sa.Integer(), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

        # Create index for faster version lookups
        op.create_index(
            'ix_file_versions_workspace_file_version',
            'file_versions',
            ['workspace_file_id', 'version_number']
        )

        print("Created file_versions table with indexes")
    else:
        print("Note: file_versions table already exists, skipping creation")


def downgrade() -> None:
    """Remove file_versions table."""
    op.drop_index('ix_file_versions_workspace_file_version', table_name='file_versions')
    op.drop_table('file_versions')
