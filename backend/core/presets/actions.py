# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Action and Tool Presets Library for LangConfig.
Enhanced with JSON Schema validation, Risk Assessment, and HITL capabilities.

This provides a BANK of reusable MCP tools and custom actions that can be added to agents.
Each preset defines:
- Tool/action configuration with JSON Schema for parameters
- Risk levels for guardrails
- HITL requirements for safety-critical actions
- Documentation and best practices

Enhanced Features:
- JSON Schema for standardized input definitions (MCP compatibility)
- Granular risk level assessment (NONE, LOW, MEDIUM, HIGH)
- Structured action types
- New presets for RAG, Code Interpreter, Terminal Access, and Agentic capabilities
"""

from typing import Dict, List, Any, Optional
from enum import Enum
# Use langchain_core.pydantic_v1 for compatibility within the LangChain ecosystem
from pydantic import BaseModel, Field


class ActionCategory(str, Enum):
    """Categories of actions and tools."""
    FILESYSTEM = "filesystem"
    CODE_ANALYSIS = "code_analysis"
    VERSION_CONTROL = "version_control"
    TESTING = "testing"
    RESEARCH = "research"  # Covers Web Search and RAG
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    EXECUTION = "execution"  # Terminal/Code Interpreter
    COMMUNICATION = "communication"
    AGENTIC = "agentic"  # Reflection, A2A
    DOCUMENTATION = "documentation"
    CUSTOM = "custom"


class ActionType(str, Enum):
    """Implementation type of the action."""
    MCP_TOOL = "mcp_tool"
    CUSTOM_ACTION = "custom_action"
    API_INTEGRATION = "api_integration"


class RiskLevel(str, Enum):
    """Risk assessment levels for actions (Guardrails/Chapter 18)."""
    NONE = "none"          # Read-only, no side effects (e.g., git status, read file)
    LOW = "low"            # Minor, reversible side effects (e.g., create temp file)
    MEDIUM = "medium"      # Significant, potentially destructive but recoverable (e.g., git commit, write source file)
    HIGH = "high"          # Irreversible or major impact (e.g., deployment, database migration, raw terminal access)


class RuntimeRequirements(BaseModel):
    """
    Runtime context requirements for actions that need access to LangGraph ToolRuntime.

    ToolRuntime provides access to:
    - state: Current agent/workflow state
    - context: Conversation context
    - store: Long-term memory (LangGraph Store)
    - stream_writer: Real-time output streaming

    Example:
        RuntimeRequirements(
            requires_runtime=True,
            features=["store", "stream_writer"],
            example_code="runtime.store.put(('cache',), key, value)"
        )
    """
    requires_runtime: bool = Field(
        default=False,
        description="If True, this action expects ToolRuntime for state/context/store access."
    )
    features: List[str] = Field(
        default_factory=list,
        description="Required runtime features: ['state', 'context', 'store', 'stream_writer']"
    )
    example_code: Optional[str] = Field(
        default=None,
        description="Example code showing how to use this action with ToolRuntime."
    )


class ExecutionConstraint(BaseModel):
    """
    Execution-time constraints and guardrails for actions.

    Prevents runaway processes, resource conflicts, and ensures safe execution.

    Example:
        ExecutionConstraint(
            max_duration_seconds=60,  # Kill after 1 minute
            max_retries=0,            # No retries
            exclusive=True,           # Block other actions
            timeout_strategy="kill"
        )
    """
    max_duration_seconds: Optional[int] = Field(
        default=None,
        description="Maximum execution time in seconds. Action is killed if exceeded."
    )
    max_retries: int = Field(
        default=1,
        description="Number of retries if action fails (default: 1)."
    )
    timeout_strategy: str = Field(
        default="kill",
        description="How to handle timeout: 'kill' (hard stop) or 'graceful_shutdown' (request stop)."
    )
    allow_parallel: bool = Field(
        default=True,
        description="Whether this action can run in parallel with other actions."
    )
    exclusive: bool = Field(
        default=False,
        description="If True, no other actions can run while this executes (e.g., Docker build)."
    )


class PerformanceEstimate(BaseModel):
    """
    Performance characteristics for UI indicators and user expectations.

    Used to show 'fast/medium/slow' indicators in UI and help users choose appropriate actions.
    """
    typical_duration_seconds: Optional[float] = Field(
        default=None,
        description="Typical execution time in seconds (for UI estimates)."
    )
    is_io_bound: bool = Field(
        default=True,
        description="True if action is I/O bound (network, file), False if CPU bound."
    )


class Compatibility(BaseModel):
    """
    Compatibility requirements for actions that need specific LangChain features or models.
    """
    min_langchain_version: str = Field(
        default="0.1.0",
        description="Minimum required LangChain version."
    )
    required_features: List[str] = Field(
        default_factory=list,
        description="Required LangChain features (e.g., ['tool_calling', 'structured_output'])."
    )


class ActionPreset(BaseModel):
    """
    Reusable action/tool configuration preset with integrated safety metadata.

    Example Usage:
        >>> preset = ActionPresetRegistry.get("filesystem_read")
        >>> # Check risk level before execution
        >>> if preset.risk_level == RiskLevel.HIGH and not preset.requires_approval:
        ...     logger.warning("High-risk action without approval requirement!")
    """
    preset_id: str = Field(..., description="Unique preset identifier")
    name: str = Field(..., description="Display name")
    # Description optimized for LLM understanding (Chapter 5)
    description: str = Field(
        ...,
        description="Detailed description: What the tool does, when to use it, and its expected output."
    )
    category: ActionCategory

    # Implementation Details
    action_type: ActionType = ActionType.MCP_TOOL
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Implementation-specific configuration (e.g., MCP server ID, service name)."
    )

    # ENHANCEMENT: JSON Schema for Parameters (Standardization/MCP Chapter 10)
    input_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []},
        description="JSON Schema defining the input parameters."
    )

    # Documentation
    usage_example: Optional[str] = None
    best_practices: List[str] = Field(default_factory=list)

    # Safety and HITL (Chapter 13/18)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = Field(
        default=False,
        description="[GUARDRAIL] If True, this action MUST pause the workflow for human approval (HITL) before execution."
    )

    # Metadata
    tags: List[str] = Field(default_factory=list)
    version: str = Field(default="2.0.0")
    is_public: bool = Field(default=True)

    # ENHANCEMENT: Runtime Context Support (LangGraph ToolRuntime integration)
    runtime: RuntimeRequirements = Field(
        default_factory=RuntimeRequirements,
        description="Runtime context requirements for stateful operations."
    )

    # ENHANCEMENT: Execution Constraints (Production Safety)
    constraints: ExecutionConstraint = Field(
        default_factory=ExecutionConstraint,
        description="Execution-time constraints and guardrails."
    )

    # ENHANCEMENT: Output Validation (Structured outputs)
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema defining expected output structure (optional, for structured outputs)."
    )

    # ENHANCEMENT: Middleware Coordination (References to middleware_presets.py)
    recommended_middleware: List[str] = Field(
        default_factory=list,
        description="Recommended middleware preset IDs from middleware_presets.py (e.g., ['logging', 'cost_tracking'])."
    )

    # ENHANCEMENT: Performance Metadata (UX indicators)
    performance: PerformanceEstimate = Field(
        default_factory=PerformanceEstimate,
        description="Performance characteristics for UI indicators."
    )

    # ENHANCEMENT: Compatibility Requirements
    compatibility: Compatibility = Field(
        default_factory=Compatibility,
        description="Compatibility requirements for LangChain features."
    )


# =============================================================================
# ACTION PRESET LIBRARY - Enhanced Bank of Tools/Actions
# =============================================================================

# ---- FILESYSTEM TOOLS ----

FILESYSTEM_READ = ActionPreset(
    preset_id="filesystem_read",
    name="Filesystem Read/List",
    description="Read file contents or list directory structures. Use this to understand the codebase structure or access configuration files. Safe, read-only operation.",
    category=ActionCategory.FILESYSTEM,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "filesystem", "operations": ["read", "list"]},
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file or directory path."},
            "recursive": {"type": "boolean", "default": False, "description": "For directories, list contents recursively."}
        },
        "required": ["path"]
    },
    usage_example="""
# Read a file
result = filesystem_read(path="src/main.py")

# List directory
files = filesystem_read(path="src/", recursive=True)
""",
    best_practices=[
        "Always validate paths exist before reading",
        "Use relative paths when possible",
        "Be mindful of large files"
    ],
    risk_level=RiskLevel.NONE,  # Read-only, completely safe
    tags=["filesystem", "read", "safe"]
)

FILESYSTEM_WRITE = ActionPreset(
    preset_id="filesystem_write",
    name="Filesystem Write/Modify",
    description="Write, create, or modify files on the disk. Use this to implement code changes or update configuration. Potentially destructive but recoverable via version control.",
    category=ActionCategory.FILESYSTEM,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "filesystem", "operations": ["write", "create", "update"]},
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "The file path to write to."},
            "content": {"type": "string", "description": "The content to write."},
            "create_dirs": {"type": "boolean", "default": True, "description": "Create parent directories if they don't exist."}
        },
        "required": ["path", "content"]
    },
    usage_example="""
# Write to file
filesystem_write(
    path="src/new_file.py",
    content="def hello(): pass",
    create_dirs=True
)
""",
    best_practices=[
        "Validate content syntax before writing",
        "Prefer atomic writes",
        "Back up critical files before modifying",
        "Follow project conventions"
    ],
    risk_level=RiskLevel.MEDIUM,  # Potentially destructive but recoverable
    tags=["filesystem", "write", "modify"]
)

# ---- VERSION CONTROL ----

GIT_STATUS = ActionPreset(
    preset_id="git_status",
    name="Git Status",
    description="Check git repository status. Read-only operation that shows current branch, modified files, and staging area state.",
    category=ActionCategory.VERSION_CONTROL,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "git", "command": "status"},
    input_schema={
        "type": "object",
        "properties": {
            "show_untracked": {"type": "boolean", "default": True}
        },
        "required": []
    },
    usage_example="""
# Get repo status
status = git_status()
print(f"Branch: {status['branch']}")
print(f"Changes: {len(status['modified_files'])}")
""",
    best_practices=[
        "Check status before making changes",
        "Use to validate clean working tree"
    ],
    risk_level=RiskLevel.NONE,  # Read-only
    tags=["git", "status", "vcs", "safe"],
    # ENHANCED: Output validation for git status structure
    output_schema={
        "type": "object",
        "properties": {
            "branch": {"type": "string", "description": "Current branch name"},
            "modified_files": {"type": "array", "items": {"type": "string"}, "description": "List of modified files"},
            "untracked_files": {"type": "array", "items": {"type": "string"}, "description": "List of untracked files"},
            "staged_files": {"type": "array", "items": {"type": "string"}, "description": "List of staged files"},
            "is_clean": {"type": "boolean", "description": "True if working tree is clean"},
            "ahead": {"type": "integer", "description": "Commits ahead of remote"},
            "behind": {"type": "integer", "description": "Commits behind remote"}
        },
        "required": ["branch", "is_clean"]
    },
    performance=PerformanceEstimate(
        typical_duration_seconds=0.5,  # Very fast
        is_io_bound=True  # Git repository I/O
    )
)

GIT_COMMIT = ActionPreset(
    preset_id="git_commit",
    name="Git Commit",
    description="Commit changes to git repository. Creates permanent history entry. Reversible via git revert but adds to history.",
    category=ActionCategory.VERSION_CONTROL,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "git", "command": "commit"},
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The commit message."},
            "add_all": {"type": "boolean", "default": False, "description": "Stage all changes before committing."},
            "amend": {"type": "boolean", "default": False, "description": "Amend the previous commit."}
        },
        "required": ["message"]
    },
    usage_example="""
# Commit changes
git_commit(
    message="feat: Add new feature",
    add_all=True
)
""",
    best_practices=[
        "Write clear, descriptive commit messages",
        "Follow conventional commits format",
        "Keep commits atomic and focused",
        "Review changes before committing"
    ],
    risk_level=RiskLevel.MEDIUM,  # Permanent history but reversible
    tags=["git", "commit", "vcs"]
)

# ---- EXECUTION (NEW) ----

TERMINAL_ACCESS = ActionPreset(
    preset_id="terminal_access",
    name="Terminal Access (Restricted)",
    description="Execute shell commands in a restricted environment. Use for running build scripts, package managers, or complex diagnostics. High risk due to potential system-level impact.",
    category=ActionCategory.EXECUTION,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "terminal"},
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout_seconds": {"type": "integer", "default": 60, "description": "Command timeout in seconds."},
            "working_directory": {"type": "string", "description": "Working directory for command execution."}
        },
        "required": ["command"]
    },
    usage_example="""
# Run build script
terminal_access(
    command="npm run build",
    timeout_seconds=300,
    working_directory="./frontend"
)
""",
    best_practices=[
        "Use only when specific tools are unavailable",
        "Sanitize inputs rigorously",
        "Set reasonable timeouts",
        "Avoid destructive commands without confirmation"
    ],
    risk_level=RiskLevel.HIGH,  # High risk: system-level access
    requires_approval=True,  # HITL required for safety
    tags=["terminal", "shell", "execute", "high-risk"],
    # ENHANCED: Strict execution constraints for safety
    constraints=ExecutionConstraint(
        max_duration_seconds=60,  # Kill after 1 minute by default
        max_retries=0,            # No retries for terminal commands (too risky)
        timeout_strategy="kill",  # Hard kill on timeout
        exclusive=False,          # Can run with other actions (but with caution)
        allow_parallel=True       # Allow parallel, but HITL will gate this
    ),
    recommended_middleware=["logging", "cost_tracking"],  # Always log terminal access
    performance=PerformanceEstimate(
        typical_duration_seconds=5.0,  # Varies widely, 5s is estimate
        is_io_bound=True  # Mostly I/O and external process execution
    )
)

CODE_INTERPRETER_PYTHON = ActionPreset(
    preset_id="code_interpreter_python",
    name="Python Code Interpreter (PALM)",
    description="Execute Python code in a secure sandbox for data analysis, calculations, or complex logic (Chapter 17). Isolated execution environment with limited system access.",
    category=ActionCategory.EXECUTION,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "code_interpreter", "language": "python"},
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "The Python code snippet to execute."},
            "timeout_seconds": {"type": "integer", "default": 30}
        },
        "required": ["code"]
    },
    usage_example="""
# Execute Python for data analysis
code_interpreter_python(
    code='''
import pandas as pd
data = pd.read_csv("data.csv")
print(data.describe())
'''
)
""",
    best_practices=[
        "Write isolated Python scripts",
        "Handle potential errors within the script",
        "Use for calculations, not system operations",
        "Validate inputs before execution"
    ],
    risk_level=RiskLevel.MEDIUM,  # Sandboxed but still code execution
    tags=["python", "interpreter", "PALM", "data-analysis", "Chapter-17"]
)

# ---- RESEARCH (RAG/Chapter 14) ----

RAG_SEARCH_INTERNAL = ActionPreset(
    preset_id="rag_search_internal",
    name="Internal Knowledge Search (RAG)",
    description="Semantic search over the internal knowledge base (VectorDB). Use for finding guidelines, past decisions, internal documentation, and project-specific context. Read-only operation.",
    category=ActionCategory.RESEARCH,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "rag_retriever", "scope": "internal"},
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language query for semantic search."},
            "top_k": {"type": "integer", "default": 5, "description": "Number of results to return."},
            "min_relevance": {"type": "number", "default": 0.7, "description": "Minimum relevance score (0.0-1.0)."}
        },
        "required": ["query"]
    },
    usage_example="""
# Search internal knowledge
results = rag_search_internal(
    query="authentication best practices for this project",
    top_k=5,
    min_relevance=0.75
)
for result in results:
    print(f"Relevance: {result['score']}: {result['content'][:100]}")
""",
    best_practices=[
        "Use specific, detailed queries",
        "Combine with web search for comprehensive research",
        "Filter by relevance threshold",
        "Cite sources in final output"
    ],
    risk_level=RiskLevel.NONE,  # Read-only search
    tags=["rag", "knowledge", "search", "internal", "Chapter-14"],
    # ENHANCED: Runtime context for caching and streaming
    runtime=RuntimeRequirements(
        requires_runtime=True,
        features=["store", "stream_writer"],
        example_code="""
# Example: Cache RAG results in long-term memory
from langchain.tools import tool, ToolRuntime

@tool
def rag_search_with_cache(query: str, runtime: ToolRuntime) -> str:
    # Check cache first
    cache_key = f"rag_cache:{query}"
    cached = runtime.store.get(("rag_cache",), cache_key)
    if cached:
        runtime.stream_writer(f"📚 Using cached result for: {query}")
        return cached.value

    # Search if not cached
    runtime.stream_writer(f"🔍 Searching knowledge base: {query}")
    results = perform_rag_search(query)

    # Cache for future use
    runtime.store.put(("rag_cache",), cache_key, results)
    return results
"""
    ),
    performance=PerformanceEstimate(
        typical_duration_seconds=2.0,  # Vector search is fast
        is_io_bound=True  # Database I/O
    )
)

WEB_SEARCH = ActionPreset(
    preset_id="web_search",
    name="Web Search",
    description="Search the web for current information, documentation, and best practices. Use for research tasks requiring up-to-date external knowledge.",
    category=ActionCategory.RESEARCH,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "web_search", "max_results": 10},
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
            "site": {"type": "string", "description": "Restrict search to specific site (e.g., 'stackoverflow.com')."},
            "date_range": {"type": "string", "description": "Date range filter (e.g., 'past_year')."}
        },
        "required": ["query"]
    },
    usage_example="""
# Search for documentation
results = web_search(
    query="React hooks best practices",
    site="react.dev"
)
""",
    best_practices=[
        "Use specific search queries",
        "Prefer official documentation",
        "Verify information from multiple sources",
        "Combine with RAG for complete context"
    ],
    risk_level=RiskLevel.NONE,  # Read-only
    tags=["web-search", "research", "documentation"]
)

# ---- AGENTIC (Reflection/Chapter 4) ----

SELF_REFLECTION_CRITIQUE = ActionPreset(
    preset_id="self_reflection_critique",
    name="Self-Reflection Critique",
    description="Agent analyzes its own proposed plan or output against specific criteria. Used internally by agents to improve quality before execution (Chapter 4 - Reflection).",
    category=ActionCategory.AGENTIC,
    action_type=ActionType.CUSTOM_ACTION,
    config={"service": "reflection_engine"},
    input_schema={
        "type": "object",
        "properties": {
            "content_to_review": {"type": "string", "description": "The plan or output to review."},
            "criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of criteria to evaluate against (e.g., ['security', 'efficiency', 'maintainability'])."
            }
        },
        "required": ["content_to_review", "criteria"]
    },
    usage_example="""
# Reflect on proposed implementation
critique = self_reflection_critique(
    content_to_review=proposed_code,
    criteria=["security", "performance", "maintainability"]
)
if critique['issues']:
    # Revise based on feedback
    pass
""",
    best_practices=[
        "Use before committing to decisions",
        "Define clear, specific criteria",
        "Act on feedback received",
        "Iterate until criteria are met"
    ],
    risk_level=RiskLevel.NONE,  # Internal analysis only
    tags=["reflection", "quality", "internal", "Chapter-4"]
)

# ---- CODE ANALYSIS ----

SYNTAX_CHECK = ActionPreset(
    preset_id="syntax_check",
    name="Syntax Checker",
    description="Validate code syntax without execution. Fast and safe analysis.",
    category=ActionCategory.CODE_ANALYSIS,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "code_analysis", "operation": "syntax_check"},
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Code to validate."},
            "language": {"type": "string", "description": "Programming language (e.g., 'python', 'javascript')."},
            "strict_mode": {"type": "boolean", "default": True}
        },
        "required": ["code", "language"]
    },
    usage_example="""
# Check Python syntax
result = syntax_check(
    code="def hello(): print('hi')",
    language="python"
)
""",
    best_practices=[
        "Always check syntax before writing to files",
        "Use strict mode for production code"
    ],
    risk_level=RiskLevel.NONE,  # Read-only analysis
    tags=["code-analysis", "syntax", "validation", "safe"]
)

LINT_CODE = ActionPreset(
    preset_id="lint_code",
    name="Code Linter",
    description="Lint code for style and quality issues. Can auto-fix minor issues.",
    category=ActionCategory.CODE_ANALYSIS,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "code_analysis", "operation": "lint"},
    input_schema={
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "language": {"type": "string"},
            "config_file": {"type": "string", "description": "Path to linter config."},
            "auto_fix": {"type": "boolean", "default": False}
        },
        "required": ["code", "language"]
    },
    best_practices=[
        "Run linter before commits",
        "Use project-specific config",
        "Auto-fix when safe"
    ],
    risk_level=RiskLevel.NONE,  # Read-only (auto_fix is separate action)
    tags=["code-analysis", "linting", "quality"]
)

# ---- TESTING ----

RUN_TESTS = ActionPreset(
    preset_id="run_tests",
    name="Test Runner",
    description="Execute test suites. Can be slow but essential for validation. Read-only in terms of production code.",
    category=ActionCategory.TESTING,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "test_runner", "framework": "pytest"},
    input_schema={
        "type": "object",
        "properties": {
            "test_path": {"type": "string", "description": "Path to tests."},
            "verbose": {"type": "boolean", "default": True},
            "coverage": {"type": "boolean", "default": True},
            "parallel": {"type": "boolean", "default": True}
        },
        "required": ["test_path"]
    },
    usage_example="""
# Run tests with coverage
result = run_tests(
    test_path="tests/",
    coverage=True,
    parallel=True
)
""",
    best_practices=[
        "Run tests after code changes",
        "Use parallel execution for speed",
        "Track coverage trends",
        "Fix failing tests immediately"
    ],
    risk_level=RiskLevel.LOW,  # Can create temp files but no production impact
    tags=["testing", "qa", "validation"],
    # ENHANCED: Output validation for structured test results
    output_schema={
        "type": "object",
        "properties": {
            "passed": {"type": "integer", "description": "Number of passing tests"},
            "failed": {"type": "integer", "description": "Number of failing tests"},
            "skipped": {"type": "integer", "description": "Number of skipped tests"},
            "coverage_percent": {"type": "number", "minimum": 0, "maximum": 100, "description": "Code coverage percentage"},
            "duration_seconds": {"type": "number", "description": "Total test execution time"},
            "failures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "test_name": {"type": "string"},
                        "error_message": {"type": "string"},
                        "traceback": {"type": "string"}
                    }
                }
            }
        },
        "required": ["passed", "failed"]
    },
    performance=PerformanceEstimate(
        typical_duration_seconds=30.0,  # Varies widely based on test suite size
        is_io_bound=False  # Mostly CPU bound (test execution)
    )
)

# ---- INFRASTRUCTURE ----

DOCKER_BUILD = ActionPreset(
    preset_id="docker_build",
    name="Docker Build",
    description="Build Docker images. Resource-intensive and can affect local Docker daemon. Requires Docker daemon running.",
    category=ActionCategory.INFRASTRUCTURE,
    action_type=ActionType.MCP_TOOL,
    config={"mcp_server": "docker", "operation": "build"},
    input_schema={
        "type": "object",
        "properties": {
            "dockerfile": {"type": "string", "description": "Path to Dockerfile."},
            "tag": {"type": "string", "description": "Image tag."},
            "context": {"type": "string", "default": ".", "description": "Build context path."},
            "no_cache": {"type": "boolean", "default": False},
            "build_args": {"type": "object", "default": {}}
        },
        "required": ["dockerfile", "tag"]
    },
    usage_example="""
# Build Docker image
result = docker_build(
    dockerfile="Dockerfile",
    tag="myapp:latest",
    context="."
)
""",
    best_practices=[
        "Use .dockerignore to speed builds",
        "Layer Dockerfile for caching",
        "Tag images semantically",
        "Scan images for vulnerabilities"
    ],
    risk_level=RiskLevel.HIGH,  # System-level resource usage
    requires_approval=True,  # HITL required
    tags=["docker", "infrastructure", "deployment", "high-risk"],
    # ENHANCED: Strict constraints for resource-intensive operations
    constraints=ExecutionConstraint(
        max_duration_seconds=600,  # 10 minutes max for build
        max_retries=1,             # Allow one retry on failure
        timeout_strategy="graceful_shutdown",  # Try to stop gracefully
        exclusive=True,            # No other actions while Docker builds
        allow_parallel=False       # Must run alone
    ),
    recommended_middleware=["logging", "cost_tracking"],  # Track build times and costs
    performance=PerformanceEstimate(
        typical_duration_seconds=120.0,  # 2 minutes typical, varies greatly
        is_io_bound=True  # Heavy disk and network I/O
    )
)

# ---- CUSTOM ACTIONS ----

AIDER_EDIT = ActionPreset(
    preset_id="aider_edit",
    name="Aider Edit",
    description="Use Aider to edit code with AI assistance. Git-aware and powerful. Can make significant code changes.",
    category=ActionCategory.CUSTOM,
    action_type=ActionType.CUSTOM_ACTION,
    config={"service": "aider", "auto_commit": True},
    input_schema={
        "type": "object",
        "properties": {
            "files": {"type": "array", "items": {"type": "string"}, "description": "Files to edit."},
            "instruction": {"type": "string", "description": "Editing instruction."},
            "model": {"type": "string", "default": "gpt-4o"},
            "yes_to_all": {"type": "boolean", "default": False}
        },
        "required": ["files", "instruction"]
    },
    usage_example="""
# Edit code with Aider
result = aider_edit(
    files=["src/main.py"],
    instruction="Add error handling to the main function"
)
""",
    best_practices=[
        "Be specific in instructions",
        "Review changes before accepting",
        "Use for focused edits",
        "Keep file list small"
    ],
    risk_level=RiskLevel.MEDIUM,  # Code changes but version controlled
    tags=["aider", "code-generation", "ai"]
)


# =============================================================================
# ACTION PRESET REGISTRY
# =============================================================================

class ActionPresetRegistry:
    """Registry of available action presets."""

    _presets: Dict[str, ActionPreset] = {}

    @classmethod
    def register(cls, preset: ActionPreset):
        """Register a preset in the library."""
        cls._presets[preset.preset_id] = preset

    @classmethod
    def get(cls, preset_id: str) -> Optional[ActionPreset]:
        """Get preset by ID."""
        return cls._presets.get(preset_id)

    @classmethod
    def list_all(cls) -> List[ActionPreset]:
        """List all presets."""
        return list(cls._presets.values())

    @classmethod
    def list_by_category(cls, category: ActionCategory) -> List[ActionPreset]:
        """List presets in a category."""
        return [p for p in cls._presets.values() if p.category == category]

    @classmethod
    def list_by_risk_level(cls, risk_level: RiskLevel) -> List[ActionPreset]:
        """List presets by risk level."""
        return [p for p in cls._presets.values() if p.risk_level == risk_level]

    @classmethod
    def get_safe_actions(cls) -> List[ActionPreset]:
        """Get all safe (no risk) actions."""
        return [p for p in cls._presets.values() if p.risk_level == RiskLevel.NONE]

    @classmethod
    def get_high_risk_actions(cls) -> List[ActionPreset]:
        """Get all high-risk actions requiring careful use."""
        return [p for p in cls._presets.values() if p.risk_level == RiskLevel.HIGH]

    @classmethod
    def search(cls, query: str) -> List[ActionPreset]:
        """Search presets by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for preset in cls._presets.values():
            if (query_lower in preset.name.lower() or
                query_lower in preset.description.lower() or
                any(query_lower in tag for tag in preset.tags)):
                results.append(preset)
        return results


# Register all built-in presets
for preset in [
    FILESYSTEM_READ,
    FILESYSTEM_WRITE,
    GIT_STATUS,
    GIT_COMMIT,
    TERMINAL_ACCESS,
    CODE_INTERPRETER_PYTHON,
    RAG_SEARCH_INTERNAL,
    WEB_SEARCH,
    SELF_REFLECTION_CRITIQUE,
    SYNTAX_CHECK,
    LINT_CODE,
    RUN_TESTS,
    DOCKER_BUILD,
    AIDER_EDIT,
]:
    ActionPresetRegistry.register(preset)


# =============================================================================
# API HELPER FUNCTIONS
# =============================================================================

def get_action_library() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get action library organized by category for UI display.

    Returns:
        Dictionary mapping category names to preset summaries with enhanced metadata
    """
    library = {}
    for category in ActionCategory:
        presets = ActionPresetRegistry.list_by_category(category)
        library[category.value] = [
            {
                "preset_id": p.preset_id,
                "name": p.name,
                "description": p.description,
                "action_type": p.action_type.value,
                "tags": p.tags,
                "safety": {
                    "risk_level": p.risk_level.value,
                    "requires_approval": p.requires_approval
                },
                # ENHANCED: New fields for production features
                "runtime": {
                    "requires_runtime": p.runtime.requires_runtime,
                    "features": p.runtime.features
                } if p.runtime.requires_runtime else None,
                "constraints": {
                    "max_duration_seconds": p.constraints.max_duration_seconds,
                    "exclusive": p.constraints.exclusive,
                    "allow_parallel": p.constraints.allow_parallel
                } if p.constraints.max_duration_seconds or p.constraints.exclusive else None,
                "performance": {
                    "typical_duration_seconds": p.performance.typical_duration_seconds,
                    "is_io_bound": p.performance.is_io_bound
                } if p.performance.typical_duration_seconds else None,
                "recommended_middleware": p.recommended_middleware if p.recommended_middleware else None,
                "has_output_schema": p.output_schema is not None
            }
            for p in presets
        ]
    return library


def get_recommended_actions_for_agent(agent_template_id: str) -> List[str]:
    """
    Get recommended actions for an agent template.

    This maps agent types to useful actions.
    """
    recommendations = {
        "code_implementer": [
            "filesystem_read",
            "filesystem_write",
            "git_status",
            "git_commit",
            "syntax_check",
            "aider_edit"
        ],
        "system_architect": [
            "filesystem_read",
            "rag_search_internal",
            "web_search",
            "self_reflection_critique"
        ],
        "code_reviewer": [
            "filesystem_read",
            "lint_code",
            "syntax_check",
            "git_status"
        ],
        "test_generator": [
            "filesystem_read",
            "filesystem_write",
            "run_tests",
            "syntax_check"
        ],
        "qa_validator": [
            "run_tests",
            "lint_code",
            "syntax_check"
        ],
        "devops_automation": [
            "docker_build",
            "terminal_access",  # With HITL approval
            "git_status",
            "git_commit"
        ],
        "research_agent": [
            "web_search",
            "rag_search_internal",
            "filesystem_read"
        ]
    }

    return recommendations.get(agent_template_id, [])
