# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add custom_output_path column to workflow_profiles

Revision ID: 010_workflow_output_path
Revises: 009_presentation_jobs
Create Date: 2025-01-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010_workflow_output_path'
down_revision = '009_presentation_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add custom_output_path column to workflow_profiles table."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if column already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'workflow_profiles'
            AND column_name = 'custom_output_path'
        )
        """
    ))
    column_exists = result.scalar()

    if not column_exists:
        op.add_column(
            'workflow_profiles',
            sa.Column('custom_output_path', sa.String(500), nullable=True)
        )
    else:
        print("Note: custom_output_path column already exists, skipping addition")


def downgrade() -> None:
    """Remove custom_output_path column from workflow_profiles table."""
    op.drop_column('workflow_profiles', 'custom_output_path')
