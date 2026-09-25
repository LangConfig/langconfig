# Quality gates and branch validation

The quality bootstrap adds focused linting, explicit formatting and type-check
commands, and a production-build import check. It preserves the existing
production dependency versions, React Flow 11, Vite 7, and TypeScript 5.
Later feature branches extend the checks alongside the code they introduce.

## Current checks

Run these commands from the repository root unless stated otherwise.

| Command | Scope and behavior |
| --- | --- |
| `npm run lint` | Biome recommended lint rules for `scripts/check-build.mjs` and `biome.json`; does not rewrite files. |
| `npm run format:check` | Checks formatting for that same Biome scope; drift fails the command. |
| `npm run format` | Applies formatting to that same scope. |
| `npm run typecheck` | TypeScript checks the application included by `tsconfig.json`, without emitting files. |
| `npm run check:interfaces` | Compatibility alias that runs lint, formatting check, and application type checking. |
| `npm run format:interfaces` | Compatibility alias for `npm run format`. |
| `npm run build` | Runs application type checking, the Vite production build, and the static-import guard. |
| `python -m ruff check .` | Checks the runtime envelope, database safety helper, schema migrations 023–026, subagent-job model/schema regression, advisory gate/policy tests, and embedding compatibility test using `E4`, `E7`, `E9`, and `F`. The exact eleven paths are in `ruff.toml`. |

The build guard traverses every application entry's static imports, including
indirect imports, using `dist/.vite/manifest.json`. It rejects eager
`vendor-3d` and `vendor-export` chunks and permits dynamic imports of them.
It also fails when the manifest has no entry or references a missing chunk.
This validates the current named vendor chunks; it does not measure bundle
size or prove that all dependencies are split optimally.

Biome and Ruff use explicit file lists. These checks do not establish that the
legacy application is fully lint-clean or formatted. Ruff has a 120-character
line-length setting for future formatting work, but the enabled rules do not
enforce line length. Python static typing and formatting are not yet CI gates.
Application type checking does not cover every build/test configuration file.

## Install and run the checks

Use Node.js `^20.19.0` or `>=22.12.0` and npm 10+. Use a Python 3.12 virtual
environment for parity with CI; follow [Setup](SETUP.md) for application
dependencies. Installing the development requirements alone is sufficient for
the focused Python lint check.

```bash
npm ci
python -m pip install -r backend/requirements-dev.txt
python -m ruff check .
npm run check:interfaces
npm run build
```

Verify `python --version` before installing or running backend commands. On
Windows, activate `.venv` or call its interpreter explicitly:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
& .\.venv\Scripts\python.exe -m ruff check .
```

Biome is pinned in `package.json` and `package-lock.json`; Ruff is pinned in
`backend/requirements-dev.txt`. Commit the npm manifest and lock together.
Do not update runtime dependency ranges as a side effect of adding a check.

## Backend tests use a disposable database

Create a separate test database with the default Compose credentials:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U langconfig langconfig_test
```

The `createdb` command is a one-time step; omit it if that disposable database
already exists. Set both URLs before starting pytest, so application imports
and test fixtures use the same database. Adjust the credentials and port for
your local Compose configuration.

PowerShell:

```powershell
$env:DATABASE_URL = 'postgresql://langconfig:langconfig_dev@localhost:5433/langconfig_test'
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://langconfig:langconfig_dev@localhost:5433/langconfig_test'
Set-Location backend
python -m pytest -q --ignore=tests/test_playwright_tools.py
Set-Location ..
```

Bash:

```bash
export DATABASE_URL=postgresql://langconfig:langconfig_dev@localhost:5433/langconfig_test
export TEST_DATABASE_URL=postgresql+asyncpg://langconfig:langconfig_dev@localhost:5433/langconfig_test
cd backend
python -m pytest -q --ignore=tests/test_playwright_tools.py
cd ..
```

Fixtures rebuild the test database's schema. Use a database containing no data
you need. Keep these environment variables in a dedicated test terminal; they
remain set in that shell until removed or the terminal closes. The excluded
Playwright file is a manual browser-tool smoke script, matching existing CI.

## CI and feature branches

CI runs for pushes to `main` and `codex/**`, all pull requests, and manual
dispatches. Concurrency is grouped by workflow and ref, so a new run cancels
an obsolete run on the same ref. A PR and a branch push may each start a run.

The bootstrap adds a Python lint job and frontend lint/format checks. The
frontend build also checks application types and lazy vendor imports. Existing
backend tests continue with both database URLs pointing to `langconfig_test`.
The async database fixtures now use `pytest_asyncio.fixture`, matching strict
asyncio mode. Migration tests normalize the asyncpg URL to a synchronous driver
for Alembic and no longer skip programming errors as database outages. Their
20 migration/database-safety regressions passed against a disposable database.
The inherited Python dependency audit is now an enforcing security job. It
resolves the full manifest, rejects unassessed findings and scanner errors, and
retains the complete report. The four security dependency upgrades and the sole
existing NLTK assessment (expires October 8) are documented in
[DEPENDENCY_SECURITY.md](DEPENDENCY_SECURITY.md). CI enables the pinned MiniLM
embedding regression and checks installed dependency consistency with pip.

Add frontend unit/browser runners, API generation checks, scoped mypy, recipe
evaluations, expanded lint lists, and coverage enforcement in branches
that also contain their required tests, modules, and dependency changes.
Do not enable a CI command before its inputs exist on that branch.

For each feature branch, document its base and merge order, user-visible
behavior, touched interfaces, configuration/schema migrations, and exact
validation results. Record skipped or unavailable checks explicitly. Historical
test counts from another branch are not validation of the current branch.
