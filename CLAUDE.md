# LangConfig

Visual platform for building LangChain agents and LangGraph workflows.

## Stack

- **Frontend:** React 19 + TypeScript + Tailwind CSS 4 + ReactFlow (`src/`)
- **Backend:** Python 3.11 + FastAPI + LangChain v1.0 + LangGraph (`backend/`)
- **Database:** PostgreSQL 16 + pgvector + Alembic

## Commands

```bash
# Start development
cd backend && python main.py      # API server :8765
npm run dev                        # Frontend :1420

# Database
docker-compose up -d postgres      # Start PostgreSQL
cd backend && alembic upgrade head # Run migrations

# Testing
cd backend && pytest               # Backend tests
npm run build                      # Frontend build check
```

## Key Paths

| Path | Purpose |
|------|---------|
| `backend/core/workflows/executor.py` | Workflow execution engine |
| `backend/core/agents/factory.py` | Agent creation |
| `backend/api/` | REST API routes |
| `backend/models/` | SQLAlchemy ORM models |
| `backend/services/` | Business logic services |
| `src/features/workflows/` | Workflow canvas UI |
| `src/features/agents/` | Agent builder UI |
| `src/hooks/` | React hooks (useWorkflowStream, etc.) |

## API

- Base URL: `http://localhost:8765`
- Swagger docs: `http://localhost:8765/docs`
- Key endpoints:
  - `POST /api/workflows/{id}/execute` - Run workflow (SSE)
  - `POST /api/agents/{id}/chat` - Chat with agent (SSE)
  - `POST /api/knowledge/documents` - Upload RAG document

## Shell Commands (Important!)

This is a **Windows** environment but the shell uses **bash syntax** (Git Bash/WSL), NOT CMD or PowerShell.

```bash
# CORRECT (bash syntax)
test -f backend/.env && echo "exists" || echo "missing"
ls -la backend/.env 2>/dev/null
grep "PATTERN" file.txt
cat file.txt | head -20

# WRONG (Windows CMD syntax - will fail)
if exist backend\.env (echo exists)
dir backend\.env
findstr "PATTERN" file.txt
type file.txt
```

**Python commands:** Always use the full Python 3.12 path for consistency:
```bash
cd backend && "C:\Users\Cade\AppData\Local\Programs\Python\Python312\python.exe" -m pip install package
cd backend && "C:\Users\Cade\AppData\Local\Programs\Python\Python312\python.exe" -c "import module"
```

**Environment files:** There are TWO `.env` files:
- `/.env` - Root (used by frontend/docker)
- `/backend/.env` - Backend specific (loaded by FastAPI)

Backend Python loads from `backend/.env`, so backend-specific secrets must be there.

## Detailed Docs

See `.claude/docs/` for task-specific guidance:

| File | Contents |
|------|----------|
| `architecture.md` | System design, components, project structure |
| `workflows.md` | LangGraph patterns, node types, execution flow |
| `agents.md` | Agent system, middleware, tools, delegation |
| `api.md` | REST endpoints, error codes, streaming |
| `database.md` | PostgreSQL, Alembic, checkpointing |
| `troubleshooting.md` | Common issues and solutions |
| `contributing.md` | Development setup, code style, PR process |
