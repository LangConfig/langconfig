# LangConfig

Visual platform for building LangChain agents and LangGraph workflows.

## Stack

- **Frontend:** React 19 + TypeScript + Tailwind CSS 4 + ReactFlow (`src/`)
- **Backend:** Python 3.11-3.13 (3.12 tested) + FastAPI + LangChain v1.3 + LangGraph (`backend/`)
- **Database:** PostgreSQL 16 + pgvector + Alembic

## Commands

```bash
# Start development
cd backend && python main.py      # API server :8780
npm run dev                        # Frontend :1425

# Database
docker compose up -d postgres      # Start PostgreSQL
cd backend && python -m alembic upgrade head # Run migrations

# Testing
cd backend && python -m pytest     # Backend tests
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

- Base URL: `http://localhost:8780`
- Swagger docs: `http://localhost:8780/docs`
- Key endpoints:
  - `POST /api/orchestration/execute` - Run workflow (SSE)
  - `POST /api/chat/start` - Create an agent chat session
  - `POST /api/chat/message/stream` - Stream a chat response (SSE)
  - `POST /api/rag/upload` - Upload a RAG document

## Local setup

- Follow `docs/SETUP.md`; use `python -m ...` so commands run in the active virtual environment.
- The root `.env` is canonical for Docker, the frontend, and the backend.
- `backend/.env` is optional and only for backend-specific local overrides.
- Use `python backend/scripts/setup.py` for a blank database; use `python -m alembic upgrade head` only for an existing LangConfig schema.

## Detailed Docs

Use the tracked public documentation so guidance is available in every clone:

| File | Contents |
|------|----------|
| `README.md` | Product overview, features, and quick start |
| `docs/SETUP.md` | Canonical clone, setup, upgrade, and troubleshooting guide |
| `CONTRIBUTING.md` | Contribution workflow and code style |
| `backend/api/chat/README.md` | Chat routes, storage, and streaming contract |
| `docs/GOOGLE_OAUTH_SETUP.md` | Optional Google Slides OAuth setup |
| `http://localhost:8780/docs` | Live OpenAPI documentation while the backend is running |
