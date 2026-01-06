# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Configurable node generators for the Executable Workflow Exporter.

Generates workflow node implementations that read configuration from
state.runtime_config, allowing runtime customization of:
- Model selection
- System prompts
- Tool availability
- Temperature and max tokens
- Control node settings (loops, HITL)
"""

import logging
from textwrap import dedent
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


# Available models for runtime selection
AVAILABLE_MODELS = {
    "claude-opus-4-5": {
        "provider": "anthropic",
        "class": "ChatAnthropic",
        "import": "from langchain_anthropic import ChatAnthropic",
        "api_key_env": "ANTHROPIC_API_KEY"
    },
    "claude-haiku-4-5": {
        "provider": "anthropic",
        "class": "ChatAnthropic",
        "import": "from langchain_anthropic import ChatAnthropic",
        "api_key_env": "ANTHROPIC_API_KEY"
    },
    "gpt-5.2": {
        "provider": "openai",
        "class": "ChatOpenAI",
        "import": "from langchain_openai import ChatOpenAI",
        "api_key_env": "OPENAI_API_KEY"
    },
    "gemini-3-pro-preview": {
        "provider": "google",
        "class": "ChatGoogleGenerativeAI",
        "import": "from langchain_google_genai import ChatGoogleGenerativeAI",
        "api_key_env": "GOOGLE_API_KEY"
    }
}


class ConfigurableNodeGenerators:
    """Generators for configurable workflow node functions."""

    @staticmethod
    def generate_agent_node(
        safe_id: str, label: str, default_model: str, default_prompt: str,
        native_tools: List[str], custom_tools: List[str]
    ) -> str:
        """Generate a configurable agent node function."""
        all_tools = native_tools + custom_tools
        tools_str = str(all_tools)

        return dedent(f'''\
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} agent node with runtime configuration."""
                logger.info(f"[{label}] Starting execution...")

                try:
                    # Get runtime configuration from state
                    runtime = state.get("runtime_config", {{}})

                    # Model configuration (with API key validation)
                    model_name = runtime.get("model", "{default_model}")
                    temperature = runtime.get("temperature", 0.7)
                    max_tokens = runtime.get("max_tokens", 4096)

                    # System prompt (editable at runtime)
                    system_prompt = runtime.get("system_prompt", """{default_prompt}""")

                    # Tool availability (filtered by enabled tools)
                    all_available_tools = {tools_str}
                    enabled_tools = runtime.get("enabled_tools", all_available_tools)
                    active_tools = [t for t in all_available_tools if t in enabled_tools]

                    # Get tools for this node
                    tools = get_tools_for_node(active_tools)

                    # Create LLM instance using init_chat_model for dynamic selection
                    llm = init_chat_model(
                        model_name,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                    # Build messages from state
                    messages = state.get("messages", [])
                    query = state.get("query", "")

                    if not messages and query:
                        messages = [HumanMessage(content=query)]

                    # Create agent using LangChain create_agent
                    agent = create_agent(
                        model=llm,
                        tools=tools if tools else [],
                        system_prompt=system_prompt
                    )

                    # Execute agent
                    result = await agent.ainvoke({{"messages": messages}})
                    response_messages = result.get("messages", [])

                    logger.info(f"[{label}] Completed successfully")

                    return {{
                        "messages": response_messages,
                        "current_node": "{safe_id}",
                        "last_agent_type": "agent",
                        "step_history": [{{
                            "node": "{safe_id}",
                            "agent": "{label}",
                            "model": model_name,
                            "status": "completed"
                        }}]
                    }}

                except Exception as e:
                    logger.error(f"[{label}] Failed: {{e}}")
                    import traceback
                    traceback.print_exc()
                    return {{
                        "error_message": str(e),
                        "step_history": [{{
                            "node": "{safe_id}",
                            "agent": "{label}",
                            "status": "failed",
                            "error": str(e)
                        }}]
                    }}
        ''')

    @staticmethod
    def generate_deepagent_node(
        safe_id: str, label: str, default_model: str, default_prompt: str,
        native_tools: List[str], custom_tools: List[str]
    ) -> str:
        """Generate a configurable DeepAgent node function."""
        # Build tools string for this node
        all_tools = native_tools + custom_tools
        tools_str = repr(all_tools)

        return dedent(f'''\
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} DeepAgent node with runtime configuration."""
                logger.info(f"[{label}] Starting DeepAgent execution...")

                try:
                    from deepagents import create_deep_agent

                    # Get runtime configuration
                    runtime = state.get("runtime_config", {{}})
                    model_name = runtime.get("model", "{default_model}")
                    system_prompt = runtime.get("system_prompt", """{default_prompt}""")
                    temperature = runtime.get("temperature", 0.7)
                    max_tokens = runtime.get("max_tokens", 4096)

                    # Get tools for this node
                    tools = get_tools_for_node({tools_str})

                    # Get API key from runtime config if available
                    api_key = runtime.get("api_key")

                    # Create model instance dynamically with API key if available
                    if api_key:
                        model_instance = init_chat_model(
                            model_name,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            api_key=api_key
                        )
                    else:
                        model_instance = init_chat_model(
                            model_name,
                            temperature=temperature,
                            max_tokens=max_tokens
                        )

                    # Create DeepAgent with tools
                    agent = create_deep_agent(
                        model=model_instance,
                        tools=tools if tools else [],
                        system_prompt=system_prompt
                    )

                    # Build input from state
                    messages = state.get("messages", [])
                    query = state.get("query", "")

                    if not messages and query:
                        messages = [HumanMessage(content=query)]

                    # Execute DeepAgent
                    result = await agent.ainvoke({{"messages": messages}})

                    logger.info(f"[{label}] DeepAgent completed successfully")

                    # Handle both dict and Overwrite object returns from deepagents
                    if isinstance(result, dict):
                        result_messages = result.get("messages", [])
                    else:
                        # deepagents may return Overwrite object - extract value
                        from langgraph.graph.state import Overwrite
                        if isinstance(result, Overwrite):
                            result_messages = result.value if hasattr(result, 'value') else []
                        else:
                            result_messages = getattr(result, 'messages', [])

                    return {{
                        "messages": result_messages,
                        "current_node": "{safe_id}",
                        "last_agent_type": "deepagent",
                        "step_history": [{{
                            "node": "{safe_id}",
                            "agent": "{label}",
                            "type": "deepagent",
                            "model": model_name,
                            "status": "completed"
                        }}]
                    }}

                except Exception as e:
                    logger.error(f"[{label}] DeepAgent failed: {{e}}")
                    return {{
                        "error_message": str(e),
                        "step_history": [{{
                            "node": "{safe_id}",
                            "agent": "{label}",
                            "status": "failed",
                            "error": str(e)
                        }}]
                    }}
        ''')

    @staticmethod
    def generate_loop_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate a configurable loop node function."""
        default_max = config.get("max_iterations", 3)
        default_exit = config.get("exit_condition", "")

        return dedent(f'''\
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - configurable loop control."""
                logger.info(f"[{label}] Loop iteration check...")

                # Get runtime configuration for control nodes
                runtime = state.get("runtime_config", {{}})
                control_config = runtime.get("control_nodes", {{}}).get("{safe_id}", {{}})

                max_iterations = control_config.get("max_iterations", {default_max})
                exit_condition = control_config.get("exit_condition", "{default_exit}")

                # Track iterations
                loop_iterations = state.get("loop_iterations", {{}})
                current_iteration = loop_iterations.get("{safe_id}", 0) + 1
                loop_iterations["{safe_id}"] = current_iteration

                # Check exit conditions
                should_exit = False
                exit_reason = None

                if current_iteration >= max_iterations:
                    should_exit = True
                    exit_reason = f"Max iterations ({{max_iterations}}) reached"

                # Check custom exit condition
                if exit_condition and not should_exit:
                    messages = state.get("messages", [])
                    if messages and exit_condition.lower() in messages[-1].content.lower():
                        should_exit = True
                        exit_reason = "Exit condition met"

                route = "exit" if should_exit else "continue"
                logger.info(f"[{label}] Iteration {{current_iteration}}, route: {{route}}")

                return {{
                    "loop_iterations": loop_iterations,
                    "loop_route": route,
                    "current_node": "{safe_id}",
                    "step_history": [{{
                        "node": "{safe_id}",
                        "type": "loop",
                        "iteration": current_iteration,
                        "max_iterations": max_iterations,
                        "route": route,
                        "status": "completed"
                    }}]
                }}
        ''')

    @staticmethod
    def generate_approval_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate a configurable HITL approval node."""
        return dedent(f'''\
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - configurable human approval."""
                logger.info(f"[{label}] Requesting approval...")

                # Get runtime configuration for HITL
                runtime = state.get("runtime_config", {{}})
                control_config = runtime.get("control_nodes", {{}}).get("{safe_id}", {{}})

                auto_approve = control_config.get("auto_approve", False)
                timeout_seconds = control_config.get("timeout_seconds", 300)

                messages = state.get("messages", [])

                if auto_approve:
                    # Auto-approve mode for testing
                    status = "approved"
                    route = "continue"
                    logger.info(f"[{label}] Auto-approved")
                else:
                    # Interactive approval via Streamlit
                    # This is handled by the UI - set pending state
                    return {{
                        "pending_approval": {{
                            "node_id": "{safe_id}",
                            "label": "{label}",
                            "message_preview": messages[-1].content[:500] if messages else "",
                            "timeout_seconds": timeout_seconds
                        }},
                        "current_node": "{safe_id}",
                        "step_history": [{{
                            "node": "{safe_id}",
                            "type": "approval",
                            "status": "pending"
                        }}]
                    }}

                return {{
                    "approval_status": status,
                    "approval_route": route,
                    "current_node": "{safe_id}",
                    "step_history": [{{
                        "node": "{safe_id}",
                        "type": "approval",
                        "status": status
                    }}]
                }}
        ''')

    @staticmethod
    def generate_nodes_module(
        nodes: List[Dict[str, Any]],
        used_models: Set[str],
        sanitize_name_func
    ) -> str:
        """
        Generate configurable workflow/nodes.py.

        Args:
            nodes: List of node configurations
            used_models: Set of model names used in the workflow
            sanitize_name_func: Function to sanitize node names
        """
        node_functions = []
        has_deepagent_nodes = False

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})

            # Skip control nodes
            agent_type_raw = node_data.get("agentType", "default")
            if agent_type_raw.upper() in ("START_NODE", "END_NODE"):
                continue

            # Get config
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})
            node_config = {**node_config_nested, **node_config_top}

            agent_type = agent_type_raw.lower()
            label = node_data.get("label") or node_data.get("name") or node_id
            safe_id = sanitize_name_func(node_id)

            # Get defaults
            model = (
                node_config_top.get("model") or
                node_data.get("model") or
                node_config_nested.get("model") or
                "gpt-5.2"
            )

            system_prompt = (
                node_config_top.get("system_prompt") or
                node_config_nested.get("system_prompt") or
                "You are a helpful assistant."
            )

            native_tools = node_config.get("native_tools", [])
            custom_tools = node_config.get("custom_tools", [])
            use_deepagents = node_config.get("use_deepagents", False)

            # Escape prompt
            system_prompt_escaped = system_prompt.replace('"""', '\\"\\"\\"').replace("\\", "\\\\")

            # Generate appropriate node
            if agent_type in ("loop", "loop_node"):
                func = ConfigurableNodeGenerators.generate_loop_node(safe_id, label, node_config)
            elif agent_type in ("approval", "hitl"):
                func = ConfigurableNodeGenerators.generate_approval_node(safe_id, label, node_config)
            elif use_deepagents or agent_type == "deepagent":
                has_deepagent_nodes = True
                func = ConfigurableNodeGenerators.generate_deepagent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )
            else:
                func = ConfigurableNodeGenerators.generate_agent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )

            node_functions.append(func)

        functions_str = "\n\n".join(node_functions) if node_functions else "pass"

        # Build imports - always include all possible LLM imports for dynamic selection
        header = '''"""Configurable node implementations for the workflow.

Nodes read from state.runtime_config for dynamic configuration of:
- Model selection
- System prompts
- Tool availability
- Temperature / max tokens
"""

import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, AIMessage
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

from .state import WorkflowState
from tools import get_tools_for_node

logger = logging.getLogger(__name__)


# Available models for runtime selection
AVAILABLE_MODELS = {
    "claude-opus-4-5": {"provider": "anthropic", "api_key_env": "ANTHROPIC_API_KEY"},
    "gpt-5.2": {"provider": "openai", "api_key_env": "OPENAI_API_KEY"},
    "gemini-3-pro-preview": {"provider": "google", "api_key_env": "GOOGLE_API_KEY"},
}


'''
        return header + functions_str
