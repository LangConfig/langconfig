# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Node generators for the Executable Workflow Exporter.

Generates workflow node implementations for different agent types.
"""

import logging
from textwrap import dedent
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class NodeGenerators:
    """Generators for workflow node functions."""

    @staticmethod
    def generate_agent_node(
        safe_id: str, label: str, model: str, system_prompt: str,
        native_tools: List[str], custom_tools: List[str]
    ) -> str:
        """Generate a standard agent node function."""
        tools_list = native_tools + custom_tools
        tools_str = str(tools_list)

        # Determine LLM class based on model name
        model_lower = model.lower()
        if "gpt" in model_lower or "openai" in model_lower:
            llm_class = "ChatOpenAI"
        elif "claude" in model_lower or "anthropic" in model_lower:
            llm_class = "ChatAnthropic"
        elif "gemini" in model_lower or "google" in model_lower:
            llm_class = "ChatGoogleGenerativeAI"
        else:
            # Default to ChatOpenAI for unknown models
            llm_class = "ChatOpenAI"

        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} agent node."""
                logger.info(f"[{label}] Starting execution...")

                try:
                    # Get tools for this node
                    tools = get_tools_for_node({tools_str})

                    # Create LLM instance
                    llm = {llm_class}(model="{model}")

                    # Build messages from state
                    messages = state.get("messages", [])
                    query = state.get("query", "")

                    if not messages and query:
                        messages = [HumanMessage(content=query)]

                    # System prompt for this agent
                    system_prompt = """{system_prompt}"""

                    # Create agent using LangChain v1.1 create_agent
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
        ''').strip()

    @staticmethod
    def generate_deepagent_node(
        safe_id: str, label: str, model: str, system_prompt: str,
        native_tools: List[str], custom_tools: List[str]
    ) -> str:
        """Generate a DeepAgent node function."""
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} DeepAgent node."""
                logger.info(f"[{label}] Starting DeepAgent execution...")

                try:
                    # Create DeepAgent using deepagents v2.x pattern
                    agent = create_deepagent(
                        model="{model}",
                        system_prompt="""{system_prompt}"""
                    )

                    # Build input from state
                    messages = state.get("messages", [])
                    query = state.get("query", "")

                    if not messages and query:
                        messages = [HumanMessage(content=query)]

                    # Execute DeepAgent
                    # DeepAgents has built-in: TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware
                    result = await agent.ainvoke({{"messages": messages}})

                    logger.info(f"[{label}] DeepAgent completed successfully")

                    return {{
                        "messages": result.get("messages", []),
                        "current_node": "{safe_id}",
                        "last_agent_type": "deepagent",
                        "step_history": [{{
                            "node": "{safe_id}",
                            "agent": "{label}",
                            "type": "deepagent",
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
        ''').strip()

    @staticmethod
    def generate_start_node(safe_id: str, label: str) -> str:
        """Generate a start node function."""
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - workflow entry point."""
                logger.info(f"[{label}] Workflow starting...")

                query = state.get("query", "")

                return {{
                    "messages": [HumanMessage(content=query)] if query else [],
                    "current_node": "{safe_id}",
                    "step_history": [{{
                        "node": "{safe_id}",
                        "type": "start",
                        "status": "completed"
                    }}]
                }}
        ''').strip()

    @staticmethod
    def generate_end_node(safe_id: str, label: str) -> str:
        """Generate an end node function."""
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - workflow exit point."""
                logger.info(f"[{label}] Workflow completed")

                messages = state.get("messages", [])
                final_content = messages[-1].content if messages else "No result"

                return {{
                    "current_node": "{safe_id}",
                    "result": {{"final_output": final_content}},
                    "step_history": [{{
                        "node": "{safe_id}",
                        "type": "end",
                        "status": "completed"
                    }}]
                }}
        ''').strip()

    @staticmethod
    def generate_conditional_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate a conditional node function."""
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - conditional routing."""
                logger.info(f"[{label}] Evaluating condition...")

                messages = state.get("messages", [])
                condition_config = {repr(config)}

                # Default routing logic - can be customized
                route = "default"

                if messages:
                    last_content = messages[-1].content.lower()
                    # Simple keyword-based routing
                    if "yes" in last_content or "approve" in last_content:
                        route = "true"
                    elif "no" in last_content or "reject" in last_content:
                        route = "false"

                logger.info(f"[{label}] Route selected: {{route}}")

                return {{
                    "conditional_route": route,
                    "current_node": "{safe_id}",
                    "step_history": [{{
                        "node": "{safe_id}",
                        "type": "conditional",
                        "route": route,
                        "status": "completed"
                    }}]
                }}
        ''').strip()

    @staticmethod
    def generate_loop_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate a loop node function."""
        max_iterations = config.get("max_iterations", 3)
        exit_condition = config.get("exit_condition", "")
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - loop iteration control."""
                logger.info(f"[{label}] Loop iteration check...")

                max_iterations = {max_iterations}
                exit_condition = "{exit_condition}"

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
                        "route": route,
                        "status": "completed"
                    }}]
                }}
        ''').strip()

    @staticmethod
    def generate_approval_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate an approval (HITL) node function."""
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - human approval required."""
                logger.info(f"[{label}] Requesting human approval...")

                print("\\n" + "=" * 50)
                print("HUMAN APPROVAL REQUIRED")
                print("=" * 50)
                print(f"Node: {label}")

                messages = state.get("messages", [])
                if messages:
                    print(f"\\nLast message: {{messages[-1].content[:500]}}...")

                approval = input("\\nApprove? (yes/no): ").strip().lower()

                if approval in ("yes", "y", "approve"):
                    status = "approved"
                    route = "continue"
                else:
                    status = "rejected"
                    route = "reject"

                logger.info(f"[{label}] Approval status: {{status}}")

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
        ''').strip()

    @staticmethod
    def generate_tool_node(safe_id: str, label: str, config: Dict) -> str:
        """Generate a direct tool execution node."""
        tool_name = config.get("tool_name", "")
        tool_params = config.get("tool_params", {})
        return dedent(f'''
            async def execute_{safe_id}(state: WorkflowState) -> Dict[str, Any]:
                """Execute {label} - direct tool invocation."""
                logger.info(f"[{label}] Executing tool...")

                tool_name = "{tool_name}"
                tool_params = {repr(tool_params)}

                try:
                    from tools import get_tool_by_name

                    tool = get_tool_by_name(tool_name)
                    if tool:
                        # Get input from state or params
                        messages = state.get("messages", [])
                        query = state.get("query", "")
                        input_val = messages[-1].content if messages else query

                        result = await tool.ainvoke(input_val)

                        return {{
                            "messages": [AIMessage(content=str(result))],
                            "current_node": "{safe_id}",
                            "step_history": [{{
                                "node": "{safe_id}",
                                "type": "tool",
                                "tool": tool_name,
                                "status": "completed"
                            }}]
                        }}
                    else:
                        raise ValueError(f"Tool '{{tool_name}}' not found")

                except Exception as e:
                    logger.error(f"[{label}] Tool execution failed: {{e}}")
                    return {{
                        "error_message": str(e),
                        "step_history": [{{
                            "node": "{safe_id}",
                            "type": "tool",
                            "status": "failed",
                            "error": str(e)
                        }}]
                    }}
        ''').strip()

    @staticmethod
    def generate_nodes_module(
        nodes: List[Dict[str, Any]],
        used_models: Set[str],
        sanitize_name_func
    ) -> str:
        """
        Generate workflow/nodes.py with node implementations.

        Args:
            nodes: List of node configurations
            used_models: Set of model names used in the workflow
            sanitize_name_func: Function to sanitize node names
        """
        node_functions = []

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})

            # Skip control nodes - they don't need execute functions
            agent_type_raw = node_data.get("agentType", "default")
            if agent_type_raw.upper() in ("START_NODE", "END_NODE"):
                continue

            # Config can be in multiple places
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})
            node_config = {**node_config_nested, **node_config_top}

            agent_type = agent_type_raw.lower()
            label = node_data.get("label") or node_data.get("name") or node_id
            safe_id = sanitize_name_func(node_id)

            # Get model from various locations
            model = (
                node_config_top.get("model") or
                node_data.get("model") or
                node_config_nested.get("model") or
                "gpt-4o"
            )

            # Get system prompt
            system_prompt = (
                node_config_top.get("system_prompt") or
                node_config_nested.get("system_prompt") or
                "You are a helpful assistant."
            )

            # Tools from merged config
            native_tools = node_config.get("native_tools", [])
            custom_tools = node_config.get("custom_tools", [])
            use_deepagents = node_config.get("use_deepagents", False)

            logger.info(f"Node {node_id}: model={model}, prompt_len={len(system_prompt)}, native_tools={native_tools}")

            # Escape system prompt for string literal
            system_prompt_escaped = system_prompt.replace('"""', '\\"\\"\\"').replace("\\", "\\\\")

            # Generate appropriate node function
            if agent_type in ("start", "start_node"):
                func = NodeGenerators.generate_start_node(safe_id, label)
            elif agent_type in ("end", "end_node"):
                func = NodeGenerators.generate_end_node(safe_id, label)
            elif agent_type in ("conditional", "conditional_node"):
                func = NodeGenerators.generate_conditional_node(safe_id, label, node_config)
            elif agent_type in ("loop", "loop_node"):
                func = NodeGenerators.generate_loop_node(safe_id, label, node_config)
            elif agent_type in ("approval", "hitl"):
                func = NodeGenerators.generate_approval_node(safe_id, label, node_config)
            elif agent_type in ("tool", "tool_node"):
                func = NodeGenerators.generate_tool_node(safe_id, label, node_config)
            elif use_deepagents or agent_type == "deepagent":
                func = NodeGenerators.generate_deepagent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )
            else:
                func = NodeGenerators.generate_agent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )

            node_functions.append(func)

        functions_str = "\n\n\n".join(node_functions) if node_functions else "pass"

        # Determine which LLM imports are needed
        llm_imports = set()
        for model in used_models:
            model_lower = model.lower()
            if "gpt" in model_lower or "openai" in model_lower:
                llm_imports.add("from langchain_openai import ChatOpenAI")
            elif "claude" in model_lower or "anthropic" in model_lower:
                llm_imports.add("from langchain_anthropic import ChatAnthropic")
            elif "gemini" in model_lower or "google" in model_lower:
                llm_imports.add("from langchain_google_genai import ChatGoogleGenerativeAI")

        if not llm_imports:
            llm_imports.add("from langchain_openai import ChatOpenAI")

        llm_imports_str = "\n".join(sorted(llm_imports))

        header = f'''"""Node implementations for the workflow."""

import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent

{llm_imports_str}

from .state import WorkflowState
from tools import get_tools_for_node

logger = logging.getLogger(__name__)


'''
        return header + functions_str
