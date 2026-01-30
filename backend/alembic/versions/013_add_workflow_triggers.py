# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""add workflow_triggers and trigger_logs tables

Revision ID: 013_workflow_triggers
Revises: 012_workflow_schedules
Create Date: 2025-01-22 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_workflow_triggers'
down_revision = '012_workflow_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create workflow trigger tables."""

    conn = op.get_bind()

    # Check if workflow_triggers table already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'workflow_triggers'
        )
        """
    ))
    triggers_exists = result.scalar()

    if not triggers_exists:
        # Create workflow_triggers table
        op.create_table(
            'workflow_triggers',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('workflow_id', sa.Integer(),
                      sa.ForeignKey('workflow_profiles.id', ondelete='CASCADE'),
                      nullable=False, index=True),

            # Trigger metadata
            sa.Column('name', sa.String(255), nullable=True),
            sa.Column('trigger_type', sa.String(50), nullable=False, index=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),

            # Configuration
            sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),

            # Webhook-specific
            sa.Column('webhook_secret', sa.String(64), nullable=True),

            # State tracking
            sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),

            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

        print("Created workflow_triggers table")
    else:
        print("Note: workflow_triggers table already exists, skipping creation")

    # Check if trigger_logs table already exists
    result = conn.execute(sa.text(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'trigger_logs'
        )
        """
    ))
    logs_exists = result.scalar()

    if not logs_exists:
        # Create trigger_logs table
        op.create_table(
            'trigger_logs',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('trigger_id', sa.Integer(),
                      sa.ForeignKey('workflow_triggers.id', ondelete='CASCADE'),
                      nullable=False, index=True),

            # Execution details
            sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', index=True),

            # Trigger source info
            sa.Column('trigger_source', sa.String(255), nullable=True),
            sa.Column('trigger_payload', postgresql.JSONB(), nullable=True),

            # Task reference
            sa.Column('task_id', sa.Integer(),
                      sa.ForeignKey('background_tasks.id', ondelete='SET NULL'),
                      nullable=True, index=True),

            # Error tracking
            sa.Column('error_message', sa.Text(), nullable=True),

            # Timestamps
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

        # Create composite index for trigger history queries
        op.create_index(
            'ix_trigger_logs_trigger_triggered_at',
            'trigger_logs',
            ['trigger_id', 'triggered_at']
        )

        print("Created trigger_logs table with indexes")
    else:
        print("Note: trigger_logs table already exists, skipping creation")


def downgrade() -> None:
    """Remove workflow trigger tables."""
    # Drop trigger_logs first (has FK to workflow_triggers)
    op.drop_index('ix_trigger_logs_trigger_triggered_at', table_name='trigger_logs')
    op.drop_table('trigger_logs')

    # Drop workflow_triggers
    op.drop_table('workflow_triggers')
