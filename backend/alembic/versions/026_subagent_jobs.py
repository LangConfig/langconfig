"""Background workflow delegation using durable Task dispatch."""
import sqlalchemy as sa
from alembic import op

revision = '026_subagent_jobs'
down_revision = '025_workflow_evaluations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('subagent_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('parent_task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('worker_task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False, unique=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('workflow_version_id', sa.Integer(), sa.ForeignKey('workflow_versions.id'), nullable=False),
        sa.Column('request_key', sa.String(255), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('cancel_with_parent', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('parent_task_id', 'request_key', name='uq_subagent_job_request'))
    for field in ('parent_task_id', 'project_id', 'status'):
        op.create_index(f'ix_subagent_jobs_{field}', 'subagent_jobs', [field])


def downgrade():
    op.drop_table('subagent_jobs')
