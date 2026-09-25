# LangConfig

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11--3.13-blue.svg)](https://www.python.org/downloads/)
[![Node](https://img.shields.io/badge/Node-%5E20.19.0%20%7C%7C%20%3E%3D22.12.0-green.svg)](https://nodejs.org/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![LangChain](https://img.shields.io/badge/LangChain-v1.3-orange.svg)](https://langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-v1.2-orange.svg)](https://langchain-ai.github.io/langgraph/)


<img width="2615" height="816" alt="Langconfig Banner" src="https://github.com/user-attachments/assets/059f5595-2a48-4fae-bab8-5760661bcbb5" />



# Open-source visual platform for building, testing, and deploying LangChain agents and LangGraph workflows.

LangConfig makes agentic AI accessible. Build LangChain Agents and Deep Agents with full control over their toolsets, prompts, and memory configurations—no coding required.

Drop agents onto a visual canvas and connect them into multi-agent LangGraph workflows. Run workflows and watch agent thinking, tool selection, outputs, and errors in real-time. Test a workflow, review the output, tweak tools or RAG settings, run it again, and compare results—all in one place.

Create custom tools using LangChain's middleware system, or use prebuilt templates for Discord, Slack, and other integrations. Open a chat interface with any agent to collaboratively improve its system prompt, test behavior, and get feedback. Conversation context flows seamlessly into workflow execution with simple on/off controls.

When you're ready to share or deploy, export your workflow as a JSON config that anyone with LangConfig can import instantly. Or download a complete Python package—LangChain/LangGraph code, execution scripts, and a Streamlit web UI—ready to run anywhere.

LangConfig ships with 8 out-of-box workflow templates spanning research, coding, code review, privacy, and content production — including parallel multi-provider review panels, evaluator-optimizer loops with human approval gates, and deterministic PII-safe tool pipelines. We're actively building new features and templates to make it easy to pick up and start experimenting with agentic AI.

---

## Key Features

- **Visual Workflow Builder** - Drag-and-drop LangGraph state graphs on an interactive canvas
- **3D Spatial Builder** - Build the same workflows in a game-like 3D space and watch multi-agent executions animate live: glowing nodes, tool pulses along edges, orbiting subagent swarms, and a replay timeline for past runs
- **Multi-Runtime Agents** - Run chat agents on LangGraph (default), Google ADK, or Anthropic Managed Agents (hosted sessions), selected per agent template
- **Adaptive Thinking & Prompt Caching** - Claude agents support adaptive thinking with effort control, visible thinking summaries in chat, cached system prompts, and Anthropic server-side web search/fetch tools
- **Custom Agent Builder** - Create specialized agents with AI-generated configurations
- **Interactive Chat Testing** - Test agents with live streaming, tool execution visibility, and document upload
- **RAG Knowledge Base** - Upload documents (PDF, DOCX, code) for semantic search with pgvector
- **Repository Browser** - Clone git repositories read-only, browse with syntax-highlighted previews, and ingest files or folders into the knowledge base
- **Multi-Model Support** - OpenAI (GPT-5.5, GPT-5.4 series), Anthropic (Claude Fable 5, Sonnet 5, Opus 4.8, Sonnet 4.6, Haiku 4.5), Google (Gemini 3.1 Pro, Gemini 2.5 Flash), local models (Ollama, LM Studio)
- **Deep Agents v0.6 Support** - Build long-running agents with filesystem, todo, subagent, checkpoint, and store-backed workflows
- **Multi-Agent Patterns** - Supervisor (hierarchical delegation) and Swarm (peer-to-peer handoffs) strategies via `langgraph-supervisor` and `langgraph-swarm`
- **Node-Level Caching** - Per-node `CachePolicy` with configurable TTL and backend (in-memory or Redis) to skip redundant re-execution
- **Deferred Node Execution** - Map-reduce patterns: fan out to parallel agents, then a synthesis node collects all results
- **Dynamic Tool System** - `langgraph-bigtool` for large tool registries (15+ tools) and middleware-based tool add/remove based on workflow state
- **Model Capability Profiles** - Auto-detect model capabilities (function calling, structured output, vision, JSON mode) to adapt agent behavior per model
- **Custom Tool Builder** - Create specialized tools beyond built-in MCP servers
- **Tools Hub** - Browse tool templates and manage custom tools alongside agents in the Agents area
- **Privacy Tools** - Configure reusable PII profiles and run PII detection/redaction in workflows
- **Local Audio Transcription** - Upload audio for local `faster-whisper` transcription and pass transcripts through downstream workflow nodes
- **GPT Image 2 Tools** - Generate OpenAI image artifacts with supported size, quality, background, and output format controls
- **Real-Time Monitoring** - Watch agent execution, tool calls, token usage, and costs live
- **Artifact Gallery** - View and bulk download generated images and files from workflow executions
- **Workflow Scheduling** - Automate workflows with cron expressions, timezone support, and concurrency controls
- **Event-Driven Triggers** - Fire workflows from webhooks (HMAC-SHA256 verified) or file system changes (glob patterns, debounce)
- **File Versioning & Diff Viewer** - Track file version history with unified and side-by-side diff views
- **Presentation Generation** - Export workflow artifacts to Google Slides, PDF, or Reveal.js presentations
- **Export to Code** - Generate standalone Python packages with Streamlit UI, FastAPI server, or raw LangGraph code
- **LangGraph Subgraph Streaming** - Nested subgraph execution with real-time SSE streaming
- **Human-in-the-Loop** - Add approval checkpoints for critical decisions - Still Experimental
- **Experimental Automation Workspace** - Hermes validates approval-gated drafts before applying workflows, agents, tools, schedules, or triggers
- **Experimental Platform Brain** - In-memory lexical search over public docs, API routes, recipes, tools, and selected database entities
- **Experimental Local Codex Harness** - Run a separately installed, locally authenticated Codex CLI in bounded workspaces without storing its credentials in LangConfig
- **Advanced Memory** - Short-term (LangGraph checkpoints) and long-term (pgvector + LangGraph Store) persistence
- **Local-First Storage** - Projects and run history stay in your local database; configured hosted model providers and the optional Codex CLI can send prompts and tool context to their external services

<img width="1872" height="930" alt="image" src="https://github.com/user-attachments/assets/a4c3ad34-39ee-4792-9f1d-77e563c6e3f3" />

---

## Quick Start

### Prerequisites

- **Node.js** `^20.19.0` or `>=22.12.0`, with npm 10+ ([Download](https://nodejs.org/))
- **Python** 3.11-3.13; Python 3.12 is regularly tested ([Download](https://www.python.org/downloads/))
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop/))

### Installation

**1. Clone Repository**
```bash
git clone https://github.com/langconfig/langconfig.git
cd langconfig
```

**2. Create an Isolated Python Environment and Install Frontend Dependencies**
```bash
python -m venv .venv
# Activate .venv using the command for your shell; see docs/SETUP.md
npm ci
```

**3. Run Backend Setup Script**
```bash
python backend/scripts/setup.py
```

This automated script will:
- Check Python 3.11-3.13 and Docker prerequisites
- Create `.env` from `.env.example`
- Install backend Python dependencies
- Start PostgreSQL via Docker
- Initialize the database and seed agent templates
- Seed **8 ready-to-run template workflows** (Deep Research, Learning Research, Research & Content Editor, Code Review Panel, Plan-Build-Verify Coder, Privacy-First Document Analyst, Competitive Intel Sweep, Content Studio Pipeline)

See the [complete setup guide](docs/SETUP.md) for shell-specific virtual
environment commands, existing-clone upgrades, test database setup, and optional
features.

After upgrading LangConfig, re-sync the seeded template workflows with the latest recipe definitions:

```bash
python backend/db/seed_langconfig_dev.py --refresh-templates
```

This only updates rows marked as templates (`is_template = true`) — your own workflows are never touched.

**4. Add Your API Keys**

Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

---

## Running LangConfig

### Web App Mode (Recommended)

**Terminal 1 - Start Backend:**
```bash
cd backend
python main.py
```

Backend runs at: `http://127.0.0.1:8780`

**Terminal 2 - Start Frontend:**
```bash
npm run dev
```

Frontend runs at: `http://localhost:1425`

Open your browser to `http://localhost:1425`

### Experimental Desktop Shell (Not End-to-End Tested)

The supported development path is the web app above. The Tauri shell has not
been used or tested end-to-end and should not be treated as a release-ready
desktop application or onboarding requirement.

Requires **Rust** ([Install](https://rustup.rs/))

**Windows users**: Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)

```bash
# Start backend in Terminal 1
cd backend
python main.py

# Start desktop app in Terminal 2
npm run tauri dev
```

For contributors working on the experiment, this is intended to open a native
desktop window instead of a browser.

The desktop shell currently uses the system Python installation; production
installers do not bundle Python or backend dependencies yet.

---

## Project Structure

```
langconfig/
├── src/                      # React 19 frontend (TypeScript + Tailwind)
│   ├── features/
│   │   ├── workflows/        # Visual canvas & workflow management
│   │   ├── agents/           # Agent builder & library
│   │   ├── chat/             # Interactive chat testing
│   │   ├── knowledge/        # RAG document upload
│   │   ├── memory/           # Memory visualization
│   │   ├── tools/            # Custom tool builder
│   │   └── settings/         # App settings & API keys
│   ├── components/           # Shared UI components
│   ├── contexts/             # React context providers
│   ├── hooks/                # Custom React hooks
│   └── lib/                  # API client & utilities
├── backend/                  # Python FastAPI backend
│   ├── api/                  # REST API routes
│   │   ├── workflows/        # Workflow execution & management
│   │   ├── agents/           # Agent CRUD & templates
│   │   ├── chat/             # Chat sessions & streaming
│   │   ├── knowledge/        # Document upload & RAG
│   │   ├── tools/            # Custom tool management
│   │   ├── schedules/        # Cron-based workflow scheduling
│   │   ├── triggers/         # Event-driven workflow triggers
│   │   ├── webhooks/         # Incoming webhook endpoints
│   │   ├── presentations/    # Presentation generation (Slides, PDF, Reveal.js)
│   │   └── system/           # Settings and system API routes
│   ├── core/
│   │   ├── workflows/        # LangGraph orchestration engine (caching, deferred nodes, supervisor/swarm)
│   │   ├── agents/           # Agent factory, base classes, model profiles
│   │   ├── templates/        # Pre-built agent & workflow templates
│   │   ├── tools/            # Native tools, custom tools, bigtool registry
│   │   ├── codegen/          # Python code export generation
│   │   └── middleware/       # LangGraph middleware (RAG, validation, dynamic tools)
│   ├── services/
│   │   ├── context_retrieval.py    # RAG retrieval with HyDE
│   │   ├── llama_config.py         # Vector store (pgvector)
│   │   ├── token_counter.py        # Token tracking & cost calculation
│   │   ├── scheduler_service.py    # APScheduler cron service
│   │   └── triggers/               # File watcher & trigger services
│   ├── models/               # SQLAlchemy ORM models
│   ├── middleware/           # FastAPI middleware (performance, CORS)
│   ├── db/                   # Database initialization
│   │   ├── init_postgres.sql       # pgvector setup (auto-run on Docker start)
│   │   └── init_deepagents.py      # Seed agent templates
│   └── alembic/              # Database migrations
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── src-tauri/                # Tauri desktop app (optional)
├── docker-compose.yml        # PostgreSQL + pgvector setup
└── .env                      # API keys (create from .env.example)
```

---

## Database Setup Explained

LangConfig uses a single PostgreSQL database with pgvector for:

- **Workflows & Projects** - Visual workflow definitions and project organization
- **Agents & Templates** - Custom agents and pre-built templates
- **Chat Sessions** - Conversation history and session state
- **Vector Storage** - Document embeddings for RAG retrieval
- **LangGraph Checkpoints** - Workflow state persistence (via `langgraph-checkpoint-postgres`)
- **Schedules & Triggers** - Cron schedules, webhook triggers, file watchers, and execution logs
- **File Versions** - Workspace file version history with diffs

**Setup Steps:**

1. **Docker starts PostgreSQL** - `docker compose up -d postgres`
   - Automatically runs `backend/db/init_postgres.sql`
   - Creates `vector` extension (pgvector)
   - Creates initial `vector_documents` table

2. **The setup script creates the current schema on a fresh database**
   - SQLAlchemy creates all current application tables
   - Alembic is stamped at the current head for future upgrades
   - Existing LangConfig databases are preserved and upgraded with Alembic

3. **Seed agent templates (optional)** - `cd backend && python db/init_deepagents.py`  **Experimental**
   - Populates `deep_agent_templates` table with pre-built agents
   - Adds templates like Research Agent, Code Reviewer, etc.

---

## Usage Examples

### Example 1: Test an Agent Interactively

1. Click an agent from the library (e.g., "Research Agent")
2. Click the **Chat** icon
3. Upload documents for RAG context (optional)
4. Send a message: `"Summarize the key findings in these papers"`
5. Watch the agent use tools in real-time
6. View token costs and metrics in the sidebar

### Example 2: Build a Multi-Agent Workflow

1. Go to **Studio** → **New Workflow**
2. Drag "Research Agent" to canvas
3. Drag "Code Implementer" to canvas
4. Connect them: Research → Implementer
5. Click **Run**
6. Enter task: `"Research best practices for authentication and implement it"`
7. Research Agent finds information → passes to Implementer → code is generated

### Example 3: Create a Custom Agent with AI

1. Click **Agent Builder** from toolbar
2. Enter name: `"Security Auditor"`
3. Enter description: `"Reviews code for security vulnerabilities and suggests fixes"`
4. Click **AI Generate** → GPT-5.4 suggests:
   - Model: `gpt-5.4` (reasoning capability)
   - Temperature: `0.2` (focused, deterministic)
   - Tools: `filesystem`, `grep`, `web_search`
   - System prompt: Specialized security analysis prompt
5. Review and customize (add more tools, adjust prompt)
6. Click **Save** → use in workflows or chat testing

### Example 4: Fan-Out Research with Deferred Synthesis

1. Go to **Studio** → **New Workflow**
2. Add 3 research agents in parallel (e.g., "Market Research", "Technical Research", "Competitor Analysis")
3. Add a "Synthesis" agent and connect all 3 research agents to it
4. Open Synthesis node settings → enable **Wait for all inputs**
5. Click **Run** → all 3 agents execute in parallel → Synthesis waits for all results → produces merged analysis

### Example 5: Use Supervisor Multi-Agent Strategy

1. Go to **Studio** → **New Workflow**
2. Set strategy type to **Supervisor**
3. Define worker agents (e.g., "Researcher", "Writer", "Editor") with their tools and prompts
4. The supervisor automatically delegates tasks to workers and collects results
5. Click **Run** → supervisor orchestrates the team

### Example 6: Export Workflow as Standalone App

1. Build workflow visually (e.g., Research → Plan → Implement → Test)
2. Click **Export** → **Download Python Package**
3. Extract the ZIP file to any folder
4. Run `pip install -r requirements.txt`
5. Add API keys to `.env`
6. Run `streamlit run streamlit_app.py`
7. Use your workflow as a standalone web app with live streaming output

---

## Configuration

### Environment Variables

The setup script creates a new `.env` with a unique encryption key. Edit that
file to configure the application. Existing `.env` files are preserved; see
[setup and key preservation](docs/SETUP.md) before changing a key used by saved credentials.

**Required:**
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (default: `postgresql://langconfig:langconfig_dev@localhost:5433/langconfig`) |

**LLM API Keys** (at least one required):
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT models |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models |
| `GOOGLE_API_KEY` | Google API key for Gemini models |

**Optional:**
| Variable | Description | Default |
|----------|-------------|--------|
| `GITHUB_TOKEN` | GitHub token for private repository access | - |
| `GITLAB_TOKEN` | GitLab token for GitLab MCP tools | - |
| `APP_ENCRYPTION_KEY` | Key used to encrypt credentials saved in Settings | Generated when setup creates a new `.env`; existing keys preserved; required in production |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `DEBUG` | Enable verbose backend logging (`true` or `false`) | `true` in development |

**Workflow Execution:**
| Variable | Description | Default |
|----------|-------------|--------|
| `MAX_EXECUTION_HISTORY_PER_WORKFLOW` | History entries to keep | `100` |
| `EXECUTION_HISTORY_RETENTION_DAYS` | Days to retain history | `90` |

API keys can also be configured via **Settings UI** in the app (stored encrypted in database, takes priority over `.env`).

### Local Models

Run models locally with zero API costs:

1. Install [Ollama](https://ollama.ai/) or [LM Studio](https://lmstudio.ai/)
2. Start local model server (default: `http://localhost:11434`)
3. Go to **Settings** → **API Keys**
4. Add Local Provider:
   - **Base URL**: `http://localhost:11434/v1`
   - **Model**: `llama3.1` (or your model name)
5. Use in any agent configuration

### Built-in Tools

**Native Python Tools** (no external dependencies):
- `web_search` - Web search via DuckDuckGo (free, no API key)
- `web_fetch` - Fetch webpage content
- `file_read` / `file_write` / `file_list` - File system operations
- `memory_store` / `memory_recall` - Long-term memory (PostgreSQL-backed)
- `reasoning_chain` - Break down complex tasks into logical steps
- `calculator` - Evaluate simple arithmetic expressions
- `pii_detect` / `pii_redact` - Detect and redact PII with optional reusable profiles
- `audio_transcribe` - Transcribe local audio files with `faster-whisper`
- `generate_image` - Generate GPT Image 2 image artifacts for workflow/chat output

**Browser Automation** (Playwright, requires `playwright install chromium`):
- `browser_navigate` - Navigate URLs with JavaScript rendering
- `browser_click` - Click elements on page
- `browser_extract` - Extract text/links from pages
- `browser_screenshot` - Capture page screenshots

**Custom Tool Templates** (create via UI):
- **Notifications**: Slack, Discord (multi-channel webhooks)
- **CMS/Publishing**: WordPress REST API, Twitter/X API
- **Image/Video**: GPT Image 2, DALL-E 3, ChatGPT Image Gen 1.5, Sora, Imagen 3, Nano Banana (Gemini 2.5 Flash Image), Veo 3.1 Fast
- **Database**: PostgreSQL, MySQL, MongoDB queries
- **API/Webhook**: Custom REST API calls with auth
- **Data Transform**: JSON ↔ CSV ↔ XML ↔ YAML conversion

---

## Tech Stack

**Frontend:**
- React 19.2 + TypeScript 5.8
- Tailwind CSS 4.1
- ReactFlow 11.11 (visual canvas)
- TanStack Query 5.90
- Tauri 2.0 (optional desktop app)

**Backend:**
- Python 3.11-3.13 (3.12 regularly tested)
- FastAPI 0.136
- LangChain 1.3.x (full ecosystem)
- LangGraph 1.2.x (with checkpoint-postgres, supervisor, swarm, bigtool)
- Deep Agents 0.6.x
- LlamaIndex (document indexing & RAG)
- faster-whisper (local audio transcription)

**Database:**
- PostgreSQL 16 with pgvector
- SQLAlchemy 2.0 + Alembic (migrations)
- langgraph-checkpoint-postgres (state persistence)

**AI/ML:**
- OpenAI (GPT-5.5, GPT-5.4, GPT-5.4 Mini, GPT-5.4 Nano, GPT Image 2)
- Anthropic (Claude Fable 5, Claude Sonnet 5, Claude Opus 4.8, Claude Sonnet 4.6, Claude Haiku 4.5)
- Google (Gemini 3.1 Pro Preview, Gemini 2.5 Flash, Gemini 2.5 Flash Lite)
- Local models via Ollama/LM Studio
- Sentence Transformers (embeddings)
- Unstructured (document processing)

---

## Automation

LangConfig supports automated workflow execution through cron schedules, webhooks, and file system triggers.

### Cron Scheduling

Schedule workflows to run automatically on a recurring basis:

1. Open a workflow → **Settings** → **Schedule**
2. Enter a cron expression (e.g., `0 9 * * 1-5` for weekdays at 9 AM)
3. Select a timezone and configure optional input data
4. Enable the schedule

Schedules support concurrency limits, idempotency keys for deduplication, and a full execution history log.

### Webhook Triggers

Trigger workflows from external services via HTTP:

1. Open a workflow → **Settings** → **Triggers** → **Add Webhook**
2. Copy the generated webhook URL and secret
3. Configure your external service to POST to the URL
4. Payloads are verified with HMAC-SHA256 signatures and optional IP whitelisting

Use input mapping to transform incoming payloads into workflow input.

### File Watch Triggers

Trigger workflows when files change on disk:

1. Open a workflow → **Settings** → **Triggers** → **Add File Watch**
2. Set a directory path and glob pattern (e.g., `*.csv`)
3. Choose events to watch: created, modified, deleted, or moved
4. Configure debounce interval to prevent rapid re-triggers

File watchers support recursive directory monitoring.

---

## Troubleshooting

### Port Already in Use

```bash
# Windows PowerShell: identify the owning process before stopping it
Get-NetTCPConnection -LocalPort 1425,8780 -ErrorAction SilentlyContinue

# macOS/Linux: identify the owning process before stopping it
lsof -i :1425 -i :8780
```

### PostgreSQL Connection Failed

```bash
# Check Docker is running
docker compose ps

# Restart PostgreSQL
docker compose restart postgres

# Check logs
docker compose logs postgres
```

### Database Migration Issues

```bash
# Record the current revision and complete error before changing data
cd backend
python -m alembic current
python -m alembic upgrade head
```

For a brand-new database, use `python backend/scripts/setup.py`. Do not use
`alembic downgrade base` as a routine reset; it can destroy application data.

### Python Dependencies Issues

```bash
# Reinstall all dependencies
cd backend
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements.txt
```

---

## Experimental Desktop Packaging (Unverified)

Desktop packaging has not been tested end-to-end or used for a release. The web
app is the supported way to run LangConfig.

**Prerequisites:**
- Rust installed ([Install](https://rustup.rs/))
- Visual Studio Build Tools (Windows only)

```bash
npm run tauri build
```

The Tauri configuration declares these intended targets, but successful release
artifacts have not been verified:
- **Windows**: `.exe`, `.msi`
- **macOS**: `.app`, `.dmg`
- **Linux**: `.AppImage`, `.deb`

The generated desktop package still requires a compatible system Python and an
installed backend environment.

---

## Development

### Running Tests

```bash
# Backend tests
cd backend
python -m pytest

# Frontend type-check and production build
cd ..
npm run build
```

### Database Migrations

```bash
cd backend

# Create new migration
python -m alembic revision --autogenerate -m "Description of changes"

# Apply migration
python -m alembic upgrade head

# Rollback migration
python -m alembic downgrade -1
```

### Adding Custom Agent Templates

Agent templates are defined in `backend/core/agents/templates.py`. Workflow recipes (multi-node templates) are in `backend/core/templates/workflow_recipes.py`.

To add new templates:
1. Add your template definition to the appropriate file
2. Templates are auto-registered on backend startup
3. For database-stored agents, use the Agent Builder UI or run:

```bash
cd backend
python db/init_deepagents.py
```

---

## Documentation

- **[Development Setup](./docs/SETUP.md)** - Canonical fresh-clone and upgrade instructions
- **[Google OAuth Setup](./docs/GOOGLE_OAUTH_SETUP.md)** - Google Slides export credentials
- **[Chat API Documentation](./backend/api/chat/README.md)** - Interactive chat testing API
- **[GitHub Issues](https://github.com/langconfig/langconfig/issues)** - Report bugs and request features

---

## Contributing

We welcome contributions! Whether you're:
- Adding agent templates
- Improving UI/UX
- Writing documentation
- Reporting bugs
- Suggesting features

**How to Contribute:**

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit: `git commit -m 'Add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open a Pull Request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

---

## License

Copyright 2025 LangConfig Contributors

Licensed under the MIT License. See [LICENSE](./LICENSE) file for details.

### Third-Party Licenses

- **LangChain & LangGraph** - MIT License
- **FastAPI** - MIT License
- **React** - MIT License
- **Tauri** - Apache 2.0 / MIT License
- **PostgreSQL** - PostgreSQL License

---

## Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/langconfig/langconfig/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/langconfig/langconfig/discussions)

---

**LangConfig - Visual AI Agent Workflows Powered by LangChain & LangGraph**
