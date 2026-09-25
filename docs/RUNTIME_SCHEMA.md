# Runtime schema foundation

This branch adds database structures for durable workflow dispatch, scoped skills,
version evaluations, and background jobs. It registers their SQLAlchemy models so
fresh installation and Alembic metadata include the same tables. Runtime services,
API routes, workers, and UI controls arrive in subsequent feature branches.
The new ORM constraint names match their migrations, so a database created by the
fresh-install path can also follow the documented downgrade path.

The four revisions retain one migration chain:

| Revision | Database change |
| --- | --- |
| `023_durable_workflow_dispatch` | Nullable task ownership, immutable-version, checkpoint, lease, dispatch and budget fields; per-generation execution references. Existing tasks receive generation `0` and `cancel_requested=false`. |
| `024_scope_skills` | Replaces global skill-name uniqueness with separate global and project constraints. Backfills project ownership only when a skill path matches exactly one registered project repository. |
| `025_workflow_evaluations` | Adds nullable `workflow_versions.runtime_snapshot` and separate evaluation/case tables. |
| `026_subagent_jobs` | Adds child-job ownership, request deduplication, status, and workflow-version references. |

Revision 025 belongs in this foundation because checkpoint recovery also needs the
runtime snapshot column. Background jobs reuse durable task dispatch, and workflow
history retention must recognize evaluation and child-job references. Keeping
their schema together lets later branches introduce those services without
querying absent tables or columns.

## Existing installations

Back up the database before upgrading and retain a tested restore path. Use the
canonical root `.env` and active backend environment described in [SETUP.md](SETUP.md).
Confirm the target database and inspect `python -m alembic current` from `backend/`.
An installation at `022_add_hermes_drafts` can run:

```console
python -m alembic upgrade head
python -m alembic current
```

Do not stamp an existing database forward to bypass these migrations. For a blank
database, use the normal `python backend/scripts/setup.py` installation path.

These upgrades preserve existing workflow configurations, tasks, execution
results, and version snapshots. Legacy runtime snapshots remain null: no runtime
settings or replay guarantees are invented. Project-skill backfill is the one
intentional existing-row change; unresolved or ambiguous paths remain unchanged.
This schema branch alone does not provide project-aware skill lookup. Until the
scoped skill runtime branch lands, keep skill names globally distinct.

Downgrading removes the newly introduced data structures and their contents; it
is not a data-preserving reversal for features used after upgrade. Revision 024
refuses to restore global uniqueness while duplicate skill names exist across
scopes. Rename or remove those duplicates intentionally before downgrading. The
project associations already backfilled are retained.

## Verification

`backend/tests/test_runtime_schema_migrations.py` is independent of later runtime
and evaluation test fixtures. It checks model registration and exercises actual
Alembic upgrade, downgrade, and reupgrade on populated revision 022, preserving
every original column value except the deliberate project-skill backfill. It also
checks skill scope uniqueness, task defaults, nullable legacy runtime snapshots,
job foreign keys, and transactional rejection of an unsafe duplicate-name downgrade.

The regression requires PostgreSQL/pgvector and an explicit `TEST_DATABASE_URL`
whose database name contains an underscore- or hyphen-delimited `test` segment.
Use a database reserved exclusively for this test: it rebuilds its `public` schema.
It bootstraps current metadata and downgrades to revision 022 before inserting
legacy rows because the historical initial migration cannot bootstrap an empty
database. No application or provider runtime is invoked.

```console
python -m pytest tests/test_runtime_schema_migrations.py -q
```
