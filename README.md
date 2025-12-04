# LangConfig

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org/)
[![React](https://img.shields.io/badge/React-19-blue.svg)](https://react.dev/)
[![LangChain](https://img.shields.io/badge/LangChain-v1.0-orange.svg)](https://langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-latest-orange.svg)](https://langchain-ai.github.io/langgraph/)

**Visual, no-code interface for building LangChain agents and LangGraph multi-agent workflows.**

Build AI agent systems using LangChain and LangGraph. No coding required.

---

## Key Features

- **Visual Workflow Builder** - Drag-and-drop LangGraph state graphs on an interactive canvas
- **Custom Agent Builder** - Create specialized agents with AI-generated configurations
- **Interactive Chat Testing** - Test agents with live streaming, tool execution visibility, and document upload
- **RAG Knowledge Base** - Upload documents (PDF, DOCX, code) for semantic search with pgvector
- **Multi-Model Support** - OpenAI (GPT-4o, GPT-5), Anthropic (Claude 4.5 Sonnet/Opus/Haiku), Google (Gemini 3 Pro, Gemini 2.5), DeepSeek, local models (Ollama, LM Studio)
- **Custom Tool Builder** - Create specialized tools beyond built-in MCP servers
- **Real-Time Monitoring** - Watch agent execution, tool calls, token usage, and costs live
- **Export to Code** - Generate LangGraph Python code from visual workflows
- **Human-in-the-Loop** - Add approval checkpoints for critical decisions - Still Experimental
- **Advanced Memory** - Short-term (LangGraph checkpoints) and long-term (pgvector + LangGraph Store) persistence
- **Local-First** - All data stays on your machine

---

## Quick Start

### Prerequisites

- **Node.js** 18+ ([Download](https://nodejs.org/))
- **Python** 3.10+ ([Download](https://www.python.org/downloads/))
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop/))

### Installation

**1. Clone Repository**
```bash
git clone https://github.com/langconfig/langconfig.git
cd langconfig
```

**2. Install Dependencies**
```bash
# Frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
cd ..
```

**3. Start PostgreSQL with pgvector**
```bash
docker-compose up -d postgres
```

This starts PostgreSQL 16 with pgvector extension on port 5433. The `init_postgres.sql` script automatically enables pgvector and creates the vector_documents table.

**4. Configure Environment**
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

**5. Initialize Database**
```bash
cd backend

# Run migrations to create all tables
alembic upgrade head

# Seed agent templates (optional)
python db/init_deepagents.py

cd ..
```

---

## Running LangConfig

### Web App Mode (Recommended)

**Terminal 1 - Start Backend:**
```bash
cd backend
python main.py
```

Backend runs at: `http://127.0.0.1:8765`

**Terminal 2 - Start Frontend:**
```bash
npm run dev
```

Frontend runs at: `http://localhost:1420`

Open your browser to `http://localhost:1420`

### Desktop App Mode (Advanced)

Requires **Rust** ([Install](https://rustup.rs/))

**Windows users**: Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)

```bash
# Start backend in Terminal 1
cd backend
python main.py

# Start desktop app in Terminal 2
npm run tauri dev
```

This opens a native desktop window instead of a browser.

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
│   │   └── settings/         # API keys & configuration
│   ├── core/
│   │   ├── workflows/        # LangGraph orchestration engine
│   │   ├── agents/           # Agent factory & base classes
│   │   ├── templates/        # Pre-built agent & workflow templates
│   │   ├── tools/            # Native and custom tool integrations
│   │   ├── codegen/          # Python code export generation
│   │   └── middleware/       # LangGraph middleware (RAG, validation)
│   ├── services/             
│   │   ├── context_retrieval.py    # RAG retrieval with HyDE
│   │   ├── llama_config.py         # Vector store (pgvector)
│   │   └── token_counter.py        # Token tracking & cost calculation
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

**Setup Steps:**

1. **Docker starts PostgreSQL** - `docker-compose up -d postgres`
   - Automatically runs `backend/db/init_postgres.sql`
   - Creates `vector` extension (pgvector)
   - Creates initial `vector_documents` table

2. **Alembic creates all tables** - `alembic upgrade head`
   - Runs migrations in `backend/alembic/versions/`
   - Creates: workflows, projects, agents, chat_sessions, session_documents, checkpoints, etc.

3. **Seed agent templates (optional)** - `python db/init_deepagents.py`  **Experimental**
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
4. Click **AI Generate** → GPT-4o suggests:
   - Model: `gpt-4o` (reasoning capability)
   - Temperature: `0.2` (focused, deterministic)
   - Tools: `filesystem`, `grep`, `web_search`
   - System prompt: Specialized security analysis prompt
5. Review and customize (add more tools, adjust prompt)
6. Click **Save** → use in workflows or chat testing

### Example 4: Export Workflow to Code

1. Build workflow visually (e.g., Research → Plan → Implement → Test)
2. Click **Export** → **Python Code**

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

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
| `DEEPSEEK_API_KEY` | DeepSeek API key | - |
| `GITHUB_PAT` | GitHub Personal Access Token | - |
| `GITLAB_PAT` | GitLab Personal Access Token | - |
| `LOCAL_LLM_HOST` | Local model server URL | `http://localhost:11434` |
| `SECRET_KEY` | App secret key | Auto-generated |
| `ENVIRONMENT` | `development` or `production` | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |

**Workflow Execution:**
| Variable | Description | Default |
|----------|-------------|--------|
| `MAX_WORKFLOW_TIMEOUT` | Max workflow runtime (seconds) | `300` |
| `MAX_CONCURRENT_WORKFLOWS` | Parallel workflow limit | `5` |
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

**Browser Automation** (Playwright, requires `playwright install chromium`):
- `browser_navigate` - Navigate URLs with JavaScript rendering
- `browser_click` - Click elements on page
- `browser_extract` - Extract text/links from pages
- `browser_screenshot` - Capture page screenshots

**Custom Tool Templates** (create via UI):
- **Notifications**: Slack, Discord (multi-channel webhooks)
- **CMS/Publishing**: WordPress REST API, Twitter/X API
- **Image/Video**: DALL-E 3, Sora, Imagen 3, Nano Banana (Gemini 2.5 Flash Image), Veo 3
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
- Python 3.11+
- FastAPI 0.115
- LangChain v1.0 (full ecosystem)
- LangGraph 0.4+ (with checkpoint-postgres)
- LlamaIndex (document indexing & RAG)

**Database:**
- PostgreSQL 16 with pgvector
- SQLAlchemy 2.0 + Alembic (migrations)
- langgraph-checkpoint-postgres (state persistence)

**AI/ML:**
- OpenAI (GPT-4o, GPT-4o-mini, GPT-5, o3, o3-mini, o4-mini)
- Anthropic (Claude 4.5 Sonnet, Claude 4.5 Opus, Claude 4.5 Haiku)
- Google (Gemini 3 Pro Preview, Gemini 2.5 Flash, Gemini 2.0 Flash)
- DeepSeek (DeepSeek Chat, DeepSeek Reasoner)
- Local models via Ollama/LM Studio
- Sentence Transformers (embeddings)
- Unstructured (document processing)

---

## Troubleshooting

### Port Already in Use

```bash
# Windows
taskkill /F /IM node.exe

# macOS/Linux
lsof -ti:1420 | xargs kill -9
```

### PostgreSQL Connection Failed

```bash
# Check Docker is running
docker-compose ps

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Database Migration Issues

```bash
# Reset migrations (WARNING: deletes all data)
cd backend
alembic downgrade base
alembic upgrade head
```

### Python Dependencies Issues

```bash
# Reinstall all dependencies
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Building Desktop Installers (Optional)

**Prerequisites:**
- Rust installed ([Install](https://rustup.rs/))
- Visual Studio Build Tools (Windows only)

```bash
npm run tauri build
```

Generates platform-specific installers:
- **Windows**: `.exe`, `.msi`
- **macOS**: `.app`, `.dmg`
- **Linux**: `.AppImage`, `.deb`

Total size: ~250MB (includes Python runtime and dependencies)

---

## Development

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
npm test
```

### Database Migrations

```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
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
