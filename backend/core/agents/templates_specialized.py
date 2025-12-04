# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangConfig Specialized Agent Templates
==================================

Domain-specific agent templates designed specifically for LangConfig's use cases.
These templates leverage real MCP servers and tools configured in the system.

Each template is production-ready with:
- Real MCP tool integrations (no fake/mock tools)
- Specific prompts for LangConfig workflows
- Optimized model selection
- Resilience and error handling
"""

from core.agents.templates import AgentTemplate, AgentCategory


# =============================================================================
# WORKFLOW & ORCHESTRATION SPECIALISTS
# =============================================================================

WORKFLOW_ARCHITECT = AgentTemplate(
    template_id="workflow_architect",
    name="Agent Workflow Designer",
    description="""Designs multi-agent workflows and orchestration patterns.
    Expert in LangGraph, agent delegation, and task decomposition.

    WHEN TO USE:
    - Design complex multi-step workflows
    - Plan agent collaboration patterns
    - Optimize workflow efficiency
    - Architect LangGraph state machines""",
    category=AgentCategory.ARCHITECTURE,

    model="claude-sonnet-4-5-20250929",  # Claude excels at system design
    fallback_models=["gpt-5", "gemini-2.5-pro"],
    temperature=0.4,

    system_prompt="""ROLE: Agent Workflow Architect
EXPERTISE: Multi-agent systems, LangGraph orchestration, task decomposition, workflow optimization.

GOAL: Design efficient multi-agent workflows using LangGraph patterns.

WORKFLOW DESIGN PRINCIPLES:
1. Decompose complex tasks into specialized sub-agents
2. Define clear state transitions and control flow
3. Minimize handoff overhead between agents
4. Plan error recovery and fallback paths
5. Optimize for parallel execution where possible

MCP TOOLS AVAILABLE:
- sequential_thinking: Break down complex workflow requirements
- memory: Store workflow patterns and best practices
- filesystem: Read existing workflow blueprints, write new designs

DESIGN DELIVERABLES:
- LangGraph state machine diagrams (Mermaid)
- Agent role definitions and capabilities
- Tool assignment matrix
- Error handling strategy
- Performance optimization recommendations

OUTPUT: Complete workflow specification with architecture docs.""",

    mcp_tools=["reasoning_chain", "memory_store", "file_read", "file_write", "file_list"],

    enable_model_routing=False,  # Always use best model for architecture
    enable_parallel_tools=False,  # Architecture is sequential thinking
    enable_memory=True,
    memory_types=["pattern", "decision", "relationship"],

    timeout_seconds=600,

    tags=["architecture", "workflows", "langgraph", "orchestration"],
    version="2.0.0"
)


PERFORMANCE_ANALYST = AgentTemplate(
    template_id="performance_analyst",
    name="Workflow Performance Analyst",
    description="""Analyzes workflow execution metrics, identifies bottlenecks, and recommends optimizations.
    Uses database and memory tools to query execution history.

    WHEN TO USE:
    - Analyze slow workflow executions
    - Identify performance bottlenecks
    - Optimize agent selection
    - Recommend infrastructure improvements""",
    category=AgentCategory.QA_VALIDATION,

    model="gpt-5",
    fallback_models=["claude-sonnet-4-5-20250929", "gpt-4o-mini"],
    temperature=0.3,

    system_prompt="""ROLE: Performance Engineer & Data Analyst
EXPERTISE: Performance optimization, SQL analytics, workflow profiling, cost analysis.

GOAL: Analyze workflow execution data to identify and resolve performance issues.

ANALYSIS WORKFLOW:
1. Query database for workflow execution history
2. Calculate key metrics: latency, token usage, cost, error rates
3. Identify bottlenecks: slow agents, expensive models, redundant steps
4. Compare similar workflow patterns
5. Generate optimization recommendations

MCP TOOLS AVAILABLE:
- database: Query projects, tasks, executions, metrics tables
- memory: Store performance patterns and optimization history
- sequential_thinking: Structure complex performance analysis
- filesystem: Export reports, charts, dashboards

METRICS TO TRACK:
- Execution time per workflow/agent
- Token usage and API costs
- Error rates and retry counts
- Agent tool usage patterns
- Model selection effectiveness

OUTPUT: Performance report with metrics, visualizations, and actionable recommendations.""",

    mcp_tools=["memory_store", "reasoning_chain", "file_read", "file_write", "file_list"],

    enable_model_routing=True,  # Can use cheaper models for simple queries
    enable_parallel_tools=True,  # Parallel database queries
    enable_memory=True,
    memory_types=["pattern", "fact"],

    timeout_seconds=600,

    tags=["performance", "analytics", "optimization", "monitoring"],
    version="2.0.0"
)


# =============================================================================
# DOCUMENT & KNOWLEDGE SPECIALISTS
# =============================================================================

CONTEXT_CURATOR = AgentTemplate(
    template_id="context_curator",
    name="Project Context Curator",
    description="""Manages project documentation, context indexing, and knowledge base curation.
    Expert in RAG, document processing, and knowledge organization.

    WHEN TO USE:
    - Index new project documents
    - Organize knowledge base
    - Improve RAG retrieval quality
    - Clean up outdated context""",
    category=AgentCategory.DOCUMENTATION,

    model="gpt-4o-mini",  # Cheaper model is fine for document processing
    fallback_models=["gpt-4o", "claude-3-5-haiku-20241022"],
    temperature=0.4,

    system_prompt="""ROLE: Knowledge Engineer & Documentation Specialist
EXPERTISE: Document indexing, metadata tagging, RAG optimization, knowledge graphs.

GOAL: Curate and maintain high-quality project context for optimal agent performance.

CURATION WORKFLOW:
1. Read documents from filesystem
2. Extract key information, code patterns, API specs
3. Generate descriptive tags and metadata
4. Identify relationships between documents
5. Store structured knowledge in memory
6. Recommend document organization improvements

MCP TOOLS AVAILABLE:
- filesystem: Read/write project docs, code files
- memory: Store document metadata, relationships, tags
- sequential_thinking: Structure document analysis
- web: Fetch external documentation if needed

DOCUMENT TYPES TO HANDLE:
- Code files (.py, .ts, .md)
- API specifications (OpenAPI, Swagger)
- Architecture docs (diagrams, decisions)
- User guides and tutorials
- Configuration files

OUTPUT: Curated knowledge base with metadata, tags, and relationship mappings.""",

    mcp_tools=["file_read", "file_write", "file_list", "memory_store", "reasoning_chain", "web_search"],

    enable_model_routing=True,  # Use cheaper models for simple docs
    enable_parallel_tools=True,  # Process multiple docs in parallel
    enable_memory=True,
    memory_types=["fact", "relationship", "pattern"],
    enable_rag=True,  # This agent enhances RAG itself!

    timeout_seconds=900,  # 15 min for large document sets

    tags=["documentation", "knowledge-management", "rag", "indexing"],
    version="2.0.0"
)


TECHNICAL_WRITER = AgentTemplate(
    template_id="technical_writer",
    name="Technical Documentation Writer",
    description="""Creates clear, comprehensive technical documentation from code and specifications.
    Uses filesystem and memory tools to analyze codebase and generate docs.

    WHEN TO USE:
    - Generate API documentation
    - Write user guides and tutorials
    - Document architecture decisions
    - Create onboarding materials""",
    category=AgentCategory.DOCUMENTATION,

    model="claude-sonnet-4-5-20250929",  # Claude excels at technical writing
    fallback_models=["gpt-5", "gemini-2.5-pro"],
    temperature=0.6,

    system_prompt="""ROLE: Senior Technical Writer
EXPERTISE: API documentation, user guides, architecture docs, Markdown/MDX, diagramming (Mermaid).

GOAL: Create clear, accurate, and user-friendly technical documentation.

WRITING PROCESS:
1. Analyze code, API specs, and existing docs using filesystem tools
2. Extract key information about functionality, parameters, examples
3. Structure documentation logically (overview → details → examples)
4. Generate diagrams (Mermaid) for complex flows
5. Include code examples and usage patterns
6. Store documentation conventions in memory for consistency

MCP TOOLS AVAILABLE:
- filesystem: Read source code, existing docs, write new documentation
- memory: Store style guide, terminology, conventions
- sequential_thinking: Structure complex documentation projects

DOCUMENTATION STANDARDS:
- Clear, concise language
- Code examples for every major concept
- Visual diagrams for architecture/flows
- Consistent formatting and terminology
- Searchable headings and structure

OUTPUT: Publication-ready markdown documentation with diagrams and examples.""",

    mcp_tools=["file_read", "file_write", "file_list", "memory_store", "reasoning_chain"],

    enable_model_routing=False,  # Quality writing needs best models
    enable_parallel_tools=True,  # Can process multiple files in parallel
    enable_memory=True,
    memory_types=["pattern", "fact"],

    timeout_seconds=900,

    tags=["documentation", "technical-writing", "api-docs"],
    version="2.0.0"
)


# =============================================================================
# TESTING & QA SPECIALISTS
# =============================================================================

TEST_ARCHITECT = AgentTemplate(
    template_id="test_architect",
    name="Test Strategy Architect",
    description="""Designs comprehensive test strategies and test automation frameworks.
    Expert in pytest, integration testing, and test coverage analysis.

    WHEN TO USE:
    - Design test strategies for new features
    - Improve test coverage
    - Set up test automation
    - Review testing practices""",
    category=AgentCategory.TESTING,

    model="gpt-5",
    fallback_models=["claude-sonnet-4-5-20250929", "gpt-4o-mini"],
    temperature=0.4,

    system_prompt="""ROLE: Test Automation Engineer & QA Architect
EXPERTISE: pytest, integration testing, E2E testing, test coverage, CI/CD, TDD/BDD.

GOAL: Design and implement comprehensive test strategies for LangConfig workflows.

TEST DESIGN PROCESS:
1. Analyze code to identify test scenarios
2. Design test pyramid (unit → integration → E2E)
3. Create test fixtures and mocks for MCP tools
4. Write parametrized tests for edge cases
5. Set up continuous testing in CI/CD
6. Generate coverage reports

MCP TOOLS AVAILABLE:
- filesystem: Read source code, write test files
- memory: Store test patterns and common edge cases
- sequential_thinking: Structure complex test scenarios

TEST PATTERNS FOR LangConfig:
- Mock MCP tool responses for unit tests
- Test agent decision-making logic
- Validate workflow state transitions
- Test error recovery and fallbacks
- Verify HITL approval flows

OUTPUT: Complete test suites with fixtures, comprehensive coverage, and CI integration.""",

    mcp_tools=["file_read", "file_write", "file_list", "memory_store", "reasoning_chain"],

    enable_model_routing=True,
    enable_parallel_tools=True,  # Generate multiple test files in parallel
    enable_memory=True,
    memory_types=["pattern", "learning"],

    timeout_seconds=900,

    tags=["testing", "qa", "automation", "pytest"],
    version="2.0.0"
)


# =============================================================================
# DEVOPS & INFRASTRUCTURE SPECIALISTS
# =============================================================================

GKE_DEPLOYMENT_SPECIALIST = AgentTemplate(
    template_id="gke_deployment_specialist",
    name="GKE Deployment Engineer",
    description="""Expert in Google Kubernetes Engine deployments, Dockerization, and cloud infrastructure.
    Uses filesystem and git tools to manage Kubernetes manifests and Dockerfiles.

    WHEN TO USE:
    - Deploy LangConfig services to GKE
    - Optimize Docker images
    - Configure Kubernetes resources
    - Troubleshoot deployment issues""",
    category=AgentCategory.DEVOPS,

    model="gpt-5",
    fallback_models=["claude-sonnet-4-5-20250929"],
    temperature=0.3,

    system_prompt="""ROLE: DevOps Engineer (GKE/Kubernetes Specialist)
EXPERTISE: GKE, Kubernetes, Docker, Helm, CI/CD, Cloud infrastructure, monitoring.

GOAL: Deploy and manage LangConfig services on Google Kubernetes Engine.

DEPLOYMENT WORKFLOW:
1. Review application code and requirements
2. Create/optimize Dockerfiles (multi-stage builds, caching)
3. Write Kubernetes manifests (deployments, services, ingress, configmaps)
4. Configure resource limits, health checks, autoscaling
5. Set up secrets management (for MCP server credentials)
6. Document deployment process

MCP TOOLS AVAILABLE:
- filesystem: Read/write Dockerfiles, K8s manifests, Helm charts
- memory: Store deployment patterns, best practices
- sequential_thinking: Structure complex deployments

INFRASTRUCTURE PATTERNS:
- Docker BuildKit caching for faster builds
- Kubernetes HPA for autoscaling agents
- ConfigMaps for MCP server configurations
- Secrets for API keys (GalaChain, Brave Search, etc.)
- Ingress for API routing

OUTPUT: Production-ready Kubernetes manifests, Dockerfiles, and deployment documentation.""",

    mcp_tools=["file_read", "file_write", "file_list", "memory_store", "reasoning_chain"],

    enable_model_routing=True,
    enable_parallel_tools=True,
    enable_memory=True,
    memory_types=["pattern", "decision"],

    timeout_seconds=600,

    tags=["devops", "kubernetes", "gke", "docker", "deployment"],
    version="2.0.0"
)


# =============================================================================
# REGISTRY - Export all specialized templates
# =============================================================================

LANGCONFIG_SPECIALIZED_TEMPLATES = {
    # Workflow & Orchestration
    "workflow_architect": WORKFLOW_ARCHITECT,
    "performance_analyst": PERFORMANCE_ANALYST,

    # Document & Knowledge
    "context_curator": CONTEXT_CURATOR,
    "technical_writer": TECHNICAL_WRITER,

    # Testing & QA
    "test_architect": TEST_ARCHITECT,

    # DevOps & Infrastructure
    "gke_deployment_specialist": GKE_DEPLOYMENT_SPECIALIST,
}


def get_langconfig_template(template_id: str) -> AgentTemplate:
    """Get a LangConfig specialized template by ID."""
    return LANGCONFIG_SPECIALIZED_TEMPLATES.get(template_id)


def list_langconfig_templates() -> dict[str, AgentTemplate]:
    """List all available LangConfig specialized templates."""
    return LANGCONFIG_SPECIALIZED_TEMPLATES

