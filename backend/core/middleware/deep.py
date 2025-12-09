# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
DeepAgents Middleware Wrappers for LangConfig.

Provides middleware implementations that integrate DeepAgents patterns
with LangConfig's existing architecture.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field
from models.enums import MiddlewareType

logger = logging.getLogger(__name__)


# =============================================================================
# Todo List Middleware
# =============================================================================

class TodoItem(BaseModel):
    """A single todo item for tracking agent tasks."""
    id: str  # Changed from int to str to match deepagents schema
    content: str
    status: str = Field(default="pending", description="pending, in_progress, or completed")
    created_at: str
    completed_at: Optional[str] = None


class TodoListMiddleware:
    """
    Middleware for task planning and progress tracking.
    Wraps DeepAgents' TodoListMiddleware with LangConfig integration.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize TodoList middleware.

        Args:
            config: Configuration including auto_track flag
        """
        self.config = config or {}
        self.auto_track = self.config.get("auto_track", True)
        self.todos: List[TodoItem] = []
        self.next_id = 1

        logger.info(f"TodoListMiddleware initialized (auto_track={self.auto_track})")

    def create_tools(self) -> List[BaseTool]:
        """Create LangChain tools for todo management."""

        def write_todos(todos: List[Dict[str, str]]) -> str:
            """
            Create or update the task list.

            Args:
                todos: List of todo items with 'content' and 'status' fields

            Returns:
                Confirmation message with todo list
            """
            try:
                import datetime

                # Clear existing todos
                self.todos.clear()
                self.next_id = 1

                # Add new todos
                for todo_dict in todos:
                    todo = TodoItem(
                        id=str(self.next_id),  # Convert to string
                        content=todo_dict["content"],
                        status=todo_dict.get("status", "pending"),
                        created_at=datetime.datetime.utcnow().isoformat()
                    )
                    self.todos.append(todo)
                    self.next_id += 1

                # Format response
                result = f"Todo list updated with {len(self.todos)} items:\n"
                for todo in self.todos:
                    status_icon = {
                        "pending": "⏳",
                        "in_progress": "🔄",
                        "completed": "✅"
                    }.get(todo.status, "❓")
                    result += f"{status_icon} {todo.id}. [{todo.status}] {todo.content}\n"

                logger.info(f"Updated todo list: {len(self.todos)} items")
                return result

            except Exception as e:
                logger.error(f"Error writing todos: {e}")
                return f"Error updating todos: {str(e)}"

        def update_todo_status(todo_id: str, status: str) -> str:
            """
            Update the status of a specific todo item.

            Args:
                todo_id: ID of the todo to update
                status: New status (pending, in_progress, completed)

            Returns:
                Confirmation message
            """
            import datetime

            valid_statuses = ["pending", "in_progress", "completed"]
            if status not in valid_statuses:
                return f"Error: Invalid status '{status}'. Must be one of: {valid_statuses}"

            for todo in self.todos:
                if todo.id == todo_id:
                    todo.status = status
                    if status == "completed":
                        todo.completed_at = datetime.datetime.utcnow().isoformat()

                    logger.info(f"Updated todo {todo_id} to status: {status}")
                    return f"✅ Todo #{todo_id} marked as '{status}'"

            return f"Error: Todo #{todo_id} not found"

        def get_todos() -> str:
            """
            Get the current todo list.

            Returns:
                Formatted list of all todos
            """
            if not self.todos:
                return "No todos yet. Use write_todos to create a task list."

            result = f"Current Todo List ({len(self.todos)} items):\n"
            for todo in self.todos:
                status_icon = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "completed": "✅"
                }.get(todo.status, "❓")
                result += f"{status_icon} {todo.id}. [{todo.status}] {todo.content}\n"

            return result

        # Create LangChain tools
        return [
            StructuredTool.from_function(
                func=write_todos,
                name="write_todos",
                description="Create or update the task list with multiple todo items. Use this to plan your work."
            ),
            StructuredTool.from_function(
                func=update_todo_status,
                name="update_todo_status",
                description="Update the status of a specific todo item (pending, in_progress, completed)"
            ),
            StructuredTool.from_function(
                func=get_todos,
                name="get_todos",
                description="Get the current todo list to see progress"
            )
        ]

    def get_state(self) -> Dict[str, Any]:
        """Get current middleware state for checkpointing."""
        return {
            "todos": [todo.dict() for todo in self.todos],
            "next_id": self.next_id
        }

    def set_state(self, state: Dict[str, Any]):
        """Restore middleware state from checkpoint."""
        self.todos = [TodoItem(**todo) for todo in state.get("todos", [])]
        self.next_id = state.get("next_id", 1)


# =============================================================================
# Filesystem Middleware
# =============================================================================

class FilesystemMiddleware:
    """
    Middleware for filesystem access and context management.
    Integrates with existing MCP filesystem tools and adds auto-eviction.
    """

    def __init__(
        self,
        mcp_manager=None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Filesystem middleware.

        Args:
            mcp_manager: MCP manager for loading filesystem tools
            config: Configuration including auto_eviction settings
        """
        self.mcp_manager = mcp_manager
        self.config = config or {}
        self.auto_eviction = self.config.get("auto_eviction", True)
        self.eviction_threshold = self.config.get("eviction_threshold_bytes", 1000000)  # 1MB
        self.evicted_results = {}

        logger.info(
            f"FilesystemMiddleware initialized "
            f"(auto_eviction={self.auto_eviction}, threshold={self.eviction_threshold})"
        )

    async def create_tools(self) -> List[BaseTool]:
        """Create filesystem tools from MCP manager."""
        tools = []

        # Load all filesystem tools (DeepAgents standard)
        # See: https://docs.langchain.com/oss/python/deepagents/harness
        try:
            from core.agents.factory import AgentFactory
            from tools.native_tools import FILESYSTEM_TOOLS
            fs_tools = await AgentFactory._load_native_tools(FILESYSTEM_TOOLS)
            tools.extend(fs_tools)
            logger.info(f"Loaded {len(fs_tools)} filesystem tools: {FILESYSTEM_TOOLS}")
        except Exception as e:
            logger.error(f"Error loading filesystem tools: {e}")

        # Add eviction management tool
        def get_evicted_result(result_id: str) -> str:
            """
            Retrieve a previously evicted large result.

            Args:
                result_id: ID of the evicted result

            Returns:
                The evicted result content
            """
            if result_id in self.evicted_results:
                return f"Evicted Result [{result_id}]:\n{self.evicted_results[result_id]}"
            return f"Error: No evicted result found with ID '{result_id}'"

        tools.append(
            StructuredTool.from_function(
                func=get_evicted_result,
                name="get_evicted_result",
                description="Retrieve a large result that was automatically evicted to save context"
            )
        )

        return tools

    def maybe_evict_result(self, result: str, tool_name: str) -> str:
        """
        Check if result should be evicted to save context.

        Args:
            result: Tool result string
            tool_name: Name of the tool that produced it

        Returns:
            Either the original result or a reference to evicted result
        """
        if not self.auto_eviction:
            return result

        result_size = len(result.encode('utf-8'))

        if result_size > self.eviction_threshold:
            # Evict to storage
            result_id = f"{tool_name}_{len(self.evicted_results)}"
            self.evicted_results[result_id] = result

            logger.info(
                f"Evicted large result from {tool_name} "
                f"({result_size} bytes) with ID: {result_id}"
            )

            return (
                f"[Large result evicted - {result_size} bytes]\n"
                f"Use get_evicted_result('{result_id}') to retrieve it.\n"
                f"Preview (first 500 chars):\n{result[:500]}..."
            )

        return result

    def get_state(self) -> Dict[str, Any]:
        """Get current middleware state."""
        return {
            "evicted_results": self.evicted_results
        }

    def set_state(self, state: Dict[str, Any]):
        """Restore middleware state."""
        self.evicted_results = state.get("evicted_results", {})


# =============================================================================
# SubAgent Middleware
# =============================================================================

class SubAgentMiddleware:
    """
    Middleware for spawning specialized subagents.
    Integrates with AgentTemplateRegistry to create subagents on-demand.
    """

    def __init__(
        self,
        template_registry=None,
        agent_factory=None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize SubAgent middleware.

        Args:
            template_registry: Agent template registry for loading templates
            agent_factory: AgentFactory for creating subagents
            config: Configuration including max_depth and max_concurrent
        """
        self.template_registry = template_registry
        self.agent_factory = agent_factory
        self.config = config or {}
        self.max_depth = self.config.get("max_depth", 3)
        self.max_concurrent = self.config.get("max_concurrent", 5)
        self.active_subagents = []
        self.current_depth = 0

        logger.info(
            f"SubAgentMiddleware initialized "
            f"(max_depth={self.max_depth}, max_concurrent={self.max_concurrent})"
        )

    def create_tools(self) -> List[BaseTool]:
        """Create tools for subagent spawning."""

        def spawn_subagent(
            template_id: str,
            task_description: str,
            context: Optional[str] = None
        ) -> str:
            """
            Spawn a specialized subagent to handle a specific task.

            Args:
                template_id: ID of agent template to use (e.g., 'code_researcher', 'test_generator')
                task_description: Description of what the subagent should do
                context: Optional additional context for the subagent

            Returns:
                Result from the subagent execution
            """
            # Check depth limit
            if self.current_depth >= self.max_depth:
                return f"Error: Maximum subagent depth ({self.max_depth}) reached"

            # Check concurrent limit
            if len(self.active_subagents) >= self.max_concurrent:
                return f"Error: Maximum concurrent subagents ({self.max_concurrent}) reached"

            try:
                logger.info(f"Spawning subagent: {template_id} for task: {task_description}")

                # This would integrate with your actual agent execution
                # For now, return a placeholder that shows the structure
                subagent_id = f"subagent_{len(self.active_subagents)}"
                self.active_subagents.append({
                    "id": subagent_id,
                    "template_id": template_id,
                    "task": task_description
                })

                result = (
                    f"Subagent '{template_id}' spawned successfully\n"
                    f"Task: {task_description}\n"
                    f"[Subagent execution would happen here]\n"
                    f"Subagent ID: {subagent_id}"
                )

                return result

            except Exception as e:
                logger.error(f"Error spawning subagent: {e}")
                return f"Error spawning subagent: {str(e)}"

        def list_available_agents() -> str:
            """
            List available agent templates that can be used as subagents.

            Returns:
                Formatted list of available agent templates
            """
            if not self.template_registry:
                return "No agent templates available"

            try:
                # Get templates from registry
                from core.agents.templates import AgentTemplateRegistry
                templates = AgentTemplateRegistry.list_all()

                result = f"Available Agent Templates ({len(templates)}):\n\n"
                for template in templates:
                    result += f"• {template.template_id}: {template.name}\n"
                    result += f"  {template.description}\n"
                    result += f"  Category: {template.category.value}\n\n"

                return result

            except Exception as e:
                logger.error(f"Error listing templates: {e}")
                return f"Error listing templates: {str(e)}"

        return [
            StructuredTool.from_function(
                func=spawn_subagent,
                name="spawn_subagent",
                description="Spawn a specialized subagent to handle a specific subtask. Use for complex work that needs focus."
            ),
            StructuredTool.from_function(
                func=list_available_agents,
                name="list_available_agents",
                description="List all available agent templates that can be spawned as subagents"
            )
        ]

    def get_state(self) -> Dict[str, Any]:
        """Get current middleware state."""
        return {
            "active_subagents": self.active_subagents,
            "current_depth": self.current_depth
        }

    def set_state(self, state: Dict[str, Any]):
        """Restore middleware state."""
        self.active_subagents = state.get("active_subagents", [])
        self.current_depth = state.get("current_depth", 0)


# =============================================================================
# Middleware Factory
# =============================================================================

class DeepAgentsMiddlewareFactory:
    """Factory for creating middleware instances."""

    @staticmethod
    def create_middleware(
        middleware_type,  # Can be MiddlewareType enum or string (auto-converted)
        config: Dict[str, Any],
        mcp_manager=None,
        agent_factory=None,
        template_registry=None
    ):
        """
        Create a middleware instance.

        Args:
            middleware_type: Type of middleware (MiddlewareType enum or string)
            config: Middleware configuration
            mcp_manager: Optional MCP manager
            agent_factory: Optional agent factory
            template_registry: Optional template registry

        Returns:
            Middleware instance
        """
        # Convert string to enum if needed (backwards compatibility)
        if isinstance(middleware_type, str):
            middleware_type = MiddlewareType(middleware_type)

        if middleware_type == MiddlewareType.TODO_LIST:
            return TodoListMiddleware(config=config)

        elif middleware_type == MiddlewareType.FILESYSTEM:
            return FilesystemMiddleware(
                mcp_manager=mcp_manager,
                config=config
            )

        elif middleware_type == MiddlewareType.SUBAGENT:
            return SubAgentMiddleware(
                template_registry=template_registry,
                agent_factory=agent_factory,
                config=config
            )

        else:
            raise ValueError(f"Unknown middleware type: {middleware_type}")

    @staticmethod
    async def create_all_tools(
        middleware_configs: List[Dict[str, Any]],
        mcp_manager=None,
        agent_factory=None,
        template_registry=None
    ) -> List[BaseTool]:
        """
        Create tools from all middleware configurations.

        Args:
            middleware_configs: List of middleware configurations
            mcp_manager: Optional MCP manager
            agent_factory: Optional agent factory
            template_registry: Optional template registry

        Returns:
            List of all tools from all middleware
        """
        all_tools = []

        for middleware_config in middleware_configs:
            if not middleware_config.get("enabled", True):
                continue

            middleware_type = middleware_config["type"]
            config = middleware_config.get("config", {})

            try:
                middleware = DeepAgentsMiddlewareFactory.create_middleware(
                    middleware_type=middleware_type,
                    config=config,
                    mcp_manager=mcp_manager,
                    agent_factory=agent_factory,
                    template_registry=template_registry
                )

                # Get tools from middleware
                if hasattr(middleware, 'create_tools'):
                    if asyncio.iscoroutinefunction(middleware.create_tools):
                        tools = await middleware.create_tools()
                    else:
                        tools = middleware.create_tools()
                    all_tools.extend(tools)
                    logger.info(f"Added {len(tools)} tools from {middleware_type} middleware")

            except Exception as e:
                logger.error(f"Error creating middleware {middleware_type}: {e}")

        return all_tools


# Import asyncio for async checks
import asyncio
