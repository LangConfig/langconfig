# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
MCP (Model Context Protocol) Tool Schemas

Defines the structure for MCP tool configurations, assignments, and capabilities.
MCP enables agents to use external tools through a standardized protocol.
"""

import os
import platform
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from enum import Enum

# Platform-specific command
NPX_CMD = "npx.cmd" if platform.system() == "Windows" else "npx"


class MCPServerType(str, Enum):
    """Available MCP server types"""
    FILESYSTEM = "filesystem"
    WEB = "web"
    CODE_EXECUTION = "code_execution"
    GIT = "git"
    GITLAB = "gitlab"
    ATLASSIAN = "atlassian"
    DATABASE = "database"
    BROWSER = "browser"
    SEARCH = "search"
    TIME = "time"
    MEMORY = "memory"
    SEQUENTIAL_THINKING = "sequential_thinking"
    CUSTOM = "custom"


class MCPToolCapability(BaseModel):
    """Describes what an MCP tool can do"""
    name: str = Field(..., description="Tool name (e.g., 'gala_chain_deploy')")
    description: str = Field(..., description="Human-readable description")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for tool inputs")
    category: str = Field(default="general", description="Tool category")


class BlockchainConfig(BaseModel):
    """Blockchain-specific configuration for MCP servers"""
    is_blockchain: bool = Field(default=False, description="Whether this is a blockchain MCP server")
    blockchain_type: Optional[str] = Field(None, description="Type of blockchain (gala_chain, ethereum, etc.)")
    requires_credentials: bool = Field(default=False, description="Whether blockchain credentials are required")
    credential_types: List[str] = Field(default_factory=list, description="Supported credential types")


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server instance"""
    
    server_type: MCPServerType = Field(..., description="Type of MCP server")
    
    server_id: str = Field(
        ..., 
        description="Unique identifier for this server instance",
        example="gala-chain-launchpad-1"
    )
    
    display_name: str = Field(
        ...,
        description="Human-readable name",
        example="Gala Chain Launchpad"
    )
    
    npm_package: Optional[str] = Field(
        None,
        description="NPM package name if applicable",
        example="@gala-chain/launchpad-mcp-server"
    )
    
    command: List[str] = Field(
        ...,
        description="Command to start the MCP server",
        example=["npx", "-y", "@gala-chain/launchpad-mcp-server"]
    )
    
    env_vars: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the server"
    )
    
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Server-specific configuration"
    )
    
    enabled: bool = Field(
        default=True,
        description="Whether this server is active"
    )
    
    capabilities: List[MCPToolCapability] = Field(
        default_factory=list,
        description="Available tools from this server"
    )
    
    blockchain_config: Optional[BlockchainConfig] = Field(
        None,
        description="Blockchain-specific configuration if applicable"
    )


class MCPToolAssignment(BaseModel):
    """Assigns specific MCP tools to a workflow node"""
    
    server_id: str = Field(
        ...,
        description="ID of the MCP server providing the tool"
    )
    
    tool_name: str = Field(
        ...,
        description="Name of the tool to use",
        example="gala_chain_deploy_contract"
    )
    
    enabled: bool = Field(
        default=True,
        description="Whether this tool is active for the node"
    )
    
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific configuration overrides"
    )


class NodeMCPConfig(BaseModel):
    """MCP tool configuration for a workflow node"""
    
    tools: List[MCPToolAssignment] = Field(
        default_factory=list,
        description="List of MCP tools assigned to this node"
    )
    
    allow_all_tools: bool = Field(
        default=False,
        description="Whether to allow all available tools (unsafe for production)"
    )
    
    tool_choice: Literal["auto", "required", "none"] = Field(
        default="auto",
        description="How the agent should use tools"
    )


class MCPToolInvocation(BaseModel):
    """Request to invoke an MCP tool"""
    
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=30, description="Timeout in seconds")


class MCPToolResult(BaseModel):
    """Result from an MCP tool invocation"""
    
    success: bool
    tool_name: str
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = Field(description="Execution time in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Pre-configured MCP servers
#
# This dictionary contains MCP server templates organized into two categories:
#
# CORE SERVERS (Essential - enabled by default where appropriate):
#   - filesystem: Local file system operations
#   - git: Version control operations
#   - web: Web search and fetch capabilities
#   - sequential_thinking: Enhanced reasoning and planning
#   - time: Date and time operations
#   - memory: Persistent agent memory
#   - github: GitHub integration
#   - test_runner: Run tests (pytest, jest)
#   - static_analyzer: Code quality tools (pylint, mypy, eslint, tsc)
#
# EXAMPLE SERVERS (Optional templates - disabled by default):
#   - code_execution: Execute code (security risk, use with caution)
#   - database: Database operations (requires configuration)
#   - puppeteer: Browser automation
#   - chrome_devtools: Visual browser interaction
#   - brave_search: Web search (requires API key)
#   - gitlab: GitLab CI/CD integration
#   - atlassian: Jira, Confluence, Compass integration
#   - slack: Slack messaging integration
#   - google_drive: Google Drive integration
#   - everart: AI art generation
#
# Users can enable EXAMPLE servers or use them as templates for custom integrations.
BUILTIN_MCP_SERVERS = {
    # Filesystem operations
    "filesystem": MCPServerConfig(
        server_type=MCPServerType.FILESYSTEM,
        server_id="filesystem-local",
        display_name="Local Filesystem",
        npm_package="@modelcontextprotocol/server-filesystem",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-filesystem", "/app"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]  # Will be discovered at runtime
    ),

    # Git operations
    "git": MCPServerConfig(
        server_type=MCPServerType.GIT,
        server_id="git-local",
        display_name="Git Version Control",
        npm_package="@modelcontextprotocol/server-git",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-git"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),

    # Code execution (for testing/validation)
    "code_execution": MCPServerConfig(
        server_type=MCPServerType.CODE_EXECUTION,
        server_id="code-execution-local",
        display_name="Code Execution",
        npm_package="@modelcontextprotocol/server-execution",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-execution"],
        env_vars={},
        enabled=False,  # Disabled by default for safety
        capabilities=[]
    ),
    
    # Web/HTTP requests
    "web": MCPServerConfig(
        server_type=MCPServerType.WEB,
        server_id="web-search",
        display_name="Web Search & Fetch",
        npm_package="@modelcontextprotocol/server-fetch",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-fetch"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),
    
    # Database operations
    "database": MCPServerConfig(
        server_type=MCPServerType.DATABASE,
        server_id="database-tools",
        display_name="Database Tools",
        npm_package="@modelcontextprotocol/server-postgres",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-postgres"],
        env_vars={},
        enabled=False,  # Needs database connection config
        capabilities=[]
    ),

    # Brave Search (web search with API)
    "brave_search": MCPServerConfig(
        server_type=MCPServerType.SEARCH,
        server_id="brave-search",
        display_name="Brave Search",
        npm_package="@modelcontextprotocol/server-brave-search",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-brave-search"],
        env_vars={},
        enabled=False,  # Needs BRAVE_API_KEY environment variable
        capabilities=[]
    ),
    
    # Puppeteer (browser automation)
    "puppeteer": MCPServerConfig(
        server_type=MCPServerType.BROWSER,
        server_id="puppeteer-browser",
        display_name="Browser Automation (Puppeteer)",
        npm_package="@modelcontextprotocol/server-puppeteer",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-puppeteer"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),
    
    # Chrome DevTools MCP (visual browser interaction)
    "chrome_devtools": MCPServerConfig(
        server_type=MCPServerType.BROWSER,
        server_id="chrome-devtools",
        display_name="Chrome DevTools (Visual Browser)",
        npm_package="chrome-devtools-mcp",
        command=[NPX_CMD, "-y", "chrome-devtools-mcp@latest", "--headless=false"],
        env_vars={},
        enabled=True,  # Enable for visual web interaction
        capabilities=[]  # Will be discovered at runtime (26 tools)
    ),

    # Sequential Thinking (reasoning/planning)
    "sequential_thinking": MCPServerConfig(
        server_type=MCPServerType.SEQUENTIAL_THINKING,
        server_id="sequential-thinking",
        display_name="Sequential Thinking",
        npm_package="@modelcontextprotocol/server-sequential-thinking",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-sequential-thinking"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),

    # Time server (date/time operations)
    "time": MCPServerConfig(
        server_type=MCPServerType.TIME,
        server_id="time-tools",
        display_name="Time & Date Tools",
        npm_package="@modelcontextprotocol/server-time",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-time"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),

    # Memory server (persistent agent memory)
    "memory": MCPServerConfig(
        server_type=MCPServerType.MEMORY,
        server_id="memory-tools",
        display_name="Memory Store",
        npm_package="@modelcontextprotocol/server-memory",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-memory"],
        env_vars={},
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),

    # GitHub integration
    "github": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="github-tools",
        display_name="GitHub Integration",
        npm_package="@modelcontextprotocol/server-github",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-github"],
        env_vars={
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
        },
        enabled=True,  # Re-enabled with lazy loading, health checks, and pre-installed packages
        capabilities=[]
    ),

    # GitLab integration
    "gitlab": MCPServerConfig(
        server_type=MCPServerType.GITLAB,
        server_id="gitlab-tools",
        display_name="GitLab Integration",
        npm_package="mcp-remote",
        command=[
            NPX_CMD, "-y", "mcp-remote",
            os.getenv("GITLAB_MCP_URL", "https://gitlab.com/api/v4/mcp"),
            "--static-oauth-client-metadata",
            '{"scope": "mcp"}'
        ],
        env_vars={
            # GitLab OAuth credentials (if needed for private instances)
            "GITLAB_URL": os.getenv("GITLAB_URL", "https://gitlab.com"),
            "GITLAB_TOKEN": os.getenv("GITLAB_TOKEN", ""),  # Optional: Personal Access Token
        },
        enabled=False,  # Enable when project is on GitLab
        capabilities=[
            MCPToolCapability(
                name="get_mcp_server_version",
                description="Get GitLab MCP server version",
                input_schema={},
                category="system"
            ),
            MCPToolCapability(
                name="create_issue",
                description="Create a new issue in GitLab",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["project_id", "title"]
                },
                category="issues"
            ),
            MCPToolCapability(
                name="get_issue",
                description="Get details of a GitLab issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "issue_iid": {"type": "integer"}
                    },
                    "required": ["project_id", "issue_iid"]
                },
                category="issues"
            ),
            MCPToolCapability(
                name="create_merge_request",
                description="Create a new merge request in GitLab",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "source_branch": {"type": "string"},
                        "target_branch": {"type": "string"},
                        "title": {"type": "string"}
                    },
                    "required": ["project_id", "source_branch", "target_branch", "title"]
                },
                category="merge_requests"
            ),
            MCPToolCapability(
                name="get_merge_request",
                description="Get details of a GitLab merge request",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "merge_request_iid": {"type": "integer"}
                    },
                    "required": ["project_id", "merge_request_iid"]
                },
                category="merge_requests"
            ),
            MCPToolCapability(
                name="get_merge_request_commits",
                description="Get commits in a merge request",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "merge_request_iid": {"type": "integer"}
                    },
                    "required": ["project_id", "merge_request_iid"]
                },
                category="merge_requests"
            ),
            MCPToolCapability(
                name="get_merge_request_diffs",
                description="Get diffs/changes in a merge request",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "merge_request_iid": {"type": "integer"}
                    },
                    "required": ["project_id", "merge_request_iid"]
                },
                category="merge_requests"
            ),
            MCPToolCapability(
                name="get_merge_request_pipelines",
                description="Get CI/CD pipelines for a merge request",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "merge_request_iid": {"type": "integer"}
                    },
                    "required": ["project_id", "merge_request_iid"]
                },
                category="ci_cd"
            ),
            MCPToolCapability(
                name="get_pipeline_jobs",
                description="Get jobs in a CI/CD pipeline",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "pipeline_id": {"type": "integer"}
                    },
                    "required": ["project_id", "pipeline_id"]
                },
                category="ci_cd"
            ),
            MCPToolCapability(
                name="gitlab_search",
                description="Search across GitLab (issues, MRs, code, etc.)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "scope": {"type": "string", "enum": ["issues", "merge_requests", "projects", "users", "commits", "blobs"]},
                        "search": {"type": "string"}
                    },
                    "required": ["scope", "search"]
                },
                category="search"
            ),
            MCPToolCapability(
                name="get_code_context",
                description="Get code context from GitLab (experimental)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "string"},
                        "ref": {"type": "string"},
                        "file_path": {"type": "string"}
                    },
                    "required": ["project_id", "file_path"]
                },
                category="code"
            ),
        ]
    ),

    # Atlassian (Jira, Confluence, Compass)
    "atlassian": MCPServerConfig(
        server_type=MCPServerType.ATLASSIAN,
        server_id="atlassian-tools",
        display_name="Atlassian (Jira, Confluence, Compass)",
        npm_package="mcp-remote",
        command=[
            NPX_CMD, "-y", "mcp-remote",
            "https://mcp.atlassian.com/v1/sse",
            "--oauth2"
        ],
        env_vars={
            # Atlassian Cloud site URL
            "ATLASSIAN_SITE_URL": os.getenv("ATLASSIAN_SITE_URL", ""),  # e.g., https://your-domain.atlassian.net
            "ATLASSIAN_USER_EMAIL": os.getenv("ATLASSIAN_USER_EMAIL", ""),  # User email for OAuth
            # OAuth tokens will be managed by mcp-remote during first connection
        },
        enabled=False,  # Enable when Atlassian integration is needed
        capabilities=[
            # Jira capabilities
            MCPToolCapability(
                name="jira_search",
                description="Search Jira issues using JQL or natural language",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "JQL query or natural language search"},
                        "max_results": {"type": "integer", "default": 50}
                    },
                    "required": ["query"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_get_issue",
                description="Get details of a specific Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Issue key (e.g., PROJ-123)"}
                    },
                    "required": ["issue_key"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_create_issue",
                description="Create a new Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project": {"type": "string", "description": "Project key"},
                        "summary": {"type": "string", "description": "Issue summary/title"},
                        "description": {"type": "string", "description": "Issue description"},
                        "issue_type": {"type": "string", "description": "Issue type (e.g., Bug, Task, Story)"},
                        "priority": {"type": "string", "description": "Priority (e.g., High, Medium, Low)"}
                    },
                    "required": ["project", "summary", "issue_type"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_update_issue",
                description="Update an existing Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string", "description": "Issue key to update"},
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {"type": "string"},
                        "assignee": {"type": "string"},
                        "priority": {"type": "string"}
                    },
                    "required": ["issue_key"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_bulk_create",
                description="Create multiple Jira issues at once",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "project": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "issue_type": {"type": "string"}
                                }
                            }
                        }
                    },
                    "required": ["issues"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_add_comment",
                description="Add a comment to a Jira issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "comment": {"type": "string"}
                    },
                    "required": ["issue_key", "comment"]
                },
                category="jira"
            ),
            MCPToolCapability(
                name="jira_transition_issue",
                description="Transition a Jira issue to a different status",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "transition": {"type": "string", "description": "Target status (e.g., In Progress, Done)"}
                    },
                    "required": ["issue_key", "transition"]
                },
                category="jira"
            ),
            # Confluence capabilities
            MCPToolCapability(
                name="confluence_search",
                description="Search Confluence pages and spaces",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "space_key": {"type": "string", "description": "Optional: limit to specific space"}
                    },
                    "required": ["query"]
                },
                category="confluence"
            ),
            MCPToolCapability(
                name="confluence_get_page",
                description="Get a Confluence page by ID or title",
                input_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string"},
                        "space_key": {"type": "string"}
                    }
                },
                category="confluence"
            ),
            MCPToolCapability(
                name="confluence_create_page",
                description="Create a new Confluence page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "space_key": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string", "description": "Page content in Confluence storage format"}
                    },
                    "required": ["space_key", "title", "content"]
                },
                category="confluence"
            ),
            MCPToolCapability(
                name="confluence_update_page",
                description="Update an existing Confluence page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "page_id": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["page_id"]
                },
                category="confluence"
            ),
            # Compass capabilities
            MCPToolCapability(
                name="compass_search_components",
                description="Search Compass components (services, libraries)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                },
                category="compass"
            ),
        ]
    ),

    # Slack integration
    "slack": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="slack-tools",
        display_name="Slack Integration",
        npm_package="@modelcontextprotocol/server-slack",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-slack"],
        env_vars={},
        enabled=False,  # Needs SLACK_BOT_TOKEN and SLACK_TEAM_ID
        capabilities=[]
    ),
    
    # Google Drive
    "google_drive": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="google-drive",
        display_name="Google Drive",
        npm_package="@modelcontextprotocol/server-gdrive",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-gdrive"],
        env_vars={},
        enabled=False,  # Needs Google OAuth credentials
        capabilities=[]
    ),
    
    # EverArt (AI art generation)
    "everart": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="everart-tools",
        display_name="EverArt AI Generation",
        npm_package="@modelcontextprotocol/server-everart",
        command=[NPX_CMD, "-y", "@modelcontextprotocol/server-everart"],
        env_vars={},
        enabled=False,  # Needs EVERART_API_KEY
        capabilities=[]
    ),

    # Test Runner (pytest, jest, vitest, mocha)
    "test_runner": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="test-runner",
        display_name="Test Runner (pytest, jest)",
        npm_package=None,  # Local Python server
        command=["python", "/app/mcp-servers/test-runner/server.py"],
        env_vars={},
        enabled=True,  # Essential for verification
        capabilities=[
            MCPToolCapability(
                name="run_pytest",
                description="Run Python tests using pytest. Returns structured test results including pass/fail counts, individual test outcomes, and error messages.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to test file or directory"},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional pytest arguments (e.g., ['-k', 'test_name'])"
                        }
                    },
                    "required": ["path"]
                },
                category="testing"
            ),
            MCPToolCapability(
                name="run_jest",
                description="Run JavaScript/TypeScript tests using Jest. Returns structured test results including pass/fail counts, test durations, and error messages.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to test file or directory"},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional Jest arguments (e.g., ['--watch'])"
                        }
                    },
                    "required": ["path"]
                },
                category="testing"
            ),
            MCPToolCapability(
                name="run_tests_auto",
                description="Automatically detect test framework and run tests. Supports Python (pytest), JavaScript/TypeScript (Jest). Returns structured results.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to test file or directory"}
                    },
                    "required": ["path"]
                },
                category="testing"
            )
        ]
    ),

    # Static Analyzer (pylint, mypy, eslint, tsc)
    "static_analyzer": MCPServerConfig(
        server_type=MCPServerType.CUSTOM,
        server_id="static-analyzer",
        display_name="Static Analyzer (pylint, mypy, eslint, tsc)",
        npm_package=None,  # Local Python server
        command=["python", "/app/mcp-servers/static-analyzer/server.py"],
        env_vars={},
        enabled=True,  # Essential for verification
        capabilities=[
            MCPToolCapability(
                name="run_pylint",
                description="Run pylint on Python code. Returns linting issues with severity levels and a quality score.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to Python file or directory"}
                    },
                    "required": ["path"]
                },
                category="linting"
            ),
            MCPToolCapability(
                name="run_mypy",
                description="Run mypy type checking on Python code. Returns type errors with file locations.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to Python file or directory"}
                    },
                    "required": ["path"]
                },
                category="linting"
            ),
            MCPToolCapability(
                name="run_eslint",
                description="Run ESLint on JavaScript/TypeScript code. Returns linting issues with severity levels.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to JS/TS file or directory"}
                    },
                    "required": ["path"]
                },
                category="linting"
            ),
            MCPToolCapability(
                name="run_tsc",
                description="Run TypeScript compiler type checking. Returns type errors.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to TypeScript project (directory with tsconfig.json)"}
                    },
                    "required": ["path"]
                },
                category="linting"
            ),
            MCPToolCapability(
                name="analyze_auto",
                description="Automatically detect language and run appropriate static analysis tools. Returns combined results.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Path to file or directory"}
                    },
                    "required": ["path"]
                },
                category="linting"
            )
        ]
    )
}
