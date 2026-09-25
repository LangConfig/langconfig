"""Allow separately scoped project skills with the same name."""
import sqlalchemy as sa
from alembic import op

revision = '024_scope_skills'
down_revision = '023_durable_workflow_dispatch'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints('skills'):
        if constraint['column_names'] == ['skill_id']:
            op.drop_constraint(constraint['name'], 'skills', type_='unique')
    for index in inspector.get_indexes('skills'):
        if index['column_names'] == ['skill_id'] and index.get('unique') and not index.get('duplicates_constraint'):
            op.drop_index(index['name'], table_name='skills')
    if not any(index['name'] == 'ix_skills_skill_id' and not index.get('unique') for index in inspector.get_indexes('skills')):
        op.create_index('ix_skills_skill_id', 'skills', ['skill_id'])
    op.create_index('uq_skills_global_name', 'skills', ['skill_id'], unique=True, postgresql_where=sa.text('project_id IS NULL'))
    op.create_index('uq_skills_project_name', 'skills', ['project_id', 'skill_id'], unique=True, postgresql_where=sa.text('project_id IS NOT NULL'))
    # Older indexing omitted project_id. Backfill only an unambiguous registered
    # repository association; unresolved records remain unusable by the resolver.
    def normalized(path):
        value = str(path or '').replace('\\', '/').rstrip('/')
        return value.casefold() if len(value) > 1 and value[1] == ':' else value
    connection = op.get_bind()
    repositories = connection.execute(sa.text('SELECT project_id, local_path FROM git_repositories WHERE local_path IS NOT NULL')).all()
    records = connection.execute(sa.text("SELECT id, source_path FROM skills WHERE source_type = 'project' AND project_id IS NULL")).all()
    for skill_id, path in records:
        matches = {project_id for project_id, root in repositories if normalized(path).startswith(normalized(root) + '/.langconfig/skills/')}
        if len(matches) == 1:
            connection.execute(sa.text('UPDATE skills SET project_id = :project WHERE id = :skill'), {'project': matches.pop(), 'skill': skill_id})


def downgrade():
    duplicates = op.get_bind().execute(sa.text('SELECT skill_id FROM skills GROUP BY skill_id HAVING count(*) > 1 LIMIT 1')).first()
    if duplicates:
        raise RuntimeError('Cannot downgrade scoped skills while duplicate names exist; rename them first')
    op.drop_index('uq_skills_project_name', table_name='skills')
    op.drop_index('uq_skills_global_name', table_name='skills')
    op.drop_index('ix_skills_skill_id', table_name='skills')
    op.create_index('ix_skills_skill_id', 'skills', ['skill_id'], unique=True)
