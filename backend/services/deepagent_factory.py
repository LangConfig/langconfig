# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
DeepAgent Factory Service.

Creates DeepAgents using the deepagents library while integrating
with LangConfig's existing agent factory infrastructure.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from models.deep_agent import (
    DeepAgentConfig,
    SubAgentConfig,
    MiddlewareConfig,
    BackendConfig,
    GuardrailsConfig
)
from models.enums import SubAgentType, MiddlewareType, BackendType
from core.middleware.deep import DeepAgentsMiddlewareFactory
from core.agents.factory import AgentFactory

logger = logging.getLogger(__name__)


class DeepAgentFactory:
    """
    Factory for creating DeepAgents with full middleware and backend support.
    Wraps the deepagents library while integrating with LangConfig infrastructure.
    """
    # Note: Type validation now handled by Pydantic enums in models.enums
    # No need for VALID_* constants anymore

    @staticmethod
    def _validate_deep_agent_config(config: DeepAgentConfig) -> List[str]:
        """
        Basic validation of DeepAgent configuration.

        Returns:
            List of error/warning messages (empty if valid)
        """
        errors = []

        # 1. Required: model must be set
        if not config.model:
            errors.append("model is required")

        # 2. Required: system_prompt must be set
        if not config.system_prompt:
            errors.append("system_prompt is required")

        # 3. Validate temperature bounds (0.0 to 2.0)
        if not (0.0 <= config.temperature <= 2.0):
            errors.append(f"temperature must be between 0.0 and 2.0, got {config.temperature}")

        # 4-6. Type and consistency validation now handled by Pydantic validators
        # Enum types ensure only valid values are accepted
        # @model_validator decorators check cross-field constraints
        # No runtime validation needed here

        return errors

    @staticmethod
    async def create_deep_agent(
        config: DeepAgentConfig,
        project_id: int,
        task_id: int,
        context: str,
        mcp_manager=None,
        vector_store=None
    ) -> Tuple[CompiledStateGraph, List[BaseTool], List[Any]]:
        """
        Create a DeepAgent with middleware, subagents, and backends.

        Args:
            config: DeepAgent configuration
            project_id: Project ID for context
            task_id: Task ID for context
            context: Additional context string
            mcp_manager: MCP manager for tool loading
            vector_store: Vector store for RAG

        Returns:
            Tuple of (agent, tools, callbacks)
        """
        try:
            from deepagents import create_deep_agent
        except ImportError:
            logger.error("deepagents library not installed. Falling back to regular agent.")
            return await DeepAgentFactory._fallback_to_regular_agent(
                config, project_id, task_id, context, mcp_manager, vector_store
            )

        # Validate configuration
        config_errors = DeepAgentFactory._validate_deep_agent_config(config)
        if config_errors:
            logger.warning(f"DeepAgent config validation warnings: {', '.join(config_errors)}")

        logger.info(
            f"Creating DeepAgent for task {task_id} "
            f"(model={config.model}, middleware={len(config.middleware)}, "
            f"subagents={len(config.subagents)})"
        )

        # Setup observability callbacks (Langfuse, etc.)
        callbacks = await DeepAgentFactory._setup_callbacks(project_id, task_id)
        callback_handler = callbacks[0] if callbacks else None

        # Load base tools from configuration
        base_tools = await DeepAgentFactory._load_base_tools(
            config, mcp_manager, vector_store, project_id, task_id
        )

        # Create middleware-specific tools
        middleware_tools = await DeepAgentsMiddlewareFactory.create_all_tools(
            middleware_configs=[m.dict() for m in config.middleware],
            mcp_manager=mcp_manager,
            template_registry=None,
            agent_factory=None
        )

        # Combine all available tools
        all_tools = base_tools + middleware_tools
        logger.info(f"Total tools: {len(all_tools)} (base={len(base_tools)}, middleware={len(middleware_tools)})")

        # Prepare subagent configurations
        subagents_config = await DeepAgentFactory._prepare_subagents(
            config.subagents,
            enable_compiled=getattr(config, 'enable_compiled_subagents', True),
            project_id=project_id,
            task_id=task_id,
            mcp_manager=mcp_manager,
            vector_store=vector_store
        )

        # Initialize middleware instances with instrumentation
        middleware_instances = []

        # Import instrumentation utilities
        from services.deepagents_instrumentation import (
            instrument_deepagents_middleware,
            create_todo_tracker
        )

        # Initialize FilesystemMiddleware if enabled
        filesystem_config = next(
            (m for m in config.middleware if m.type == MiddlewareType.FILESYSTEM),
            None
        )
        if filesystem_config and filesystem_config.enabled:
            try:
                from deepagents.middleware.filesystem import FilesystemMiddleware
                from deepagents.memory.backends import StateBackend

                fs_middleware = FilesystemMiddleware(backend=StateBackend())
                instrumented_fs = instrument_deepagents_middleware(
                    fs_middleware,
                    callback_handler=callback_handler
                )
                middleware_instances.append(instrumented_fs)
                logger.info("FilesystemMiddleware initialized")
            except ImportError as e:
                logger.warning(f"FilesystemMiddleware not available: {e}")

        # Initialize SubAgentMiddleware if subagents configured
        if subagents_config:
            try:
                from deepagents.middleware.subagents import SubAgentMiddleware

                subagent_middleware = SubAgentMiddleware(
                    subagents=subagents_config,
                    default_model=config.model
                )
                instrumented_subagent = instrument_deepagents_middleware(
                    subagent_middleware,
                    callback_handler=callback_handler
                )
                middleware_instances.append(instrumented_subagent)
                logger.info(f"SubAgentMiddleware initialized ({len(subagents_config)} subagents)")
            except ImportError as e:
                logger.warning(f"SubAgentMiddleware not available: {e}")

        # Get PostgreSQL checkpointer for conversation persistence
        from core.workflows.checkpointing.manager import get_checkpointer
        checkpointer = get_checkpointer()

        if checkpointer:
            logger.info("Conversation persistence enabled")
        else:
            logger.warning("Checkpointer unavailable - conversations will not persist")

        # Prepare guardrails configuration for memory management
        guardrails_config = None
        if config.guardrails:
            guardrails_config = {
                "token_limits": config.guardrails.token_limits,
                "enable_auto_eviction": config.guardrails.enable_auto_eviction,
                "enable_summarization": config.guardrails.enable_summarization,
                "interrupts": config.guardrails.interrupts
            }

        # Create DeepAgent with all components
        try:
            agent_kwargs = {
                "model": config.model,
                "tools": all_tools,
                "system_prompt": config.system_prompt,
                "middleware": middleware_instances if middleware_instances else None,
                "subagents": subagents_config if subagents_config else None,
                "checkpointer": checkpointer,
            }

            # Try to pass guardrails if supported
            try:
                agent = create_deep_agent(**agent_kwargs, guardrails=guardrails_config)
                logger.info("Guardrails configuration applied")
            except TypeError as e:
                if "guardrails" in str(e):
                    logger.warning("Guardrails parameter not supported, creating without it")
                    agent = create_deep_agent(**agent_kwargs)
                else:
                    raise

            logger.info(f"DeepAgent created for task {task_id}")
            logger.info(f"  Persistence: {'enabled' if checkpointer else 'disabled'}")
            logger.info(f"  Token limits: {config.guardrails.token_limits}")
            logger.info(f"  Auto-eviction: {config.guardrails.enable_auto_eviction}")
            logger.info(f"  Summarization: {config.guardrails.enable_summarization}")

            return agent, all_tools, callbacks

        except Exception as e:
            logger.error(f"Error creating DeepAgent: {e}")
            logger.info("Falling back to regular agent")
            return await DeepAgentFactory._fallback_to_regular_agent(
                config, project_id, task_id, context, mcp_manager, vector_store
            )

    @staticmethod
    async def _load_base_tools(
        config: DeepAgentConfig,
        mcp_manager,
        vector_store,
        project_id: int,
        task_id: int
    ) -> List[BaseTool]:
        """Load base tools from configuration (native, CLI, and custom tools)."""
        tools = []

        # Load native tools (file operations, web search, etc.)
        if config.native_tools:
            try:
                from core.agents.factory import AgentFactory
                native_tools = await AgentFactory._load_native_tools(config.native_tools)
                tools.extend(native_tools)
                logger.info(f"Loaded {len(native_tools)} native tools")
            except Exception as e:
                logger.error(f"Failed to load native tools: {e}")

        # Load CLI tools (command-line integrations)
        if config.cli_tools:
            try:
                cli_tools = await AgentFactory._load_cli_tools(config.cli_tools)
                tools.extend(cli_tools)
                logger.info(f"Loaded {len(cli_tools)} CLI tools")
            except Exception as e:
                logger.error(f"Failed to load CLI tools: {e}")

        # Load custom tools (user-defined tools)
        if config.custom_tools:
            logger.info(f"Custom tools requested: {config.custom_tools}")
            # Custom tool loading would be implemented here

        return tools

    @staticmethod
    async def _prepare_subagents(
        subagent_configs: List[SubAgentConfig],
        enable_compiled: bool = True,
        project_id: int = None,
        task_id: int = None,
        mcp_manager=None,
        vector_store=None
    ) -> List[Any]:
        """
        Prepare subagent configurations for DeepAgents.

        Supports both dictionary-based and CompiledSubAgent (workflow-based).

        Args:
            subagent_configs: List of subagent configurations
            enable_compiled: Whether to enable CompiledSubAgent support
            project_id: Project ID for workflow loading
            task_id: Task ID for context
            mcp_manager: MCP manager instance
            vector_store: Vector store instance

        Returns:
            List of subagent configurations (dicts or CompiledSubAgent objects)
        """
        from deepagents import CompiledSubAgent
        from sqlalchemy.orm import Session
        from db.database import get_db

        subagents = []
        visited_workflows = set()  # For circular dependency detection

        for sub_config in subagent_configs:
            # Dictionary-based subagent (simple)
            if sub_config.type == SubAgentType.DICTIONARY:
                subagent = {
                    "name": sub_config.name,
                    "description": sub_config.description,
                    "system_prompt": sub_config.system_prompt or "",
                    "tools": sub_config.tools,
                }

                if sub_config.model:
                    subagent["model"] = sub_config.model

                if sub_config.interrupt_on:
                    subagent["interrupt_on"] = sub_config.interrupt_on

                subagents.append(subagent)
                logger.info(f"Dictionary subagent prepared: {sub_config.name}")

            # Workflow-based CompiledSubAgent
            elif sub_config.type == SubAgentType.COMPILED:
                if not enable_compiled:
                    logger.warning(
                        f"CompiledSubAgent '{sub_config.name}' skipped - feature disabled. "
                        f"Enable with enable_compiled_subagents=True"
                    )
                    continue

                if not sub_config.workflow_id:
                    logger.error(f"CompiledSubAgent '{sub_config.name}' missing workflow_id")
                    continue

                # Detect circular dependencies
                if sub_config.workflow_id in visited_workflows:
                    logger.error(
                        f"Circular dependency detected: workflow {sub_config.workflow_id} "
                        f"already in subagent chain"
                    )
                    continue

                visited_workflows.add(sub_config.workflow_id)

                try:
                    # Load and compile the workflow
                    compiled_workflow = await DeepAgentFactory._load_and_compile_workflow(
                        workflow_id=sub_config.workflow_id,
                        project_id=project_id,
                        task_id=task_id,
                        mcp_manager=mcp_manager,
                        vector_store=vector_store,
                        visited_workflows=visited_workflows
                    )

                    if compiled_workflow:
                        compiled_subagent = CompiledSubAgent(
                            name=sub_config.name,
                            description=sub_config.description,
                            runnable=compiled_workflow
                        )
                        subagents.append(compiled_subagent)
                        logger.info(f"CompiledSubAgent prepared: {sub_config.name} (workflow {sub_config.workflow_id})")
                    else:
                        logger.error(f"Failed to compile workflow {sub_config.workflow_id} for subagent {sub_config.name}")

                except Exception as e:
                    logger.error(f"Error preparing CompiledSubAgent '{sub_config.name}': {e}", exc_info=True)
                    continue

            else:
                logger.warning(f"Unknown subagent type: {sub_config.type} for {sub_config.name}")

        logger.info(f"Prepared {len(subagents)} subagents total")
        return subagents

    @staticmethod
    async def _load_and_compile_workflow(
        workflow_id: int,
        project_id: int,
        task_id: int,
        mcp_manager,
        vector_store,
        visited_workflows: set
    ):
        """
        Load and compile a workflow to use as a CompiledSubAgent.

        Args:
            workflow_id: ID of the workflow to load
            project_id: Project ID for context
            task_id: Task ID for context
            mcp_manager: MCP manager instance
            vector_store: Vector store instance
            visited_workflows: Set of already visited workflow IDs (for circular detection)

        Returns:
            Compiled LangGraph workflow ready to use as a subagent
        """
        from db.database import get_db
        from models.workflow import WorkflowProfile
        from core.workflows.executor import SimpleWorkflowExecutor

        logger.info(f"Loading workflow {workflow_id} for CompiledSubAgent...")

        # Acquire session BEFORE try block - guarantees finally can close it
        db = next(get_db())
        try:
            # Load workflow from database
            workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()

            if not workflow:
                logger.error(f"Workflow {workflow_id} not found in database")
                return None

            # Check for circular dependencies in workflow nodes
            # If any node in this workflow has a subagent that references a workflow in visited_workflows,
            # we have a circular dependency
            workflow_data = workflow.workflow_data or {}
            nodes = workflow_data.get('nodes', [])

            for node in nodes:
                node_config = node.get('data', {}).get('config', {})
                node_subagents = node_config.get('subagents', [])

                for subagent in node_subagents:
                    if isinstance(subagent, dict) and subagent.get('type') == 'compiled':
                        sub_workflow_id = subagent.get('workflow_id')
                        if sub_workflow_id in visited_workflows:
                            logger.error(
                                f"Circular dependency detected in workflow {workflow_id}: "
                                f"node references workflow {sub_workflow_id} which is already in the chain"
                            )
                            return None

            # Create executor and build the graph
            executor = SimpleWorkflowExecutor()
            graph = await executor._build_graph_from_workflow(workflow)

            # Compile the graph (without checkpointing for subagents - they use parent's checkpoint)
            compiled_graph = graph.compile()

            logger.info(f"Successfully compiled workflow {workflow_id} ({workflow.name}) for CompiledSubAgent")
            return compiled_graph

        except Exception as e:
            logger.error(f"Error loading/compiling workflow {workflow_id}: {e}", exc_info=True)
            return None
        finally:
            db.close()  # Always closes - no conditional check needed

    @staticmethod
    async def _setup_callbacks(project_id: int, task_id: int) -> List[Any]:
        """Setup callbacks for logging and monitoring."""
        callbacks = []

        # Add Langfuse callback if available
        try:
            from langfuse.callback import CallbackHandler
            callback = CallbackHandler(
                tags=[f"project_{project_id}", f"task_{task_id}", "deepagent"]
            )
            callbacks.append(callback)
            logger.info("Langfuse callback added")
        except ImportError:
            pass

        return callbacks

    @staticmethod
    async def _fallback_to_regular_agent(
        config: DeepAgentConfig,
        project_id: int,
        task_id: int,
        context: str,
        mcp_manager,
        vector_store
    ) -> Tuple[CompiledStateGraph, List[BaseTool], List[Any]]:
        """
        Fallback to regular AgentFactory if DeepAgents fails.

        This ensures backward compatibility and graceful degradation.
        """
        logger.info("Using regular AgentFactory as fallback")

        # Convert DeepAgentConfig to regular agent_config for fallback
        agent_config = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "system_prompt": config.system_prompt,
            "native_tools": config.native_tools,
            "cli_tools": config.cli_tools,
            "custom_tools": config.custom_tools,
            "enable_memory": False,
            "enable_rag": False,
        }

        # Use existing AgentFactory
        return await AgentFactory.create_agent(
            agent_config=agent_config,
            project_id=project_id,
            task_id=task_id,
            context=context,
            mcp_manager=mcp_manager,
            vector_store=vector_store
        )

    @staticmethod
    def create_default_config(
        template_id: Optional[str] = None,
        **overrides
    ) -> DeepAgentConfig:
        """
        Create a default DeepAgent configuration.

        Args:
            template_id: Optional base template to extend
            **overrides: Override specific config values

        Returns:
            DeepAgentConfig with defaults
        """
        from models.deep_agent import (
            create_default_middleware_config,
            create_default_backend_config,
            create_default_guardrails_config
        )

        config = {
            "model": "claude-sonnet-4-5-20250929",
            "temperature": 0.7,
            "system_prompt": "You are a helpful AI assistant with planning and research capabilities.",
            "tools": [],
            "native_tools": ["file_read", "file_write", "file_list"],
            "cli_tools": [],
            "custom_tools": [],
            "use_deepagents": True,
            "middleware": create_default_middleware_config(),
            "subagents": [],
            "backend": create_default_backend_config(),
            "guardrails": create_default_guardrails_config(),
        }

        # Apply template if specified
        if template_id:
            template_config = DeepAgentFactory._load_template_config(template_id)
            config.update(template_config)

        # Apply overrides
        config.update(overrides)

        return DeepAgentConfig(**config)

    @staticmethod
    def _load_template_config(template_id: str) -> Dict[str, Any]:
        """Load configuration from a template."""
        # This would integrate with AgentTemplateRegistry
        # For now, return empty dict
        logger.info(f"Loading template config for: {template_id}")
        return {}


# =============================================================================
# Backend Abstraction Layer
# =============================================================================

class BackendAbstraction:
    """
    Pluggable backend system for DeepAgents memory and state management.
    Supports multiple storage backends: State, Store, Filesystem, VectorDB, Composite.
    """

    def __init__(self, config: BackendConfig, project_id: int = None):
        """
        Initialize backend abstraction.

        Args:
            config: Backend configuration
            project_id: Project ID for multi-tenant backends (e.g., VectorDB)
        """
        self.config = config
        self.backend_type = config.type
        self.project_id = project_id
        self.backend = self._create_backend()

        logger.info(f"BackendAbstraction initialized (type={self.backend_type})")

    def _create_backend(self):
        """Create the appropriate backend based on config."""
        if self.backend_type == "state":
            return StateBackend(self.config.config)
        elif self.backend_type == "store":
            return StoreBackend(self.config.config)
        elif self.backend_type == "filesystem":
            return FilesystemBackend(self.config.config)
        elif self.backend_type == "vectordb":
            return VectorDBBackend(self.config.config, project_id=self.project_id)
        elif self.backend_type == "composite":
            return CompositeBackend(self.config.config, self.config.mappings, project_id=self.project_id)
        else:
            raise ValueError(f"Unknown backend type: {self.backend_type}")

    async def read(self, path: str) -> Any:
        """Read data from backend."""
        return await self.backend.read(path)

    async def write(self, path: str, data: Any):
        """Write data to backend."""
        await self.backend.write(path, data)

    async def list(self, path: str) -> List[str]:
        """List items at path."""
        return await self.backend.list(path)


class StateBackend:
    """Ephemeral backend using LangGraph State."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.state = {}

    async def read(self, path: str) -> Any:
        return self.state.get(path)

    async def write(self, path: str, data: Any):
        self.state[path] = data

    async def list(self, path: str) -> List[str]:
        prefix = path.rstrip("/") + "/"
        return [k for k in self.state.keys() if k.startswith(prefix)]


class StoreBackend:
    """
    Persistent backend using LangGraph Store for cross-session memory.

    Uses InMemoryStore by default, with optional AsyncPostgresStore from checkpointing
    if available. Provides lazy initialization to avoid import issues.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.namespace = config.get("namespace", "deepagent")
        self._store = None
        self._initialized = False
        logger.info(f"StoreBackend initialized (namespace={self.namespace})")

    async def _ensure_store(self):
        """Lazily initialize the store connection."""
        if self._initialized:
            return

        # Try global store from checkpointing, fallback to InMemoryStore
        try:
            from core.workflows.checkpointing.manager import get_store, STORE_AVAILABLE
            if STORE_AVAILABLE:
                self._store = get_store()
                if self._store:
                    logger.info("StoreBackend: Using global AsyncPostgresStore")
        except ImportError:
            pass

        if self._store is None:
            logger.info("StoreBackend: Using InMemoryStore (fallback)")
            try:
                from langgraph.store.memory import InMemoryStore
                self._store = InMemoryStore()
            except ImportError:
                logger.warning("StoreBackend: langgraph.store.memory not available")

        self._initialized = True

    def _build_namespace(self, path: str) -> tuple:
        """Convert path to LangGraph Store namespace tuple."""
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            return (self.namespace,)
        return (self.namespace, *parts[:-1])

    def _get_key(self, path: str) -> str:
        """Extract key from path."""
        parts = [p for p in path.strip("/").split("/") if p]
        return parts[-1] if parts else "default"

    async def read(self, path: str) -> Any:
        """Read data from LangGraph Store."""
        await self._ensure_store()

        if not self._store:
            logger.warning("StoreBackend: Store not available")
            return None

        namespace = self._build_namespace(path)
        key = self._get_key(path)

        try:
            result = await self._store.aget(namespace, key)
            if result is None:
                logger.debug(f"StoreBackend: No data at {path}")
                return None
            # Result is a StoreItem with .value attribute
            return result.value if hasattr(result, 'value') else result
        except Exception as e:
            logger.error(f"StoreBackend read error: {e}")
            return None

    async def write(self, path: str, data: Any):
        """Write data to LangGraph Store."""
        await self._ensure_store()

        if not self._store:
            logger.warning("StoreBackend: Store not available")
            return

        namespace = self._build_namespace(path)
        key = self._get_key(path)

        try:
            await self._store.aput(namespace, key, {"value": data})
            logger.debug(f"StoreBackend: Wrote data to {path}")
        except Exception as e:
            logger.error(f"StoreBackend write error: {e}")
            raise

    async def list(self, path: str) -> List[str]:
        """List items at path in LangGraph Store."""
        await self._ensure_store()

        if not self._store:
            return []

        namespace = self._build_namespace(path)

        try:
            results = await self._store.asearch(namespace)
            return [item.key for item in results]
        except Exception as e:
            logger.error(f"StoreBackend list error: {e}")
            return []


class FilesystemBackend:
    """Backend using local filesystem."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_path = config.get("base_path", "/tmp/deepagent_storage")

    async def read(self, path: str) -> Any:
        import aiofiles
        import os
        full_path = os.path.join(self.base_path, path.lstrip("/"))
        async with aiofiles.open(full_path, 'r') as f:
            return await f.read()

    async def write(self, path: str, data: Any):
        import aiofiles
        import os
        full_path = os.path.join(self.base_path, path.lstrip("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, 'w') as f:
            await f.write(str(data))

    async def list(self, path: str) -> List[str]:
        import os
        full_path = os.path.join(self.base_path, path.lstrip("/"))
        if os.path.exists(full_path):
            return os.listdir(full_path)
        return []


class VectorDBBackend:
    """
    Backend using pgvector for semantic memory retrieval.

    Integrates with existing LlamaIndex PGVectorStore infrastructure:
    - Uses get_vector_store(project_id) for project-scoped tables
    - Uses Settings.embed_model for embeddings
    - Follows ContextRetriever patterns for search
    - Multi-tenant via project-scoped tables: data_project_index_{project_id}
    """

    def __init__(self, config: Dict[str, Any], project_id: int = None):
        self.config = config
        self.project_id = project_id
        self.namespace = config.get("namespace", "deepagent_memory")
        self.min_similarity = config.get("min_similarity", 0.7)
        self.top_k = config.get("top_k", 5)
        self._vector_store = None
        self._initialized = False
        logger.info(f"VectorDBBackend initialized (project_id={project_id}, namespace={self.namespace})")

    def set_project_id(self, project_id: int):
        """Set project_id for multi-tenant vector store access."""
        self.project_id = project_id
        self._initialized = False  # Force re-initialization

    async def _ensure_initialized(self):
        """Lazily initialize pgvector connection."""
        if self._initialized:
            return

        if not self.project_id:
            logger.warning("VectorDBBackend: No project_id set, cannot access vector store")
            return

        try:
            from services.llama_config import get_vector_store, ensure_initialized

            # Initialize LlamaIndex settings (embeddings model)
            ensure_initialized()

            # Get project-scoped vector store (table: data_project_index_{project_id})
            self._vector_store = get_vector_store(self.project_id)
            self._initialized = True
            logger.info(f"VectorDBBackend connected to pgvector (project={self.project_id})")

        except Exception as e:
            logger.error(f"VectorDBBackend initialization failed: {e}")
            self._vector_store = None

    async def read(self, path: str) -> Any:
        """Read data via semantic search. Path is used as query."""
        await self._ensure_initialized()

        if not self._vector_store:
            logger.warning("VectorDBBackend: Vector store not available")
            return None

        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.core.retrievers import VectorIndexRetriever

            # Create index and retriever
            index = VectorStoreIndex.from_vector_store(self._vector_store)
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=1
            )

            # Retrieve nodes
            nodes = await retriever.aretrieve(path)

            if nodes and nodes[0].score >= self.min_similarity:
                node = nodes[0]
                logger.debug(f"VectorDBBackend: Found node (score={node.score:.3f})")
                return {
                    "content": node.node.get_content(),
                    "metadata": node.node.metadata,
                    "score": node.score
                }
            return None

        except Exception as e:
            logger.error(f"VectorDBBackend read error: {e}")
            return None

    async def write(self, path: str, data: Any):
        """Store data with semantic embedding in pgvector."""
        await self._ensure_initialized()

        if not self._vector_store:
            logger.warning("VectorDBBackend: Vector store not available")
            return

        try:
            from llama_index.core.schema import TextNode
            from llama_index.core import Settings
            import uuid
            from datetime import datetime

            # Prepare content and metadata
            if isinstance(data, dict):
                content = str(data.get("content", data))
                extra_metadata = data.get("metadata", {})
            else:
                content = str(data)
                extra_metadata = {}

            # Generate embedding using Settings.embed_model
            embedding = await Settings.embed_model.aget_text_embedding(content)

            # Create TextNode with metadata
            node = TextNode(
                text=content,
                id_=str(uuid.uuid4()),
                embedding=embedding,
                metadata={
                    "namespace": self.namespace,
                    "path": path,
                    "project_id": self.project_id,
                    "indexed_at": datetime.utcnow().isoformat(),
                    **extra_metadata
                }
            )

            # Add to pgvector store
            self._vector_store.add([node])
            logger.debug(f"VectorDBBackend: Stored node at path={path}")

        except Exception as e:
            logger.error(f"VectorDBBackend write error: {e}")
            raise

    async def list(self, path: str) -> List[str]:
        """List documents matching a query prefix via semantic search."""
        results = await self.search(path, k=20)
        return [r.get("path", f"doc_{i}") for i, r in enumerate(results)]

    async def search(
        self,
        query: str,
        k: int = None,
        min_similarity: float = None,
        use_hyde: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search across stored memories.

        Args:
            query: Search query
            k: Number of results (default: self.top_k)
            min_similarity: Minimum similarity threshold
            use_hyde: Use HyDE (Hypothetical Document Embeddings) for better retrieval
        """
        await self._ensure_initialized()

        if not self._vector_store:
            return []

        k = k or self.top_k
        threshold = min_similarity or self.min_similarity

        try:
            # Option: Use ContextRetriever for HyDE-augmented search
            if use_hyde and self.project_id:
                try:
                    from services.context_retrieval import ContextRetriever

                    retriever = ContextRetriever()
                    result = await retriever.retrieve_context(
                        project_id=self.project_id,
                        task_description=query,
                        similarity_top_k=k,
                        use_hyde=True
                    )

                    return [
                        {
                            "content": chunk.get("text", ""),
                            "path": chunk.get("metadata", {}).get("path"),
                            "score": chunk.get("score", 0),
                            "metadata": chunk.get("metadata", {})
                        }
                        for chunk in result.get("chunks", [])
                        if chunk.get("score", 0) >= threshold
                    ]
                except ImportError:
                    logger.warning("VectorDBBackend: ContextRetriever not available, using standard retrieval")

            # Standard retrieval via VectorIndexRetriever
            from llama_index.core import VectorStoreIndex
            from llama_index.core.retrievers import VectorIndexRetriever

            index = VectorStoreIndex.from_vector_store(self._vector_store)
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=k
            )

            nodes = await retriever.aretrieve(query)

            return [
                {
                    "content": node.node.get_content(),
                    "path": node.node.metadata.get("path"),
                    "score": node.score,
                    "metadata": node.node.metadata
                }
                for node in nodes
                if node.score >= threshold
            ]

        except Exception as e:
            logger.error(f"VectorDBBackend search error: {e}")
            return []


class CompositeBackend:
    """Backend that combines multiple backends with path mappings."""

    def __init__(self, config: Dict[str, Any], mappings: Optional[Dict[str, Dict[str, Any]]], project_id: int = None):
        self.config = config
        self.mappings = mappings or {}
        self.backends = {}
        self.project_id = project_id

        # Create backends for each mapping
        for path_prefix, backend_config in self.mappings.items():
            backend_type = backend_config["type"]
            backend_cfg = backend_config.get("config", {})

            if backend_type == "state":
                self.backends[path_prefix] = StateBackend(backend_cfg)
            elif backend_type == "store":
                self.backends[path_prefix] = StoreBackend(backend_cfg)
            elif backend_type == "filesystem":
                self.backends[path_prefix] = FilesystemBackend(backend_cfg)
            elif backend_type == "vectordb":
                self.backends[path_prefix] = VectorDBBackend(backend_cfg, project_id=project_id)

    def _find_backend(self, path: str):
        """Find the appropriate backend for a path."""
        for prefix, backend in self.backends.items():
            if path.startswith(prefix):
                return backend, path[len(prefix):]
        # Default to first backend
        return list(self.backends.values())[0] if self.backends else None, path

    async def read(self, path: str) -> Any:
        backend, relative_path = self._find_backend(path)
        if backend:
            return await backend.read(relative_path)
        return None

    async def write(self, path: str, data: Any):
        backend, relative_path = self._find_backend(path)
        if backend:
            await backend.write(relative_path, data)

    async def list(self, path: str) -> List[str]:
        backend, relative_path = self._find_backend(path)
        if backend:
            return await backend.list(relative_path)
        return []
