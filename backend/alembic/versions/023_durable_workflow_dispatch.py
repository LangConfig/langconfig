"""Persist workflow dispatch ownership and versioned attempt history."""
import sqlalchemy as sa
from alembic import op

revision = '023_durable_workflow_dispatch'
down_revision = '022_add_hermes_drafts'
branch_labels = None
depends_on = None


def upgrade():
    for column in [
        sa.Column('workflow_version_id', sa.Integer(), nullable=True),
        sa.Column('checkpoint_thread_id', sa.String(), nullable=True),
        sa.Column('dispatch_key', sa.String(255), nullable=True),
        sa.Column('dispatch_state', sa.String(32), nullable=True),
        sa.Column('dispatch_generation', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dispatch_payload', sa.JSON(), nullable=True),
        sa.Column('lease_owner', sa.String(100), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_requested', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('runtime_compatibility', sa.JSON(), nullable=True),
        sa.Column('call_counts', sa.JSON(), nullable=True),
        sa.Column('last_checkpoint', sa.JSON(), nullable=True),
        sa.Column('parent_checkpoint', sa.JSON(), nullable=True),
    ]:
        op.add_column('tasks', column)
    op.create_foreign_key('fk_task_workflow_version', 'tasks', 'workflow_versions', ['workflow_version_id'], ['id'])
    op.create_index('ix_tasks_dispatch_state', 'tasks', ['dispatch_state'])
    op.create_unique_constraint('uq_tasks_dispatch_key', 'tasks', ['dispatch_key'])
    op.add_column('workflow_executions', sa.Column('task_id', sa.Integer(), nullable=True))
    op.add_column('workflow_executions', sa.Column('dispatch_generation', sa.Integer(), nullable=True))
    op.add_column('workflow_executions', sa.Column('checkpoint_ref', sa.JSON(), nullable=True))
    op.create_foreign_key('fk_execution_task', 'workflow_executions', 'tasks', ['task_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_workflow_executions_task_id', 'workflow_executions', ['task_id'])
    op.create_unique_constraint('uq_workflow_execution_dispatch', 'workflow_executions', ['task_id', 'dispatch_generation'])


def downgrade():
    op.drop_constraint('uq_workflow_execution_dispatch', 'workflow_executions', type_='unique')
    op.drop_index('ix_workflow_executions_task_id', table_name='workflow_executions')
    op.drop_constraint('fk_execution_task', 'workflow_executions', type_='foreignkey')
    for name in ['checkpoint_ref', 'dispatch_generation', 'task_id']:
        op.drop_column('workflow_executions', name)
    op.drop_index('ix_tasks_dispatch_state', table_name='tasks')
    op.drop_constraint('uq_tasks_dispatch_key', 'tasks', type_='unique')
    op.drop_constraint('fk_task_workflow_version', 'tasks', type_='foreignkey')
    for name in ['parent_checkpoint', 'last_checkpoint', 'call_counts', 'runtime_compatibility',
                 'cancel_requested', 'lease_expires_at', 'lease_owner', 'dispatch_payload',
                 'dispatch_generation', 'dispatch_state', 'dispatch_key', 'checkpoint_thread_id', 'workflow_version_id']:
        op.drop_column('tasks', name)
