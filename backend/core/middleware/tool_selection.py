# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Dynamic Tool Selection Middleware (LangGraph v1.0)

Intelligently filters and selects tools based on:
- User permissions and role
- Task classification
- Context and requirements
- Security constraints

Example Usage:
    from core.middleware.tool_selection import (
        PermissionBasedToolMiddleware,
        ClassificationBasedToolMiddleware
    )

    agent = create_agent(
        model="gpt-4o",
        tools=all_available_tools,
        middleware=[
            PermissionBasedToolMiddleware(),  # Filter by user role
            ClassificationBasedToolMiddleware(),  # Filter by task type
            # ... other middleware
        ]
    )
"""

import logging
from typing import List, Set, Callable, Dict, Any
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from core.middleware.core import AgentMiddleware
from core.workflows.context import UserRole

logger = logging.getLogger(__name__)


# =============================================================================
# Permission-Based Tool Filtering
# =============================================================================

class PermissionBasedToolMiddleware(AgentMiddleware):
    """
    Filter tools based on user role and permissions.

    Tool Access Levels:
    - ADMIN: All tools
    - EDITOR: All except destructive operations
    - VIEWER: Only read-only tools

    Example:
        >>> middleware = [PermissionBasedToolMiddleware()]
        >>> # Viewers only get read tools, admins get all tools
    """

    # Define tool permissions
    ADMIN_ONLY_TOOLS = {
        "delete_file",
        "deploy_code",
        "modify_infrastructure",
        "delete_resource",
        "drop_table",
        "revoke_access",
        "terminate_instance"
    }

    EDITOR_TOOLS = {
        "create_file",
        "update_file",
        "run_tests",
        "create_resource",
        "update_resource",
        "execute_query",
        "jira_create_ticket",
        "jira_update_ticket",
        "save_decision",
        "save_code_pattern"
    }

    VIEWER_TOOLS = {
        "read_file",
        "search_code",
        "list_resources",
        "query_database_readonly",
        "jira_search_tickets",
        "retrieve_decisions",
        "retrieve_code_patterns",
        "get_current_session_info"
    }

    @wrap_model_call
    def filter_tools_by_role(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Filter tools based on user role."""

        # ✅ Access user role from runtime context
        # Check if context is available
        if not hasattr(request.runtime, 'context') or request.runtime.context is None:
            logger.debug("No context available, skipping permission-based filtering")
            return handler(request)  # Skip filtering, call handler directly

        user_role = getattr(request.runtime.context, 'user_role', UserRole.VIEWER)
        user_id = getattr(request.runtime.context, 'user_id', 'unknown')

        original_tool_count = len(request.tools)

        # Filter tools based on role
        if user_role == UserRole.ADMIN:
            # Admins get all tools
            logger.info(f"User {user_id} (ADMIN) has access to all {original_tool_count} tools")

        elif user_role == UserRole.EDITOR:
            # Editors get all except admin-only tools
            request.tools = [
                t for t in request.tools
                if t.name not in self.ADMIN_ONLY_TOOLS
            ]
            logger.info(f"User {user_id} (EDITOR) filtered to {len(request.tools)}/{original_tool_count} tools")

        elif user_role == UserRole.VIEWER:
            # Viewers get only read-only tools
            request.tools = [
                t for t in request.tools
                if t.name in self.VIEWER_TOOLS
            ]
            logger.info(f"User {user_id} (VIEWER) filtered to {len(request.tools)}/{original_tool_count} tools (read-only)")

        else:
            # Unknown role - default to viewer permissions
            logger.warning(f"Unknown role {user_role} for user {user_id}, defaulting to VIEWER permissions")
            request.tools = [
                t for t in request.tools
                if t.name in self.VIEWER_TOOLS
            ]

        return handler(request)


# =============================================================================
# Classification-Based Tool Selection
# =============================================================================

class ClassificationBasedToolMiddleware(AgentMiddleware):
    """
    Select tools based on task classification.

    Different task types need different tools:
    - BACKEND: Database, API, server tools
    - FRONTEND: UI, component, styling tools
    - DEVOPS_IAC: Infrastructure, deployment tools
    - etc.

    Example:
        >>> middleware = [ClassificationBasedToolMiddleware()]
        >>> # Backend tasks only get backend-relevant tools
    """

    # Tool sets for different classifications
    BACKEND_TOOLS = {
        "run_python",
        "query_database",
        "execute_query",
        "deploy_service",
        "create_api_endpoint",
        "test_endpoint",
        "jira_create_ticket",
        "save_decision"
    }

    FRONTEND_TOOLS = {
        "run_npm",
        "build_ui",
        "preview_component",
        "run_tests",
        "lint_code",
        "jira_create_ticket",
        "save_decision"
    }

    DEVOPS_TOOLS = {
        "apply_terraform",
        "deploy_k8s",
        "run_ansible",
        "check_infra_status",
        "scale_service",
        "jira_create_ticket",
        "save_decision"
    }

    DATABASE_TOOLS = {
        "query_database",
        "execute_query",
        "create_migration",
        "backup_database",
        "optimize_query",
        "jira_create_ticket",
        "save_decision"
    }

    # Common tools available to all classifications
    COMMON_TOOLS = {
        "read_file",
        "search_code",
        "save_decision",
        "retrieve_decisions",
        "jira_search_tickets",
        "get_current_session_info"
    }

    @wrap_model_call
    def filter_tools_by_classification(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Filter tools based on task classification."""

        # ✅ Access classification from state
        if not hasattr(request, 'state') or request.state is None:
            logger.debug("No state available, skipping classification-based filtering")
            return handler(request)

        classification = request.state.get("classification")

        if not classification:
            # No classification - keep all tools
            logger.debug("No classification found, keeping all tools")
            return handler(request)

        original_tool_count = len(request.tools)

        # Get appropriate tool set
        allowed_tools = self.COMMON_TOOLS.copy()

        if classification == "BACKEND":
            allowed_tools.update(self.BACKEND_TOOLS)
        elif classification == "FRONTEND":
            allowed_tools.update(self.FRONTEND_TOOLS)
        elif classification == "DEVOPS_IAC":
            allowed_tools.update(self.DEVOPS_TOOLS)
        elif classification == "DATABASE":
            allowed_tools.update(self.DATABASE_TOOLS)
        else:
            # Unknown classification - allow all tools
            logger.debug(f"Unknown classification {classification}, keeping all tools")
            return handler(request)

        # Filter tools
        request.tools = [
            t for t in request.tools
            if t.name in allowed_tools
        ]

        logger.info(f"Classification {classification}: filtered to {len(request.tools)}/{original_tool_count} tools")

        return handler(request)


# =============================================================================
# Context-Based Tool Availability
# =============================================================================

class ContextBasedToolMiddleware(AgentMiddleware):
    """
    Enable/disable tools based on runtime context.

    For example:
    - Jira tools only if jira_api_token is configured
    - GitHub tools only if github_token is configured
    - AWS tools only if aws credentials are configured

    Example:
        >>> middleware = [ContextBasedToolMiddleware()]
        >>> # Tools requiring credentials are automatically filtered out
    """

    @wrap_model_call
    def filter_tools_by_context(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Filter tools based on available credentials and context."""

        context = request.runtime.context
        original_tool_count = len(request.tools)
        filtered_tools = []

        for tool in request.tools:
            tool_name = tool.name

            # Check Jira tools
            if tool_name.startswith("jira_"):
                if context.jira_api_token and context.jira_email:
                    filtered_tools.append(tool)
                else:
                    logger.debug(f"Filtering out {tool_name}: Jira credentials not configured")

            # Check GitHub tools
            elif tool_name.startswith("github_"):
                if context.github_token:
                    filtered_tools.append(tool)
                else:
                    logger.debug(f"Filtering out {tool_name}: GitHub token not configured")

            # Check AWS tools
            elif tool_name.startswith("aws_"):
                if context.aws_access_key_id and context.aws_secret_access_key:
                    filtered_tools.append(tool)
                else:
                    logger.debug(f"Filtering out {tool_name}: AWS credentials not configured")

            # Check memory tools
            elif "memory" in tool_name:
                if context.enable_memory:
                    filtered_tools.append(tool)
                else:
                    logger.debug(f"Filtering out {tool_name}: Memory not enabled")

            # Check RAG tools
            elif "rag" in tool_name or "search_code" in tool_name:
                if context.enable_rag:
                    filtered_tools.append(tool)
                else:
                    logger.debug(f"Filtering out {tool_name}: RAG not enabled")

            # All other tools pass through
            else:
                filtered_tools.append(tool)

        request.tools = filtered_tools

        if len(filtered_tools) < original_tool_count:
            logger.info(f"Context filtering: {len(filtered_tools)}/{original_tool_count} tools available")

        return handler(request)


# =============================================================================
# Explicit Tool Allow/Block Lists
# =============================================================================

class AllowBlockListMiddleware(AgentMiddleware):
    """
    Enforce explicit allow/block lists from context.

    Context can specify:
    - allowed_tools: Only these tools are available
    - blocked_tools: These tools are never available

    Example:
        >>> context = WorkflowContext(
        ...     user_id=123,
        ...     allowed_tools=["read_file", "search_code"],  # Only these
        ...     blocked_tools=["delete_file"]  # Never this
        ... )
    """

    @wrap_model_call
    def filter_tools_by_lists(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Apply allow/block lists."""

        context = request.runtime.context
        allowed_tools = context.allowed_tools
        blocked_tools = context.blocked_tools

        # Apply block list first
        if blocked_tools:
            request.tools = [
                t for t in request.tools
                if t.name not in blocked_tools
            ]
            logger.info(f"Blocked {len(blocked_tools)} tools: {blocked_tools}")

        # Apply allow list (overrides everything else)
        if allowed_tools:
            request.tools = [
                t for t in request.tools
                if t.name in allowed_tools
            ]
            logger.info(f"Allowed only {len(allowed_tools)} tools: {allowed_tools}")

        return handler(request)


# =============================================================================
# Combined Tool Selection Middleware
# =============================================================================

class ComprehensiveToolSelectionMiddleware(AgentMiddleware):
    """
    Combines all tool selection strategies.

    Order of application:
    1. Permission-based (user role)
    2. Classification-based (task type)
    3. Context-based (credentials available)
    4. Allow/Block lists (explicit control)

    Example:
        >>> middleware = [ComprehensiveToolSelectionMiddleware()]
        >>> # All filtering strategies applied automatically
    """

    def __init__(self):
        self.permission_filter = PermissionBasedToolMiddleware()
        self.classification_filter = ClassificationBasedToolMiddleware()
        self.context_filter = ContextBasedToolMiddleware()
        self.list_filter = AllowBlockListMiddleware()

    @wrap_model_call
    def filter_tools(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        """Apply all filters in sequence."""

        original_count = len(request.tools)

        # 1. Permission filter
        request = self.permission_filter.filter_tools_by_role(request, lambda r: r)

        # 2. Classification filter
        request = self.classification_filter.filter_tools_by_classification(request, lambda r: r)

        # 3. Context filter
        request = self.context_filter.filter_tools_by_context(request, lambda r: r)

        # 4. Allow/Block lists
        request = self.list_filter.filter_tools_by_lists(request, lambda r: r)

        final_count = len(request.tools)

        logger.info(f"Comprehensive tool filtering: {final_count}/{original_count} tools available")

        return handler(request)
