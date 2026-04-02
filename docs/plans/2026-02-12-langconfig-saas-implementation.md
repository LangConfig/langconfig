# LangConfig SaaS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a cloud-first multi-tenant SaaS platform for visual AI workflow orchestration with plugin-based framework support, BYOK pricing, and team workspaces.

**Architecture:** New codebase — React SPA (Vite) + FastAPI backend + Better Auth (Node.js) + PostgreSQL/pgvector + Stripe billing. Plugin engine abstracts orchestration frameworks (LangGraph first, then CrewAI, raw Python). Multi-tenancy via PostgreSQL RLS. Deployed on Railway.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, ReactFlow, Vite, FastAPI, Python 3.12, Better Auth, Stripe, PostgreSQL 16, pgvector, Alembic, Railway

**Design Doc:** `docs/plans/2026-02-12-langconfig-saas-design.md`

---

## Prerequisites

Before starting, you need:
- Node.js 20+ and npm
- Python 3.12
- PostgreSQL 16 running locally (via Docker or native)
- Git
- Railway CLI (`npm install -g @railway/cli`)
- Stripe CLI (`brew install stripe/stripe-cli/stripe` or Windows equivalent)

---

## Phase 1: Foundation (Weeks 1-3)

### Task 1: Initialize Monorepo Structure

**Files:**
- Create: `langconfig-cloud/` (root directory — NEW REPO, not inside current langconfig)
- Create: `langconfig-cloud/package.json` (root workspace)
- Create: `langconfig-cloud/.gitignore`
- Create: `langconfig-cloud/.env.example`

**Step 1: Create the new repository**

```bash
cd ~/projects
mkdir langconfig-cloud && cd langconfig-cloud
git init
```

**Step 2: Create root package.json for npm workspaces**

```json
{
  "name": "langconfig-cloud",
  "private": true,
  "workspaces": ["apps/*", "packages/*"],
  "scripts": {
    "dev": "concurrently \"npm run dev:web\" \"npm run dev:auth\" \"npm run dev:api\"",
    "dev:web": "npm run dev --workspace=apps/web",
    "dev:auth": "npm run dev --workspace=apps/auth",
    "dev:api": "cd services/api && python -m uvicorn main:app --reload --port 8765"
  },
  "devDependencies": {
    "concurrently": "^9.0.0"
  }
}
```

**Step 3: Create directory scaffold**

```bash
mkdir -p apps/web/src/{features,components,hooks,lib,types}
mkdir -p apps/auth
mkdir -p packages/core/{orchestration,plugins}
mkdir -p services/api/{routes,middleware,models,services}
mkdir -p infra
```

**Step 4: Create .gitignore**

```
node_modules/
dist/
.env
*.pyc
__pycache__/
.venv/
*.egg-info/
.pytest_cache/
```

**Step 5: Create .env.example**

```bash
# Database
DATABASE_URL=postgresql://langconfig:langconfig@localhost:5432/langconfig_cloud

# Better Auth
BETTER_AUTH_SECRET=change-me-to-a-random-string
BETTER_AUTH_URL=http://localhost:3000

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRO=price_...

# App
APP_ENCRYPTION_KEY=change-me-to-a-random-string
FRONTEND_URL=http://localhost:1420
API_URL=http://localhost:8765
```

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: initialize monorepo structure"
```

---

### Task 2: Docker Compose for Local Development

**Files:**
- Create: `langconfig-cloud/docker-compose.yml`

**Step 1: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: langconfig_cloud
      POSTGRES_USER: langconfig
      POSTGRES_PASSWORD: langconfig
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langconfig -d langconfig_cloud"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

**Step 2: Start and verify**

```bash
docker-compose up -d postgres
# Expected: postgres container running on port 5432
docker-compose ps
```

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add docker-compose for local PostgreSQL with pgvector"
```

---

### Task 3: FastAPI Backend Skeleton

**Files:**
- Create: `services/api/main.py`
- Create: `services/api/config.py`
- Create: `services/api/requirements.txt`
- Create: `services/api/routes/__init__.py`
- Create: `services/api/routes/health.py`
- Test: `services/api/tests/test_health.py`

**Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.31.0
pydantic==2.10.0
pydantic-settings==2.6.0
sqlalchemy[asyncio]==2.0.35
alembic==1.13.3
psycopg[binary]==3.2.3
pgvector==0.3.5
PyJWT[crypto]==2.9.0
httpx==0.27.2
cryptography==43.0.0
python-dotenv==1.0.1
aiofiles==24.1.0
stripe==10.0.0
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==5.0.0
httpx==0.27.2
```

**Step 2: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://langconfig:langconfig@localhost:5432/langconfig_cloud"
    better_auth_url: str = "http://localhost:3000"
    better_auth_secret: str = "change-me"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    app_encryption_key: str = "change-me"
    frontend_url: str = "http://localhost:1420"
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 3: Create health route**

```python
# services/api/routes/health.py
from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "langconfig-cloud"}
```

**Step 4: Create main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routes.health import router as health_router

app = FastAPI(
    title="LangConfig Cloud",
    version="0.1.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:1420"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
```

**Step 5: Write the failing test**

```python
# services/api/tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Step 6: Run test**

```bash
cd services/api
pip install -r requirements.txt
pytest tests/test_health.py -v
# Expected: PASS
```

**Step 7: Commit**

```bash
git add services/api/
git commit -m "feat: FastAPI backend skeleton with health endpoint"
```

---

### Task 4: Database Schema — Core Models + Alembic

**Files:**
- Create: `services/api/db.py` (engine + session)
- Create: `services/api/models/__init__.py`
- Create: `services/api/models/base.py`
- Create: `services/api/models/user.py`
- Create: `services/api/models/organization.py`
- Create: `services/api/models/project.py`
- Create: `services/api/alembic.ini`
- Create: `services/api/alembic/env.py`
- Test: `services/api/tests/test_models.py`

**Step 1: Create db.py (async engine + session factory)**

```python
# services/api/db.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.database_url, echo=settings.environment == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Step 2: Create models/base.py with TimestampMixin and OptimisticLockMixin**

```python
# services/api/models/base.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class OptimisticLockMixin:
    lock_version: Mapped[int] = mapped_column(Integer, default=1)
```

**Step 3: Create models/user.py**

```python
# services/api/models/user.py
"""User model — synced from Better Auth's 'user' table.
Better Auth owns user creation. This model reads from the same table."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user"  # Better Auth's default table name

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    image: Mapped[str] = mapped_column(String, nullable=True)
    email_verified: Mapped[bool] = mapped_column(default=False, name="emailVerified")
    stripe_customer_id: Mapped[str] = mapped_column(String, nullable=True)
```

**Step 4: Create models/organization.py**

```python
# services/api/models/organization.py
"""Organization model — synced from Better Auth's 'organization' table.
Extended with billing fields that Better Auth doesn't manage."""
from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from db import Base
from models.base import TimestampMixin


class PlanTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Organization(Base, TimestampMixin):
    __tablename__ = "organization"  # Better Auth's default table name

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    logo: Mapped[str] = mapped_column(String, nullable=True)

    # Billing (our extension, not from Better Auth)
    plan: Mapped[PlanTier] = mapped_column(SAEnum(PlanTier), default=PlanTier.free)
    stripe_subscription_id: Mapped[str] = mapped_column(String, nullable=True)
    stripe_customer_id: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    projects = relationship("Project", back_populates="organization")
```

**Step 5: Create models/project.py**

```python
# services/api/models/project.py
from sqlalchemy import String, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.base import TimestampMixin, OptimisticLockMixin


class Project(Base, TimestampMixin, OptimisticLockMixin):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organization.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    plugin_id: Mapped[str] = mapped_column(String(50), default="langgraph")
    created_by: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="projects")
    workflows = relationship("Workflow", back_populates="project")
```

**Step 6: Create models/__init__.py**

```python
from models.user import User
from models.organization import Organization, PlanTier
from models.project import Project

__all__ = ["User", "Organization", "PlanTier", "Project"]
```

**Step 7: Initialize Alembic**

```bash
cd services/api
alembic init alembic
```

Then edit `alembic/env.py` to use async engine and import all models:

```python
# Key changes to alembic/env.py:
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from db import Base
from models import *  # Import all models so Alembic sees them

target_metadata = Base.metadata

# ... use run_async_migrations() pattern
```

And edit `alembic.ini`:
```ini
sqlalchemy.url = postgresql+psycopg://langconfig:langconfig@localhost:5432/langconfig_cloud
```

**Step 8: Generate and run first migration**

```bash
cd services/api
alembic revision --autogenerate -m "initial schema: user, organization, project"
alembic upgrade head
```

**Step 9: Write test for models**

```python
# services/api/tests/test_models.py
import pytest
from models.organization import PlanTier


def test_plan_tier_values():
    assert PlanTier.free.value == "free"
    assert PlanTier.pro.value == "pro"
    assert PlanTier.enterprise.value == "enterprise"
```

**Step 10: Run test and commit**

```bash
pytest tests/test_models.py -v
# Expected: PASS
git add services/api/
git commit -m "feat: core database models (user, org, project) with Alembic"
```

---

### Task 5: Workflow & Execution Models

**Files:**
- Create: `services/api/models/workflow.py`
- Create: `services/api/models/execution.py`
- Create: `services/api/models/chat.py`
- Create: `services/api/models/knowledge.py`
- Create: `services/api/models/vault.py`
- Modify: `services/api/models/__init__.py`

**Step 1: Create models/workflow.py**

```python
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base
from models.base import TimestampMixin, OptimisticLockMixin


class Workflow(Base, TimestampMixin, OptimisticLockMixin):
    __tablename__ = "workflow"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    graph_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    project = relationship("Project", back_populates="workflows")
    executions = relationship("WorkflowExecution", back_populates="workflow")
```

**Step 2: Create models/execution.py**

```python
import enum
from sqlalchemy import String, Integer, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from db import Base
from models.base import TimestampMixin


class ExecutionStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class WorkflowExecution(Base, TimestampMixin):
    __tablename__ = "workflow_execution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow.id", ondelete="CASCADE"), index=True
    )
    triggered_by: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        SAEnum(ExecutionStatus), default=ExecutionStatus.pending
    )
    results: Mapped[dict] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSONB, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    error_message: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
```

**Step 3: Create models/chat.py**

```python
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    workflow_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    messages: Mapped[dict] = mapped_column(JSONB, default=list)
```

**Step 4: Create models/knowledge.py**

```python
import enum
from sqlalchemy import String, Integer, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from db import Base
from models.base import TimestampMixin


class IndexingStatus(str, enum.Enum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_document"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)  # OpenAI text-embedding-3-small
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        SAEnum(IndexingStatus), default=IndexingStatus.pending
    )
    chunk_metadata: Mapped[dict] = mapped_column("metadata", type_=__import__('sqlalchemy').dialects.postgresql.JSONB, nullable=True)
```

**Step 5: Create models/vault.py**

```python
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class ApiKeyVault(Base, TimestampMixin):
    __tablename__ = "api_key_vault"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, anthropic, google, etc.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=True)  # User-friendly name
```

**Step 6: Create models/file.py**

```python
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class ProjectFile(Base, TimestampMixin):
    __tablename__ = "project_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
```

**Step 7: Update models/__init__.py**

```python
from models.user import User
from models.organization import Organization, PlanTier
from models.project import Project
from models.workflow import Workflow
from models.execution import WorkflowExecution, ExecutionStatus
from models.chat import ChatSession
from models.knowledge import KnowledgeDocument, IndexingStatus
from models.vault import ApiKeyVault
from models.file import ProjectFile

__all__ = [
    "User", "Organization", "PlanTier", "Project",
    "Workflow", "WorkflowExecution", "ExecutionStatus",
    "ChatSession", "KnowledgeDocument", "IndexingStatus",
    "ApiKeyVault", "ProjectFile",
]
```

**Step 8: Generate migration and commit**

```bash
cd services/api
alembic revision --autogenerate -m "add workflow, execution, chat, knowledge, vault, file models"
alembic upgrade head
git add services/api/models/ services/api/alembic/
git commit -m "feat: add workflow, execution, chat, knowledge, vault, and file models"
```

---

### Task 6: PostgreSQL Row-Level Security

**Files:**
- Create: `services/api/alembic/versions/xxx_add_rls_policies.py` (manual migration)

**Step 1: Create manual Alembic migration for RLS**

```python
"""add RLS policies for tenant isolation

Every table with org_id (directly or via project) gets RLS.
The current org_id is set via a session variable: app.current_org_id
"""

def upgrade():
    op.execute("""
        -- Enable RLS on tenant-scoped tables
        ALTER TABLE project ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workflow ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workflow_execution ENABLE ROW LEVEL SECURITY;
        ALTER TABLE chat_session ENABLE ROW LEVEL SECURITY;
        ALTER TABLE knowledge_document ENABLE ROW LEVEL SECURITY;
        ALTER TABLE project_file ENABLE ROW LEVEL SECURITY;
        ALTER TABLE api_key_vault ENABLE ROW LEVEL SECURITY;

        -- Project: direct org_id
        CREATE POLICY project_tenant_isolation ON project
            USING (org_id = current_setting('app.current_org_id', true));

        -- Workflow: via project.org_id
        CREATE POLICY workflow_tenant_isolation ON workflow
            USING (project_id IN (
                SELECT id FROM project WHERE org_id = current_setting('app.current_org_id', true)
            ));

        -- Execution: via workflow -> project
        CREATE POLICY execution_tenant_isolation ON workflow_execution
            USING (workflow_id IN (
                SELECT w.id FROM workflow w
                JOIN project p ON w.project_id = p.id
                WHERE p.org_id = current_setting('app.current_org_id', true)
            ));

        -- Chat session: via project
        CREATE POLICY chat_tenant_isolation ON chat_session
            USING (project_id IN (
                SELECT id FROM project WHERE org_id = current_setting('app.current_org_id', true)
            ));

        -- Knowledge: via project
        CREATE POLICY knowledge_tenant_isolation ON knowledge_document
            USING (project_id IN (
                SELECT id FROM project WHERE org_id = current_setting('app.current_org_id', true)
            ));

        -- Files: via project
        CREATE POLICY file_tenant_isolation ON project_file
            USING (project_id IN (
                SELECT id FROM project WHERE org_id = current_setting('app.current_org_id', true)
            ));

        -- API keys: direct org_id
        CREATE POLICY vault_tenant_isolation ON api_key_vault
            USING (org_id = current_setting('app.current_org_id', true));
    """)


def downgrade():
    # Drop all RLS policies and disable RLS
    for table in ['project', 'workflow', 'workflow_execution', 'chat_session',
                  'knowledge_document', 'project_file', 'api_key_vault']:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
```

**Step 2: Run migration**

```bash
cd services/api
alembic upgrade head
```

**Step 3: Commit**

```bash
git add services/api/alembic/
git commit -m "feat: add PostgreSQL RLS policies for tenant isolation"
```

---

### Task 7: Tenant Middleware (App-Level Isolation)

**Files:**
- Create: `services/api/middleware/tenant.py`
- Create: `services/api/middleware/__init__.py`
- Test: `services/api/tests/test_tenant_middleware.py`

**Step 1: Write the failing test**

```python
# services/api/tests/test_tenant_middleware.py
import pytest
from middleware.tenant import TenantContext


def test_tenant_context_stores_org_id():
    ctx = TenantContext(user_id="user_123", org_id="org_456", role="member")
    assert ctx.user_id == "user_123"
    assert ctx.org_id == "org_456"
    assert ctx.role == "member"


def test_tenant_context_is_owner():
    ctx = TenantContext(user_id="u1", org_id="o1", role="owner")
    assert ctx.is_owner is True


def test_tenant_context_is_not_owner():
    ctx = TenantContext(user_id="u1", org_id="o1", role="member")
    assert ctx.is_owner is False
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_tenant_middleware.py -v
# Expected: FAIL — module not found
```

**Step 3: Implement tenant middleware**

```python
# services/api/middleware/tenant.py
from dataclasses import dataclass
from contextvars import ContextVar
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db import get_db

# Context var holds tenant info for the current request
_tenant_ctx: ContextVar[Optional["TenantContext"]] = ContextVar("tenant_ctx", default=None)


@dataclass
class TenantContext:
    user_id: str
    org_id: str
    role: str  # owner, admin, member, viewer

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")

    @property
    def can_write(self) -> bool:
        return self.role in ("owner", "admin", "member")


def get_tenant() -> TenantContext:
    """Dependency: get the current tenant context. Raises 401 if not set."""
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return ctx


async def set_rls_context(db: AsyncSession, org_id: str):
    """Set the PostgreSQL session variable for RLS policies."""
    await db.execute(text(f"SET LOCAL app.current_org_id = '{org_id}'"))
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_tenant_middleware.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add services/api/middleware/
git add services/api/tests/test_tenant_middleware.py
git commit -m "feat: tenant context middleware with RLS session variable"
```

---

### Task 8: Better Auth — Node.js Auth Service

**Files:**
- Create: `apps/auth/package.json`
- Create: `apps/auth/src/index.ts`
- Create: `apps/auth/src/auth.ts`
- Create: `apps/auth/tsconfig.json`

**Step 1: Initialize the auth service**

```bash
cd apps/auth
npm init -y
npm install better-auth pg hono @hono/node-server dotenv
npm install -D typescript @types/node tsx
```

**Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

**Step 3: Create auth.ts (Better Auth configuration)**

```typescript
// apps/auth/src/auth.ts
import { betterAuth } from "better-auth";
import { organization } from "better-auth/plugins";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";
import "dotenv/config";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export const auth = betterAuth({
  database: pool,
  baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
  secret: process.env.BETTER_AUTH_SECRET,

  emailAndPassword: {
    enabled: true,
  },

  socialProviders: {
    github: {
      clientId: process.env.GITHUB_CLIENT_ID || "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET || "",
    },
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    },
  },

  plugins: [
    jwt({
      jwt: {
        issuer: process.env.BETTER_AUTH_URL || "http://localhost:3000",
        audience: process.env.API_URL || "http://localhost:8765",
        expirationTime: "1h",
        definePayload: ({ user, session }) => ({
          sub: user.id,
          email: user.email,
          name: user.name,
          activeOrganizationId: (session as any).activeOrganizationId || null,
        }),
      },
    }),
    organization({
      allowUserToCreateOrganization: true,
    }),
  ],

  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24,      // 1 day
  },

  trustedOrigins: [
    process.env.FRONTEND_URL || "http://localhost:1420",
  ],
});
```

**Step 4: Create index.ts (Hono server)**

```typescript
// apps/auth/src/index.ts
import { Hono } from "hono";
import { cors } from "hono/cors";
import { serve } from "@hono/node-server";
import { auth } from "./auth";
import "dotenv/config";

const app = new Hono();

app.use(
  "/api/auth/*",
  cors({
    origin: [process.env.FRONTEND_URL || "http://localhost:1420"],
    credentials: true,
    allowHeaders: ["Content-Type", "Authorization"],
    allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
  })
);

app.on(["POST", "GET"], "/api/auth/**", (c) => {
  return auth.handler(c.req.raw);
});

app.get("/health", (c) => c.json({ status: "ok", service: "auth" }));

const port = parseInt(process.env.AUTH_PORT || "3000");
console.log(`Auth service running on http://localhost:${port}`);
serve({ fetch: app.fetch, port });
```

**Step 5: Update package.json scripts**

```json
{
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "migrate": "npx @better-auth/cli migrate",
    "generate": "npx @better-auth/cli generate"
  }
}
```

**Step 6: Run Better Auth migration**

```bash
cd apps/auth
npx @better-auth/cli migrate
# This creates: user, session, account, verification, jwks, organization, member, invitation tables
```

**Step 7: Start and test**

```bash
npm run dev
# Test: curl http://localhost:3000/health
# Expected: {"status":"ok","service":"auth"}
# Test: curl http://localhost:3000/api/auth/jwks
# Expected: {"keys":[...]} — JWKS endpoint working
```

**Step 8: Commit**

```bash
git add apps/auth/
git commit -m "feat: Better Auth service with JWT, organizations, email/password, and social auth"
```

---

### Task 9: FastAPI JWT Verification Middleware

**Files:**
- Create: `services/api/middleware/auth.py`
- Test: `services/api/tests/test_auth_middleware.py`

**Step 1: Write the failing test**

```python
# services/api/tests/test_auth_middleware.py
import pytest
from unittest.mock import patch, AsyncMock
from middleware.auth import decode_jwt_payload


@pytest.mark.asyncio
async def test_decode_jwt_raises_on_missing_kid():
    """Token without kid header should raise."""
    import jwt as pyjwt
    # Create a token without kid
    token = pyjwt.encode({"sub": "user1"}, "secret", algorithm="HS256")
    with pytest.raises(Exception):
        await decode_jwt_payload(token)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth_middleware.py -v
# Expected: FAIL — module not found
```

**Step 3: Implement auth middleware**

```python
# services/api/middleware/auth.py
import time
from typing import Optional

import jwt as pyjwt
from jwt.algorithms import OKPAlgorithm
import httpx
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import settings
from middleware.tenant import TenantContext, _tenant_ctx

security = HTTPBearer()

# JWKS cache
_jwks_cache: dict = {}
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 3600


async def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_cache_time
    if _jwks_cache and (time.time() - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.better_auth_url}/api/auth/jwks")
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = time.time()
        return _jwks_cache


def _get_public_key(jwks: dict, kid: str):
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return OKPAlgorithm.from_jwk(key_data)
    return None


async def decode_jwt_payload(token: str) -> dict:
    """Decode and verify a Better Auth JWT using JWKS."""
    unverified_header = pyjwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Token missing kid")

    jwks = await _fetch_jwks()
    public_key = _get_public_key(jwks, kid)
    if not public_key:
        raise HTTPException(status_code=401, detail="Unknown signing key")

    try:
        return pyjwt.decode(
            token,
            public_key,
            algorithms=["EdDSA"],
            issuer=settings.better_auth_url,
            audience=settings.api_url if hasattr(settings, 'api_url') else None,
            options={"verify_aud": False},  # Relaxed for dev
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """FastAPI dependency: extracts and verifies the JWT, returns payload."""
    payload = await decode_jwt_payload(credentials.credentials)
    return payload


async def require_auth(
    request: Request,
    user: dict = Depends(get_current_user),
) -> TenantContext:
    """FastAPI dependency: verifies JWT and sets tenant context.

    The JWT payload contains:
    - sub: user ID
    - email: user email
    - activeOrganizationId: currently selected org (set by frontend)
    """
    org_id = user.get("activeOrganizationId")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization selected")

    # TODO: Look up user's role in this org from the 'member' table
    # For now, default to 'member'
    ctx = TenantContext(
        user_id=user["sub"],
        org_id=org_id,
        role="member",
    )
    _tenant_ctx.set(ctx)
    return ctx
```

**Step 4: Run test**

```bash
pytest tests/test_auth_middleware.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add services/api/middleware/auth.py services/api/tests/test_auth_middleware.py
git commit -m "feat: JWT verification middleware using Better Auth JWKS endpoint"
```

---

### Task 10: React Frontend Shell (Vite + Tailwind + Router)

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/index.css`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/lib/api-client.ts`
- Create: `apps/web/src/lib/auth-client.ts`

**Step 1: Initialize the frontend**

```bash
cd apps/web
npm init -y
npm install react@19 react-dom@19 react-router-dom@7 @tanstack/react-query@5 axios reactflow @reactflow/core @reactflow/controls @reactflow/minimap
npm install -D typescript @types/react @types/react-dom vite @vitejs/plugin-react tailwindcss @tailwindcss/vite
```

**Step 2: Install Better Auth client**

```bash
npm install better-auth
```

**Step 3: Create auth-client.ts**

```typescript
// apps/web/src/lib/auth-client.ts
import { createAuthClient } from "better-auth/react";
import { organizationClient } from "better-auth/client/plugins";
import { jwtClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  baseURL: import.meta.env.VITE_AUTH_URL || "http://localhost:3000",
  plugins: [organizationClient(), jwtClient()],
});
```

**Step 4: Create api-client.ts**

```typescript
// apps/web/src/lib/api-client.ts
import axios from "axios";
import { authClient } from "./auth-client";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8765",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT to every request
api.interceptors.request.use(async (config) => {
  try {
    const { data } = await authClient.getSession();
    if (data?.session) {
      // Get JWT token for the API
      const tokenRes = await authClient.$fetch("/token", { method: "GET" });
      if (tokenRes.data?.token) {
        config.headers.Authorization = `Bearer ${tokenRes.data.token}`;
      }
    }
  } catch {
    // Not logged in — let the request go without auth
  }
  return config;
});

export default api;
```

**Step 5: Create App.tsx with router shell**

```tsx
// apps/web/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { authClient } from "./lib/auth-client";

const queryClient = new QueryClient();

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { data: session, isPending } = authClient.useSession();
  if (isPending) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!session) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function LoginPage() {
  return (
    <div className="min-h-screen bg-[#FAF3EF] flex items-center justify-center">
      <div className="border-2 border-[#1B2040] bg-white p-8 shadow-[4px_4px_0px_#1B2040] max-w-md w-full">
        <h1 className="font-serif text-3xl text-[#1B2040] mb-6">LangConfig</h1>
        <p className="text-[#5A607A] mb-8">Visual AI workflow orchestration.</p>
        {/* Auth forms will go here */}
        <p className="text-sm text-[#5A607A]">Login form coming in Task 10+</p>
      </div>
    </div>
  );
}

function DashboardPage() {
  return (
    <div className="min-h-screen bg-[#FAF3EF]">
      <nav className="border-b-2 border-[#1B2040] bg-white px-6 py-3 flex items-center justify-between">
        <h1 className="font-serif text-xl text-[#1B2040]">LangConfig</h1>
        <span className="font-mono text-xs uppercase tracking-wider text-[#5A607A]">Dashboard</span>
      </nav>
      <main className="max-w-[1200px] mx-auto py-12 px-6">
        <p className="text-[#1B2040]">Projects will load here.</p>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<AuthGuard><DashboardPage /></AuthGuard>} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

**Step 6: Create index.css with Tailwind + botanical brutalist base**

```css
/* apps/web/src/index.css */
@import "tailwindcss";

@theme {
  --font-serif: "Cormorant Garamond", serif;
  --font-mono: "JetBrains Mono", monospace;
  --color-bg: #FAF3EF;
  --color-surface: #FFFFFF;
  --color-text: #1B2040;
  --color-text-secondary: #5A607A;
  --color-accent: #E8868B;
  --color-accent-light: rgba(232, 134, 139, 0.2);
  --color-accent-dark: #D0696E;
  --color-border: #1B2040;
}

body {
  font-family: Inter, system-ui, sans-serif;
  background-color: var(--color-bg);
  color: var(--color-text);
  line-height: 1.6;
}
```

**Step 7: Create vite.config.ts, tsconfig.json, index.html, main.tsx**

```typescript
// apps/web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 1420 },
});
```

```tsx
// apps/web/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

```html
<!-- apps/web/index.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LangConfig</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 8: Start and verify**

```bash
cd apps/web && npm run dev
# Open http://localhost:1420 — should see login page with botanical brutalist styling
```

**Step 9: Commit**

```bash
git add apps/web/
git commit -m "feat: React frontend shell with Tailwind, Better Auth client, botanical brutalist theme"
```

---

### Task 11: Railway Deployment Config

**Files:**
- Create: `infra/railway.toml`
- Create: `apps/web/Dockerfile`
- Create: `services/api/Dockerfile`
- Create: `apps/auth/Dockerfile`

**Step 1: Create Dockerfiles for each service**

```dockerfile
# apps/web/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```dockerfile
# services/api/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8765"]
```

```dockerfile
# apps/auth/Dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

**Step 2: Create railway.toml**

```toml
# infra/railway.toml
# Railway deploys each service from its directory.
# Configure via Railway dashboard: link each service to its subdirectory.
# Environment variables set in Railway dashboard per service.
```

**Step 3: Commit**

```bash
git add infra/ apps/web/Dockerfile services/api/Dockerfile apps/auth/Dockerfile
git commit -m "chore: add Dockerfiles and Railway deployment config"
```

---

### Task 12: Encryption Service

**Files:**
- Create: `services/api/services/__init__.py`
- Create: `services/api/services/encryption.py`
- Test: `services/api/tests/test_encryption.py`

**Step 1: Write the failing test**

```python
# services/api/tests/test_encryption.py
import pytest
from services.encryption import EncryptionService


def test_encrypt_decrypt_roundtrip():
    svc = EncryptionService("test-secret-key")
    original = "sk-abc123-my-openai-key"
    encrypted = svc.encrypt(original)
    assert encrypted != original
    decrypted = svc.decrypt(encrypted)
    assert decrypted == original


def test_encrypted_values_are_different_each_time():
    svc = EncryptionService("test-secret-key")
    e1 = svc.encrypt("same-value")
    e2 = svc.encrypt("same-value")
    # Fernet uses random IVs, so encrypted values differ
    assert e1 != e2


def test_decrypt_wrong_key_fails():
    svc1 = EncryptionService("key-one")
    svc2 = EncryptionService("key-two")
    encrypted = svc1.encrypt("secret")
    with pytest.raises(Exception):
        svc2.decrypt(encrypted)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_encryption.py -v
# Expected: FAIL
```

**Step 3: Implement encryption service**

```python
# services/api/services/encryption.py
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    def __init__(self, secret_key: str):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"langconfig_cloud_salt",
            iterations=100_000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self._fernet.decrypt(encrypted_data.encode()).decode()
```

**Step 4: Run tests**

```bash
pytest tests/test_encryption.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add services/api/services/ services/api/tests/test_encryption.py
git commit -m "feat: Fernet encryption service for API key vault"
```

---

## Phase 2: Core Engine (Weeks 4-7)

### Task 13: Plugin Interface — Abstract Base Class

**Files:**
- Create: `packages/core/orchestration/__init__.py`
- Create: `packages/core/orchestration/plugin_interface.py`
- Create: `packages/core/orchestration/types.py`
- Test: `packages/core/tests/test_plugin_interface.py`

**Step 1: Write the failing test**

```python
# packages/core/tests/test_plugin_interface.py
import pytest
from orchestration.plugin_interface import OrchestratorPlugin
from orchestration.types import PluginMetadata, NodeType, GraphConfig, ValidationResult


def test_cannot_instantiate_abstract_plugin():
    with pytest.raises(TypeError):
        OrchestratorPlugin()


def test_plugin_metadata_fields():
    meta = PluginMetadata(
        id="langgraph",
        name="LangGraph",
        version="1.0.0",
        description="LangGraph orchestration",
    )
    assert meta.id == "langgraph"


def test_node_type_has_config_schema():
    node = NodeType(
        id="agent",
        name="Agent",
        description="An LLM agent node",
        config_schema={"model": {"type": "string"}, "system_prompt": {"type": "string"}},
        inputs=["messages"],
        outputs=["response"],
    )
    assert "model" in node.config_schema
```

**Step 2: Implement types.py**

```python
# packages/core/orchestration/types.py
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


@dataclass
class PluginMetadata:
    id: str
    name: str
    version: str
    description: str
    icon: str = ""
    docs_url: str = ""


@dataclass
class NodeType:
    id: str
    name: str
    description: str
    config_schema: dict[str, Any]  # JSON Schema for node config panel
    inputs: list[str]
    outputs: list[str]
    category: str = "general"


@dataclass
class GraphConfig:
    id: str
    plugin: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ExecutionEventType(str, Enum):
    status = "status"
    node_start = "node_start"
    node_end = "node_end"
    llm_token = "llm_token"
    tool_start = "tool_start"
    tool_end = "tool_end"
    error = "error"
    complete = "complete"


@dataclass
class ExecutionEvent:
    type: ExecutionEventType
    data: dict[str, Any]
    node_id: Optional[str] = None
    timestamp: Optional[float] = None


@dataclass
class ExecutionResult:
    success: bool
    output: Any = None
    events: list[ExecutionEvent] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    cost: float = 0.0
    error: Optional[str] = None


@dataclass
class ChatResult:
    response: str
    events: list[ExecutionEvent] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    cost: float = 0.0


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str
```

**Step 3: Implement plugin_interface.py**

```python
# packages/core/orchestration/plugin_interface.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable

from orchestration.types import (
    PluginMetadata, NodeType, GraphConfig, ValidationResult,
    ExecutionEvent, ExecutionResult, ChatResult, Message,
)

# Callback type for streaming events to the frontend
ExecutionCallbacks = Callable[[ExecutionEvent], None]


class OrchestratorPlugin(ABC):
    """Interface every orchestration backend must implement."""

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin identification and metadata."""

    @abstractmethod
    def get_node_types(self) -> list[NodeType]:
        """Return available node types with config schemas.
        The frontend canvas renders these dynamically."""

    @abstractmethod
    def validate_graph(self, graph_config: GraphConfig) -> ValidationResult:
        """Validate the user's graph configuration before execution."""

    @abstractmethod
    async def execute(
        self,
        graph_config: GraphConfig,
        inputs: dict,
        credentials: dict,
        on_event: ExecutionCallbacks,
    ) -> ExecutionResult:
        """Execute a workflow. Stream progress via on_event callback."""

    @abstractmethod
    async def chat(
        self,
        graph_config: GraphConfig,
        message: str,
        history: list[Message],
        credentials: dict,
        on_event: ExecutionCallbacks,
    ) -> ChatResult:
        """Interactive chat with a workflow/agent."""
```

**Step 4: Run tests**

```bash
cd packages/core
pip install pytest
pytest tests/test_plugin_interface.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add packages/core/
git commit -m "feat: orchestrator plugin interface with types and abstract base class"
```

---

### Task 14: Plugin Registry

**Files:**
- Create: `packages/core/orchestration/registry.py`
- Test: `packages/core/tests/test_registry.py`

**Step 1: Write the failing test**

```python
# packages/core/tests/test_registry.py
import pytest
from orchestration.registry import PluginRegistry
from orchestration.plugin_interface import OrchestratorPlugin
from orchestration.types import PluginMetadata, NodeType, GraphConfig, ValidationResult, ExecutionResult, ChatResult, Message


class MockPlugin(OrchestratorPlugin):
    def get_metadata(self):
        return PluginMetadata(id="mock", name="Mock", version="1.0", description="Test")

    def get_node_types(self):
        return []

    def validate_graph(self, graph_config):
        return ValidationResult(valid=True)

    async def execute(self, graph_config, inputs, credentials, on_event):
        return ExecutionResult(success=True)

    async def chat(self, graph_config, message, history, credentials, on_event):
        return ChatResult(response="hello")


def test_register_and_get_plugin():
    registry = PluginRegistry()
    plugin = MockPlugin()
    registry.register(plugin)
    assert registry.get("mock") is plugin


def test_list_plugins():
    registry = PluginRegistry()
    registry.register(MockPlugin())
    plugins = registry.list()
    assert len(plugins) == 1
    assert plugins[0].id == "mock"


def test_get_unknown_plugin_returns_none():
    registry = PluginRegistry()
    assert registry.get("nonexistent") is None
```

**Step 2: Implement registry**

```python
# packages/core/orchestration/registry.py
from orchestration.plugin_interface import OrchestratorPlugin
from orchestration.types import PluginMetadata


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, OrchestratorPlugin] = {}

    def register(self, plugin: OrchestratorPlugin) -> None:
        meta = plugin.get_metadata()
        self._plugins[meta.id] = plugin

    def get(self, plugin_id: str) -> OrchestratorPlugin | None:
        return self._plugins.get(plugin_id)

    def list(self) -> list[PluginMetadata]:
        return [p.get_metadata() for p in self._plugins.values()]
```

**Step 3: Run tests and commit**

```bash
pytest tests/test_registry.py -v
# Expected: PASS
git add packages/core/orchestration/registry.py packages/core/tests/test_registry.py
git commit -m "feat: plugin registry for discovering and loading orchestration plugins"
```

---

### Task 15: LangGraph Plugin — Metadata + Node Types

**Files:**
- Create: `packages/core/plugins/__init__.py`
- Create: `packages/core/plugins/langgraph/__init__.py`
- Create: `packages/core/plugins/langgraph/plugin.py`
- Create: `packages/core/plugins/langgraph/node_types.py`
- Test: `packages/core/tests/test_langgraph_plugin.py`

**Step 1: Write the failing test**

```python
# packages/core/tests/test_langgraph_plugin.py
import pytest
from plugins.langgraph.plugin import LangGraphPlugin


def test_metadata():
    plugin = LangGraphPlugin()
    meta = plugin.get_metadata()
    assert meta.id == "langgraph"
    assert meta.name == "LangGraph"


def test_node_types_include_agent():
    plugin = LangGraphPlugin()
    types = plugin.get_node_types()
    ids = [t.id for t in types]
    assert "agent" in ids
    assert "tool" in ids
    assert "router" in ids


def test_agent_node_has_model_config():
    plugin = LangGraphPlugin()
    types = plugin.get_node_types()
    agent = next(t for t in types if t.id == "agent")
    assert "model" in agent.config_schema
    assert "system_prompt" in agent.config_schema
```

**Step 2: Implement node_types.py**

```python
# packages/core/plugins/langgraph/node_types.py
from orchestration.types import NodeType

LANGGRAPH_NODE_TYPES = [
    NodeType(
        id="agent",
        name="Agent",
        description="An LLM-powered agent that can use tools and reason",
        category="core",
        inputs=["messages"],
        outputs=["response"],
        config_schema={
            "model": {"type": "string", "default": "gpt-4o", "description": "LLM model to use"},
            "system_prompt": {"type": "string", "default": "", "description": "System prompt"},
            "temperature": {"type": "number", "default": 0.7, "min": 0, "max": 2},
            "tools": {"type": "array", "items": {"type": "string"}, "default": []},
        },
    ),
    NodeType(
        id="tool",
        name="Tool",
        description="A tool that an agent can invoke",
        category="tools",
        inputs=["tool_call"],
        outputs=["tool_result"],
        config_schema={
            "tool_type": {"type": "string", "enum": ["web_search", "web_fetch", "custom"]},
            "config": {"type": "object", "default": {}},
        },
    ),
    NodeType(
        id="router",
        name="Router",
        description="Conditional routing based on state or LLM decision",
        category="control",
        inputs=["state"],
        outputs=["branch_a", "branch_b"],
        config_schema={
            "routing_type": {"type": "string", "enum": ["conditional", "llm_decision"]},
            "conditions": {"type": "array", "items": {"type": "object"}, "default": []},
        },
    ),
    NodeType(
        id="human_input",
        name="Human Input",
        description="Pause execution for human approval or input",
        category="control",
        inputs=["state"],
        outputs=["approved", "rejected"],
        config_schema={
            "prompt": {"type": "string", "default": "Please review and approve"},
            "timeout_seconds": {"type": "integer", "default": 3600},
        },
    ),
    NodeType(
        id="subgraph",
        name="Subgraph",
        description="Embed another workflow as a node",
        category="advanced",
        inputs=["state"],
        outputs=["result"],
        config_schema={
            "workflow_id": {"type": "integer", "description": "ID of the workflow to embed"},
        },
    ),
]
```

**Step 3: Implement plugin.py (metadata + node types only — execution in next task)**

```python
# packages/core/plugins/langgraph/plugin.py
from orchestration.plugin_interface import OrchestratorPlugin, ExecutionCallbacks
from orchestration.types import (
    PluginMetadata, NodeType, GraphConfig, ValidationResult,
    ExecutionResult, ChatResult, Message,
)
from plugins.langgraph.node_types import LANGGRAPH_NODE_TYPES


class LangGraphPlugin(OrchestratorPlugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="langgraph",
            name="LangGraph",
            version="1.0.0",
            description="Build workflows using LangGraph state machines",
            docs_url="https://langchain-ai.github.io/langgraph/",
        )

    def get_node_types(self) -> list[NodeType]:
        return LANGGRAPH_NODE_TYPES

    def validate_graph(self, graph_config: GraphConfig) -> ValidationResult:
        errors = []
        if not graph_config.nodes:
            errors.append("Graph must have at least one node")
        # Validate edges reference existing nodes
        node_ids = {n["id"] for n in graph_config.nodes}
        for edge in graph_config.edges:
            if edge["source"] not in node_ids:
                errors.append(f"Edge source '{edge['source']}' not found")
            if edge["target"] not in node_ids:
                errors.append(f"Edge target '{edge['target']}' not found")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def execute(
        self, graph_config: GraphConfig, inputs: dict,
        credentials: dict, on_event: ExecutionCallbacks,
    ) -> ExecutionResult:
        # TODO: Implement in Task 16
        raise NotImplementedError("LangGraph execution coming in Task 16")

    async def chat(
        self, graph_config: GraphConfig, message: str, history: list[Message],
        credentials: dict, on_event: ExecutionCallbacks,
    ) -> ChatResult:
        # TODO: Implement in Task 17
        raise NotImplementedError("LangGraph chat coming in Task 17")
```

**Step 4: Run tests and commit**

```bash
pytest tests/test_langgraph_plugin.py -v
# Expected: PASS
git add packages/core/plugins/
git commit -m "feat: LangGraph plugin with node types (agent, tool, router, human_input, subgraph)"
```

---

### Task 16: LangGraph Plugin — Execution Engine

**Files:**
- Create: `packages/core/plugins/langgraph/executor.py`
- Create: `packages/core/plugins/langgraph/requirements.txt`
- Modify: `packages/core/plugins/langgraph/plugin.py`
- Test: `packages/core/tests/test_langgraph_execution.py`

**Step 1: Create requirements.txt for the plugin**

```
langchain>=0.3.0
langchain-core>=0.3.0
langchain-openai>=0.2.0
langchain-anthropic>=0.2.0
langchain-google-genai>=2.0.0
langgraph>=0.2.0
```

**Step 2: Implement executor.py**

This is the core execution engine — it translates the visual graph config into a LangGraph StateGraph and runs it with SSE event streaming. Port the best patterns from the existing `backend/core/workflows/executor.py`.

```python
# packages/core/plugins/langgraph/executor.py
"""Translates a visual GraphConfig into a LangGraph StateGraph and executes it."""
import operator
import time
from typing import TypedDict, Annotated, Any

from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent

from orchestration.types import (
    GraphConfig, ExecutionEvent, ExecutionEventType,
    ExecutionResult, ChatResult, Message,
)
from orchestration.plugin_interface import ExecutionCallbacks


class WorkflowState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    current_node: str
    results: dict[str, Any]


def _create_llm(node_config: dict, credentials: dict):
    """Create an LLM instance based on the model string and credentials."""
    model = node_config.get("model", "gpt-4o")
    temperature = node_config.get("temperature", 0.7)

    if model.startswith("gpt") or model.startswith("o"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=credentials.get("openai"),
            streaming=True,
        )
    elif model.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=credentials.get("anthropic"),
            streaming=True,
        )
    elif model.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=credentials.get("google"),
            streaming=True,
        )
    else:
        # Default to OpenAI
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=credentials.get("openai"),
            streaming=True,
        )


async def execute_graph(
    graph_config: GraphConfig,
    inputs: dict,
    credentials: dict,
    on_event: ExecutionCallbacks,
) -> ExecutionResult:
    """Build and execute a LangGraph workflow from visual graph config."""
    on_event(ExecutionEvent(
        type=ExecutionEventType.status,
        data={"message": "Building graph..."},
    ))

    try:
        # For simple single-agent graphs, use create_react_agent
        agent_nodes = [n for n in graph_config.nodes if n.get("type") == "agent"]

        if len(agent_nodes) == 1 and len(graph_config.nodes) == 1:
            # Simple case: single agent
            node = agent_nodes[0]
            config = node.get("config", {})
            llm = _create_llm(config, credentials)

            agent = create_react_agent(llm, tools=[])
            query = inputs.get("query", inputs.get("message", ""))

            on_event(ExecutionEvent(
                type=ExecutionEventType.node_start,
                node_id=node["id"],
                data={"node_name": config.get("name", "Agent")},
            ))

            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=query)]},
            )

            response = result["messages"][-1].content if result["messages"] else ""

            on_event(ExecutionEvent(
                type=ExecutionEventType.node_end,
                node_id=node["id"],
                data={"output": response},
            ))

            on_event(ExecutionEvent(
                type=ExecutionEventType.complete,
                data={"output": response},
            ))

            return ExecutionResult(success=True, output=response)

        # Multi-node graph: build StateGraph
        # (Full multi-node execution to be expanded as the product matures)
        builder = StateGraph(WorkflowState)

        # Add nodes
        for node in graph_config.nodes:
            node_id = node["id"]
            node_type = node.get("type", "agent")
            config = node.get("config", {})

            if node_type == "agent":
                llm = _create_llm(config, credentials)

                async def agent_fn(state, _llm=llm, _config=config, _node_id=node_id):
                    on_event(ExecutionEvent(
                        type=ExecutionEventType.node_start,
                        node_id=_node_id,
                        data={"node_name": _config.get("name", "Agent")},
                    ))
                    system = _config.get("system_prompt", "")
                    msgs = state["messages"]
                    if system:
                        msgs = [SystemMessage(content=system)] + msgs
                    response = await _llm.ainvoke(msgs)
                    on_event(ExecutionEvent(
                        type=ExecutionEventType.node_end,
                        node_id=_node_id,
                        data={"output": response.content},
                    ))
                    return {
                        "messages": [response],
                        "results": {_node_id: response.content},
                    }

                builder.add_node(node_id, agent_fn)

        # Add edges
        for edge in graph_config.edges:
            builder.add_edge(edge["source"], edge["target"])

        # Set entry point (first node)
        if graph_config.nodes:
            builder.set_entry_point(graph_config.nodes[0]["id"])

        # Find terminal nodes (no outgoing edges) and connect to END
        sources = {e["source"] for e in graph_config.edges}
        targets = {e["target"] for e in graph_config.edges}
        terminal = targets - sources
        if not terminal and graph_config.nodes:
            terminal = {graph_config.nodes[-1]["id"]}
        for node_id in terminal:
            builder.add_edge(node_id, END)

        graph = builder.compile()

        query = inputs.get("query", inputs.get("message", ""))
        result = await graph.ainvoke({
            "messages": [HumanMessage(content=query)],
            "current_node": "",
            "results": {},
        })

        output = result["messages"][-1].content if result["messages"] else ""

        on_event(ExecutionEvent(
            type=ExecutionEventType.complete,
            data={"output": output},
        ))

        return ExecutionResult(success=True, output=output)

    except Exception as e:
        on_event(ExecutionEvent(
            type=ExecutionEventType.error,
            data={"error": str(e)},
        ))
        return ExecutionResult(success=False, error=str(e))
```

**Step 3: Update plugin.py to wire in executor**

Replace the `execute` and `chat` methods in `plugin.py`:

```python
    async def execute(
        self, graph_config: GraphConfig, inputs: dict,
        credentials: dict, on_event: ExecutionCallbacks,
    ) -> ExecutionResult:
        from plugins.langgraph.executor import execute_graph
        return await execute_graph(graph_config, inputs, credentials, on_event)

    async def chat(
        self, graph_config: GraphConfig, message: str, history: list[Message],
        credentials: dict, on_event: ExecutionCallbacks,
    ) -> ChatResult:
        from plugins.langgraph.executor import execute_graph
        result = await execute_graph(
            graph_config,
            {"message": message},
            credentials,
            on_event,
        )
        return ChatResult(
            response=result.output or "",
            token_usage=result.token_usage,
            cost=result.cost,
        )
```

**Step 4: Write test (mocked LLM)**

```python
# packages/core/tests/test_langgraph_execution.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from plugins.langgraph.plugin import LangGraphPlugin
from orchestration.types import GraphConfig, ExecutionEvent


@pytest.mark.asyncio
async def test_validate_empty_graph():
    plugin = LangGraphPlugin()
    config = GraphConfig(id="test", plugin="langgraph", nodes=[], edges=[])
    result = plugin.validate_graph(config)
    assert result.valid is False
    assert "at least one node" in result.errors[0]


@pytest.mark.asyncio
async def test_validate_valid_single_agent():
    plugin = LangGraphPlugin()
    config = GraphConfig(
        id="test",
        plugin="langgraph",
        nodes=[{"id": "n1", "type": "agent", "config": {"model": "gpt-4o"}}],
        edges=[],
    )
    result = plugin.validate_graph(config)
    assert result.valid is True


@pytest.mark.asyncio
async def test_validate_bad_edge():
    plugin = LangGraphPlugin()
    config = GraphConfig(
        id="test",
        plugin="langgraph",
        nodes=[{"id": "n1", "type": "agent", "config": {}}],
        edges=[{"source": "n1", "target": "n_missing"}],
    )
    result = plugin.validate_graph(config)
    assert result.valid is False
    assert "n_missing" in result.errors[0]
```

**Step 5: Run tests and commit**

```bash
pytest tests/test_langgraph_execution.py -v
# Expected: PASS
git add packages/core/plugins/langgraph/
git add packages/core/tests/test_langgraph_execution.py
git commit -m "feat: LangGraph plugin execution engine with multi-node graph support"
```

---

### Task 17: Plugins API Route

**Files:**
- Create: `services/api/routes/plugins.py`
- Modify: `services/api/main.py`
- Test: `services/api/tests/test_plugins_route.py`

**Step 1: Write the failing test**

```python
# services/api/tests/test_plugins_route.py
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_list_plugins():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/plugins")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["id"] == "langgraph"


@pytest.mark.asyncio
async def test_get_plugin_node_types():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/plugins/langgraph/node-types")
    assert response.status_code == 200
    data = response.json()
    ids = [n["id"] for n in data]
    assert "agent" in ids
```

**Step 2: Implement plugins route**

```python
# services/api/routes/plugins.py
from fastapi import APIRouter, HTTPException

# Import plugin system
import sys
sys.path.insert(0, "../../packages/core")  # Adjust path for monorepo
from orchestration.registry import PluginRegistry
from plugins.langgraph.plugin import LangGraphPlugin

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

# Initialize plugin registry
plugin_registry = PluginRegistry()
plugin_registry.register(LangGraphPlugin())


@router.get("")
async def list_plugins():
    """List all available orchestration plugins."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "version": m.version,
            "description": m.description,
        }
        for m in plugin_registry.list()
    ]


@router.get("/{plugin_id}/node-types")
async def get_node_types(plugin_id: str):
    """Get available node types for a plugin (drives the canvas palette)."""
    plugin = plugin_registry.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return [
        {
            "id": n.id,
            "name": n.name,
            "description": n.description,
            "category": n.category,
            "config_schema": n.config_schema,
            "inputs": n.inputs,
            "outputs": n.outputs,
        }
        for n in plugin.get_node_types()
    ]
```

**Step 3: Add to main.py**

```python
from routes.plugins import router as plugins_router
app.include_router(plugins_router)
```

**Step 4: Run tests and commit**

```bash
pytest tests/test_plugins_route.py -v
# Expected: PASS
git add services/api/routes/plugins.py services/api/main.py services/api/tests/test_plugins_route.py
git commit -m "feat: plugins API route for listing plugins and node types"
```

---

### Task 18: Workflow CRUD API Routes

**Files:**
- Create: `services/api/routes/workflows.py`
- Create: `services/api/routes/projects.py`
- Test: `services/api/tests/test_workflow_routes.py`

**Step 1: Implement projects route (dependency for workflows)**

```python
# services/api/routes/projects.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db import get_db
from middleware.auth import require_auth
from middleware.tenant import TenantContext, set_rls_context
from models import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    plugin_id: str = "langgraph"


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    plugin_id: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    result = await db.execute(
        select(Project).where(Project.org_id == tenant.org_id)
    )
    return result.scalars().all()


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        org_id=tenant.org_id,
        name=data.name,
        description=data.description,
        plugin_id=data.plugin_id,
        created_by=tenant.user_id,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project
```

**Step 2: Implement workflows route**

```python
# services/api/routes/workflows.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Any

from db import get_db
from middleware.auth import require_auth
from middleware.tenant import TenantContext, set_rls_context
from models import Workflow, Project

router = APIRouter(prefix="/api/projects/{project_id}/workflows", tags=["workflows"])


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    graph_config: dict[str, Any] = {}


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    graph_config: dict[str, Any] | None = None
    lock_version: int  # Required for optimistic locking


class WorkflowResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None
    graph_config: dict
    lock_version: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    project_id: int,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    result = await db.execute(
        select(Workflow).where(Workflow.project_id == project_id)
    )
    return result.scalars().all()


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    project_id: int,
    data: WorkflowCreate,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    # Verify project exists and belongs to tenant
    project = await db.get(Project, project_id)
    if not project or project.org_id != tenant.org_id:
        raise HTTPException(status_code=404, detail="Project not found")

    workflow = Workflow(
        project_id=project_id,
        name=data.name,
        description=data.description,
        graph_config=data.graph_config,
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    project_id: int,
    workflow_id: int,
    data: WorkflowUpdate,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Optimistic locking
    if workflow.lock_version != data.lock_version:
        raise HTTPException(status_code=409, detail="Conflict: workflow was modified")

    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    if data.graph_config is not None:
        workflow.graph_config = data.graph_config
    workflow.lock_version += 1

    await db.flush()
    await db.refresh(workflow)
    return workflow
```

**Step 3: Add routes to main.py**

```python
from routes.projects import router as projects_router
from routes.workflows import router as workflows_router
app.include_router(projects_router)
app.include_router(workflows_router)
```

**Step 4: Commit**

```bash
git add services/api/routes/ services/api/main.py
git commit -m "feat: project and workflow CRUD API routes with tenant isolation and optimistic locking"
```

---

### Task 19: Workflow Execution API (SSE Streaming)

**Files:**
- Create: `services/api/routes/execute.py`
- Modify: `services/api/main.py`

**Step 1: Implement SSE execution endpoint**

```python
# services/api/routes/execute.py
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db import get_db
from middleware.auth import require_auth
from middleware.tenant import TenantContext, set_rls_context
from models import Workflow, WorkflowExecution, ExecutionStatus
from models.vault import ApiKeyVault
from services.encryption import EncryptionService
from config import settings

# Plugin imports
import sys
sys.path.insert(0, "../../packages/core")
from orchestration.types import GraphConfig, ExecutionEvent
from routes.plugins import plugin_registry

router = APIRouter(tags=["execution"])


class ExecuteRequest(BaseModel):
    query: str
    inputs: dict = {}


@router.post("/api/projects/{project_id}/workflows/{workflow_id}/execute")
async def execute_workflow(
    project_id: int,
    workflow_id: int,
    data: ExecuteRequest,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)

    # Load workflow
    workflow = await db.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Load credentials (BYOK)
    from sqlalchemy import select
    vault_result = await db.execute(
        select(ApiKeyVault).where(ApiKeyVault.org_id == tenant.org_id)
    )
    vault_entries = vault_result.scalars().all()

    encryption = EncryptionService(settings.app_encryption_key)
    credentials = {}
    for entry in vault_entries:
        credentials[entry.provider] = encryption.decrypt(entry.encrypted_key)

    # Create execution record
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        triggered_by=tenant.user_id,
        status=ExecutionStatus.running,
    )
    db.add(execution)
    await db.flush()
    await db.refresh(execution)

    # Get the plugin for this project's orchestration framework
    project = await db.get(
        __import__('models').Project, project_id
    )
    plugin = plugin_registry.get(project.plugin_id if project else "langgraph")
    if not plugin:
        raise HTTPException(status_code=400, detail="Unknown plugin")

    graph_config = GraphConfig(
        id=str(workflow.id),
        plugin=project.plugin_id if project else "langgraph",
        nodes=workflow.graph_config.get("nodes", []),
        edges=workflow.graph_config.get("edges", []),
    )

    # Validate
    validation = plugin.validate_graph(graph_config)
    if not validation.valid:
        raise HTTPException(status_code=400, detail={"errors": validation.errors})

    # SSE streaming
    event_queue: asyncio.Queue[ExecutionEvent | None] = asyncio.Queue()

    def on_event(event: ExecutionEvent):
        event_queue.put_nowait(event)

    async def run_execution():
        try:
            result = await plugin.execute(
                graph_config,
                {"query": data.query, **data.inputs},
                credentials,
                on_event,
            )
            # Update execution record
            execution.status = ExecutionStatus.completed if result.success else ExecutionStatus.failed
            execution.results = {"output": result.output}
            execution.token_usage = result.token_usage
            execution.cost = result.cost
            execution.error_message = result.error
            await db.commit()
        except Exception as e:
            execution.status = ExecutionStatus.failed
            execution.error_message = str(e)
            await db.commit()
        finally:
            await event_queue.put(None)  # Signal end

    async def event_generator():
        task = asyncio.create_task(run_execution())
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps({'type': event.type.value, 'data': event.data, 'node_id': event.node_id})}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Execution-Id": str(execution.id),
        },
    )
```

**Step 2: Add to main.py**

```python
from routes.execute import router as execute_router
app.include_router(execute_router)
```

**Step 3: Commit**

```bash
git add services/api/routes/execute.py services/api/main.py
git commit -m "feat: workflow execution API with SSE streaming and BYOK credential injection"
```

---

### Task 19b: Tools System — Models & Factory

Port the tools system from the existing LangConfig codebase. Tools are fundamental to agent workflows — without them, agents can't do anything useful.

**Source files to reference:**
- `backend/core/tools/factory.py` — Tool creation factory
- `backend/core/tools/templates.py` — Pre-configured tool templates
- `backend/core/tools/execution_wrapper.py` — Constraint enforcement
- `backend/models/custom_tool.py` — Custom tool ORM model
- `backend/api/tools/routes.py` — Tool API routes
- `backend/tools/native_tools.py` — Native tool implementations

**Files:**
- Create: `services/api/models/custom_tool.py`
- Create: `services/api/models/tool_execution_log.py`
- Create: `packages/core/tools/__init__.py`
- Create: `packages/core/tools/factory.py`
- Create: `packages/core/tools/native_tools.py`
- Create: `packages/core/tools/execution_wrapper.py`
- Test: `packages/core/tests/test_tool_factory.py`

**Step 1: Create custom tool model**

```python
# services/api/models/custom_tool.py
import enum
from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class ToolType(str, enum.Enum):
    api = "api"
    notification = "notification"
    image_video = "image_video"
    database = "database"
    data_transform = "data_transform"
    mcp = "mcp"
    skill = "skill"


class CustomTool(Base, TimestampMixin):
    __tablename__ = "custom_tool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    tool_type: Mapped[ToolType] = mapped_column(SAEnum(ToolType), nullable=False)
    implementation_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    input_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_template_based: Mapped[bool] = mapped_column(Boolean, default=False)
    template_type: Mapped[str] = mapped_column(String(100), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
```

**Step 2: Create tool execution log model**

```python
# services/api/models/tool_execution_log.py
import enum
from sqlalchemy import String, Integer, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class ToolExecutionStatus(str, enum.Enum):
    success = "success"
    error = "error"
    timeout = "timeout"


class ToolExecutionLog(Base, TimestampMixin):
    __tablename__ = "tool_execution_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[str] = mapped_column(String(100), index=True)
    workflow_execution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workflow_execution.id", ondelete="SET NULL"), nullable=True
    )
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=True)
    output_result: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[ToolExecutionStatus] = mapped_column(SAEnum(ToolExecutionStatus))
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
```

**Step 3: Create native tools (no external dependencies)**

Port from `backend/tools/native_tools.py`. These are the essential tools that work without MCP servers:

```python
# packages/core/tools/native_tools.py
"""Native tool implementations — no MCP or external services required."""
from langchain_core.tools import StructuredTool


def create_web_search_tool() -> StructuredTool:
    """DuckDuckGo web search — free, no API key."""
    async def web_search(query: str, max_results: int = 5) -> str:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return "\n\n".join(
            f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results
        )

    return StructuredTool.from_function(
        coroutine=web_search,
        name="web_search",
        description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets.",
    )


def create_web_fetch_tool() -> StructuredTool:
    """Fetch and extract content from a URL."""
    async def web_fetch(url: str) -> str:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()
        # Simple HTML to text extraction
        from html.parser import HTMLParser
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
            def handle_data(self, data):
                self.text.append(data.strip())
        parser = TextExtractor()
        parser.feed(response.text)
        return " ".join(filter(None, parser.text))[:10000]

    return StructuredTool.from_function(
        coroutine=web_fetch,
        name="web_fetch",
        description="Fetch content from a URL and extract text.",
    )


def get_native_tools() -> dict[str, StructuredTool]:
    """Return all native tools keyed by name."""
    return {
        "web_search": create_web_search_tool(),
        "web_fetch": create_web_fetch_tool(),
    }
```

**Step 4: Create execution wrapper with constraints**

Port from `backend/core/tools/execution_wrapper.py`:

```python
# packages/core/tools/execution_wrapper.py
"""Wrap tools with timeout, retry, and execution constraints."""
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from langchain_core.tools import BaseTool


@dataclass
class ExecutionConstraint:
    max_duration_seconds: Optional[int] = 30
    max_retries: int = 0
    exclusive: bool = False


async def wrap_tool_with_constraints(
    tool: BaseTool,
    constraints: ExecutionConstraint,
) -> BaseTool:
    """Wrap a tool's execution with timeout and retry logic."""
    original_func = tool.coroutine or tool.func

    async def constrained_invoke(*args, **kwargs):
        last_error = None
        for attempt in range(constraints.max_retries + 1):
            try:
                if constraints.max_duration_seconds:
                    result = await asyncio.wait_for(
                        original_func(*args, **kwargs),
                        timeout=constraints.max_duration_seconds,
                    )
                else:
                    result = await original_func(*args, **kwargs)
                return result
            except asyncio.TimeoutError:
                last_error = f"Tool timed out after {constraints.max_duration_seconds}s"
            except Exception as e:
                last_error = str(e)
                if attempt < constraints.max_retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return f"Error: {last_error}"

    tool.coroutine = constrained_invoke
    return tool
```

**Step 5: Create tool factory**

```python
# packages/core/tools/factory.py
"""Create LangChain tools from configuration dicts."""
from langchain_core.tools import StructuredTool, BaseTool
from tools.native_tools import get_native_tools


class ToolFactory:
    """Create tools from config. Supports native, custom, MCP, and skill tools."""

    @staticmethod
    def create_tools(tool_configs: list[dict], credentials: dict = {}) -> list[BaseTool]:
        """Create a list of tools from configuration dicts.

        Each config has:
            {"name": "web_search", "type": "native"}
            {"name": "my_api", "type": "custom", "config": {...}}
            {"name": "server/tool", "type": "mcp", "server_id": "..."}
            {"name": "my_skill", "type": "skill", "skill_path": "..."}
        """
        tools = []
        native = get_native_tools()

        for config in tool_configs:
            tool_type = config.get("type", "native")
            name = config.get("name", "")

            if tool_type == "native" and name in native:
                tools.append(native[name])
            elif tool_type == "custom":
                tool = ToolFactory._create_custom_tool(config)
                if tool:
                    tools.append(tool)
            elif tool_type == "mcp":
                tool = ToolFactory._create_mcp_tool(config)
                if tool:
                    tools.append(tool)
            elif tool_type == "skill":
                tool = ToolFactory._create_skill_tool(config)
                if tool:
                    tools.append(tool)

        return tools

    @staticmethod
    def _create_custom_tool(config: dict) -> BaseTool | None:
        """Create a tool from a custom tool config (API, notification, etc.)."""
        impl = config.get("config", {})
        tool_subtype = impl.get("tool_type", "api")

        if tool_subtype == "api":
            return ToolFactory._create_api_tool(config, impl)
        # Add more subtypes as needed
        return None

    @staticmethod
    def _create_api_tool(config: dict, impl: dict) -> BaseTool:
        """Create an HTTP API tool."""
        import httpx

        async def call_api(**kwargs) -> str:
            url = impl.get("url", "").format(**kwargs)
            method = impl.get("method", "GET").upper()
            headers = impl.get("headers", {})
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(method, url, headers=headers, json=kwargs)
                return response.text[:5000]

        return StructuredTool.from_function(
            coroutine=call_api,
            name=config.get("name", "api_tool"),
            description=config.get("description", "Call an external API"),
        )

    @staticmethod
    def _create_mcp_tool(config: dict) -> BaseTool | None:
        """Create a tool backed by an MCP server. Delegates to MCPManager."""
        # MCP tools are created by the MCP manager at runtime
        # This is a placeholder — actual implementation connects to MCP subprocess
        return None

    @staticmethod
    def _create_skill_tool(config: dict) -> BaseTool | None:
        """Create a tool from a skill.md file."""
        skill_path = config.get("skill_path", "")
        if not skill_path:
            return None

        async def run_skill(input_text: str) -> str:
            # Read the skill.md file and use it as a prompt/template
            try:
                with open(skill_path, "r") as f:
                    skill_content = f.read()
                return f"[Skill loaded from {skill_path}]\n{skill_content}\n\nInput: {input_text}"
            except Exception as e:
                return f"Error loading skill: {e}"

        return StructuredTool.from_function(
            coroutine=run_skill,
            name=config.get("name", "skill_tool"),
            description=config.get("description", f"Run skill from {skill_path}"),
        )
```

**Step 6: Write tests**

```python
# packages/core/tests/test_tool_factory.py
import pytest
from tools.factory import ToolFactory
from tools.native_tools import get_native_tools


def test_native_tools_exist():
    tools = get_native_tools()
    assert "web_search" in tools
    assert "web_fetch" in tools


def test_factory_creates_native_tools():
    configs = [
        {"name": "web_search", "type": "native"},
        {"name": "web_fetch", "type": "native"},
    ]
    tools = ToolFactory.create_tools(configs)
    assert len(tools) == 2
    names = [t.name for t in tools]
    assert "web_search" in names
    assert "web_fetch" in names


def test_factory_skips_unknown_native():
    configs = [{"name": "nonexistent", "type": "native"}]
    tools = ToolFactory.create_tools(configs)
    assert len(tools) == 0
```

**Step 7: Run tests and commit**

```bash
cd packages/core
pytest tests/test_tool_factory.py -v
# Expected: PASS
git add packages/core/tools/ services/api/models/custom_tool.py services/api/models/tool_execution_log.py
git commit -m "feat: tools system with native tools, factory, execution constraints, and custom tool models"
```

---

### Task 19c: MCP Server Integration

Port MCP (Model Context Protocol) support so agents can use external tool servers.

**Source files to reference:**
- `backend/services/mcp_manager.py` — MCP server lifecycle management
- `backend/schemas/mcp_tools.py` — MCP tool schemas

**Files:**
- Create: `packages/core/tools/mcp_manager.py`
- Create: `packages/core/tools/mcp_types.py`
- Create: `services/api/routes/mcp.py`
- Test: `packages/core/tests/test_mcp_manager.py`

**Step 1: Create MCP types**

```python
# packages/core/tools/mcp_types.py
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class MCPServerStatus(str, Enum):
    stopped = "stopped"
    starting = "starting"
    running = "running"
    error = "error"


@dataclass
class MCPServerConfig:
    server_id: str
    name: str
    command: list[str]  # e.g. ["npx", "-y", "@modelcontextprotocol/server-filesystem"]
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""


@dataclass
class MCPTool:
    server_id: str
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPToolResult:
    success: bool
    result: Any = None
    error: Optional[str] = None
```

**Step 2: Create MCP manager**

```python
# packages/core/tools/mcp_manager.py
"""Manages MCP server lifecycles and tool invocations.
Servers are started lazily on first tool call."""
import asyncio
import json
import subprocess
from typing import Optional

from tools.mcp_types import MCPServerConfig, MCPServerStatus, MCPTool, MCPToolResult


class MCPManager:
    """Singleton manager for MCP server processes."""

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._tool_cache: dict[str, list[MCPTool]] = {}
        self._status: dict[str, MCPServerStatus] = {}

    def register_server(self, config: MCPServerConfig):
        """Register an MCP server configuration."""
        self._servers[config.server_id] = config
        self._status[config.server_id] = MCPServerStatus.stopped

    def list_servers(self) -> list[dict]:
        """List all registered servers with status."""
        return [
            {
                "server_id": sid,
                "name": self._servers[sid].name,
                "status": self._status.get(sid, MCPServerStatus.stopped).value,
                "enabled": self._servers[sid].enabled,
            }
            for sid in self._servers
        ]

    async def get_tools(self, server_id: str) -> list[MCPTool]:
        """Get available tools from an MCP server (cached)."""
        if server_id in self._tool_cache:
            return self._tool_cache[server_id]
        # TODO: Start server and discover tools via JSON-RPC
        return []

    async def invoke_tool(
        self, server_id: str, tool_name: str, arguments: dict
    ) -> MCPToolResult:
        """Invoke a tool on an MCP server."""
        if server_id not in self._servers:
            return MCPToolResult(success=False, error=f"Unknown server: {server_id}")
        # TODO: JSON-RPC call to the MCP server process
        return MCPToolResult(success=False, error="MCP invocation not yet implemented")

    async def shutdown(self):
        """Stop all running MCP server processes."""
        for sid, proc in self._processes.items():
            if proc.poll() is None:
                proc.terminate()
        self._processes.clear()


# Default MCP server configurations (can be overridden per-org)
DEFAULT_MCP_SERVERS = [
    MCPServerConfig(
        server_id="filesystem",
        name="Filesystem",
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
        description="Local file operations",
    ),
    MCPServerConfig(
        server_id="web",
        name="Web Search & Fetch",
        command=["npx", "-y", "@anthropic/mcp-server-web"],
        description="Web search and URL fetching",
    ),
    MCPServerConfig(
        server_id="github",
        name="GitHub",
        command=["npx", "-y", "@modelcontextprotocol/server-github"],
        description="GitHub repository operations",
    ),
    MCPServerConfig(
        server_id="memory",
        name="Memory",
        command=["npx", "-y", "@modelcontextprotocol/server-memory"],
        description="Persistent key-value memory",
    ),
]
```

**Step 3: Create MCP API route**

```python
# services/api/routes/mcp.py
from fastapi import APIRouter, Depends

from middleware.auth import require_auth
from middleware.tenant import TenantContext

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("/servers")
async def list_mcp_servers(tenant: TenantContext = Depends(require_auth)):
    """List available MCP servers for the current org."""
    # TODO: Load org-specific MCP server configs
    from tools.mcp_manager import DEFAULT_MCP_SERVERS
    return [
        {"server_id": s.server_id, "name": s.name, "description": s.description, "enabled": s.enabled}
        for s in DEFAULT_MCP_SERVERS
    ]


@router.get("/servers/{server_id}/tools")
async def list_server_tools(server_id: str, tenant: TenantContext = Depends(require_auth)):
    """List tools available from an MCP server."""
    # TODO: Connect to MCP manager and discover tools
    return []
```

**Step 4: Write test and commit**

```python
# packages/core/tests/test_mcp_manager.py
import pytest
from tools.mcp_manager import MCPManager, DEFAULT_MCP_SERVERS
from tools.mcp_types import MCPServerConfig, MCPServerStatus


def test_register_server():
    mgr = MCPManager()
    config = MCPServerConfig(server_id="test", name="Test", command=["echo"])
    mgr.register_server(config)
    servers = mgr.list_servers()
    assert len(servers) == 1
    assert servers[0]["server_id"] == "test"


def test_default_servers_exist():
    assert len(DEFAULT_MCP_SERVERS) >= 4
    ids = [s.server_id for s in DEFAULT_MCP_SERVERS]
    assert "filesystem" in ids
    assert "web" in ids
```

```bash
pytest tests/test_mcp_manager.py -v
# Expected: PASS
git add packages/core/tools/mcp_* services/api/routes/mcp.py
git commit -m "feat: MCP server manager with lazy loading, default servers, and API route"
```

---

### Task 19d: Skill.md File Support

Enable loading skills from `.md` files — markdown-defined tool/prompt templates that agents can use. This mirrors the skill.md pattern used in Claude Code and allows users to create reusable agent capabilities without writing Python.

**Files:**
- Create: `packages/core/tools/skill_loader.py`
- Create: `services/api/routes/skills.py`
- Create: `services/api/models/skill.py`
- Test: `packages/core/tests/test_skill_loader.py`

**Step 1: Create skill model**

```python
# services/api/models/skill.py
from sqlalchemy import String, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db import Base
from models.base import TimestampMixin


class Skill(Base, TimestampMixin):
    __tablename__ = "skill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(
        String, ForeignKey("organization.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # The markdown content
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # Shared with community
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("user.id"), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", type_=JSONB, nullable=True)
```

**Step 2: Create skill loader**

```python
# packages/core/tools/skill_loader.py
"""Load skills from .md files and convert them to LangChain tools."""
import re
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.tools import StructuredTool


@dataclass
class SkillDefinition:
    name: str
    description: str
    content: str  # Full markdown content
    arguments: list[dict] = field(default_factory=list)  # Parsed from frontmatter
    tags: list[str] = field(default_factory=list)


def parse_skill_md(content: str) -> SkillDefinition:
    """Parse a skill.md file into a SkillDefinition.

    Expected format:
    ```
    # Skill Name

    Description of what the skill does.

    ## Arguments
    - `input_text` (string, required): The input to process
    - `context` (string, optional): Additional context

    ## Instructions
    [The actual skill instructions/prompt template]
    ```
    """
    lines = content.strip().split("\n")

    # Extract name from first heading
    name = "unnamed_skill"
    description = ""
    arguments = []
    instructions = ""

    section = "header"
    for line in lines:
        if line.startswith("# ") and section == "header":
            name = line[2:].strip()
            section = "description"
        elif line.startswith("## Arguments"):
            section = "arguments"
        elif line.startswith("## Instructions") or line.startswith("## Prompt"):
            section = "instructions"
        elif section == "description" and line.strip():
            description += line.strip() + " "
        elif section == "arguments" and line.strip().startswith("- "):
            # Parse argument: - `name` (type, required): description
            match = re.match(r"- `(\w+)`\s*\((\w+)(?:,\s*(required|optional))?\):\s*(.*)", line.strip())
            if match:
                arguments.append({
                    "name": match.group(1),
                    "type": match.group(2),
                    "required": match.group(3) != "optional",
                    "description": match.group(4),
                })
        elif section == "instructions":
            instructions += line + "\n"

    return SkillDefinition(
        name=name.lower().replace(" ", "_"),
        description=description.strip(),
        content=instructions.strip() or content,
        arguments=arguments,
    )


def skill_to_tool(skill: SkillDefinition) -> StructuredTool:
    """Convert a SkillDefinition into a LangChain StructuredTool.

    The tool returns the skill content as a prompt template,
    with arguments interpolated.
    """
    async def run_skill(**kwargs) -> str:
        result = skill.content
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    return StructuredTool.from_function(
        coroutine=run_skill,
        name=skill.name,
        description=skill.description or f"Run the {skill.name} skill",
    )
```

**Step 3: Create skills API route**

```python
# services/api/routes/skills.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from db import get_db
from middleware.auth import require_auth
from middleware.tenant import TenantContext, set_rls_context
from models.skill import Skill

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    content: str  # Markdown content
    project_id: int | None = None
    is_public: bool = False


class SkillResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    content: str
    is_public: bool
    usage_count: int

    class Config:
        from_attributes = True


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    project_id: int | None = None,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    query = select(Skill).where(Skill.org_id == tenant.org_id)
    if project_id:
        query = query.where(Skill.project_id == project_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=SkillResponse, status_code=201)
async def create_skill(
    data: SkillCreate,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    skill = Skill(
        org_id=tenant.org_id,
        project_id=data.project_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        content=data.content,
        is_public=data.is_public,
        created_by=tenant.user_id,
    )
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return skill


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: int,
    tenant: TenantContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await set_rls_context(db, tenant.org_id)
    skill = await db.get(Skill, skill_id)
    if not skill or skill.org_id != tenant.org_id:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill
```

**Step 4: Write tests**

```python
# packages/core/tests/test_skill_loader.py
import pytest
from tools.skill_loader import parse_skill_md, skill_to_tool


def test_parse_skill_md():
    content = """# Research Assistant

Helps research a topic and summarize findings.

## Arguments
- `topic` (string, required): The topic to research
- `depth` (string, optional): How deep to research

## Instructions
Research the following topic thoroughly: {topic}
Depth: {depth}
Provide a structured summary with sources.
"""
    skill = parse_skill_md(content)
    assert skill.name == "research_assistant"
    assert "research" in skill.description.lower()
    assert len(skill.arguments) == 2
    assert skill.arguments[0]["name"] == "topic"
    assert skill.arguments[0]["required"] is True
    assert skill.arguments[1]["name"] == "depth"
    assert skill.arguments[1]["required"] is False


def test_skill_to_tool():
    content = """# Summarizer

Summarize text.

## Instructions
Summarize: {input_text}
"""
    skill = parse_skill_md(content)
    tool = skill_to_tool(skill)
    assert tool.name == "summarizer"


@pytest.mark.asyncio
async def test_skill_tool_interpolation():
    content = """# Greeter

Greets someone.

## Instructions
Hello, {name}! Welcome to {place}.
"""
    skill = parse_skill_md(content)
    tool = skill_to_tool(skill)
    result = await tool.coroutine(name="Alice", place="LangConfig")
    assert "Alice" in result
    assert "LangConfig" in result
```

**Step 5: Run tests and commit**

```bash
pytest tests/test_skill_loader.py -v
# Expected: PASS
git add packages/core/tools/skill_loader.py services/api/routes/skills.py services/api/models/skill.py
git commit -m "feat: skill.md loader with markdown parsing, tool conversion, and CRUD API"
```

---

### Task 19e: CLI & Developer Tools for Agents

Agents need real developer tools to be genuinely useful — not just web search. This task adds shell execution, git operations, test runners, linters, and package management as agent-callable tools. These are what make LangConfig agents competitive with Claude Code, Cursor, and Devin.

**Source files to reference:**
- `backend/tools/native_tools.py` — file system tools (read, write, edit, ls, glob, grep)
- `backend/services/mcp_manager.py` — MCP servers for git, test runner, static analyzer
- `backend/schemas/mcp_tools.py` — test runner & static analyzer MCP configs

**Files:**
- Create: `packages/core/tools/cli_tools.py`
- Create: `packages/core/tools/git_tools.py`
- Create: `packages/core/tools/dev_tools.py`
- Modify: `packages/core/tools/native_tools.py`
- Modify: `packages/core/tools/factory.py`
- Test: `packages/core/tests/test_cli_tools.py`

**Step 1: Create sandboxed shell execution tool**

This is the most powerful and most dangerous tool. It must be sandboxed.

```python
# packages/core/tools/cli_tools.py
"""CLI tools for agent use — sandboxed shell execution."""
import asyncio
import os
from dataclasses import dataclass
from typing import Optional

from langchain_core.tools import StructuredTool


@dataclass
class ShellSandbox:
    """Sandbox configuration for shell execution."""
    allowed_commands: set[str] = None  # None = allow all, set = whitelist
    blocked_patterns: set[str] = None  # Patterns to block (rm -rf, etc.)
    working_directory: Optional[str] = None
    timeout_seconds: int = 30
    max_output_chars: int = 10000

    def __post_init__(self):
        if self.blocked_patterns is None:
            self.blocked_patterns = {
                "rm -rf /", "rm -rf ~", ":(){ :|:& };:",  # Fork bomb
                "mkfs", "dd if=", "> /dev/sd",            # Destructive
                "chmod 777 /", "chown root",               # Privilege escalation
                "curl | sh", "wget | sh",                  # Pipe to shell
                "sudo rm", "sudo mkfs",                    # Sudo destructive
            }

    def validate_command(self, command: str) -> tuple[bool, str]:
        """Check if a command is safe to run."""
        cmd_lower = command.lower().strip()
        for pattern in self.blocked_patterns:
            if pattern.lower() in cmd_lower:
                return False, f"Blocked: command matches dangerous pattern '{pattern}'"
        if self.allowed_commands:
            base_cmd = cmd_lower.split()[0] if cmd_lower else ""
            if base_cmd not in self.allowed_commands:
                return False, f"Blocked: '{base_cmd}' not in allowed commands"
        return True, ""


# Default sandbox for agents — blocks destructive patterns but allows common dev tools
DEFAULT_SANDBOX = ShellSandbox(
    timeout_seconds=60,
    max_output_chars=20000,
)

# Restricted sandbox — whitelist of safe commands only
RESTRICTED_SANDBOX = ShellSandbox(
    allowed_commands={
        "ls", "cat", "head", "tail", "grep", "find", "wc",
        "echo", "pwd", "whoami", "date", "env",
        "python", "python3", "pip", "pip3",
        "node", "npm", "npx",
        "git", "gh",
        "pytest", "jest", "vitest",
        "pylint", "mypy", "eslint", "tsc",
        "curl", "wget",
        "docker", "docker-compose",
    },
    timeout_seconds=30,
    max_output_chars=10000,
)


def create_shell_tool(sandbox: ShellSandbox = DEFAULT_SANDBOX) -> StructuredTool:
    """Create a sandboxed shell execution tool for agents."""

    async def run_shell(command: str, working_directory: str = "") -> str:
        """Execute a shell command and return stdout + stderr."""
        safe, reason = sandbox.validate_command(command)
        if not safe:
            return f"Error: {reason}"

        cwd = working_directory or sandbox.working_directory or os.getcwd()

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=sandbox.timeout_seconds,
            )
            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                output += f"\n[exit code: {proc.returncode}]"
            return output[:sandbox.max_output_chars]
        except asyncio.TimeoutError:
            return f"Error: Command timed out after {sandbox.timeout_seconds}s"
        except Exception as e:
            return f"Error: {e}"

    return StructuredTool.from_function(
        coroutine=run_shell,
        name="shell",
        description=(
            "Execute a shell command. Use for: running scripts, installing packages, "
            "checking system state, running builds, etc. Returns stdout and stderr."
        ),
    )
```

**Step 2: Create git tools**

```python
# packages/core/tools/git_tools.py
"""Git tools for agents — common git operations without raw shell."""
from langchain_core.tools import StructuredTool
import asyncio


async def _run_git(args: list[str], cwd: str = ".") -> str:
    """Run a git command and return output."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    output = stdout.decode("utf-8", errors="replace")
    if stderr:
        output += "\n" + stderr.decode("utf-8", errors="replace")
    return output.strip()[:10000]


def create_git_tools() -> list[StructuredTool]:
    """Create a suite of git tools for agents."""

    async def git_status(repo_path: str = ".") -> str:
        """Show working tree status (modified, staged, untracked files)."""
        return await _run_git(["status", "--short"], cwd=repo_path)

    async def git_diff(repo_path: str = ".", staged: bool = False) -> str:
        """Show changes in working tree or staged changes."""
        args = ["diff", "--stat"]
        if staged:
            args.append("--cached")
        return await _run_git(args, cwd=repo_path)

    async def git_log(repo_path: str = ".", count: int = 10) -> str:
        """Show recent commit history."""
        return await _run_git(
            ["log", f"-{count}", "--oneline", "--graph"], cwd=repo_path
        )

    async def git_add(files: str, repo_path: str = ".") -> str:
        """Stage files for commit. Use '.' for all changes."""
        return await _run_git(["add"] + files.split(), cwd=repo_path)

    async def git_commit(message: str, repo_path: str = ".") -> str:
        """Create a git commit with the given message."""
        return await _run_git(["commit", "-m", message], cwd=repo_path)

    async def git_branch(repo_path: str = ".") -> str:
        """List branches and show current branch."""
        return await _run_git(["branch", "-v"], cwd=repo_path)

    async def git_checkout(branch: str, create: bool = False, repo_path: str = ".") -> str:
        """Switch branches or create a new branch."""
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        return await _run_git(args, cwd=repo_path)

    async def git_stash(action: str = "list", repo_path: str = ".") -> str:
        """Manage stash (list, push, pop, apply)."""
        return await _run_git(["stash", action], cwd=repo_path)

    return [
        StructuredTool.from_function(coroutine=git_status, name="git_status",
            description="Show working tree status — modified, staged, and untracked files"),
        StructuredTool.from_function(coroutine=git_diff, name="git_diff",
            description="Show file changes (unstaged by default, use staged=True for staged)"),
        StructuredTool.from_function(coroutine=git_log, name="git_log",
            description="Show recent commit history as a graph"),
        StructuredTool.from_function(coroutine=git_add, name="git_add",
            description="Stage files for commit. Pass file paths or '.' for all"),
        StructuredTool.from_function(coroutine=git_commit, name="git_commit",
            description="Create a git commit with the given message"),
        StructuredTool.from_function(coroutine=git_branch, name="git_branch",
            description="List all branches with current branch highlighted"),
        StructuredTool.from_function(coroutine=git_checkout, name="git_checkout",
            description="Switch to a branch, or create a new one with create=True"),
        StructuredTool.from_function(coroutine=git_stash, name="git_stash",
            description="Manage git stash — list, push, pop, or apply"),
    ]
```

**Step 3: Create dev/utility tools (test runners, linters, package managers)**

```python
# packages/core/tools/dev_tools.py
"""Developer utility tools — test runners, linters, package managers."""
from langchain_core.tools import StructuredTool
import asyncio
import os


async def _run_cmd(cmd: list[str], cwd: str = ".", timeout: int = 120) -> str:
    """Run a command and return output."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    output = stdout.decode("utf-8", errors="replace")
    if stderr:
        output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")
    output += f"\n[exit code: {proc.returncode}]"
    return output.strip()[:20000]


def create_test_runner_tools() -> list[StructuredTool]:
    """Tools for running tests (pytest, jest, vitest)."""

    async def run_pytest(
        path: str = ".", args: str = "-v", working_directory: str = "."
    ) -> str:
        """Run Python tests with pytest. Returns pass/fail summary and error details."""
        cmd = ["python", "-m", "pytest", path] + args.split()
        return await _run_cmd(cmd, cwd=working_directory, timeout=120)

    async def run_jest(
        path: str = ".", args: str = "", working_directory: str = "."
    ) -> str:
        """Run JavaScript/TypeScript tests with Jest."""
        cmd = ["npx", "jest", path] + (args.split() if args else [])
        return await _run_cmd(cmd, cwd=working_directory, timeout=120)

    async def run_vitest(
        path: str = ".", args: str = "--run", working_directory: str = "."
    ) -> str:
        """Run Vite-based tests with Vitest."""
        cmd = ["npx", "vitest", path] + args.split()
        return await _run_cmd(cmd, cwd=working_directory, timeout=120)

    async def run_tests_auto(path: str = ".", working_directory: str = ".") -> str:
        """Auto-detect test framework and run tests.
        Checks for pytest.ini/conftest.py (Python) or jest.config/vitest.config (JS)."""
        cwd = working_directory
        if os.path.exists(os.path.join(cwd, "conftest.py")) or \
           os.path.exists(os.path.join(cwd, "pytest.ini")):
            return await run_pytest(path, "-v", cwd)
        elif os.path.exists(os.path.join(cwd, "vitest.config.ts")) or \
             os.path.exists(os.path.join(cwd, "vitest.config.js")):
            return await run_vitest(path, "--run", cwd)
        elif os.path.exists(os.path.join(cwd, "jest.config.js")) or \
             os.path.exists(os.path.join(cwd, "jest.config.ts")):
            return await run_jest(path, "", cwd)
        elif os.path.exists(os.path.join(cwd, "package.json")):
            return await _run_cmd(["npm", "test"], cwd=cwd)
        return "Could not auto-detect test framework. Use run_pytest, run_jest, or run_vitest directly."

    return [
        StructuredTool.from_function(coroutine=run_pytest, name="run_pytest",
            description="Run Python tests with pytest. Returns results with pass/fail counts"),
        StructuredTool.from_function(coroutine=run_jest, name="run_jest",
            description="Run JavaScript/TypeScript tests with Jest"),
        StructuredTool.from_function(coroutine=run_vitest, name="run_vitest",
            description="Run Vite-based tests with Vitest"),
        StructuredTool.from_function(coroutine=run_tests_auto, name="run_tests",
            description="Auto-detect test framework (pytest/jest/vitest) and run tests"),
    ]


def create_linter_tools() -> list[StructuredTool]:
    """Static analysis and linting tools."""

    async def run_pylint(path: str = ".", working_directory: str = ".") -> str:
        """Lint Python code with pylint. Returns issues with severity levels."""
        return await _run_cmd(["python", "-m", "pylint", path, "--output-format=text"], cwd=working_directory)

    async def run_mypy(path: str = ".", working_directory: str = ".") -> str:
        """Type check Python code with mypy."""
        return await _run_cmd(["python", "-m", "mypy", path], cwd=working_directory)

    async def run_eslint(path: str = ".", working_directory: str = ".") -> str:
        """Lint JavaScript/TypeScript with ESLint."""
        return await _run_cmd(["npx", "eslint", path], cwd=working_directory)

    async def run_tsc(working_directory: str = ".") -> str:
        """TypeScript type checking (no emit)."""
        return await _run_cmd(["npx", "tsc", "--noEmit"], cwd=working_directory)

    return [
        StructuredTool.from_function(coroutine=run_pylint, name="run_pylint",
            description="Lint Python code with pylint — returns issues and quality score"),
        StructuredTool.from_function(coroutine=run_mypy, name="run_mypy",
            description="Type check Python code with mypy"),
        StructuredTool.from_function(coroutine=run_eslint, name="run_eslint",
            description="Lint JavaScript/TypeScript with ESLint"),
        StructuredTool.from_function(coroutine=run_tsc, name="run_tsc",
            description="TypeScript type checking — runs tsc --noEmit"),
    ]


def create_package_manager_tools() -> list[StructuredTool]:
    """Package management tools for Python and JavaScript."""

    async def pip_install(packages: str, working_directory: str = ".") -> str:
        """Install Python packages with pip."""
        return await _run_cmd(
            ["python", "-m", "pip", "install"] + packages.split(),
            cwd=working_directory,
        )

    async def pip_list(working_directory: str = ".") -> str:
        """List installed Python packages."""
        return await _run_cmd(["python", "-m", "pip", "list"], cwd=working_directory)

    async def npm_install(packages: str = "", working_directory: str = ".") -> str:
        """Install Node.js packages with npm."""
        cmd = ["npm", "install"] + (packages.split() if packages else [])
        return await _run_cmd(cmd, cwd=working_directory)

    async def npm_run(script: str, working_directory: str = ".") -> str:
        """Run an npm script (e.g., build, test, lint)."""
        return await _run_cmd(["npm", "run", script], cwd=working_directory)

    return [
        StructuredTool.from_function(coroutine=pip_install, name="pip_install",
            description="Install Python packages with pip"),
        StructuredTool.from_function(coroutine=pip_list, name="pip_list",
            description="List installed Python packages"),
        StructuredTool.from_function(coroutine=npm_install, name="npm_install",
            description="Install Node.js packages with npm"),
        StructuredTool.from_function(coroutine=npm_run, name="npm_run",
            description="Run an npm script (build, test, lint, dev, etc.)"),
    ]


def create_docker_tools() -> list[StructuredTool]:
    """Docker tools for container management."""

    async def docker_ps(all: bool = False) -> str:
        """List running containers (or all with all=True)."""
        args = ["docker", "ps"]
        if all:
            args.append("-a")
        return await _run_cmd(args)

    async def docker_compose_up(
        services: str = "", detach: bool = True, working_directory: str = "."
    ) -> str:
        """Start docker-compose services."""
        cmd = ["docker-compose", "up"]
        if detach:
            cmd.append("-d")
        if services:
            cmd.extend(services.split())
        return await _run_cmd(cmd, cwd=working_directory)

    async def docker_logs(container: str, tail: int = 50) -> str:
        """Show container logs."""
        return await _run_cmd(["docker", "logs", "--tail", str(tail), container])

    return [
        StructuredTool.from_function(coroutine=docker_ps, name="docker_ps",
            description="List Docker containers (running or all)"),
        StructuredTool.from_function(coroutine=docker_compose_up, name="docker_compose_up",
            description="Start docker-compose services"),
        StructuredTool.from_function(coroutine=docker_logs, name="docker_logs",
            description="Show logs from a Docker container"),
    ]
```

**Step 4: Update native_tools.py to include file system tools (port from existing)**

Add to `packages/core/tools/native_tools.py` — these complete the file system toolkit:

```python
# Add to native_tools.py

def create_file_read_tool() -> StructuredTool:
    """Read file contents with line numbers."""
    async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset:offset + limit]
            return "".join(
                f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected)
            )
        except Exception as e:
            return f"Error: {e}"

    return StructuredTool.from_function(
        coroutine=read_file, name="read_file",
        description="Read a file's contents with line numbers. Supports offset and limit.",
    )


def create_file_write_tool() -> StructuredTool:
    """Write content to a file."""
    async def write_file(file_path: str, content: str) -> str:
        try:
            import os
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written {len(content)} chars to {file_path}"
        except Exception as e:
            return f"Error: {e}"

    return StructuredTool.from_function(
        coroutine=write_file, name="write_file",
        description="Write content to a file. Creates parent directories if needed.",
    )


def create_file_edit_tool() -> StructuredTool:
    """Find and replace text in a file."""
    async def edit_file(file_path: str, old_string: str, new_string: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_string not in content:
                return f"Error: old_string not found in {file_path}"
            count = content.count(old_string)
            if count > 1:
                return f"Error: old_string found {count} times — must be unique. Add more context."
            content = content.replace(old_string, new_string, 1)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Replaced 1 occurrence in {file_path}"
        except Exception as e:
            return f"Error: {e}"

    return StructuredTool.from_function(
        coroutine=edit_file, name="edit_file",
        description="Find and replace a unique string in a file. old_string must appear exactly once.",
    )


def create_ls_tool() -> StructuredTool:
    """List directory contents."""
    async def ls(directory_path: str = ".") -> str:
        import os
        try:
            entries = []
            for name in sorted(os.listdir(directory_path)):
                full = os.path.join(directory_path, name)
                if os.path.isdir(full):
                    entries.append(f"  {name}/")
                else:
                    size = os.path.getsize(full)
                    entries.append(f"  {name} ({size} bytes)")
            return "\n".join(entries) or "(empty directory)"
        except Exception as e:
            return f"Error: {e}"

    return StructuredTool.from_function(
        coroutine=ls, name="ls",
        description="List files and directories in a path.",
    )


def create_glob_tool() -> StructuredTool:
    """Find files matching a glob pattern."""
    async def glob_search(pattern: str, path: str = ".") -> str:
        import glob as g
        import os
        matches = sorted(g.glob(os.path.join(path, pattern), recursive=True))
        return "\n".join(matches[:100]) or "No matches found"

    return StructuredTool.from_function(
        coroutine=glob_search, name="glob",
        description="Find files matching a glob pattern (e.g., '**/*.py', 'src/**/*.tsx').",
    )


def create_grep_tool() -> StructuredTool:
    """Search file contents for a pattern."""
    async def grep_search(pattern: str, path: str = ".", file_pattern: str = "") -> str:
        import re, os, glob as g
        results = []
        if os.path.isfile(path):
            files = [path]
        elif file_pattern:
            files = g.glob(os.path.join(path, file_pattern), recursive=True)
        else:
            files = g.glob(os.path.join(path, "**", "*"), recursive=True)

        regex = re.compile(pattern)
        for fp in files[:500]:
            if not os.path.isfile(fp):
                continue
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{fp}:{i}: {line.rstrip()}")
                            if len(results) >= 50:
                                return "\n".join(results) + "\n... (truncated at 50 matches)"
            except Exception:
                continue
        return "\n".join(results) or "No matches found"

    return StructuredTool.from_function(
        coroutine=grep_search, name="grep",
        description="Search file contents for a regex pattern. Returns matching lines with file:line prefix.",
    )


def get_native_tools() -> dict[str, StructuredTool]:
    """Return all native tools keyed by name."""
    return {
        "web_search": create_web_search_tool(),
        "web_fetch": create_web_fetch_tool(),
        "read_file": create_file_read_tool(),
        "write_file": create_file_write_tool(),
        "edit_file": create_file_edit_tool(),
        "ls": create_ls_tool(),
        "glob": create_glob_tool(),
        "grep": create_grep_tool(),
    }
```

**Step 5: Update ToolFactory to include all tool categories**

Update `packages/core/tools/factory.py` to support tool category loading:

```python
# Add to ToolFactory class:

TOOL_CATEGORIES = {
    "shell": lambda: [create_shell_tool()],
    "git": lambda: create_git_tools(),
    "test": lambda: create_test_runner_tools(),
    "lint": lambda: create_linter_tools(),
    "package": lambda: create_package_manager_tools(),
    "docker": lambda: create_docker_tools(),
}

@staticmethod
def create_tools(tool_configs: list[dict], credentials: dict = {}) -> list[BaseTool]:
    tools = []
    native = get_native_tools()

    for config in tool_configs:
        tool_type = config.get("type", "native")
        name = config.get("name", "")

        if tool_type == "native" and name in native:
            tools.append(native[name])
        elif tool_type == "category" and name in ToolFactory.TOOL_CATEGORIES:
            tools.extend(ToolFactory.TOOL_CATEGORIES[name]())
        elif tool_type == "custom":
            # ... existing custom tool logic
        elif tool_type == "mcp":
            # ... existing MCP logic
        elif tool_type == "skill":
            # ... existing skill logic

    return tools
```

Now a workflow node can specify tools like:
```json
{
  "tools": [
    {"name": "web_search", "type": "native"},
    {"name": "read_file", "type": "native"},
    {"name": "git", "type": "category"},
    {"name": "test", "type": "category"},
    {"name": "shell", "type": "category"}
  ]
}
```

**Step 6: Write tests**

```python
# packages/core/tests/test_cli_tools.py
import pytest
from tools.cli_tools import ShellSandbox, RESTRICTED_SANDBOX, DEFAULT_SANDBOX


def test_default_sandbox_blocks_dangerous():
    safe, reason = DEFAULT_SANDBOX.validate_command("rm -rf /")
    assert safe is False
    assert "dangerous" in reason.lower() or "blocked" in reason.lower()


def test_default_sandbox_allows_normal():
    safe, _ = DEFAULT_SANDBOX.validate_command("ls -la")
    assert safe is True


def test_restricted_sandbox_whitelist():
    safe, _ = RESTRICTED_SANDBOX.validate_command("python -m pytest")
    assert safe is True


def test_restricted_sandbox_blocks_unlisted():
    safe, _ = RESTRICTED_SANDBOX.validate_command("nc -lvp 4444")
    assert safe is False


def test_fork_bomb_blocked():
    safe, _ = DEFAULT_SANDBOX.validate_command(":(){ :|:& };:")
    assert safe is False
```

```python
# packages/core/tests/test_git_tools.py
import pytest
from tools.git_tools import create_git_tools


def test_git_tools_created():
    tools = create_git_tools()
    names = [t.name for t in tools]
    assert "git_status" in names
    assert "git_diff" in names
    assert "git_log" in names
    assert "git_add" in names
    assert "git_commit" in names
    assert "git_branch" in names
    assert "git_checkout" in names
    assert len(tools) >= 7
```

```python
# packages/core/tests/test_dev_tools.py
import pytest
from tools.dev_tools import (
    create_test_runner_tools,
    create_linter_tools,
    create_package_manager_tools,
    create_docker_tools,
)


def test_test_runner_tools():
    tools = create_test_runner_tools()
    names = [t.name for t in tools]
    assert "run_pytest" in names
    assert "run_jest" in names
    assert "run_tests" in names


def test_linter_tools():
    tools = create_linter_tools()
    names = [t.name for t in tools]
    assert "run_pylint" in names
    assert "run_mypy" in names
    assert "run_eslint" in names
    assert "run_tsc" in names


def test_package_manager_tools():
    tools = create_package_manager_tools()
    names = [t.name for t in tools]
    assert "pip_install" in names
    assert "npm_install" in names
    assert "npm_run" in names


def test_docker_tools():
    tools = create_docker_tools()
    names = [t.name for t in tools]
    assert "docker_ps" in names
    assert "docker_compose_up" in names
```

**Step 7: Run tests and commit**

```bash
cd packages/core
pytest tests/test_cli_tools.py tests/test_git_tools.py tests/test_dev_tools.py -v
# Expected: PASS
git add packages/core/tools/ packages/core/tests/
git commit -m "feat: CLI/dev tools — shell, git, test runners, linters, package managers, docker"
```

---

### Task 19g: Wire Tools into Plugin Execution

Connect the tools system to the plugin execution flow so agents can actually use tools during workflow runs.

**Files:**
- Modify: `packages/core/plugins/langgraph/executor.py`
- Modify: `packages/core/plugins/langgraph/plugin.py`
- Modify: `services/api/routes/execute.py`

**Step 1: Update LangGraph executor to accept tools**

The `execute_graph` function needs to:
1. Read tool configs from each agent node's `config.tools` array
2. Create tools via `ToolFactory.create_tools()`
3. Pass tools to `create_react_agent()` or bind them to the LLM

Key changes to `executor.py`:

```python
# In execute_graph(), when creating a single agent:
from tools.factory import ToolFactory

# Load tools from node config
tool_configs = config.get("tools", [])
# Convert string tool names to native tool configs
normalized = [
    {"name": t, "type": "native"} if isinstance(t, str) else t
    for t in tool_configs
]
tools = ToolFactory.create_tools(normalized, credentials)

agent = create_react_agent(llm, tools=tools)
```

**Step 2: Update execute route to pass custom tools from DB**

In `services/api/routes/execute.py`, before calling `plugin.execute()`:
- Load custom tools from DB for the org
- Load skills from DB for the project
- Merge with the graph config's tool references

**Step 3: Commit**

```bash
git add packages/core/plugins/langgraph/executor.py services/api/routes/execute.py
git commit -m "feat: wire tools (native, custom, MCP, skills) into plugin execution flow"
```

---

### Task 19h: Tool Templates Registry

Port the template system so users can quickly create tools from pre-configured templates.

**Files:**
- Create: `packages/core/tools/templates.py`
- Create: `services/api/routes/tool_templates.py`
- Test: `packages/core/tests/test_templates.py`

**Step 1: Create templates**

Port the highest-priority templates from `backend/core/tools/templates.py`:

```python
# packages/core/tools/templates.py
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolTemplate:
    template_id: str
    name: str
    description: str
    tool_type: str  # api, notification, image_video, etc.
    config_template: dict[str, Any]
    input_schema_template: dict[str, Any]
    required_user_fields: list[str]
    setup_instructions: str = ""
    is_featured: bool = False
    priority: int = 0


# Featured templates
TEMPLATES: list[ToolTemplate] = [
    ToolTemplate(
        template_id="slack_notification",
        name="Slack Notification",
        description="Send messages to Slack channels via webhook",
        tool_type="notification",
        config_template={
            "webhook_url": "{SLACK_WEBHOOK_URL}",
            "channel": "#general",
        },
        input_schema_template={
            "message": {"type": "string", "description": "Message to send"},
        },
        required_user_fields=["webhook_url"],
        setup_instructions="1. Go to api.slack.com/apps\n2. Create incoming webhook\n3. Copy webhook URL",
        is_featured=True,
        priority=100,
    ),
    ToolTemplate(
        template_id="api_webhook",
        name="API / Webhook",
        description="Call any HTTP API endpoint",
        tool_type="api",
        config_template={
            "url": "{API_URL}",
            "method": "GET",
            "headers": {},
            "auth_type": "none",
        },
        input_schema_template={
            "params": {"type": "object", "description": "Request parameters"},
        },
        required_user_fields=["url"],
        is_featured=True,
        priority=90,
    ),
    ToolTemplate(
        template_id="dalle3",
        name="DALL-E 3 Image Generation",
        description="Generate images using OpenAI DALL-E 3",
        tool_type="image_video",
        config_template={
            "provider": "openai",
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard",
        },
        input_schema_template={
            "prompt": {"type": "string", "description": "Image description"},
        },
        required_user_fields=[],
        setup_instructions="Requires OpenAI API key in your organization's API key vault",
        is_featured=True,
        priority=85,
    ),
]


class ToolTemplateRegistry:
    _templates: dict[str, ToolTemplate] = {t.template_id: t for t in TEMPLATES}

    @classmethod
    def list_all(cls) -> list[ToolTemplate]:
        return sorted(cls._templates.values(), key=lambda t: -t.priority)

    @classmethod
    def list_featured(cls) -> list[ToolTemplate]:
        return [t for t in cls.list_all() if t.is_featured]

    @classmethod
    def get(cls, template_id: str) -> ToolTemplate | None:
        return cls._templates.get(template_id)

    @classmethod
    def register(cls, template: ToolTemplate):
        cls._templates[template.template_id] = template
```

**Step 2: Create API route and commit**

```python
# services/api/routes/tool_templates.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/tool-templates", tags=["tool-templates"])

import sys
sys.path.insert(0, "../../packages/core")
from tools.templates import ToolTemplateRegistry


@router.get("")
async def list_templates(featured: bool = False):
    templates = ToolTemplateRegistry.list_featured() if featured else ToolTemplateRegistry.list_all()
    return [
        {
            "template_id": t.template_id,
            "name": t.name,
            "description": t.description,
            "tool_type": t.tool_type,
            "required_user_fields": t.required_user_fields,
            "setup_instructions": t.setup_instructions,
            "is_featured": t.is_featured,
        }
        for t in templates
    ]


@router.get("/{template_id}")
async def get_template(template_id: str):
    t = ToolTemplateRegistry.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": t.template_id,
        "name": t.name,
        "description": t.description,
        "tool_type": t.tool_type,
        "config_template": t.config_template,
        "input_schema_template": t.input_schema_template,
        "required_user_fields": t.required_user_fields,
        "setup_instructions": t.setup_instructions,
    }
```

```bash
git add packages/core/tools/templates.py services/api/routes/tool_templates.py
git commit -m "feat: tool template registry with featured templates (Slack, API, DALL-E 3)"
```

---

## Phase 3: Workspace (Weeks 8-10) — Outline

> Detailed task breakdowns for Phase 3 will be written when Phase 2 is complete.

### Task 20: Project Files API
- CRUD for project files with versioning
- `services/api/routes/files.py`
- File tree endpoint, version history, diff

### Task 21: Chat Sessions API
- `services/api/routes/chat.py`
- Session CRUD, message append, SSE streaming for chat
- Wire to plugin's `chat()` method

### Task 22: Knowledge Base / RAG API
- `services/api/routes/knowledge.py`
- Document upload, chunking, embedding (pgvector)
- Semantic search endpoint
- Uses org's BYOK embedding API key

### Task 23: Frontend — Projects Dashboard
- `apps/web/src/features/projects/`
- Project list, create modal, project card component
- Botanical brutalist card design (2px border, offset shadow)

### Task 24: Frontend — Workflow Canvas
- `apps/web/src/features/canvas/`
- ReactFlow canvas with dynamic node palette from plugin API
- Node config sidebar panel
- Save/load graph config
- Execute button with SSE event handling

### Task 25: Frontend — Chat Interface
- `apps/web/src/features/chat/`
- Chat panel (sliding or modal)
- Message streaming via SSE
- Session management

### Task 26: Frontend — File Browser
- `apps/web/src/features/projects/FileBrowser.tsx`
- Tree view of project files
- Inline file editor

### Task 27: Frontend — Knowledge Upload
- `apps/web/src/features/knowledge/`
- Drag-and-drop document upload
- Indexing status display
- Search interface

---

## Phase 4: SaaS Layer (Weeks 11-13) — Outline

### Task 28: BYOK API Keys Vault UI + API
- `services/api/routes/settings.py` — store/retrieve encrypted keys
- `apps/web/src/features/settings/ApiKeys.tsx` — key management UI
- Encrypt on save, mask on display, test connection button

### Task 29: Stripe Integration — Products & Subscriptions
- `services/api/routes/billing.py`
- Create Stripe products/prices for Free, Pro, Enterprise
- Subscription creation, upgrade, downgrade
- Stripe Customer Portal redirect

### Task 30: Stripe Webhook Handler
- `services/api/routes/stripe_webhook.py`
- Handle: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- Update org `plan` and `stripe_subscription_id` on events

### Task 31: Usage Metering
- `services/api/middleware/metering.py`
- Count executions per org per billing period
- Block Free tier when over 100 executions/mo
- Report Pro tier overage to Stripe Usage Records

### Task 32: Team Management
- `apps/web/src/features/settings/Team.tsx`
- Invite members (via Better Auth organization plugin)
- Role management (owner, admin, member, viewer)
- Remove members

### Task 33: Org Switcher
- `apps/web/src/components/OrgSwitcher.tsx`
- Header dropdown to switch active organization
- Create new organization
- Calls Better Auth's `setActiveOrganization`

### Task 34: Frontend — Billing Dashboard
- `apps/web/src/features/settings/Billing.tsx`
- Current plan display, usage metrics
- Upgrade/downgrade buttons
- Invoice history (Stripe Customer Portal link)

---

## Phase 5: Polish & Launch (Weeks 14-16) — Outline

### Task 35: Onboarding Flow
- First-run wizard: create org, add API key, create first project
- `apps/web/src/features/onboarding/`

### Task 36: Landing Page
- Botanical brutalist marketing page
- Feature highlights, pricing table, CTA
- Either in the same React app or a separate page

### Task 37: Documentation
- API docs (FastAPI auto-generates Swagger)
- User guide (getting started, concepts, tutorials)
- Plugin development guide (for future community plugins)

### Task 38: End-to-End Testing
- Playwright tests for critical flows:
  - Signup → Create org → Add API key → Create project → Build workflow → Execute → See results
  - Billing: upgrade plan, usage metering

### Task 39: Security Audit
- RLS policy verification (cross-tenant data leak tests)
- JWT verification edge cases
- API key encryption audit
- Rate limiting per org

### Task 40: Railway Production Deployment
- Production environment variables
- Database backups configuration
- Monitoring and alerting
- Custom domain setup

---

## Phase 6: Expand (Week 17+) — Outline

### Task 41: CrewAI Plugin
- Implement `OrchestratorPlugin` for CrewAI
- Role-based agent nodes, task delegation
- `packages/core/plugins/crewai/`

### Task 42: Raw Python Plugin
- Custom Python function nodes
- Sandboxed execution (subprocess with timeout)
- `packages/core/plugins/raw_python/`

### Task 43: Extract OSS Core
- Publish `packages/core/` as standalone package
- CLI for local execution
- Documentation for self-hosting

---

## Key Reference: Existing LangConfig Patterns to Port

When implementing each task, reference these patterns from the existing codebase:

| Pattern | Source File | What to Port |
|---|---|---|
| State machine execution | `backend/core/workflows/executor.py` | TypedDict state, astream_events loop, safety limits |
| Agent creation with fallback | `backend/core/agents/factory.py` | Model routing, tool loading, structured output |
| SSE event streaming | `backend/core/workflows/executor.py` | Event bus pattern, token buffering |
| Tool factory | `backend/core/tools/factory.py` | Type-specific tool creation, validation, caching |
| Tool templates | `backend/core/tools/templates.py` | Pre-configured templates with registry pattern |
| Tool constraints | `backend/core/tools/execution_wrapper.py` | Timeout, retry, exclusive execution, HITL |
| MCP manager | `backend/services/mcp_manager.py` | Lazy-loaded servers, health checks, capability caching |
| Native tools | `backend/tools/native_tools.py` | web_search, web_fetch, filesystem — no MCP needed |
| Custom tools model | `backend/models/custom_tool.py` | Custom tool ORM with usage tracking |
| ReactFlow canvas | `src/features/workflows/canvas/WorkflowCanvas.tsx` | Node types, execution status, conflict handling |
| Chat streaming | `src/features/chat/ChatContext.tsx` | Session management, message banking |
| Optimistic locking | `backend/models/base.py` (OptimisticLockMixin) | lock_version pattern, 409 conflict response |
| API client | `src/lib/api-client.ts` | Axios interceptors, error handling classes |
| Encryption | `backend/services/encryption.py` | Fernet + PBKDF2HMAC pattern |
| Config | `backend/config.py` | Pydantic BaseSettings with DB fallback |
