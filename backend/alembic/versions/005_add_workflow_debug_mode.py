# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add debug_mode column to workflow_profiles

Revision ID: 005_workflow_debug_mode
Revises: 004_workspace_files
Create Date: 2025-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_workflow_debug_mode'
down_revision = '004_workspace_files'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add debug_mode column to workflow_profiles table."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if column already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'workflow_profiles'
            AND column_name = 'debug_mode'
        )
        """
    ))
    column_exists = result.scalar()

    if not column_exists:
        op.add_column(
            'workflow_profiles',
            sa.Column('debug_mode', sa.Boolean(), nullable=False, server_default='false')
        )
    else:
        print("Note: debug_mode column already exists, skipping addition")


def downgrade() -> None:
    """Remove debug_mode column from workflow_profiles table."""
    op.drop_column('workflow_profiles', 'debug_mode')
