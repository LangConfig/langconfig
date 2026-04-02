# LangConfig SaaS: Cloud-First Multi-Tenant Platform

**Date:** 2026-02-12
**Status:** Approved
**Approach:** Cloud-first, extract OSS later (Approach C)

---

## Vision

A new product built from scratch — a visual platform for building AI agent workflows that competes with n8n but is purpose-built for AI. Cherry-picks the best ideas from the current LangConfig (project management, file system, workflow canvas, chat testing) and adds a plugin-based orchestration layer that supports multiple AI frameworks.

### Differentiation from n8n

- **AI-native workflows** — AI agents and LLM orchestration are the core primitive, not just another integration node
- **Developer experience** — visual orchestration WITH code escape hatches, git-native, custom nodes in Python/TS
- **Project-centric workspace** — workflows live inside projects with file systems, knowledge bases, and shared context

### Business Model

- **Open core** — cloud product ships first, OSS core extracted later (Phase 2+)
- **BYOK (Bring Your Own Key)** — users provide their own LLM API keys, platform charges only for seats/features
- **PLG motion** — free tier for individuals, paid tiers for teams, enterprise for large orgs

---

## System Architecture

```
+-----------------------------------------------------------+
|                    React SPA (Vite)                        |
|   +-----------+ +-----------+ +----------+ +------------+ |
|   | Workflow   | | Chat /    | | Project  | | Settings   | |
|   | Canvas     | | Test      | | Workspace| | & Billing  | |
|   +-----------+ +-----------+ +----------+ +------------+ |
+----------------------------+------------------------------+
                             | REST + SSE
+----------------------------+------------------------------+
|                   FastAPI Backend                          |
|                                                           |
|  +------------+ +------------+ +----------+ +-----------+ |
|  | Auth       | | Workspace  | | Plugin   | | Billing   | |
|  |(BetterAuth)| | Service    | | Engine   | | (Stripe)  | |
|  +------------+ +------------+ +-----+----+ +-----------+ |
|                                      |                    |
|  +-----------------------------------+------------------+ |
|  |          Orchestrator Plugin Interface                | |
|  |  +------------+ +----------+ +-------------------+   | |
|  |  | LangGraph  | | CrewAI   | | AutoGen (later)   |   | |
|  |  | Plugin     | | Plugin   | | Plugin            |   | |
|  |  +------------+ +----------+ +-------------------+   | |
|  +------------------------------------------------------+ |
+----------------------------+------------------------------+
                             |
         +-------------------+-------------------+
         |                   |                   |
   +-----+------+    +------+-----+    +--------+---+
   | PostgreSQL  |    |  pgvector   |    |   Redis    |
   | (Neon)      |    | (embeddings)|    | (optional) |
   | + RLS       |    |             |    | (Upstash)  |
   +-------------+    +-------------+    +------------+
```

### Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | React 19 + TypeScript + Tailwind CSS 4 + Vite | Heavy SPA (canvas, streaming) — SSR adds no value |
| **Canvas** | ReactFlow | Proven drag-and-drop workflow editor |
| **Backend** | Python 3.12 + FastAPI | AI frameworks are Python — no escaping it |
| **Auth** | Better Auth | Open-source, self-hostable, org/role support built-in, OSS-compatible |
| **Billing** | Stripe (Subscriptions + Usage Records) | Industry standard, handles subscriptions + metering |
| **Database** | PostgreSQL 16 + pgvector | RLS for tenant isolation, pgvector for embeddings |
| **Hosting** | Railway (PaaS) | Push-to-deploy, managed services, scales to thousands |
| **Managed PG** | Neon (optional) | Serverless scaling, branching for dev/staging |

### Why Better Auth over Clerk

- Open-source and self-hostable — critical for the open-core model
- No per-MAU pricing — costs don't scale with users
- Built-in organization and RBAC support
- Auth tables live in your PostgreSQL — one database, not two services
- Self-hosters get auth for free, no external dependency

---

## Plugin Orchestration System

### Plugin Interface

```python
class OrchestratorPlugin(ABC):
    """Interface every orchestration backend implements."""

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Name, version, description, supported features."""

    @abstractmethod
    def get_node_types(self) -> list[NodeType]:
        """Available node types with schema (inputs, outputs, config).
        The canvas renders these dynamically."""

    @abstractmethod
    def validate_graph(self, graph_config: GraphConfig) -> ValidationResult:
        """Validate the user's graph before execution."""

    @abstractmethod
    async def execute(
        self,
        graph_config: GraphConfig,
        inputs: dict,
        credentials: dict,           # BYOK: user's decrypted API keys
        callbacks: ExecutionCallbacks, # SSE streaming, status updates
    ) -> ExecutionResult:
        """Run the workflow. Stream results via callbacks."""

    @abstractmethod
    async def chat(
        self,
        graph_config: GraphConfig,
        message: str,
        history: list[Message],
        credentials: dict,
        callbacks: ExecutionCallbacks,
    ) -> ChatResult:
        """Interactive chat with a workflow/agent."""
```

### Canvas-Plugin Integration

1. User picks an orchestration framework for a project (e.g., "LangGraph")
2. Frontend calls `GET /api/plugins/{plugin_id}/node-types`
3. Plugin returns available node types with config schemas
4. Canvas renders a dynamic node palette from these types
5. User drags and wires nodes visually
6. On execute, the graph config (JSON) goes to the plugin's `execute()` method
7. Plugin translates the visual graph into its native framework and runs it

### Graph Config Format (Framework-Agnostic)

```json
{
  "id": "wf_abc123",
  "plugin": "langgraph",
  "nodes": [
    {
      "id": "node_1",
      "type": "agent",
      "position": { "x": 100, "y": 200 },
      "config": {
        "model": "gpt-4o",
        "system_prompt": "You are a research assistant.",
        "tools": ["web_search", "web_fetch"]
      }
    }
  ],
  "edges": [
    { "source": "node_1", "target": "node_2" }
  ]
}
```

### Plugin Roadmap

| Phase | Plugin | Notes |
|---|---|---|
| **Launch** | LangGraph | Port best parts from current LangConfig |
| **Month 2** | CrewAI | Role-based agents, different paradigm |
| **Month 3** | Raw Python | Escape hatch: custom Python functions as nodes |
| **Later** | AutoGen, Haystack, DSPy | Based on demand |

---

## Data Model

### Core Tables

```
users (synced from Better Auth)
  id, email, name, avatar_url, created_at, stripe_customer_id

organizations
  id, name, slug, owner_id -> users
  plan (free / pro / enterprise)
  stripe_subscription_id, created_at

org_members
  org_id -> organizations, user_id -> users
  role (owner / admin / member / viewer), joined_at

projects
  id, org_id -> organizations (tenant isolation key)
  name, description, plugin_id
  created_by -> users, created_at

workflows
  id, project_id -> projects
  name, graph_config (JSONB)
  lock_version (optimistic locking)
  created_at, updated_at

workflow_executions
  id, workflow_id -> workflows
  triggered_by -> users
  status, results (JSONB)
  token_usage, cost
  started_at, completed_at

project_files
  id, project_id -> projects
  path, content, version
  created_at, updated_at

chat_sessions
  id, project_id -> projects
  user_id -> users, workflow_id -> workflows (optional)
  messages (JSONB), created_at

knowledge_documents
  id, project_id -> projects
  filename, content, embedding (vector)
  indexing_status, created_at

api_keys_vault
  id, org_id -> organizations
  provider (openai / anthropic / google / etc.)
  encrypted_key, created_at
```

### Tenant Isolation

- Every query is scoped by `org_id` — no exceptions
- PostgreSQL Row-Level Security (RLS) policies enforce `org_id` matches JWT claim
- Application-level middleware also filters by `org_id` (defense in depth)
- API keys stored per-organization, encrypted at rest (Fernet)
- Vector embeddings scoped by `project_id` (which belongs to `org_id`)

### BYOK Credential Flow

1. User enters their LLM API key in Settings
2. Key is Fernet-encrypted and stored in `api_keys_vault` per organization
3. On workflow execution, key is decrypted server-side and passed to plugin via `credentials` parameter
4. Keys never leave the backend — frontend never sees raw keys after submission

---

## Pricing & Billing

### Tier Structure

| | Free | Pro | Enterprise |
|---|---|---|---|
| **Price** | $0 | $25/user/mo | Custom |
| **Users** | 1 | Unlimited | Unlimited |
| **Projects** | 3 | Unlimited | Unlimited |
| **Workflows/project** | 5 | Unlimited | Unlimited |
| **Executions/mo** | 100 | 5,000 | Unlimited |
| **Knowledge docs** | 10 | 500 | Unlimited |
| **File storage** | 100MB | 10GB | Custom |
| **Plugins** | LangGraph only | All | All + custom |
| **Team features** | -- | Shared workspaces, roles | SSO, RBAC, audit logs |
| **Support** | Community | Email | Dedicated + SLA |

### Billing Architecture

- Stripe Subscriptions for seat-based recurring charges
- Stripe Usage Records for execution metering (overage beyond tier limits)
- Better Auth webhook -> create Stripe customer on signup
- Stripe webhook -> update org plan on subscription changes
- Free tier: execution blocked with upgrade prompt when over limit
- Pro tier: overage charged at $0.01/execution

### What's NOT billed

- LLM token costs (BYOK — user pays their provider directly)
- Embedding generation (user's API key)
- File storage within tier limits

---

## Project Structure

```
langconfig-cloud/
  apps/
    web/                        # React SPA (Vite)
      src/
        features/
          auth/                 # Better Auth integration
          canvas/               # Workflow editor (ReactFlow)
          chat/                 # Interactive chat/test
          projects/             # Project workspace, files
          settings/             # API keys, billing, team mgmt
          onboarding/           # First-run experience
        components/             # Shared UI (botanical brutalist)
        hooks/                  # React hooks
        lib/                    # API client, utils
        types/

  packages/
    core/                       # Extractable core (future OSS)
      orchestration/
        plugin_interface.py
        graph_config.py
        execution.py
      plugins/
        langgraph/              # LangGraph plugin
        crewai/                 # CrewAI plugin (month 2)
        raw_python/             # Python functions (month 3)
      pyproject.toml

  services/
    api/                        # FastAPI backend
      routes/
        auth.py                 # Better Auth webhook sync
        orgs.py                 # Organization management
        projects.py             # Project CRUD + files
        workflows.py            # Workflow CRUD + execution
        chat.py                 # Chat/test sessions
        plugins.py              # Plugin discovery + node types
        knowledge.py            # RAG document management
        billing.py              # Stripe webhook + usage
        settings.py             # API keys vault
      middleware/
        auth.py                 # Better Auth JWT verification
        tenant.py               # Org-scoped request context
        metering.py             # Usage tracking
      models/                   # SQLAlchemy ORM
      services/                 # Business logic
      config.py
      main.py

  infra/
    railway.toml                # Railway deployment config
    alembic/                    # Database migrations

  docker-compose.yml            # Local dev (PG + Redis)
```

### Key Structural Decision

`packages/core/` houses the orchestration engine and plugins — separate from the API. This is what gets extracted as OSS later. Clean dependency boundary from day one, even though it ships as one product initially.

---

## Development Phases

| Phase | Duration | Deliverables |
|---|---|---|
| **Phase 1: Foundation** | Weeks 1-3 | Project scaffolding, Better Auth, PostgreSQL schema + RLS, Railway deploy, UI shell with botanical brutalist design |
| **Phase 2: Core Engine** | Weeks 4-7 | Plugin interface, LangGraph plugin, workflow canvas, graph execution with SSE streaming |
| **Phase 3: Workspace** | Weeks 8-10 | Projects, file system, chat/test interface, knowledge base (RAG with pgvector) |
| **Phase 4: SaaS Layer** | Weeks 11-13 | Stripe billing, usage metering, team management, BYOK vault, org switching |
| **Phase 5: Polish & Launch** | Weeks 14-16 | Onboarding flow, landing page, docs, beta launch |
| **Phase 6: Expand** | Weeks 17+ | CrewAI plugin, Raw Python plugin, enterprise features, OSS core extraction |

### ~16 weeks to beta launch

Time savings:
- Better Auth eliminates custom auth development (~3-4 weeks saved)
- Stripe eliminates billing development (~3 weeks saved)
- Workflow canvas and chat UI are rewrites of existing LangConfig code (faster than greenfield)
- Railway eliminates DevOps overhead (~2 weeks saved)

---

## Design Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| New product vs. refactor | New codebase | Current LangConfig has zero multi-tenancy; retrofitting is harder than rebuilding |
| Orchestration | Plugin architecture | The moat — framework-agnostic means the platform survives framework churn |
| Auth | Better Auth | Open-source, self-hostable, aligns with open-core model |
| Billing | Stripe | Industry standard, handles subscriptions + metering |
| Database | PostgreSQL + pgvector + RLS | One database for everything — relational, vectors, tenant isolation |
| Hosting | Railway (PaaS) | Fast deployment, managed services, migrate to AWS/GCP when needed |
| Pricing | BYOK + seat-based tiers | Users trust it (no token markup), simple billing |
| OSS strategy | Cloud-first, extract later | Ship revenue product first, open-source core once stable |
| V1 features | Canvas + Chat + Projects + Plugins | Plugin architecture is the pitch — must ship in V1 |
