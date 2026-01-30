# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add workflow_schedules and scheduled_run_logs tables

Revision ID: 012_workflow_schedules
Revises: 011_file_versions
Create Date: 2025-01-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_workflow_schedules'
down_revision = '011_file_versions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workflow scheduling tables."""

    conn = op.get_bind()

    # Check if workflow_schedules table already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'workflow_schedules'
        )
        """
    ))
    schedules_exists = result.scalar()

    if not schedules_exists:
        # Create workflow_schedules table
        op.create_table(
            'workflow_schedules',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workflow_id', sa.Integer(),
                      sa.ForeignKey('workflow_profiles.id', ondelete='CASCADE'),
                      nullable=False, index=True),

            # Schedule metadata
            sa.Column('name', sa.String(255), nullable=True),

            # Cron configuration
            sa.Column('cron_expression', sa.String(100), nullable=False),
            sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),

            # Execution settings
            sa.Column('default_input_data', postgresql.JSONB(), nullable=False,
                      server_default='{}'),
            sa.Column('max_concurrent_runs', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('timeout_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('idempotency_key_template', sa.String(255), nullable=True),

            # Tracking
            sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column('last_run_status', sa.String(20), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

        print("Created workflow_schedules table")
    else:
        print("Note: workflow_schedules table already exists, skipping creation")

    # Check if scheduled_run_logs table already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'scheduled_run_logs'
        )
        """
    ))
    logs_exists = result.scalar()

    if not logs_exists:
        # Create scheduled_run_logs table
        op.create_table(
            'scheduled_run_logs',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('schedule_id', sa.Integer(),
                      sa.ForeignKey('workflow_schedules.id', ondelete='CASCADE'),
                      nullable=False, index=True),

            # Timing
            sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),

            # Status
            sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', index=True),

            # Task reference
            sa.Column('task_id', sa.Integer(),
                      sa.ForeignKey('background_tasks.id', ondelete='SET NULL'),
                      nullable=True, index=True),

            # Error tracking
            sa.Column('error_message', sa.Text(), nullable=True),

            # Idempotency
            sa.Column('idempotency_key', sa.String(255), nullable=True),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

        # Create unique constraint for idempotency key
        op.create_unique_constraint(
            'uq_scheduled_run_logs_idempotency_key',
            'scheduled_run_logs',
            ['idempotency_key']
        )

        # Create composite index for schedule history queries
        op.create_index(
            'ix_scheduled_run_logs_schedule_scheduled_for',
            'scheduled_run_logs',
            ['schedule_id', 'scheduled_for']
        )

        print("Created scheduled_run_logs table with indexes")
    else:
        print("Note: scheduled_run_logs table already exists, skipping creation")


def downgrade() -> None:
    """Remove workflow scheduling tables."""
    # Drop scheduled_run_logs first (has FK to workflow_schedules)
    op.drop_index('ix_scheduled_run_logs_schedule_scheduled_for', table_name='scheduled_run_logs')
    op.drop_constraint('uq_scheduled_run_logs_idempotency_key', 'scheduled_run_logs', type_='unique')
    op.drop_table('scheduled_run_logs')

    # Drop workflow_schedules
    op.drop_table('workflow_schedules')
