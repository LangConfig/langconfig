# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Agent Factory for LangConfig.

Centralizes agent creation with proper configuration, tool binding, and memory integration.
This is the missing piece that connects agent configs from blueprints to actual LLM agents.

Key Responsibilities:
1. Create LLM instances from agent configs (model, temperature, etc.)
2. Load and bind MCP tools based on agent config
3. Add memory tools if enabled
4. Inject context into system prompts
5. Create fully configured LangGraph agents

This replaces the disconnected flow where agents were created without their configs.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Sequence
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.language_models import BaseLanguageModel, BaseChatModel
# IMPORTANT: LangChain v1.0 - Using unified create_agent from langchain.agents
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
# IMPORTANT: Added structured prompt components
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Assuming these modules exist in your project structure
# MIGRATED: Using native Python tools instead of MCP subprocess servers
from tools.native_tools import load_native_tools
from core.agents.memory import AgentMemorySystem
from config import settings

try:
    from langfuse.callback import CallbackHandler
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    CallbackHandler = None

logger = logging.getLogger(__name__)

# =============================================================================
# REASONING FRAMEWORK INJECTION (Enhances reliability)
# =============================================================================

# Default Configuration Constants
DEFAULT_MODEL = "claude-haiku-4-5-20251015"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 8192

# Validation Bounds Constants
MIN_TEMPERATURE = 0.0
MAX_TEMPERATURE = 2.0
MIN_MAX_TOKENS = 1
MAX_MAX_TOKENS = 500000

# Node Names Constants
REASONING_NODE = "agent"
TOOLS_NODE = "tools"

# Supported Models Registry (for validation) - Updated December 4, 2025
SUPPORTED_MODELS = {
    # OpenAI - GPT-5 Series (Current)
    "gpt-5.1",
    # OpenAI - GPT-4o Series
    "gpt-4o", "gpt-4o-mini",
    # Anthropic - Claude 4.5 (with and without date suffixes)
    "claude-opus-4-5", "claude-opus-4-5-20250514",
    "claude-sonnet-4-5", "claude-sonnet-4-5-20250514", "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5", "claude-haiku-4-5-20251015",
    # Google - Gemini 3 (Current)
    "gemini-3-pro-preview",
    # Google - Gemini 2.5
    "gemini-2.5-flash",
}

REASONING_FRAMEWORK = """
# AGENT EXECUTION FRAMEWORK (ReAct)
You are an autonomous agent. Follow this process meticulously:

1. **Analyze:** Understand the goal, conversation history, and context.
2. **Reason & Plan:** Determine the next necessary action. Decide if a tool is required.
3. **Act:** If a tool is needed, invoke it with precise parameters. You MUST use tools for external interactions (Files, APIs).
4. **Observe:** Analyze the tool output. If the goal is not met or an error occurs, adjust the plan and return to Step 2.
5. **Conclude:** Once the goal is achieved, synthesize the findings into a comprehensive final response.

## CRITICAL STOPPING CRITERIA:
- **STOP AFTER 2-3 TOOL CALLS** if you have sufficient information to answer the question
- **For searches**: One or two searches should provide enough context - do NOT search the same topic repeatedly
- **Quality over quantity**: It's better to provide a good answer with 2-3 sources than to keep searching indefinitely
- **When you have relevant information, STOP and provide your answer** - do not keep gathering more data
- **If a tool call succeeds and returns useful information, move to the Conclude step** - do not call the same tool again

## CRITICAL TOOL USAGE GUIDELINES:
- **ALWAYS verify you have ALL required parameters** before calling a tool
- **For file_write**: You MUST provide both `file_path` AND `content` parameters
  - Do NOT call file_write with only file_path
  - Wait until you have the complete content ready before writing files
- **Do NOT call tools with partial or missing arguments** - this will cause validation errors
- **If you don't have required information**, gather it first or ask for clarification
- **Read tool descriptions carefully** - they specify which parameters are required
- **Do NOT repeat the same tool call** - if web_search returns useful results, use them and move on
"""

class AgentFactory:
    """
    Factory for creating fully configured LangGraph tool-calling agents with resilience.
    """

    @staticmethod
    def _validate_agent_config(agent_config: Dict[str, Any]) -> List[str]:
        """
        Comprehensive validation of agent configuration.

        Validates:
        - Required fields
        - Parameter bounds (temperature, tokens)
        - Model compatibility
        - Tool configurations
        - Middleware compatibility
        - Mutual exclusions

        Returns:
            List of error/warning messages
        """
        errors = []

        # 1. Check required fields
        if not agent_config.get("model"):
            errors.append("model is required")

        # 2. Validate temperature bounds
        temperature = agent_config.get("temperature", DEFAULT_TEMPERATURE)
        if not isinstance(temperature, (int, float)):
            errors.append(f"temperature must be a number, got {type(temperature).__name__}")
        elif not (MIN_TEMPERATURE <= temperature <= MAX_TEMPERATURE):
            errors.append(f"temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}, got {temperature}")

        # 3. Validate max_tokens bounds
        max_tokens = agent_config.get("max_tokens", DEFAULT_MAX_TOKENS)
        if not isinstance(max_tokens, int):
            errors.append(f"max_tokens must be an integer, got {type(max_tokens).__name__}")
        elif not (MIN_MAX_TOKENS <= max_tokens <= MAX_MAX_TOKENS):
            errors.append(f"max_tokens must be between {MIN_MAX_TOKENS} and {MAX_MAX_TOKENS}, got {max_tokens}")

        # 4. Validate model name (warn if not in registry, don't fail)
        model_name = agent_config.get("model", DEFAULT_MODEL)
        if model_name and model_name not in SUPPORTED_MODELS:
            logger.warning(f"Model '{model_name}' not in supported registry. Supported: {sorted(SUPPORTED_MODELS)}")

        # 5. Check mutual exclusivity: structured output + tools
        # NOTE: Structured output and tools are mutually exclusive in most models.
        # When tools are bound, the model chooses between tool calls OR structured output,
        # creating unpredictable behavior. We disable structured output in favor of tools.
        has_tools = (
            agent_config.get("native_tools") or
            agent_config.get("mcp_tools") or
            agent_config.get("cli_tools") or
            agent_config.get("custom_tools")
        )
        if agent_config.get("enable_structured_output") and has_tools:
            errors.append("Cannot use structured output with tools (mutually exclusive)")

        # 6. Validate tool configurations (if tool IDs are strings)
        for tool_field in ["native_tools", "cli_tools", "custom_tools", "mcp_tools"]:
            tools_list = agent_config.get(tool_field, [])
            if tools_list and not isinstance(tools_list, list):
                errors.append(f"{tool_field} must be a list, got {type(tools_list).__name__}")
            elif tools_list:
                for tool in tools_list:
                    if not isinstance(tool, str):
                        errors.append(f"{tool_field} must contain strings, found {type(tool).__name__}")
                        break

        # 7. Validate interrupt node names (if provided as lists)
        for interrupt_field in ["interrupt_before", "interrupt_after"]:
            interrupt_val = agent_config.get(interrupt_field)
            if interrupt_val and isinstance(interrupt_val, list):
                valid_nodes = {REASONING_NODE, TOOLS_NODE}
                for node in interrupt_val:
                    if node not in valid_nodes:
                        logger.warning(f"{interrupt_field} contains unknown node '{node}'. Valid nodes: {valid_nodes}")

        # 8. Validate middleware configuration
        middleware = agent_config.get("middleware", [])
        if middleware and not isinstance(middleware, list):
            errors.append(f"middleware must be a list, got {type(middleware).__name__}")

        # 9. Validate fallback models
        fallback_models = agent_config.get("fallback_models", [])
        if fallback_models and not isinstance(fallback_models, list):
            errors.append(f"fallback_models must be a list, got {type(fallback_models).__name__}")
        elif fallback_models:
            for fallback in fallback_models:
                if not isinstance(fallback, str):
                    errors.append(f"fallback_models must contain strings, found {type(fallback).__name__}")
                    break

        return errors

    @staticmethod
    async def create_agent(
        agent_config: Dict[str, Any],
        project_id: int,
        task_id: int,
        context: str,
        mcp_manager: Optional[Any] = None,
        vector_store: Optional[Any] = None
    ) -> Tuple[CompiledStateGraph, List[BaseTool], List[Any]]:
        """
        Create a fully configured agent ready for execution.

        Tool Parallel Execution:
        - For queries needing multiple tools: "Weather in SF, NYC, and time in EST?"
        - The LLM recognizes it needs 3 tools and creates 3 tool calls in one message
        - create_agent routes all 3 to ToolNode concurrently (maxConcurrency determined by `enable_parallel_tools`)
        - Results aggregated and returned to LLM in single message

        Control via:
        - enable_parallel_tools=True: Tools execute concurrently (fast, default)
        - enable_parallel_tools=False: Tools execute sequentially (slower, if order matters)

        Returns:
            Tuple of (agent, tools, callbacks).
        """

        # 0. Validate Configuration
        config_errors = AgentFactory._validate_agent_config(agent_config)
        if config_errors:
            # Log but don't crash, just warn - resilience
            logger.warning(f"Config validation warnings: {', '.join(config_errors)}")

        # 1. Extract Configuration
        model_name = agent_config.get("model", DEFAULT_MODEL)
        temperature = agent_config.get("temperature", DEFAULT_TEMPERATURE)
        max_tokens = agent_config.get("max_tokens", DEFAULT_MAX_TOKENS)
        enable_streaming = agent_config.get("streaming", True)  # Enable by default for SSE streaming

        base_system_prompt = agent_config.get("system_prompt", "You are a helpful AI assistant.")
        native_tool_names = agent_config.get("native_tools", [])
        # Backward compatibility for mcp_tools
        if not native_tool_names:
            native_tool_names = agent_config.get("mcp_tools", [])
        # Added fallback support
        fallback_models = agent_config.get("fallback_models", [])
        # Memory configuration
        enable_memory = agent_config.get("enable_memory", False)

        # Long-term memory configuration (LangGraph Store)
        # Check both top-level and guardrails.long_term_memory for compatibility
        long_term_memory = agent_config.get("long_term_memory", False)
        if not long_term_memory and "guardrails" in agent_config:
            long_term_memory = agent_config.get("guardrails", {}).get("long_term_memory", False)

        # Middleware configuration (v1.0: Replaces hooks)
        middleware_list = agent_config.get("middleware", [])
        enable_default_middleware = agent_config.get("enable_default_middleware", True)

        # Backward compatibility: Support legacy hooks
        model_hooks = agent_config.get("model_hooks", [])
        enable_default_hooks = agent_config.get("enable_default_hooks", False)  # Disabled by default in v1.0

        # Structured output configuration (NEW: LangChain v1-alpha feature)
        output_schema = agent_config.get("output_schema", None)
        output_schema_name = agent_config.get("output_schema_name", None)
        enable_structured_output = agent_config.get("enable_structured_output", False)

        # Resolve schema name to actual schema if provided
        if not output_schema and output_schema_name and enable_structured_output:
            from core.utils.structured_outputs import STRUCTURED_OUTPUT_SCHEMAS
            output_schema = STRUCTURED_OUTPUT_SCHEMAS.get(output_schema_name)
            if output_schema:
                logger.info(f"📋 Resolved schema name '{output_schema_name}' to {output_schema.__name__}")
                agent_config["output_schema"] = output_schema  # Set for later use
            else:
                logger.warning(f"⚠️ Unknown schema name: {output_schema_name}. Available: {list(STRUCTURED_OUTPUT_SCHEMAS.keys())}")
                enable_structured_output = False  # Disable if schema not found

        # Parallel tool calling configuration
        enable_parallel_tools = agent_config.get("enable_parallel_tools", True)

        # HITL (Human-in-the-Loop) configuration
        interrupt_before = agent_config.get("interrupt_before", False)
        interrupt_after = agent_config.get("interrupt_after", False)

        logger.info(
            f"Creating agent for task {task_id} (model={model_name}, memory={enable_memory}, "
            f"long_term_memory={long_term_memory}, middleware={len(middleware_list)}, hooks={len(model_hooks)}, "
            f"structured_output={enable_structured_output}, streaming={enable_streaming})"
        )

        # 1b. Dynamic Model Routing (OPT-IN ONLY)
        # NOTE: Dynamic model routing requires middleware-based model selection.
        # Only activated when explicitly enabled in agent_config.
        enable_model_routing = agent_config.get("enable_model_routing", False)
        if enable_model_routing:
            try:
                from core.middleware.routing import ModelRouter

                router = ModelRouter()
                routing_strategy = agent_config.get("routing_strategy", "balanced")

                # Count tools that will be loaded
                tool_count = (
                    len(native_tool_names) +
                    len(agent_config.get("cli_tools", [])) +
                    len(agent_config.get("custom_tools", []))
                )

                # Build routing requirements
                routing_requirements = {
                    "streaming": enable_streaming,
                    "tools": tool_count > 0,
                    "structured_output": enable_structured_output,
                    "prompt_length": len(base_system_prompt),
                }

                # Route to best model
                original_model = model_name
                model_name = router.route(
                    original_model=original_model,
                    context_length=len(context),
                    tool_count=tool_count,
                    strategy=routing_strategy,
                    requirements=routing_requirements
                )

                if model_name != original_model:
                    logger.info(
                        f"🔀 Dynamic routing: {original_model} → {model_name} "
                        f"(strategy: {routing_strategy}, tools: {tool_count})"
                    )
            except Exception as e:
                logger.warning(f"Model routing failed, using original model: {e}")
                # Fall back to original model on error

        # 2. Create LLM with Fallbacks (Resilience)
        try:
            # Pass streaming flag to LLM config
            llm_config = {**agent_config, "streaming": enable_streaming}
            llm = await AgentFactory._create_llm_with_fallbacks(
                primary_model=model_name,
                fallback_models=fallback_models,
                temperature=temperature,
                max_tokens=max_tokens,
                config=llm_config
            )
        except ValueError as e:
            logger.error(f"LLM creation failed: {e}")
            raise

        # 3. Load Tools (Native, CLI, Memory, and RAG)
        tools: List[BaseTool] = []
        tools.extend(await AgentFactory._load_native_tools(native_tool_names))

        # Load CLI tools if specified
        cli_tools = agent_config.get("cli_tools", [])
        if cli_tools:
            tools.extend(await AgentFactory._load_cli_tools(cli_tools))

        # Load custom user-defined tools
        custom_tool_ids = agent_config.get("custom_tools", [])
        logger.info(f"📦 Custom tool IDs from config: {custom_tool_ids}")
        if custom_tool_ids:
            custom_tools_loaded = await AgentFactory._load_custom_tools(custom_tool_ids, project_id)
            logger.info(f"✓ Loaded {len(custom_tools_loaded)} custom tools: {[t.name for t in custom_tools_loaded]}")
            tools.extend(custom_tools_loaded)
        else:
            logger.info("ℹ️ No custom tools specified in agent config")

        if enable_memory:
            tools.extend(await AgentFactory._load_memory_tools(vector_store, project_id, task_id))

        # Check if RAG (codebase search) is enabled
        enable_rag = agent_config.get("enable_rag", False)
        if enable_rag:
            tools.extend(await AgentFactory._load_rag_tools(vector_store, project_id))

        # DIAGNOSTIC: Log final tool list (before constraint wrapping)
        tool_names = [t.name for t in tools]
        logger.info(f"🔧 TOOLS LOADED: {tool_names}")
        if "web_search" in tool_names and not native_tool_names:
            logger.error(f"❌ BUG DETECTED: web_search tool present but native_tools config is empty!")
            logger.error(f"   native_tool_names requested: {native_tool_names}")
            logger.error(f"   cli_tools requested: {cli_tools}")
            logger.error(f"   custom_tools requested: {custom_tool_ids}")

        # 3b. Wrap tools with execution constraints from action presets
        # This enforces timeouts, retries, and exclusive execution based on action preset metadata
        try:
            from core.tools.execution_wrapper import wrap_tools_with_constraints

            # Check if constraint enforcement is enabled (default: True for production safety)
            enforce_constraints = agent_config.get("enforce_tool_constraints", True)

            if enforce_constraints and tools:
                logger.info(f"🛡️ Wrapping {len(tools)} tools with execution constraints from action presets")
                tools = wrap_tools_with_constraints(tools)
                logger.info(f"✓ Tool constraint enforcement enabled")
            else:
                if not enforce_constraints:
                    logger.warning(f"⚠️ Tool constraint enforcement DISABLED by agent config")
        except Exception as e:
            logger.warning(f"Failed to wrap tools with constraints: {e}. Tools will run without constraint enforcement.")
            # Continue without constraint wrapping - tools still work, just without safety enforcement

        # 4. Check if structured output is enabled (v1.0: Use strategies)
        structured_output_strategy = None
        if enable_structured_output and output_schema:
            # NOTE: Structured output and tools are mutually exclusive in most models.
            # When tools are bound, the model chooses between tool calls OR structured output,
            # creating unpredictable behavior. We disable structured output in favor of tools.
            if agent_config.get("cli_tools") or agent_config.get("native_tools") or agent_config.get("mcp_tools"):
                logger.info(
                    f"Skipping structured output ({output_schema.__name__}) because tools are enabled; avoiding model/tool mismatch"
                )
                enable_structured_output = False
            else:
                # v1.0: Use ToolStrategy for structured output (more reliable than provider-native)
                from langchain.agents.structured_output import ToolStrategy

                structured_output_strategy = ToolStrategy(output_schema)
                logger.info(f"🔧 Structured output ENABLED: {output_schema.__name__} (using ToolStrategy)")
                agent_config["_output_schema"] = output_schema
                agent_config["_structured_output_strategy"] = structured_output_strategy

        # 4b. Check if dynamic model routing is enabled (NEW: LangChain v1-alpha feature)
        # NOTE: Dynamic model routing requires middleware-based model selection
        # Not yet supported in create_agent v1.0. Plan to implement via custom middleware.
        enable_model_routing = False
        # enable_model_routing = agent_config.get("enable_model_routing", False)

        if enable_model_routing:
            # Use dynamic model selection (60-80% cost savings!)
            from core.models.selector import ModelSelector

            logger.info(f"🚀 Dynamic model routing ENABLED for task {task_id} - optimizing for cost/quality")

            model_selector_instance = ModelSelector(
                primary_model=model_name,
                temperature=temperature,
                enable_routing=True,
                agent_config=agent_config,
                use_model_router_config=True  # Integrate with existing ModelRouter
            )

            # Create selector function that returns model with bound tools
            model_fn = model_selector_instance.create_selector(tools)

            # Store selector instance for stats tracking
            agent_config["_model_selector"] = model_selector_instance

            llm_or_model = model_fn  # This will be a Callable, not a BaseChatModel

        else:
            # Traditional static model
            llm_or_model = llm

            # NOTE: We do NOT bind tools here manually anymore.
            # create_agent handles tool binding internally, supporting parallel execution
            # based on the 'tools' argument passed to it.

        # 5. Augment Context with Pattern Recommendations (Learning Integration)
        augmented_context = await AgentFactory._augment_context_with_patterns(
            context=context,
            agent_config=agent_config,
            project_id=project_id,
            task_id=task_id
        )

        # 6. Create Optimized Prompt (Context Engineering)
        # v1.0: create_agent accepts string for system_prompt, handles messages automatically
        system_prompt_str = AgentFactory._construct_system_prompt_string(
            base_system_prompt, augmented_context, enable_memory, long_term_memory, tools
        )

        # 6b. Setup Middleware (v1.0) or Hooks (legacy)
        middleware = None
        hook_manager = None

        # v1.0: Prefer middleware over hooks
        if middleware_list or enable_default_middleware:
            middleware = await AgentFactory._setup_middleware(
                middleware_list=middleware_list,
                enable_default_middleware=enable_default_middleware,
                project_id=project_id,
                task_id=task_id
            )

            # Store middleware in config
            if middleware:
                agent_config["_middleware"] = middleware

        # Backward compatibility: Support legacy hooks if no middleware
        elif model_hooks or enable_default_hooks:
            logger.info("Using legacy hooks (consider migrating to middleware)")
            hook_manager = await AgentFactory._setup_model_hooks(
                model_hooks=model_hooks,
                enable_default_hooks=enable_default_hooks,
                project_id=project_id,
                task_id=task_id
            )

            # Store hook manager in config for later access
            if hook_manager:
                agent_config["_hook_manager"] = hook_manager

        # 6c. Setup Callbacks (e.g., LangFuse Tracing, Token Tracking)
        callbacks = AgentFactory._configure_callbacks(
            project_id=project_id,
            task_id=task_id,
            model_name=model_name,
            temperature=temperature,
            tools_count=len(tools),
            memory_enabled=enable_memory,
            fallbacks=fallback_models,
            mcp_tool_names=native_tool_names,
            agent_config=agent_config
        )

        # 7. Create LangGraph Agent (v1.0 API)
        try:
            # Use the unified agent creator
            create_agent_kwargs = {
                "model": llm_or_model,  # Unbound model (or selector callable)
                "tools": tools or [],   # create_agent handles binding
                "system_prompt": system_prompt_str,  # v1.0: Pass string, messages handled automatically
                # Note: callbacks are passed when invoking the agent, not when creating it
                # Note: streaming is configured on the model object itself, not here
                # "enable_parallel_tools": enable_parallel_tools # If supported by create_agent
            }

            # Add structured output strategy if enabled (v1.0 pattern)
            if structured_output_strategy:
                create_agent_kwargs["response_format"] = structured_output_strategy

            # Add middleware if enabled (v1.0 pattern)
            # Middleware support is now stable in LangChain 1.0
            if middleware:
                create_agent_kwargs["middleware"] = middleware
                middleware_names = [m.__class__.__name__ for m in middleware]
                logger.info(f"✓ Middleware enabled: {', '.join(middleware_names)} ({len(middleware)} total)")
            else:
                logger.debug("No middleware configured for this agent")

            # Add context_schema if provided (v1.0 pattern)
            # Allows agents to use custom runtime context types
            context_schema = agent_config.get("context_schema")
            if context_schema:
                # TODO: When langchain.agents fully supports context_schema parameter, uncomment:
                # create_agent_kwargs["context_schema"] = context_schema
                logger.debug(f"Context schema configured: {context_schema.__name__ if hasattr(context_schema, '__name__') else context_schema}")

            # Add HITL (Human-in-the-Loop) parameters
            # interrupt_before: List of node names to pause before execution
            # interrupt_after: List of node names to pause after execution
            # Common node names: ["agent"], ["tools"]
            # FIX: Support custom node lists, not just hardcoded ["agent"]
            if interrupt_before:
                nodes = interrupt_before if isinstance(interrupt_before, list) else ["agent"]
                create_agent_kwargs["interrupt_before"] = nodes
                logger.info(f"✓ HITL: Interrupt before nodes: {nodes}")
            if interrupt_after:
                nodes = interrupt_after if isinstance(interrupt_after, list) else ["agent"]
                create_agent_kwargs["interrupt_after"] = nodes
                logger.info(f"✓ HITL: Interrupt after nodes: {nodes}")

            agent_graph = create_agent(**create_agent_kwargs)

            # FIX: Verify tool binding succeeded
            if tools:
                logger.info(f"✓ Tools bound to agent: {len(tools)} tools configured")
                logger.debug(f"   Tool names: {[t.name for t in tools]}")
                # Verify parallel tool calling configuration
                if enable_parallel_tools:
                    logger.debug("   Parallel tool execution: ENABLED")
                else:
                    logger.debug("   Sequential tool execution: ENABLED")

            # Verify callbacks registered
            if callbacks:
                callback_types = [type(cb).__name__ for cb in callbacks]
                logger.info(f"✓ Callbacks registered: {', '.join(callback_types)}")

            # Log feature status
            features = []
            if enable_model_routing:
                features.append("dynamic routing")
            if enable_structured_output:
                features.append(f"structured output ({output_schema.__name__})")
            if enable_streaming:
                features.append("streaming enabled")
            if middleware:
                features.append(f"{len(middleware)} middleware")
            elif hook_manager:
                features.append(f"{len(hook_manager.hooks)} hooks (legacy)")

            if features:
                logger.info(f"✓ Agent created with: {', '.join(features)}")
            else:
                logger.info(f"✓ Agent created with static model: {model_name}")

            # Return callbacks separately for use during invocation
            return agent_graph, tools, callbacks

        except Exception as e:
            logger.error(f"Failed to create LangGraph agent: {e}", exc_info=True)
            raise

    # =============================================================================
    # Helper Methods
    # =============================================================================

    @staticmethod
    def _construct_system_prompt_string(base_prompt: str, context: str, enable_memory: bool, long_term_memory: bool = False, tools: List[BaseTool] = None) -> str:
        """
        Constructs the system prompt string using Context Engineering principles.
        Structure: Reasoning -> Role/Goal -> Context

        Note: In LangChain v1.0, create_agent handles message history automatically.
        We only need to provide the system prompt string.
        """
        # Dynamically inject memory instructions if enabled
        reasoning = REASONING_FRAMEWORK
        if enable_memory:
            reasoning += "\n# MEMORY USAGE\nYou have access to long-term memory tools (e.g., 'memory_recall', 'memory_store'). Use them to access and record knowledge relevant to this project."

        if long_term_memory:
            reasoning += "\n# WORKFLOW-SCOPED LONG-TERM MEMORY\nYou have access to workflow-scoped persistent memory via the LangGraph Store API (runtime.store). Use this to remember important information across workflow executions. Store data using workflow-specific namespaces."

        # CRITICAL: Add explicit tool enforcement if tools are available
        tool_enforcement = ""
        if tools and len(tools) > 0:
            tool_names = [t.name for t in tools]
            tool_enforcement = f"""
# CRITICAL TOOL USAGE REQUIREMENT
You have been equipped with the following tools: {', '.join(tool_names)}

**MANDATORY REQUIREMENT:**
- If your role involves using external services, APIs, or generating content (images, files, etc.), you MUST use the appropriate tool
- DO NOT just describe what you would do or provide meta-commentary
- DO NOT say things like "I understand" or "I need to work with what I have"
- ACTUALLY INVOKE THE TOOL to complete your task
- For example, if you are an "Image Generator" with an image generation tool, you MUST call that tool to generate images
- If you are a "File Writer" with a file writing tool, you MUST call that tool to write files
- Your output should be the RESULT of tool execution, not a description of what you plan to do

**If you fail to use your tools when required, your output will be considered incomplete.**
"""

        system_message_content = f"""{reasoning}
{tool_enforcement}
# YOUR SPECIFIC ROLE AND GOAL
{base_prompt}

# CURRENT CONTEXT AND TASK INFORMATION
<context>
{context}
</context>
---
"""
        return system_message_content

    @staticmethod
    def _construct_prompt_template(base_prompt: str, context: str, enable_memory: bool, long_term_memory: bool = False) -> ChatPromptTemplate:
        """
        DEPRECATED: Use _construct_system_prompt_string for v1.0 agents.

        Kept for backward compatibility with legacy code that needs ChatPromptTemplate.
        """
        system_message_content = AgentFactory._construct_system_prompt_string(base_prompt, context, enable_memory, long_term_memory)
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_message_content),
            MessagesPlaceholder(variable_name="messages"),
        ])
        return prompt_template

    @staticmethod
    async def _augment_context_with_patterns(
        context: str,
        agent_config: Dict[str, Any],
        project_id: int,
        task_id: int
    ) -> str:
        """
        Augment context with learned pattern recommendations.

        This integrates pattern learning into agent execution by providing agents with
        proven strategies from past successful workflows.

        Args:
            context: Original context string
            agent_config: Agent configuration (contains pattern hints)
            project_id: Project ID for pattern filtering
            task_id: Task ID for logging

        Returns:
            Augmented context string with pattern recommendations appended
        """
        try:
            # Check if pattern recommendations are enabled for this agent
            enable_patterns = agent_config.get("enable_pattern_recommendations", False)
            if not enable_patterns:
                logger.debug(f"Pattern recommendations disabled for task {task_id}")
                return context

            # Try to extract task description from context for better pattern matching
            # The context usually contains the task description in some form
            task_description = agent_config.get("task_description", "")
            if not task_description:
                # Try to extract from context (simple heuristic)
                lines = context.split('\n')
                # Look for lines that might contain task description
                for line in lines[:10]:  # Check first 10 lines
                    if len(line.strip()) > 20 and not line.strip().startswith('#'):
                        task_description = line.strip()
                        break

            if not task_description:
                logger.debug(f"No task description found for pattern recommendations (task {task_id})")
                return context

            # Get pattern type hints from agent config or default to common useful patterns
            pattern_types = agent_config.get("pattern_types", ["context_strategy", "agent_behavior"])

            # Fetch pattern recommendations
            from services.pattern_learning_service import PatternLearningService
            from models.agent_pattern import PatternType
            from backend.db.session import SessionLocal

            pattern_recommendations = []

            async with SessionLocal() as db:
                service = PatternLearningService(db)

                for pattern_type_str in pattern_types[:2]:  # Limit to 2 pattern types to avoid context bloat
                    try:
                        pattern_type = PatternType(pattern_type_str)
                        patterns = await service.get_pattern_recommendations(
                            task_description=task_description,
                            pattern_type=pattern_type,
                            project_id=project_id,
                            min_confidence=0.7,  # Only high-confidence recommendations
                            limit=2  # Max 2 recommendations per type
                        )

                        if patterns:
                            pattern_recommendations.extend(patterns)
                            logger.info(
                                f"Found {len(patterns)} {pattern_type_str} patterns for task {task_id}"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to get {pattern_type_str} patterns: {e}")
                        continue

            # If no patterns found, return original context
            if not pattern_recommendations:
                logger.debug(f"No pattern recommendations found for task {task_id}")
                return context

            # Format pattern recommendations for injection
            pattern_section = "\n\n# LEARNED PATTERNS FROM PAST SUCCESSES\n"
            pattern_section += "The following patterns have proven successful for similar tasks:\n\n"

            for i, pattern in enumerate(pattern_recommendations[:3], 1):  # Max 3 total patterns
                pattern_section += f"**Pattern {i}: {pattern.pattern_name}** (Type: {pattern.pattern_type})\n"
                pattern_section += f"- Success Rate: {pattern.success_rate:.1%} ({pattern.success_count}/{pattern.usage_count} uses)\n"
                pattern_section += f"- Confidence: {pattern.confidence:.2f}\n"

                if pattern.description:
                    pattern_section += f"- Description: {pattern.description}\n"

                if pattern.pattern_config:
                    # Format config as readable text (avoid dumping full JSON)
                    config_highlights = []
                    for key, value in list(pattern.pattern_config.items())[:3]:  # Top 3 config items
                        config_highlights.append(f"{key}: {value}")
                    if config_highlights:
                        pattern_section += f"- Key Settings: {', '.join(config_highlights)}\n"

                pattern_section += "\n"

            pattern_section += "**Recommendation:** Consider applying these proven patterns to improve success probability.\n"
            pattern_section += "---\n"

            # Append patterns to context
            augmented_context = context + pattern_section

            logger.info(
                f"Augmented context with {len(pattern_recommendations)} pattern recommendations "
                f"for task {task_id}"
            )

            return augmented_context

        except Exception as e:
            # Fail gracefully - if pattern retrieval fails, agent should still work with original context
            logger.warning(
                f"Failed to augment context with patterns for task {task_id}: {e}. "
                "Proceeding with original context."
            )
            return context

    @staticmethod
    async def _create_llm_with_fallbacks(
        primary_model: str,
        fallback_models: Sequence[str],
        temperature: float,
        max_tokens: Optional[int],
        config: Dict[str, Any]
    ) -> BaseLanguageModel:
        """
        Creates the primary LLM and configures fallbacks if provided.

        FIX: Enhanced error handling to ensure at least one model succeeds.

        Args:
            primary_model: Primary model identifier
            fallback_models: List of fallback model identifiers
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate
            config: Full agent configuration

        Returns:
            Configured LLM instance with fallbacks

        Raises:
            ValueError: If primary and all fallback models fail to initialize
        """
        attempted_models = []
        errors = []

        # Try primary model
        try:
            logger.info(f"Attempting to create primary model: {primary_model}")
            primary_llm = await AgentFactory._create_llm(primary_model, temperature, max_tokens, config)
            attempted_models.append(primary_model)
            logger.info(f"✓ Primary model '{primary_model}' initialized successfully")
        except Exception as e:
            error_msg = f"Primary model '{primary_model}' failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            primary_llm = None

        # If no fallback models provided, fail if primary failed
        if not fallback_models:
            if primary_llm is None:
                raise ValueError(
                    f"Failed to initialize primary model '{primary_model}'. "
                    f"Error: {errors[0]}"
                )
            return primary_llm

        # Try fallback models
        fallbacks = []
        for fb_model in fallback_models:
            try:
                logger.info(f"Attempting fallback model: {fb_model}")
                fb_llm = await AgentFactory._create_llm(fb_model, temperature, max_tokens, config)
                fallbacks.append(fb_llm)
                attempted_models.append(fb_model)
                logger.info(f"✓ Fallback model '{fb_model}' initialized successfully")
            except Exception as e:
                error_msg = f"Fallback model '{fb_model}' failed: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # If primary succeeded, apply fallbacks and return
        if primary_llm is not None:
            if fallbacks:
                logger.info(f"✓ Configured {len(fallbacks)} fallback(s) for primary model '{primary_model}'")
                return primary_llm.with_fallbacks(fallbacks)
            else:
                logger.warning(f"Primary model succeeded but no fallbacks available")
                return primary_llm

        # Primary failed - try to use first successful fallback as primary
        if fallbacks:
            logger.warning(
                f"Primary model '{primary_model}' failed, using first successful fallback '{fallback_models[0]}' as primary"
            )
            # Use first fallback as primary, rest as additional fallbacks
            primary_llm = fallbacks[0]
            additional_fallbacks = fallbacks[1:]
            if additional_fallbacks:
                return primary_llm.with_fallbacks(additional_fallbacks)
            return primary_llm

        # All models failed - raise comprehensive error
        raise ValueError(
            f"Failed to initialize any LLM. Attempted models: {attempted_models}. "
            f"Errors: {'; '.join(errors)}"
        )

    @staticmethod
    async def _create_llm(
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        config: Dict[str, Any]
    ) -> BaseChatModel:
        """
        Create an LLM instance based on model name.

        Supports:
        - OpenAI (GPT-5, GPT-4.5, o1, etc.) - Updated for 10/6/2025
        - Anthropic (Claude 4.x, Claude 3.7, etc.) - Updated for 10/6/2025
        - Google (Gemini 2.0, Gemini 1.7) - Updated for 10/6/2025
        - Local models via LiteLLM proxy

        Args:
            model_name: Model identifier (e.g., "gpt-5-turbo", "claude-4-sonnet", "gemini-2-pro")
            temperature: Temperature for generation (0.0-2.0)
            max_tokens: Maximum tokens to generate
            config: Full agent config (for provider-specific params)

        Returns:
            LangChain LLM instance (ChatOpenAI, ChatAnthropic, etc.)
        """
        logger.debug(f"Initializing LLM instance for model: {model_name}")
        streaming = config.get("streaming", True)  # Enable by default for SSE streaming

        # --- OpenAI/GPT Models ---
        if model_name.startswith("gpt"):
            if not settings.OPENAI_API_KEY:
                raise ValueError(f"OPENAI_API_KEY is required for model {model_name}")

            params = {
                "model": model_name, "temperature": temperature, "max_tokens": max_tokens,
                "streaming": streaming, "api_key": settings.OPENAI_API_KEY,
            }
            api_base = getattr(settings, 'OPENAI_API_BASE', None)
            if api_base:
                params["base_url"] = api_base
            return ChatOpenAI(**params)

        # --- Anthropic/Claude Models ---
        elif model_name.startswith("claude"):
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError(f"ANTHROPIC_API_KEY is required for model {model_name}")

            return ChatAnthropic(
                model=model_name, temperature=temperature,
                max_tokens=max_tokens or 8192, # Updated for Claude 4.x models with larger context
                api_key=settings.ANTHROPIC_API_KEY,
                streaming=streaming,
            )

        # --- Google/Gemini Models ---
        elif model_name.startswith("gemini"):
            api_key = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY
            if not api_key:
                 raise ValueError(f"Google API Key is required for model {model_name}")

            # Extract reasoning_effort and modalities from config
            reasoning_effort = config.get("reasoning_effort")
            modalities = config.get("modalities")

            # Build model kwargs
            model_kwargs = {
                "model": model_name,
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "google_api_key": api_key,
                "convert_system_message_to_human": True,  # CRITICAL FIX: Helps Gemini handle system prompts + tools
            }

            # Add reasoning_effort if specified (maps to Gemini's thinking parameters)
            # Per LiteLLM docs: Gemini 3+ uses thinking_level, Gemini 2.x uses thinking_budget
            if reasoning_effort:
                is_gemini_3 = "gemini-3" in model_name.lower()

                if is_gemini_3:
                    # Gemini 3+ uses thinking_level: "low" or "high"
                    thinking_level_map = {
                        "none": "low",      # Can't fully disable in Gemini 3
                        "minimal": "low",
                        "low": "low",
                        "medium": "high",   # Medium maps to high
                        "high": "high"
                    }
                    thinking_level = thinking_level_map.get(reasoning_effort, "low")
                    model_kwargs["thinking_level"] = thinking_level
                    logger.info(f"Gemini 3 reasoning: effort={reasoning_effort} -> thinking_level={thinking_level}")
                else:
                    # Gemini 2.x uses thinking_budget (token count)
                    thinking_budget_map = {
                        "none": 0,      # Cost optimized - 96% cheaper
                        "disable": 0,
                        "low": 1024,
                        "medium": 2048,
                        "high": 4096
                    }
                    budget = thinking_budget_map.get(reasoning_effort, 1024)
                    model_kwargs["thinking"] = {"budget_tokens": budget, "includeThoughts": budget > 0}
                    logger.info(f"Gemini 2.x reasoning: effort={reasoning_effort} -> budget={budget} tokens")

            # Add modalities if specified (for image generation models)
            if modalities:
                model_kwargs["modalities"] = modalities
                logger.info(f"Gemini modalities: {modalities}")

            return ChatGoogleGenerativeAI(**model_kwargs)

        # --- Local Models (Ollama, LM Studio, vLLM, etc.) ---
        elif model_name.startswith("local-") or any(model_name.startswith(f"{p}-") for p in ["ollama", "lmstudio", "vllm", "litellm"]):
            from services.local_model_service import LocalModelService

            # Load local model configuration from database
            local_config = LocalModelService.get_local_model_config(model_name)

            if not local_config:
                raise ValueError(
                    f"Local model '{model_name}' not found or not validated. "
                    "Configure it in Settings > Local Models and test the connection."
                )

            logger.info(f"✓ Creating local model: {local_config.model_name} via {local_config.provider} at {local_config.base_url}")

            return ChatOpenAI(
                model=local_config.model_name,
                base_url=local_config.base_url,
                api_key=local_config.api_key or "not-needed",
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
                timeout=local_config.timeout
            )

        else:
            logger.warning(f"Unknown model '{model_name}', defaulting to OpenAI-compatible (Ensure API/Base URL configured).")
            return ChatOpenAI(model=model_name, temperature=temperature, max_tokens=max_tokens, streaming=streaming)


    @staticmethod
    async def _load_native_tools(native_tool_names: List[str]) -> List[BaseTool]:
        """
        Helper to load native Python tools.

        Special handling for "browser" tool which uses Playwright (async).
        """
        if not native_tool_names:
            return []
        try:
            all_tools = []

            # Check if browser tools are requested (requires special async handling)
            browser_requested = "browser" in native_tool_names
            non_browser_tools = [t for t in native_tool_names if t != "browser"]

            # Load regular native tools (synchronous)
            if non_browser_tools:
                native_tools = load_native_tools(non_browser_tools)
                all_tools.extend(native_tools)
                logger.info(f"✓ Loaded {len(native_tools)} native Python tools")

            # Load Playwright browser tools (asynchronous) if requested
            if browser_requested:
                try:
                    from tools.native_tools import load_playwright_tools
                    browser_tools = await load_playwright_tools()
                    all_tools.extend(browser_tools)
                    logger.info(f"✓ Loaded {len(browser_tools)} Playwright browser tools")
                except Exception as e:
                    logger.error(f"Failed to load Playwright browser tools: {e}")
                    logger.error("Proceeding without browser automation")

            return all_tools
        except Exception as e:
            logger.error(f"Failed to load native tools: {e}. Proceeding without them.")
            return []

    @staticmethod
    async def _load_cli_tools(cli_tool_names: List[str]) -> List[BaseTool]:
        """
        Helper to load CLI-based tools (e.g., Jira CLI tools).

        Args:
            cli_tool_names: List of CLI tool categories to load (e.g., ["jira"])

        Returns:
            List of BaseTool instances
        """
        if not cli_tool_names:
            return []

        tools: List[BaseTool] = []

        try:
            for tool_category in cli_tool_names:
                if tool_category == "jira":
                    # Import Jira CLI tools
                    from backend.tools.jira_cli_tools import JIRA_CLI_TOOLS
                    tools.extend(JIRA_CLI_TOOLS)
                    logger.info(f"✓ Loaded {len(JIRA_CLI_TOOLS)} Jira CLI tools")
                else:
                    logger.warning(f"Unknown CLI tool category: {tool_category}")

            return tools

        except Exception as e:
            logger.error(f"Failed to load CLI tools: {e}. Proceeding without them.")
            return []

    @staticmethod
    async def _load_custom_tools(custom_tool_ids: List[str], project_id: int) -> List[BaseTool]:
        """
        Load user-defined custom tools from database.

        Args:
            custom_tool_ids: List of custom tool IDs to load
            project_id: Project ID for scoping

        Returns:
            List of BaseTool instances
        """
        if not custom_tool_ids:
            return []

        tools: List[BaseTool] = []

        try:
            # Import dependencies
            from core.tools.factory import ToolFactory
            from models.custom_tool import CustomTool
            from db.database import SessionLocal

            # Get database session
            db = SessionLocal()
            try:
                # First, list all available custom tools for debugging
                all_tools = db.query(CustomTool).all()
                logger.info(f"🔍 Available custom tools in database: {[(t.tool_id, t.name) for t in all_tools]}")

                for tool_id in custom_tool_ids:
                    try:
                        logger.info(f"🔍 Attempting to load custom tool with ID: '{tool_id}'")

                        # Fetch tool from database
                        custom_tool = db.query(CustomTool).filter(
                            CustomTool.tool_id == tool_id
                        ).first()

                        if not custom_tool:
                            logger.error(f"❌ Custom tool '{tool_id}' not found in database. Available tools: {[t.tool_id for t in all_tools]}")
                            continue

                        # Build tool configuration from database model
                        tool_config = {
                            "tool_id": custom_tool.tool_id,
                            "name": custom_tool.name,
                            "description": custom_tool.description,
                            "tool_type": custom_tool.tool_type.value,
                            "template_type": custom_tool.template_type.value if custom_tool.template_type else None,
                            "implementation_config": custom_tool.implementation_config,
                            "input_schema": custom_tool.input_schema,
                            "output_format": custom_tool.output_format
                        }

                        # Create the tool using ToolFactory
                        tool = await ToolFactory.create_tool(tool_config, project_id)
                        tools.append(tool)

                        # Update usage tracking
                        custom_tool.usage_count += 1
                        custom_tool.last_used_at = datetime.utcnow()
                        db.commit()

                        logger.info(f"✓ Loaded custom tool: {custom_tool.name} ({tool_id})")

                    except Exception as e:
                        logger.error(f"Failed to load custom tool '{tool_id}': {e}")
                        # Track error
                        try:
                            custom_tool_error = db.query(CustomTool).filter(
                                CustomTool.tool_id == tool_id
                            ).first()
                            if custom_tool_error:
                                custom_tool_error.error_count += 1
                                custom_tool_error.last_error_at = datetime.utcnow()
                                db.commit()
                        except:
                            pass
                        continue

                logger.info(f"✓ Loaded {len(tools)} custom tools total")
                return tools

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to load custom tools: {e}. Proceeding without them.")
            return []

    @staticmethod
    async def _load_memory_tools(vector_store, project_id: int, task_id: int) -> List[BaseTool]:
        """Helper to load and validate memory tools."""
        if vector_store is None:
            logger.warning("Vector store not provided, skipping memory tools.")
            return []

        try:
            memory_system = AgentMemorySystem(
                vector_store=vector_store,
                project_id=project_id,
                agent_id=f"task_{task_id}"
            )
            # The new memory system returns a List[BaseTool] directly (already structured)
            memory_tools = memory_system.create_memory_tools()

            logger.info(f"✓ Loaded {len(memory_tools)} memory tools")
            return memory_tools

        except Exception as e:
            logger.error(f"Failed to add memory tools: {e}. Proceeding without them.")
            return []

    @staticmethod
    async def _load_rag_tools(vector_store, project_id: int) -> List[BaseTool]:
        """Helper to load RAG (codebase search) tools using LlamaIndex."""
        try:
            from core.tools.adapters.llamaindex import create_llamaindex_rag_tools

            rag_tools = await create_llamaindex_rag_tools(project_id=project_id)

            logger.info(f"✓ Loaded {len(rag_tools)} RAG tools (LlamaIndex)")
            return rag_tools

        except Exception as e:
            logger.error(f"Failed to add RAG tools: {e}. Proceeding without them.")
            return []

    @staticmethod
    async def _setup_middleware(
        middleware_list: List[Any],
        enable_default_middleware: bool,
        project_id: int,
        task_id: int
    ) -> Optional[List]:
        """
        Setup middleware for v1.0 agent execution.

        Middleware provides powerful hooks for:
        - Dynamic prompts (@dynamic_prompt)
        - Pre/post model processing (before_model, after_model)
        - Tool error handling (wrap_tool_call)
        - Summarization and HITL gates

        Args:
            middleware_list: List of middleware instances or configurations
            enable_default_middleware: Whether to add default middleware
            project_id: Project ID for context
            task_id: Task ID for context

        Returns:
            List of middleware instances or None
        """
        from core.middleware.core import (
            AgentMiddleware,
            get_default_middleware,
            create_middleware_from_config,
            migrate_hook_to_middleware
        )

        middleware = []

        # Add default middleware if enabled
        if enable_default_middleware:
            default_middleware = get_default_middleware()
            middleware.extend(default_middleware)
            logger.info(f"✓ Added {len(default_middleware)} default middleware")

        # Add custom middleware
        for item in middleware_list:
            if isinstance(item, AgentMiddleware):
                # Already a middleware instance
                middleware.append(item)
            elif isinstance(item, dict):
                # Configuration dict - create middleware
                try:
                    middleware_instance = create_middleware_from_config(item)
                    middleware.append(middleware_instance)
                except Exception as e:
                    logger.error(f"Failed to create middleware from config: {e}")
            elif hasattr(item, 'pre_model') and hasattr(item, 'post_model'):
                # Legacy hook - migrate to middleware
                logger.info(f"Migrating legacy hook {item.__class__.__name__} to middleware")
                try:
                    middleware_instance = migrate_hook_to_middleware(item)
                    middleware.append(middleware_instance)
                except Exception as e:
                    logger.error(f"Failed to migrate hook to middleware: {e}")
            else:
                logger.warning(f"Unknown middleware type: {type(item)}")

        # Deduplicate middleware by name (custom overrides defaults)
        if middleware:
            seen_names = {}
            deduplicated = []

            # Process in reverse so custom middleware (added last) takes precedence
            for mw in reversed(middleware):
                name = getattr(mw, 'name', mw.__class__.__name__)
                if name not in seen_names:
                    seen_names[name] = True
                    deduplicated.insert(0, mw)  # Insert at beginning to maintain order
                else:
                    logger.debug(f"Skipping duplicate middleware: {name}")

            if len(deduplicated) < len(middleware):
                removed = len(middleware) - len(deduplicated)
                logger.info(f"✓ Removed {removed} duplicate middleware instance(s)")

            logger.info(f"✓ Initialized {len(deduplicated)} total middleware")
            return deduplicated
        else:
            logger.debug("No middleware configured")
            return None

    @staticmethod
    async def _setup_model_hooks(
        model_hooks: List[Any],
        enable_default_hooks: bool,
        project_id: int,
        task_id: int
    ):
        """
        Setup model hooks for context injection and output validation (LEGACY).

        **DEPRECATED in v1.0:** Use _setup_middleware instead.
        This method is kept for backward compatibility.

        Args:
            model_hooks: List of hook instances or configurations
            enable_default_hooks: Whether to add default hooks
            project_id: Project ID for context
            task_id: Task ID for context

        Returns:
            HookManager instance or None
        """
        from core.models.hooks import (
            HookManager,
            ModelHook,
            get_default_hooks,
            create_hook_from_config
        )

        hooks = []

        # Add default hooks if enabled
        if enable_default_hooks:
            default_hooks = get_default_hooks()
            hooks.extend(default_hooks)
            logger.info(f"✓ Added {len(default_hooks)} default hooks")

        # Add custom hooks
        for hook in model_hooks:
            if isinstance(hook, ModelHook):
                # Already a hook instance
                hooks.append(hook)
            elif isinstance(hook, dict):
                # Configuration dict - create hook
                try:
                    hook_instance = create_hook_from_config(hook)
                    hooks.append(hook_instance)
                except Exception as e:
                    logger.error(f"Failed to create hook from config: {e}")
            else:
                logger.warning(f"Unknown hook type: {type(hook)}")

        if hooks:
            hook_manager = HookManager(hooks)
            logger.info(f"✓ Initialized HookManager with {len(hooks)} total hooks")
            return hook_manager
        else:
            logger.debug("No hooks configured")
            return None

    @staticmethod
    async def create_rlm_agent(
        model: str,
        repl_env,  # RLMREPLEnvironment
        query: str,
        depth: int = 0,
        **kwargs
    ) -> CompiledStateGraph:
        """
        Create agent with RLM (Recursive Language Model) capabilities.

        This creates an agent that can recursively analyze large contexts by:
        1. Using Python REPL to explore/partition context
        2. Making recursive LLM calls on specific segments
        3. Synthesizing results hierarchically

        Args:
            model: LLM model name (e.g., "gpt-4o-mini", "claude-haiku-4-5-20251015")
            repl_env: RLM REPL environment with context loaded
            query: User query to answer
            depth: Current recursion depth (0 = root)
            **kwargs: Additional agent config

        Returns:
            Configured LangGraph ReAct agent
        """
        from services.rlm_repl_environment import RLMREPLEnvironment

        logger.info(f"Creating RLM agent at depth {depth} with model {model}")

        # 1. Create LLM
        llm = await AgentFactory._create_llm(
            model_name=model,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
            config=kwargs
        )

        # 2. Create REPL execution tool
        async def execute_python_code(code: str) -> str:
            """Execute Python code in the RLM REPL environment."""
            result = await repl_env.execute_code(code)
            if result['success']:
                output = result.get('output', '')
                return str(output) if output else "Code executed successfully (no output)"
            else:
                return f"Error: {result.get('error', 'Unknown error')}"

        repl_tool = StructuredTool.from_function(
            func=execute_python_code,
            name="execute_python",
            description=(
                "Execute Python code in a secure sandbox to explore and analyze the context. "
                "Use this to filter, search, partition, or manipulate large context data. "
                f"Available modules: {', '.join(repl_env.allowed_modules)}. "
                "The 'context' variable contains the data to analyze. "
                "You can also use lm_query(sub_query, sub_context) for recursive analysis."
            ),
            coroutine=execute_python_code
        )

        # 3. Create tools list
        tools = [repl_tool]

        # 4. Create RLM-specific prompt
        rlm_prompt = f"""You are an RLM (Recursive Language Model) agent at depth {depth}/{repl_env.max_recursion_depth}.

Your goal: {query}

CONTEXT:
The 'context' variable in your Python REPL contains the data you need to analyze. It may be:
- A large string (document, code, log, etc.)
- A list of strings (chunks, files, sections)
- A dict with structured data

AVAILABLE TOOLS:
1. execute_python(code): Run Python code to explore/manipulate context
   - Search with regex: import re; matches = re.findall(r'pattern', context)
   - Filter lists: filtered = [x for x in context if condition]
   - Slice strings: segment = context[1000:2000]
   - Parse JSON: import json; data = json.loads(context)

2. lm_query(sub_query, sub_context): Recursively call an LLM to analyze a specific segment
   - Use when deeper analysis of a section is needed
   - Example: result = lm_query("Find all function definitions", file_content)
   - Available at depth < {repl_env.max_recursion_depth}

RECOMMENDED STRATEGY:
1. First, use execute_python to inspect context structure: type(context), len(context)
2. Use execute_python to search/filter for relevant segments
3. If needed, use lm_query() for deep analysis of specific segments
4. Synthesize findings into a comprehensive answer

IMPORTANT:
- Start by understanding the context structure
- Be systematic in your exploration
- Use recursion wisely (you have {repl_env.max_recursion_depth - depth} levels remaining)

Begin by using execute_python to inspect the context.
"""

        # 5. Create ReAct agent with RLM prompt (v1.0: no pre-binding)
        # v1.0: DO NOT pre-bind tools - pass them to create_agent instead
        agent = create_agent(
            model=llm,  # Pass unbound model
            tools=tools,
            system_prompt=rlm_prompt  # v1.0: use system_prompt, not state_modifier
        )

        logger.info(f"✓ RLM agent created at depth {depth} with {len(tools)} tools")

        return agent

    @staticmethod
    def _configure_callbacks(
        project_id, task_id, model_name, temperature, tools_count,
        memory_enabled, fallbacks, mcp_tool_names=None, agent_config=None
    ):
        """
        Helper to configure callbacks for agent execution.

        Configures TokenTrackingCallback for internal token usage tracking.
        NOTE: We use our custom TokenTrackingCallback system, not LangFuse.

        Returns:
            List of configured callback handlers
        """
        callbacks = []

        # Add token tracking callback (custom internal system)
        try:
            from core.utils.token_tracking import create_token_tracking_callback

            agent_id = agent_config.get("template_id", "unknown") if agent_config else "unknown"
            token_callback = create_token_tracking_callback(
                agent_id=agent_id,
                project_id=project_id,
                task_id=str(task_id),
                mcp_tools=mcp_tool_names or []
            )
            callbacks.append(token_callback)
            logger.info("✓ Token tracking callback configured")
        except Exception as e:
            logger.warning(f"Failed to initialize token tracking callback: {e}")

        # Support for additional custom callbacks from config
        custom_callbacks = agent_config.get("callbacks", []) if agent_config else []
        if custom_callbacks:
            callbacks.extend(custom_callbacks)
            logger.info(f"✓ Added {len(custom_callbacks)} custom callback(s) from config")

        return callbacks


# =============================================================================
# Convenience Functions (No changes needed, relies on the improved Factory)
# =============================================================================

async def create_agent_from_template(
    template_id: str,
    project_id: int,
    task_id: int,
    context: str,
    customizations: Optional[Dict[str, Any]] = None,
    mcp_manager = None,
    vector_store = None
):
    """
    Create an agent from an agent template by ID. (Convenience function)
    """
    # Implementation remains the same as provided in the prompt, assuming AgentTemplateRegistry works.
    from core.agents.templates import AgentTemplateRegistry

    template = AgentTemplateRegistry.get(template_id)
    if not template:
        raise ValueError(f"Agent template not found: {template_id}")

    agent_config = template.to_agent_config()

    if customizations:
        agent_config.update(customizations)

    return await AgentFactory.create_agent(
        agent_config=agent_config,
        project_id=project_id,
        task_id=task_id,
        context=context,
        mcp_manager=mcp_manager,
        vector_store=vector_store
    )
