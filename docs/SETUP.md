# LangConfig development setup

This is the canonical setup guide for a fresh clone or fork of LangConfig.

## Prerequisites

- Git
- Docker Desktop (or another Docker Engine with Compose v2)
- Python 3.11-3.13; Python 3.12 is the regularly tested version. Python 3.14 is not yet supported by the current LangChain/Pydantic dependency set.
- Node.js `^20.19.0` or `>=22.12.0` and npm 10 or newer

Check the installed versions:

```bash
git --version
docker compose version
python --version
node --version
npm --version
```

## Fresh clone

```bash
git clone https://github.com/LangConfig/langconfig.git
cd langconfig

# Create and activate an isolated Python environment.
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows Git Bash (run this instead on Windows)
source .venv/Scripts/activate

# Windows PowerShell (run this instead on Windows)
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
npm ci
python backend/scripts/setup.py
```

The setup script installs current Python dependencies, starts PostgreSQL, creates
the current schema, stamps the current Alembic revision, and seeds starter data.
It preserves an existing LangConfig database and runs forward migrations instead.

Edit the root `.env` before using model providers. At least one of
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY` is needed for its
corresponding hosted models. When creating a new `.env` from `.env.example`,
the setup script generates a unique `APP_ENCRYPTION_KEY`. Let the script create
the file rather than copying the template first. If you create `.env` manually,
generate a unique key before saving real credentials through the Settings UI.

Setup preserves an existing `.env` byte-for-byte, including blank or placeholder
encryption keys. An existing database may already contain credentials encrypted
with its current key or the development fallback. Before changing that key,
back up `.env` and the database, then explicitly migrate the encrypted secrets
or plan to re-enter the saved credentials. Changing the key alone makes those
credentials unreadable; rerunning setup does not rotate or migrate them.

The root `.env` is canonical. `backend/.env` is optional and is only for local
backend overrides; when the backend is started from `backend/`, values already
loaded from that file take precedence.

## Start development

Use two terminals with the virtual environment active:

```bash
# Terminal 1
cd backend
python main.py

# Terminal 2, from the repository root
npm run dev
```

Open:

- Web app: <http://localhost:1425>
- API health: <http://127.0.0.1:8780/health/>
- Swagger API documentation: <http://127.0.0.1:8780/docs>

The frontend uses Vite's `/api` proxy in development. Leave
`VITE_API_BASE_URL` blank unless the API is hosted on a different origin.

## Updating an existing clone

```bash
git pull --ff-only
npm ci
python -m pip install --upgrade -r backend/requirements.txt
docker compose up -d postgres
cd backend
python -m alembic upgrade head
cd ..
```

`alembic upgrade head` is for a database that already has a LangConfig schema.
For a brand-new database, use `python backend/scripts/setup.py`; the repository's
historical baseline migration cannot bootstrap an empty PostgreSQL database.

## Optional features

### Browser tools

```bash
python -m playwright install chromium
```

### Local Codex harness (experimental)

Install or update the Codex CLI separately, run `codex login`, and confirm
`codex login status` succeeds. Select a model supported by that CLI version;
an incompatible model configured as the CLI default will make a run fail.
LangConfig delegates authentication to the CLI and does not store Codex
credentials. Codex run artifacts stay under the ignored
`backend/data/codex_runs/` directory.

The Codex, Hermes, and Platform Brain HTTP APIs fail closed by default. To use
these experimental local features, set this only in the root `.env`:

```dotenv
ENABLE_EXPERIMENTAL_LOCAL_APIS=true
```

These routes accept loopback clients only, even when enabled. Do not enable
them on a shared, proxied, remote, or hosted backend: Codex can launch local
CLI work, Hermes can publish persisted artifacts, and Platform Brain can search
project-scoped database content.

The native `http_request` and `web_fetch` tools accept public HTTP(S) destinations
only. Every DNS answer and redirect is checked before connection; private,
loopback, link-local and other non-public addresses are blocked. URL credentials
and environment proxies are not supported by these tools. Use the dedicated
approval-gated tools for local LangConfig actions.

### Hermes and Platform Brain (experimental)

Hermes provides approval-gated drafts that validate before applying changes to
workflows, agents, tools, schedules, or triggers. Platform Brain is an in-memory
lexical catalog over tracked documentation, API routes, workflow recipes, native
tools, and explicitly project-scoped projects, workflows, custom tools,
schedules, triggers, execution traces, and chat history. It is not a persistent
vector store.

Editing a saved draft's title, type or JSON clears its selection and validation.
Click **Draft** to save the edited version before validating or applying it.
Draft controls are locked while requests are pending, and changing drafts does
not disconnect the current Codex event stream.

Schedule drafts validate their cron expression and timezone and save the first
UTC run time. Enabled file-watch triggers start after their artifact commits.
Their apply result reports `activation.status` as `active`, `disabled`, or
`failed`; a startup failure includes a reason and leaves the trigger disabled.
The draft remains applied to prevent duplicate artifacts. Correct the saved
trigger's configuration and enable it through the trigger controls to retry.

### Google Slides export

Follow [Google OAuth setup](GOOGLE_OAUTH_SETUP.md).

### Desktop shell

The Tauri shell is experimental and has not been tested end-to-end; it is not a
supported onboarding path. Contributors investigating it need Rust and the
platform's native build tools and can run `npm run tauri dev` only after the web
setup works. The desktop build currently uses the system Python installation;
it does not bundle Python or backend wheels.

## Tests

Database-backed tests use a separate `langconfig_test` database by default. With
the default Compose credentials, create it once:

```bash
docker compose up -d postgres
docker compose exec postgres createdb -U langconfig langconfig_test
```

Before running pytest, set **both** `DATABASE_URL` and `TEST_DATABASE_URL` to
that disposable database in a dedicated test terminal. Use the shell-specific
commands in [Quality gates](QUALITY_GATES.md#backend-tests-use-a-disposable-database),
adjusting the credentials and port for your installation. Application imports
and test fixtures must target the same database.

```bash
# Backend unit and integration tests, after configuring both database URLs
cd backend
python -m pytest -q --ignore=tests/test_playwright_tools.py

# Frontend checks and focused Hermes browser regressions
cd ..
npm run check:interfaces
npm run build
npx playwright install chromium
npm run test:hermes
```

The migration tests bootstrap a blank `langconfig_test` schema using current
metadata and stamp it at the current Alembic head. Never use a database containing
data you need. The excluded Python Playwright file is a manual browser-tool smoke
script; `test:hermes` is a separate Chromium suite with mocked API responses.

## Troubleshooting

Check service state and logs:

```bash
docker compose ps
docker compose logs postgres
```

Check a port without killing unrelated processes:

```bash
# Windows PowerShell
Get-NetTCPConnection -LocalPort 1425,8780 -ErrorAction SilentlyContinue

# macOS/Linux
lsof -i :1425 -i :8780
```

If Python dependencies conflict, confirm the virtual environment is active and
recreate `.venv`; avoid repairing a shared global environment. If a migration
fails on an existing database, save the complete error and current revision from
`python -m alembic current` before changing data. Do not use `alembic downgrade
base` as a routine reset because it can destroy application data.
