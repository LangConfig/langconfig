# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add presentation_jobs table for tracking presentation generation

Revision ID: 009_presentation_jobs
Revises: 008_oauth_tokens
Create Date: 2025-01-05 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_presentation_jobs'
down_revision = '008_oauth_tokens'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create presentation_jobs table for tracking presentation generation status."""

    # Get connection for checking existence
    conn = op.get_bind()

    # Check if presentation_jobs table already exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'presentation_jobs')"
    ))
    table_exists = result.scalar()

    if not table_exists:
        op.create_table(
            'presentation_jobs',
            sa.Column('id', sa.Integer(), nullable=False),

            # Job status
            sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),

            # Output format: google_slides, pdf, revealjs
            sa.Column('output_format', sa.String(length=50), nullable=False),

            # Title for the presentation
            sa.Column('title', sa.String(length=500), nullable=True),

            # Theme: default, dark, minimal
            sa.Column('theme', sa.String(length=50), server_default='default'),

            # Input items (JSON array of selected artifact/file IDs)
            sa.Column('input_items', postgresql.JSONB(), nullable=False),

            # Result data
            sa.Column('result_url', sa.Text(), nullable=True),  # Google Slides URL
            sa.Column('result_file_path', sa.Text(), nullable=True),  # Local file for PDF/HTML

            # Error tracking
            sa.Column('error_message', sa.Text(), nullable=True),

            # Context
            sa.Column('workflow_id', sa.Integer(), nullable=True),
            sa.Column('task_id', sa.Integer(), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True),
                      server_default=sa.text('now()'), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

            # Constraints
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['workflow_id'], ['workflow_profiles.id'],
                                   ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id'],
                                   ondelete='SET NULL')
        )
    else:
        print("Note: presentation_jobs table already exists, skipping creation")

    # Create indexes for efficient lookups
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_presentation_jobs_status')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_presentation_jobs_status'),
            'presentation_jobs',
            ['status'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_presentation_jobs_workflow_id')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_presentation_jobs_workflow_id'),
            'presentation_jobs',
            ['workflow_id'],
            unique=False
        )

    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_presentation_jobs_created_at')"
    ))
    if not result.scalar():
        op.create_index(
            op.f('ix_presentation_jobs_created_at'),
            'presentation_jobs',
            ['created_at'],
            unique=False
        )


def downgrade() -> None:
    """Remove presentation_jobs table."""

    # Drop indexes
    op.drop_index(op.f('ix_presentation_jobs_created_at'), table_name='presentation_jobs')
    op.drop_index(op.f('ix_presentation_jobs_workflow_id'), table_name='presentation_jobs')
    op.drop_index(op.f('ix_presentation_jobs_status'), table_name='presentation_jobs')

    # Drop table
    op.drop_table('presentation_jobs')
