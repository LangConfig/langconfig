"""Persist fixture-versioned workflow evaluations and separate case metrics."""
import sqlalchemy as sa
from alembic import op

revision = '025_workflow_evaluations'
down_revision = '024_scope_skills'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('workflow_versions', sa.Column('runtime_snapshot', sa.JSON(), nullable=True))
    op.create_table('workflow_evaluations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('comparison_id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.Integer(), sa.ForeignKey('workflow_profiles.id'), nullable=False),
        sa.Column('version_id', sa.Integer(), sa.ForeignKey('workflow_versions.id'), nullable=False),
        sa.Column('fixture_version', sa.String(100), nullable=False),
        sa.Column('fixture_hash', sa.String(64), nullable=False),
        sa.Column('fixture_snapshot', sa.JSON(), nullable=False),
        sa.Column('configuration_snapshot', sa.JSON(), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False), sa.Column('seed', sa.Integer()),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('budget_usd', sa.Float()),
        sa.Column('reserved_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('max_cases', sa.Integer(), nullable=False), sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('completed_at', sa.DateTime(timezone=True)))
    for column in ('comparison_id', 'workflow_id', 'version_id'):
        op.create_index(f'ix_workflow_evaluations_{column}', 'workflow_evaluations', [column])
    op.create_table('workflow_evaluation_cases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('evaluation_id', sa.Integer(), sa.ForeignKey('workflow_evaluations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('workflow_executions.id'), nullable=False),
        sa.Column('fixture_case_id', sa.String(100), nullable=False), sa.Column('input_snapshot', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        *[sa.Column(f'{metric}_correct', sa.Boolean()) for metric in ('output', 'schema', 'tool', 'branch', 'approval', 'recovery')],
        sa.Column('token_usage', sa.JSON()), sa.Column('estimated_cost_usd', sa.Float()),
        sa.Column('latency_seconds', sa.Float(), nullable=False), sa.Column('model_ids', sa.JSON(), nullable=False),
        sa.Column('raw_result', sa.JSON(), nullable=False), sa.Column('error_message', sa.Text()))
    op.create_index('ix_workflow_evaluation_cases_evaluation_id', 'workflow_evaluation_cases', ['evaluation_id'])


def downgrade():
    op.drop_table('workflow_evaluation_cases')
    op.drop_table('workflow_evaluations')
    op.drop_column('workflow_versions', 'runtime_snapshot')
