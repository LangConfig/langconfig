# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Executable Workflow Exporter for LangConfig.

Exports user-created workflows as fully executable, standalone Python packages
that can be dropped into any repository and run immediately.

Uses LangChain v1.1 / LangGraph v1.x / DeepAgents v2.x APIs.
"""

import io
import json
import logging
import zipfile
from datetime import datetime
from textwrap import dedent, indent
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ExecutableWorkflowExporter:
    """
    Exports workflows as executable Python packages.

    Generated package structure:
    workflow_{name}_{id}/
    ├── README.md
    ├── requirements.txt
    ├── .env.example
    ├── main.py
    ├── streamlit_app.py        # Optional Streamlit UI
    ├── workflow/
    │   ├── __init__.py
    │   ├── graph.py
    │   ├── state.py
    │   ├── nodes.py
    │   └── routing.py
    ├── agents/
    │   ├── __init__.py
    │   └── factory.py
    ├── tools/
    │   ├── __init__.py
    │   ├── native.py
    │   └── custom.py
    └── config/
        └── settings.py
    """

    def __init__(self, workflow: Dict[str, Any], project_id: int, include_ui: bool = True):
        """
        Initialize the exporter.

        Args:
            workflow: Workflow data including configuration, blueprint, nodes, edges
            project_id: Project ID for fetching custom tools
            include_ui: Whether to include Streamlit UI (default: True)
        """
        self.workflow = workflow
        self.project_id = project_id
        self.include_ui = include_ui
        self.workflow_id = workflow.get("id", 0)
        self.workflow_name = workflow.get("name", "Exported Workflow")

        # Extract nodes and edges from configuration or blueprint
        config = workflow.get("configuration", {})
        blueprint = workflow.get("blueprint", {})

        self.nodes = config.get("nodes", []) or blueprint.get("nodes", [])
        self.edges = config.get("edges", []) or blueprint.get("edges", [])

        # Track what features are used for requirements
        self._used_models: Set[str] = set()
        self._used_native_tools: Set[str] = set()
        self._used_custom_tools: Set[str] = set()
        self._has_deepagents = False

        # Analyze workflow to detect features
        self._analyze_workflow()

    def _analyze_workflow(self) -> None:
        """Analyze workflow to detect used features."""
        for node in self.nodes:
            node_data = node.get("data", {})
            # Config can be in multiple places
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})
            node_config = {**node_config_nested, **node_config_top}

            # Detect model usage - check ALL locations
            model = (
                node_config_top.get("model") or
                node_data.get("model") or
                node_config_nested.get("model") or
                ""
            )
            if model:
                self._used_models.add(model)
                logger.info(f"Detected model: {model}")

            # Detect native tools
            native_tools = node_config.get("native_tools", [])
            self._used_native_tools.update(native_tools)

            # Detect custom tools
            custom_tools = node_config.get("custom_tools", [])
            self._used_custom_tools.update(custom_tools)

            # Detect DeepAgents
            if node_config.get("use_deepagents") or node_data.get("subagents"):
                self._has_deepagents = True

        logger.info(f"Workflow analysis: models={self._used_models}, native_tools={self._used_native_tools}")

    async def export_to_zip(self) -> bytes:
        """
        Export workflow as a ZIP file containing all necessary files.

        Returns:
            ZIP file as bytes
        """
        logger.info(f"Exporting workflow {self.workflow_id}: {self.workflow_name}")
        logger.info(f"Workflow has {len(self.nodes)} nodes, {len(self.edges)} edges")

        # Debug: Log raw node structure to understand data format
        # This matches how executor.py reads the data (see _build_graph_from_workflow)
        for i, node in enumerate(self.nodes[:3]):  # First 3 nodes
            logger.info(f"[EXPORT DEBUG] Node {i}: {node.get('id')}")
            logger.info(f"[EXPORT DEBUG]   Top-level keys: {list(node.keys())}")
            # Database stores config at TOP LEVEL: node["config"] (not node["data"]["config"])
            top_config = node.get("config", {})
            logger.info(f"[EXPORT DEBUG]   node.config: {top_config}")
            logger.info(f"[EXPORT DEBUG]   node.config.model: {top_config.get('model')}")
            logger.info(f"[EXPORT DEBUG]   node.config.system_prompt: {top_config.get('system_prompt', '')[:50]}...")
            # Also check data structure
            node_data = node.get("data", {})
            logger.info(f"[EXPORT DEBUG]   node.data keys: {list(node_data.keys())}")
            if "config" in node_data:
                logger.info(f"[EXPORT DEBUG]   node.data.config: {node_data.get('config', {})}")

        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Sanitize workflow name for folder
            safe_name = self._sanitize_name(self.workflow_name)
            base_path = f"workflow_{safe_name}_{self.workflow_id}"

            # Generate and add all files
            files = {
                "README.md": self._generate_readme(),
                "requirements.txt": self._generate_requirements(),
                ".env.example": self._generate_env_example(),
                "main.py": self._generate_main(),
                "workflow/__init__.py": self._generate_workflow_init(),
                "workflow/graph.py": self._generate_graph_module(),
                "workflow/state.py": self._generate_state_module(),
                "workflow/nodes.py": self._generate_nodes_module(),
                "workflow/routing.py": self._generate_routing_module(),
                "agents/__init__.py": self._generate_agents_init(),
                "agents/factory.py": self._generate_agents_module(),
                "tools/__init__.py": self._generate_tools_init(),
                "tools/native.py": self._generate_native_tools_module(),
                "tools/custom.py": await self._generate_custom_tools_module(),
                "config/__init__.py": "",
                "config/settings.py": self._generate_settings_module(),
            }

            # Add Streamlit UI if enabled
            if self.include_ui:
                files["streamlit_app.py"] = self._generate_streamlit_app()

            for filepath, content in files.items():
                zf.writestr(f"{base_path}/{filepath}", content)

        logger.info(f"Export complete: {len(files)} files generated")
        return zip_buffer.getvalue()

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for filesystem and Python identifiers."""
        sanitized = name.lower().replace(" ", "_").replace("-", "_")
        sanitized = "".join(c if c.isalnum() or c == "_" else "" for c in sanitized)
        return sanitized or "workflow"

    def _generate_readme(self) -> str:
        """Generate README.md with setup instructions."""
        ui_section = ""
        if self.include_ui:
            ui_section = """
            ## Run with Streamlit UI

            For a visual interface with live streaming output:
            ```bash
            streamlit run streamlit_app.py
            ```

            This opens a browser with:
            - **API Key Configuration** - Enter your keys directly in the sidebar
            - Query input field
            - Real-time execution status
            - Streaming agent responses
            - Tool call visualization
            - Final result display

            The Streamlit UI will show which API keys are required based on the models
            used in your workflow, and you can enter them directly without editing files.
            """

        return dedent(f'''
            # {self.workflow_name}

            Exported from LangConfig on {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC.

            ## Setup

            1. Create a virtual environment:
               ```bash
               python -m venv venv
               source venv/bin/activate  # On Windows: venv\\Scripts\\activate
               ```

            2. Install dependencies:
               ```bash
               pip install -r requirements.txt
               ```

            3. Configure API keys:
               ```bash
               cp .env.example .env
               # Edit .env and add your API keys
               ```

            4. Run the workflow:
               ```bash
               python main.py
               ```
            {ui_section}
            ## Workflow Details

            - **Name**: {self.workflow_name}
            - **Nodes**: {len(self.nodes)}
            - **Edges**: {len(self.edges)}

            ## Requirements

            - Python 3.10+
            - API keys for your chosen model provider(s)

            ## Generated with LangConfig

            This workflow was exported using LangConfig's executable export feature.
            Learn more at: https://github.com/your-repo/langconfig
        ''').strip()

    def _generate_requirements(self) -> str:
        """Generate requirements.txt based on workflow features."""
        requirements = [
            "# Core dependencies",
            "langgraph>=1.0.4",
            "langchain>=1.1.2",
            "langchain-core>=1.1.1",
            "python-dotenv>=1.0.0",
            "pydantic>=2.0.0",
            "",
        ]

        # Streamlit UI
        if self.include_ui:
            requirements.extend([
                "# Streamlit UI",
                "streamlit>=1.28.0",
                "",
            ])

        # Model-specific dependencies
        model_deps = []
        for model in self._used_models:
            model_lower = model.lower()
            if "gpt" in model_lower or "openai" in model_lower:
                model_deps.append("langchain-openai>=1.1.0")
            elif "claude" in model_lower or "anthropic" in model_lower:
                model_deps.append("langchain-anthropic>=1.2.0")
            elif "gemini" in model_lower or "google" in model_lower:
                model_deps.append("langchain-google-genai>=3.2.0")

        if model_deps:
            requirements.append("# Model providers")
            requirements.extend(sorted(set(model_deps)))
            requirements.append("")

        # DeepAgents
        if self._has_deepagents:
            requirements.append("# DeepAgents")
            requirements.append("deepagents")
            requirements.append("")

        # Tool-specific dependencies
        tool_deps = []
        if self._used_native_tools & {"web_search", "web_fetch"}:
            tool_deps.append("httpx")
        if "browser" in self._used_native_tools:
            tool_deps.append("playwright")
            tool_deps.append("langchain-community")

        if tool_deps:
            requirements.append("# Tool dependencies")
            requirements.extend(sorted(set(tool_deps)))
            requirements.append("")

        return "\n".join(requirements)

    def _generate_env_example(self) -> str:
        """Generate .env.example with API key placeholders."""
        env_vars = [
            "# API Keys - Add your keys here",
            "",
        ]

        # Detect which API keys are needed based on models
        for model in self._used_models:
            model_lower = model.lower()
            if "gpt" in model_lower or "openai" in model_lower:
                env_vars.append("OPENAI_API_KEY=sk-your-openai-key-here")
            elif "claude" in model_lower or "anthropic" in model_lower:
                env_vars.append("ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here")
            elif "gemini" in model_lower or "google" in model_lower:
                env_vars.append("GOOGLE_API_KEY=your-google-api-key-here")

        # Detect custom tool requirements
        # This requires fetching tool configs - we'll add common ones if custom tools are used
        if self._used_custom_tools:
            env_vars.append("")
            env_vars.append("# Custom Tool API Keys (add as needed)")
            env_vars.append("GEMINI_API_KEY=your-gemini-api-key-here  # For image generation")
            env_vars.append("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
            env_vars.append("SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...")

        # Remove duplicates while preserving order
        seen = set()
        unique_vars = []
        for var in env_vars:
            if var not in seen:
                seen.add(var)
                unique_vars.append(var)

        return "\n".join(unique_vars)

    def _generate_main(self) -> str:
        """Generate main.py CLI entrypoint."""
        return dedent('''
            #!/usr/bin/env python3
            """
            Main entrypoint for the exported workflow.

            Usage:
                python main.py
            """

            import asyncio
            import logging
            from dotenv import load_dotenv

            from workflow.graph import create_workflow

            # Load environment variables
            load_dotenv()

            # Configure logging
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            logger = logging.getLogger(__name__)


            async def run_workflow(query: str) -> dict:
                """Run the workflow with a query."""
                logger.info(f"Starting workflow with query: {query[:100]}...")

                # Create the workflow graph
                graph = create_workflow()

                # Create initial state
                initial_state = {
                    "messages": [],
                    "query": query,
                }

                try:
                    # Execute workflow with streaming
                    final_state = None
                    async for state in graph.astream(initial_state):
                        final_state = state
                        node_name = list(state.keys())[0] if state else "unknown"
                        logger.info(f"Completed node: {node_name}")

                    logger.info("Workflow completed successfully")
                    return final_state

                except Exception as e:
                    logger.error(f"Workflow failed: {e}")
                    raise


            async def main():
                """Main entry point."""
                print("=" * 60)
                print("Workflow Runner")
                print("=" * 60)

                query = input("\\nEnter your query: ").strip()
                if not query:
                    print("No query provided. Exiting.")
                    return

                result = await run_workflow(query)

                print("\\n" + "=" * 60)
                print("RESULT")
                print("=" * 60)

                if result:
                    # Try to extract the last message
                    for node_result in result.values():
                        if isinstance(node_result, dict) and "messages" in node_result:
                            messages = node_result["messages"]
                            if messages:
                                last_msg = messages[-1]
                                content = getattr(last_msg, "content", str(last_msg))
                                print(f"\\nFinal Response:\\n{content}")
                                break


            if __name__ == "__main__":
                asyncio.run(main())
        ''').strip()

    def _generate_workflow_init(self) -> str:
        """Generate workflow/__init__.py."""
        return dedent('''
            """Workflow package - contains graph definition and node implementations."""
            from .graph import create_workflow
            from .state import WorkflowState

            __all__ = ["create_workflow", "WorkflowState"]
        ''').strip()

    def _generate_state_module(self) -> str:
        """Generate workflow/state.py with WorkflowState TypedDict."""
        return dedent('''
            """Workflow state definition."""

            import operator
            from typing import Annotated, Any, Dict, List, Optional
            from datetime import datetime

            from langchain_core.messages import BaseMessage
            from langgraph.graph import MessagesState


            class WorkflowState(MessagesState):
                """
                State for the exported workflow.

                Extends MessagesState which provides:
                - messages: Annotated[List[BaseMessage], add_messages]
                """

                # User query
                query: str

                # Current node tracking
                current_node: Optional[str] = None
                last_agent_type: Optional[str] = None

                # Execution history
                step_history: Annotated[List[Dict[str, Any]], operator.add] = []

                # Results
                result: Optional[Dict[str, Any]] = None
                error_message: Optional[str] = None

                # Control flow
                conditional_route: Optional[str] = None
                loop_route: Optional[str] = None
                loop_iterations: Dict[str, int] = {}

                # HITL
                approval_status: Optional[str] = None
                approval_route: Optional[str] = None
        ''').strip()

    def _generate_graph_module(self) -> str:
        """Generate workflow/graph.py with StateGraph definition.

        Handles workflows with or without explicit START_NODE/END_NODE:
        - If no START_NODE: automatically detects entry point (node with no incoming edges)
        - If no END_NODE: automatically detects terminal nodes (nodes with no outgoing edges)
        """
        # Filter out START_NODE and END_NODE - they're control nodes, not executable
        executable_nodes = []
        start_node_ids = set()
        end_node_ids = set()

        for node in self.nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            agent_type = node_data.get("agentType", "").upper()

            if agent_type == "START_NODE":
                start_node_ids.add(node_id)
                logger.info(f"[GRAPH] Found START_NODE: {node_id}")
            elif agent_type == "END_NODE":
                end_node_ids.add(node_id)
                logger.info(f"[GRAPH] Found END_NODE: {node_id}")
            else:
                executable_nodes.append(node)
                logger.info(f"[GRAPH] Found executable node: {node_id} (type={agent_type})")

        # Log if no START/END nodes - we'll handle this automatically
        if not start_node_ids:
            logger.info("[GRAPH] No START_NODE found - will auto-detect entry point")
        if not end_node_ids:
            logger.info("[GRAPH] No END_NODE found - will auto-detect terminal nodes")

        # Build node additions
        node_additions = []
        for node in executable_nodes:
            node_id = node.get("id", "unknown")
            safe_id = self._sanitize_name(node_id)
            node_additions.append(f'graph.add_node("{node_id}", execute_{safe_id})')

        # Build edge additions and track connections
        edge_additions = []
        nodes_with_outgoing_to_nodes = set()  # Nodes that have edges to OTHER nodes
        nodes_with_incoming = set()
        nodes_connecting_to_end = set()  # Nodes that connect to END_NODE

        logger.info(f"[GRAPH] Processing {len(self.edges)} edges...")
        # Log raw edge structure for debugging
        if self.edges:
            logger.info(f"[GRAPH] Sample edge structure: {self.edges[0]}")

        for edge in self.edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            logger.info(f"[GRAPH] Edge: {source} -> {target}")

            if not source or not target:
                logger.info(f"[GRAPH]   SKIPPED: empty source or target")
                continue

            # Skip edges FROM START_NODE - we handle entry point separately
            if source in start_node_ids:
                logger.info(f"[GRAPH]   START edge: {target} is entry point")
                nodes_with_incoming.add(target)
                continue

            # Edge TO END_NODE - mark source as connecting to END
            if target in end_node_ids:
                logger.info(f"[GRAPH]   END edge: {source} connects to END")
                nodes_connecting_to_end.add(source)
                continue

            # Normal edge between executable nodes
            logger.info(f"[GRAPH]   ADDED: {source} -> {target}")
            edge_additions.append(f'graph.add_edge("{source}", "{target}")')
            nodes_with_outgoing_to_nodes.add(source)
            nodes_with_incoming.add(target)

        # Determine entry point:
        # 1. If START_NODE exists, use what it connects to
        # 2. Otherwise, find node with no incoming edges from other executable nodes
        # 3. Fallback to first executable node
        entry_node = None

        # First, check if START_NODE connects to something
        if start_node_ids:
            for edge in self.edges:
                if edge.get("source") in start_node_ids:
                    target = edge.get("target")
                    if target and target not in end_node_ids:
                        entry_node = target
                        logger.info(f"[GRAPH] Entry node (from START_NODE): {entry_node}")
                        break

        # If no START_NODE or it doesn't connect to anything, find node with no incoming
        if not entry_node:
            executable_node_ids = {n.get("id") for n in executable_nodes}
            for node in executable_nodes:
                nid = node.get("id")
                # Check if this node has any incoming edges from other executable nodes
                has_incoming_from_executable = any(
                    e.get("target") == nid and e.get("source") in executable_node_ids
                    for e in self.edges
                )
                if not has_incoming_from_executable:
                    entry_node = nid
                    logger.info(f"[GRAPH] Entry node (auto-detected, no incoming): {entry_node}")
                    break

        # Fallback to first executable node
        if not entry_node and executable_nodes:
            entry_node = executable_nodes[0].get("id")
            logger.info(f"[GRAPH] Entry node (fallback to first): {entry_node}")

        # Determine terminal nodes:
        # 1. Nodes explicitly connecting to END_NODE
        # 2. Nodes with no outgoing edges to other executable nodes
        terminal_nodes = set(nodes_connecting_to_end)

        # Also check for nodes with no outgoing edges to other executable nodes
        executable_node_ids = {n.get("id") for n in executable_nodes}
        for node in executable_nodes:
            nid = node.get("id")
            # Check if this node has any outgoing edges to other executable nodes
            has_outgoing_to_executable = any(
                e.get("source") == nid and e.get("target") in executable_node_ids
                for e in self.edges
            )
            if not has_outgoing_to_executable and nid not in nodes_connecting_to_end:
                terminal_nodes.add(nid)
                logger.info(f"[GRAPH] Terminal node (auto-detected, no outgoing): {nid}")

        # If no terminal nodes found, use last node
        if not terminal_nodes and executable_nodes:
            terminal_nodes = {executable_nodes[-1].get("id")}
            logger.info(f"[GRAPH] Terminal node (fallback to last): {executable_nodes[-1].get('id')}")

        logger.info(f"[GRAPH] All terminal nodes: {terminal_nodes}")

        # Add END edges for terminal nodes
        for terminal_node in terminal_nodes:
            edge_additions.append(f'graph.add_edge("{terminal_node}", END)')
            logger.info(f"[GRAPH] Adding END edge: {terminal_node} -> END")

        # Import node functions
        node_imports = []
        for node in executable_nodes:
            node_id = node.get("id", "unknown")
            safe_id = self._sanitize_name(node_id)
            node_imports.append(f"execute_{safe_id}")

        imports_str = ", ".join(node_imports) if node_imports else "pass"

        # Join with proper indentation (4 spaces for inside function)
        nodes_str = "\n    ".join(node_additions) if node_additions else "# No nodes"
        edges_str = "\n    ".join(edge_additions) if edge_additions else "# No edges"

        # Determine START edge
        start_edge = f'graph.add_edge(START, "{entry_node}")' if entry_node else "# No entry node found"

        # Build the module without dedent to avoid indentation issues
        lines = [
            '"""Workflow graph definition using LangGraph v1.x."""',
            '',
            'from langgraph.graph import StateGraph, START, END',
            '',
            'from .state import WorkflowState',
            f'from .nodes import {imports_str}',
            '',
            '',
            'def create_workflow():',
            '    """Create and compile the workflow graph."""',
            '',
            '    # Create state graph',
            '    graph = StateGraph(WorkflowState)',
            '',
            '    # Add nodes',
            f'    {nodes_str}',
            '',
            '    # Add edges (START -> nodes -> END)',
            f'    {start_edge}',
            f'    {edges_str}',
            '',
            '    # Compile graph',
            '    return graph.compile()',
        ]

        return '\n'.join(lines)

    def _generate_nodes_module(self) -> str:
        """Generate workflow/nodes.py with node implementations."""
        node_functions = []

        for node in self.nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})

            # Skip control nodes - they don't need execute functions
            agent_type_raw = node_data.get("agentType", "default")
            if agent_type_raw.upper() in ("START_NODE", "END_NODE"):
                continue

            # Config can be in multiple places:
            # 1. node.config (top-level, extracted by frontend on save)
            # 2. node.data.config (nested in React Flow data)
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})

            # Merge configs, preferring top-level config
            node_config = {**node_config_nested, **node_config_top}

            agent_type = agent_type_raw.lower()
            label = node_data.get("label") or node_data.get("name") or node_id

            safe_id = self._sanitize_name(node_id)

            # Check ALL possible locations for model:
            # 1. node.config.model (top-level config)
            # 2. node.data.model (React Flow data)
            # 3. node.data.config.model (nested config)
            model = (
                node_config_top.get("model") or
                node_data.get("model") or
                node_config_nested.get("model") or
                "gpt-4o"
            )

            # Check ALL possible locations for system_prompt:
            system_prompt = (
                node_config_top.get("system_prompt") or
                node_config_nested.get("system_prompt") or
                "You are a helpful assistant."
            )

            # Tools from merged config
            native_tools = node_config.get("native_tools", [])
            custom_tools = node_config.get("custom_tools", [])
            use_deepagents = node_config.get("use_deepagents", False)

            # Debug logging
            logger.info(f"Node {node_id}: model={model}, prompt_len={len(system_prompt)}, native_tools={native_tools}")

            # Escape system prompt for string literal
            system_prompt_escaped = system_prompt.replace('"""', '\\"\\"\\"').replace("\\", "\\\\")

            if agent_type in ("start", "start_node"):
                # Start node - just passes through
                func = self._generate_start_node(safe_id, label)
            elif agent_type in ("end", "end_node"):
                # End node - finalizes result
                func = self._generate_end_node(safe_id, label)
            elif agent_type in ("conditional", "conditional_node"):
                # Conditional node - evaluates condition
                func = self._generate_conditional_node(safe_id, label, node_config)
            elif agent_type in ("loop", "loop_node"):
                # Loop node - handles iteration
                func = self._generate_loop_node(safe_id, label, node_config)
            elif agent_type in ("approval", "hitl"):
                # HITL approval node
                func = self._generate_approval_node(safe_id, label, node_config)
            elif agent_type in ("tool", "tool_node"):
                # Direct tool execution
                func = self._generate_tool_node(safe_id, label, node_config)
            elif use_deepagents or agent_type == "deepagent":
                # DeepAgent node
                func = self._generate_deepagent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )
            else:
                # Standard agent node
                func = self._generate_agent_node(
                    safe_id, label, model, system_prompt_escaped, native_tools, custom_tools
                )

            node_functions.append(func)

        functions_str = "\n\n\n".join(node_functions) if node_functions else "pass"

        # Determine which LLM imports are needed based on models used
        llm_imports = set()
        for model in self._used_models:
            model_lower = model.lower()
            if "gpt" in model_lower or "openai" in model_lower:
                llm_imports.add("from langchain_openai import ChatOpenAI")
            elif "claude" in model_lower or "anthropic" in model_lower:
                llm_imports.add("from langchain_anthropic import ChatAnthropic")
            elif "gemini" in model_lower or "google" in model_lower:
                llm_imports.add("from langchain_google_genai import ChatGoogleGenerativeAI")

        # Default to at least one import if none detected
        if not llm_imports:
            llm_imports.add("from langchain_openai import ChatOpenAI")

        llm_imports_str = "\n".join(sorted(llm_imports))

        # Build without dedent to avoid indentation issues with interpolated functions
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

    def _generate_agent_node(
        self, safe_id: str, label: str, model: str, system_prompt: str,
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

    def _generate_deepagent_node(
        self, safe_id: str, label: str, model: str, system_prompt: str,
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

    def _generate_start_node(self, safe_id: str, label: str) -> str:
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

    def _generate_end_node(self, safe_id: str, label: str) -> str:
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

    def _generate_conditional_node(self, safe_id: str, label: str, config: Dict) -> str:
        """Generate a conditional node function."""
        condition = config.get("condition", "")
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

    def _generate_loop_node(self, safe_id: str, label: str, config: Dict) -> str:
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

    def _generate_approval_node(self, safe_id: str, label: str, config: Dict) -> str:
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

    def _generate_tool_node(self, safe_id: str, label: str, config: Dict) -> str:
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

    def _generate_routing_module(self) -> str:
        """Generate workflow/routing.py with conditional edge functions."""
        routing_functions = []

        for node in self.nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            agent_type = node_data.get("agentType", "").lower()
            safe_id = self._sanitize_name(node_id)

            if agent_type in ("conditional", "conditional_node"):
                routing_functions.append(self._generate_conditional_router(safe_id, node_id))
            elif agent_type in ("loop", "loop_node"):
                routing_functions.append(self._generate_loop_router(safe_id, node_id))
            elif agent_type in ("approval", "hitl"):
                routing_functions.append(self._generate_approval_router(safe_id, node_id))

        functions_str = "\n\n\n".join(routing_functions) if routing_functions else "# No routing functions needed"

        # Build without dedent to avoid indentation issues
        header = '''"""Routing functions for conditional edges."""

from langgraph.graph import END

from .state import WorkflowState


'''
        return header + functions_str

    def _generate_conditional_router(self, safe_id: str, node_id: str) -> str:
        """Generate a conditional routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on conditional node evaluation."""
                route = state.get("conditional_route", "default")
                # Map routes to next nodes - customize as needed
                route_map = {{
                    "true": "next_node_true",
                    "false": "next_node_false",
                    "default": END
                }}
                return route_map.get(route, END)
        ''').strip()

    def _generate_loop_router(self, safe_id: str, node_id: str) -> str:
        """Generate a loop routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on loop state."""
                route = state.get("loop_route", "continue")
                route_map = {{
                    "continue": "loop_body_node",
                    "exit": "next_after_loop"
                }}
                return route_map.get(route, END)
        ''').strip()

    def _generate_approval_router(self, safe_id: str, node_id: str) -> str:
        """Generate an approval routing function."""
        return dedent(f'''
            def route_{safe_id}(state: WorkflowState) -> str:
                """Route based on approval status."""
                route = state.get("approval_route", "reject")
                route_map = {{
                    "continue": "next_node_approved",
                    "reject": END
                }}
                return route_map.get(route, END)
        ''').strip()

    def _generate_agents_init(self) -> str:
        """Generate agents/__init__.py."""
        return dedent('''
            """Agents package - agent factory functions."""
            from .factory import create_node_agent, create_deepagent

            __all__ = ["create_node_agent", "create_deepagent"]
        ''').strip()

    def _generate_agents_module(self) -> str:
        """Generate agents/factory.py with agent creation functions."""
        return dedent('''
            """Agent factory functions using LangChain v1.1 and DeepAgents v2.x."""

            import logging
            from typing import List, Optional

            from langchain.agents import create_agent

            logger = logging.getLogger(__name__)


            def create_node_agent(
                model: str,
                tools: List = None,
                system_prompt: str = "You are a helpful assistant."
            ):
                """
                Create an agent for a workflow node.

                Uses LangChain v1.1 pattern with model as string identifier.

                Args:
                    model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4-5-20250929")
                    tools: List of tools to bind to the agent
                    system_prompt: System prompt for the agent

                Returns:
                    Compiled agent ready for invocation
                """
                agent = create_agent(
                    model=model,
                    tools=tools or [],
                    system_prompt=system_prompt
                )

                logger.info(f"Created agent with model={model}, tools={len(tools or [])}")
                return agent


            def create_deepagent(
                model: str,
                system_prompt: str = "You are a helpful assistant."
            ):
                """
                Create a DeepAgent for complex multi-step tasks.

                Uses DeepAgents v2.x pattern. DeepAgents automatically include:
                - TodoListMiddleware (planning/task breakdown)
                - FilesystemMiddleware (context management)
                - SubAgentMiddleware (spawning specialized subagents)

                Args:
                    model: Model identifier
                    system_prompt: System prompt for the agent

                Returns:
                    Compiled DeepAgent
                """
                try:
                    from langchain.chat_models import init_chat_model
                    from deepagents import create_deep_agent

                    llm = init_chat_model(model)
                    agent = create_deep_agent(
                        model=llm,
                        system_prompt=system_prompt
                    )

                    logger.info(f"Created DeepAgent with model={model}")
                    return agent

                except ImportError:
                    logger.error("DeepAgents not installed. Run: pip install deepagents")
                    raise
        ''').strip()

    def _generate_tools_init(self) -> str:
        """Generate tools/__init__.py."""
        return dedent('''
            """Tools package - native and custom tools."""

            from .native import NATIVE_TOOLS, get_tool_by_name
            from .custom import CUSTOM_TOOLS

            __all__ = ["NATIVE_TOOLS", "CUSTOM_TOOLS", "get_tools_for_node", "get_tool_by_name"]


            def get_tools_for_node(tool_names: list) -> list:
                """
                Get tools by name for a specific node.

                Args:
                    tool_names: List of tool names to load

                Returns:
                    List of tool instances
                """
                tools = []

                for name in tool_names:
                    # Check native tools first
                    if name in NATIVE_TOOLS:
                        tools.append(NATIVE_TOOLS[name])
                    # Then check custom tools
                    elif name in CUSTOM_TOOLS:
                        tools.append(CUSTOM_TOOLS[name])
                    else:
                        import logging
                        logging.warning(f"Tool not found: {name}")

                return tools
        ''').strip()

    def _generate_native_tools_module(self) -> str:
        """Generate tools/native.py with native tool implementations."""
        # Only include tools that are actually used
        tool_implementations = []

        if "web_search" in self._used_native_tools:
            tool_implementations.append(self._get_web_search_impl())

        if "web_fetch" in self._used_native_tools:
            tool_implementations.append(self._get_web_fetch_impl())

        # Filesystem tools (DeepAgents standard naming)
        if "read_file" in self._used_native_tools or "file_read" in self._used_native_tools:
            tool_implementations.append(self._get_read_file_impl())

        if "write_file" in self._used_native_tools or "file_write" in self._used_native_tools:
            tool_implementations.append(self._get_write_file_impl())

        if "ls" in self._used_native_tools or "file_list" in self._used_native_tools:
            tool_implementations.append(self._get_ls_impl())

        if "edit_file" in self._used_native_tools:
            tool_implementations.append(self._get_edit_file_impl())

        if "glob" in self._used_native_tools:
            tool_implementations.append(self._get_glob_impl())

        if "grep" in self._used_native_tools:
            tool_implementations.append(self._get_grep_impl())

        if "reasoning_chain" in self._used_native_tools:
            tool_implementations.append(self._get_reasoning_chain_impl())

        # Memory tools share helper functions, so include them together
        if "memory_store" in self._used_native_tools or "memory_recall" in self._used_native_tools:
            tool_implementations.append(self._get_memory_tools_impl())

        tools_code = "\n\n\n".join(tool_implementations) if tool_implementations else "# No native tools used"

        # Build registry - map LangConfig aliases to actual function names
        # LangConfig uses file_read/file_write/file_list but functions are read_file/write_file/ls
        tool_name_mapping = {
            "file_read": "read_file",
            "file_write": "write_file",
            "file_list": "ls",
        }
        registry_entries = []
        for tool in self._used_native_tools:
            # Map alias to actual function name, or use tool name as-is
            func_name = tool_name_mapping.get(tool, tool)
            registry_entries.append(f'    "{tool}": {func_name},')
        registry_str = "\n".join(registry_entries) if registry_entries else "    # No tools"

        # Build without dedent to avoid indentation issues
        header = '''"""Native Python tools for workflow execution."""

import logging
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


'''
        footer = f'''


# Tool registry
NATIVE_TOOLS = {{
{registry_str}
}}


def get_tool_by_name(name: str):
    """Get a native tool by name."""
    return NATIVE_TOOLS.get(name)
'''
        return header + tools_code + footer

    def _get_web_search_impl(self) -> str:
        """Get web_search tool implementation."""
        return dedent('''
            @tool
            async def web_search(query: str, max_results: int = 5) -> str:
                """
                Search the web using DuckDuckGo.

                Args:
                    query: The search query
                    max_results: Maximum results to return

                Returns:
                    Search results as formatted text
                """
                import re
                import httpx

                try:
                    url = "https://html.duckduckgo.com/html/"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }

                    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                        response = await client.post(url, data={"q": query})
                        response.raise_for_status()

                        html = response.text
                        results = []

                        # Extract snippets
                        snippet_pattern = r\'class="result__snippet"[^>]*>([^<]+(?:<b>[^<]+</b>[^<]*)*)</\'
                        matches = re.findall(snippet_pattern, html, re.IGNORECASE)

                        for match in matches[:max_results]:
                            snippet = re.sub(r\'<[^>]+>\', \'\', match)
                            snippet = snippet.replace(\'&quot;\', \'"\').replace(\'&amp;\', \'&\')
                            snippet = snippet.strip()
                            if snippet and len(snippet) > 10:
                                results.append(snippet)

                        if not results:
                            return f"No results found for: {query}"

                        result_text = f"Search results for \'{query}\':\\n\\n"
                        for i, snippet in enumerate(results, 1):
                            result_text += f"{i}. {snippet}\\n\\n"

                        return result_text

                except Exception as e:
                    return f"Search error: {str(e)}"
        ''').strip()

    def _get_web_fetch_impl(self) -> str:
        """Get web_fetch tool implementation."""
        return dedent('''
            @tool
            async def web_fetch(url: str, timeout: int = 10) -> str:
                """
                Fetch content from a URL.

                Args:
                    url: The URL to fetch
                    timeout: Request timeout in seconds

                Returns:
                    Page content as text
                """
                import httpx

                try:
                    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                        response = await client.get(url)
                        response.raise_for_status()

                        content_type = response.headers.get("content-type", "")
                        if "text" in content_type or "html" in content_type:
                            return response.text
                        else:
                            return f"Content type \'{content_type}\' is not text-based"

                except Exception as e:
                    return f"Fetch error: {str(e)}"
        ''').strip()

    def _get_read_file_impl(self) -> str:
        """Get read_file tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def read_file(file_path: str, max_chars: int = 50000) -> str:
                """
                Read file contents with optional line numbers.

                Args:
                    file_path: Path to the file
                    max_chars: Maximum characters to read

                Returns:
                    File contents
                """
                try:
                    path = Path(file_path).resolve()

                    if not path.exists():
                        return f"File not found: {file_path}"

                    content = path.read_text(encoding="utf-8")

                    if len(content) > max_chars:
                        content = content[:max_chars] + f"\\n\\n[Truncated - {len(content)} chars total]"

                    return content

                except Exception as e:
                    return f"Read error: {str(e)}"
        ''').strip()

    def _get_write_file_impl(self) -> str:
        """Get write_file tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def write_file(file_path: str, content: str) -> str:
                """
                Create a new file with the specified content.

                Args:
                    file_path: Path to write to
                    content: Content to write

                Returns:
                    Success message
                """
                try:
                    path = Path(file_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")

                    return f"Wrote {len(content)} chars to {file_path}"

                except Exception as e:
                    return f"Write error: {str(e)}"
        ''').strip()

    def _get_ls_impl(self) -> str:
        """Get ls tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def ls(directory_path: str = ".", pattern: str = "*") -> str:
                """
                List directory contents with metadata.

                Args:
                    directory_path: Path to the directory (default: current dir)
                    pattern: Glob pattern for filtering

                Returns:
                    List of files with metadata
                """
                try:
                    path = Path(directory_path).resolve()

                    if not path.exists():
                        return f"Directory not found: {directory_path}"

                    files = list(path.glob(pattern))

                    if not files:
                        return f"No files matching pattern in {directory_path}"

                    results = []
                    for f in sorted(files):
                        file_type = "DIR" if f.is_dir() else "FILE"
                        size = f.stat().st_size if f.is_file() else 0
                        results.append(f"[{file_type}] {f.name} ({size} bytes)")

                    return "\\n".join(results)

                except Exception as e:
                    return f"List error: {str(e)}"
        ''').strip()

    def _get_edit_file_impl(self) -> str:
        """Get edit_file tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def edit_file(file_path: str, old_string: str, new_string: str) -> str:
                """
                Perform exact string replacement in a file.

                Args:
                    file_path: Path to the file to edit
                    old_string: The exact text to find and replace
                    new_string: The text to replace it with

                Returns:
                    Success message or error
                """
                try:
                    path = Path(file_path).resolve()

                    if not path.exists():
                        return f"File not found: {file_path}"

                    content = path.read_text(encoding="utf-8")

                    if old_string not in content:
                        return f"String not found in file: {old_string[:50]}..."

                    # Check for uniqueness
                    count = content.count(old_string)
                    if count > 1:
                        return f"String appears {count} times. Please provide a more unique string."

                    new_content = content.replace(old_string, new_string, 1)
                    path.write_text(new_content, encoding="utf-8")

                    return f"Successfully replaced text in {file_path}"

                except Exception as e:
                    return f"Edit error: {str(e)}"
        ''').strip()

    def _get_glob_impl(self) -> str:
        """Get glob tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def glob(pattern: str, path: str = ".") -> str:
                """
                Find files matching a glob pattern.

                Args:
                    pattern: Glob pattern (e.g., "**/*.py", "src/*.ts")
                    path: Base path to search from (default: current dir)

                Returns:
                    List of matching file paths
                """
                try:
                    base_path = Path(path).resolve()

                    if not base_path.exists():
                        return f"Path not found: {path}"

                    matches = list(base_path.glob(pattern))

                    if not matches:
                        return f"No files matching pattern: {pattern}"

                    # Sort by modification time (most recent first)
                    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

                    results = []
                    for f in matches[:100]:  # Limit to 100 results
                        rel_path = f.relative_to(base_path) if f.is_relative_to(base_path) else f
                        results.append(str(rel_path))

                    result = "\\n".join(results)
                    if len(matches) > 100:
                        result += f"\\n\\n[{len(matches) - 100} more matches not shown]"

                    return result

                except Exception as e:
                    return f"Glob error: {str(e)}"
        ''').strip()

    def _get_grep_impl(self) -> str:
        """Get grep tool implementation (DeepAgents standard naming)."""
        return dedent('''
            @tool
            def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
                """
                Search file contents using regex.

                Args:
                    pattern: Regex pattern to search for
                    path: Directory to search in (default: current dir)
                    file_pattern: Glob pattern to filter files (default: all files)

                Returns:
                    Matching lines with file paths and line numbers
                """
                import re

                try:
                    base_path = Path(path).resolve()

                    if not base_path.exists():
                        return f"Path not found: {path}"

                    regex = re.compile(pattern)
                    results = []
                    files_searched = 0
                    max_results = 50

                    for file_path in base_path.rglob(file_pattern):
                        if not file_path.is_file():
                            continue

                        files_searched += 1

                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            for line_num, line in enumerate(content.splitlines(), 1):
                                if regex.search(line):
                                    rel_path = file_path.relative_to(base_path)
                                    results.append(f"{rel_path}:{line_num}: {line.strip()}")
                                    if len(results) >= max_results:
                                        break
                        except Exception:
                            continue

                        if len(results) >= max_results:
                            break

                    if not results:
                        return f"No matches found for pattern: {pattern}"

                    result = "\\n".join(results)
                    if len(results) >= max_results:
                        result += f"\\n\\n[Results limited to {max_results} matches]"

                    return result

                except re.error as e:
                    return f"Invalid regex pattern: {str(e)}"
                except Exception as e:
                    return f"Grep error: {str(e)}"
        ''').strip()

    def _get_reasoning_chain_impl(self) -> str:
        """Get reasoning_chain tool implementation."""
        return dedent('''
            @tool
            def reasoning_chain(task: str, steps: int = 5) -> str:
                """
                Break down a complex task into reasoning steps.

                Args:
                    task: The task to reason about
                    steps: Number of reasoning steps

                Returns:
                    Structured reasoning framework
                """
                return f"""
            TASK: {task}

            REASONING STEPS:
            1. Analyze the requirements and constraints
            2. Identify key objectives and success criteria
            3. Consider potential approaches and trade-offs
            4. Evaluate risks and mitigation strategies
            5. Synthesize into a concrete action plan

            Note: The agent should fill in the actual analysis for each step.
            """
        ''').strip()

    def _get_memory_tools_impl(self) -> str:
        """Get memory_store and memory_recall tool implementations."""
        return dedent('''
            import json
            from pathlib import Path
            from datetime import datetime

            # Memory file path (persists across runs)
            MEMORY_FILE = Path(__file__).parent.parent / "memory_store.json"


            def _load_memory() -> dict:
                """Load memory from file."""
                if MEMORY_FILE.exists():
                    try:
                        return json.loads(MEMORY_FILE.read_text())
                    except Exception:
                        return {"memories": []}
                return {"memories": []}


            def _save_memory(data: dict):
                """Save memory to file."""
                MEMORY_FILE.write_text(json.dumps(data, indent=2))


            @tool
            def memory_store(content: str, metadata: str = "") -> str:
                """
                Store information in long-term memory.

                Args:
                    content: The content to remember
                    metadata: Optional metadata/tags for the memory

                Returns:
                    Confirmation message
                """
                try:
                    data = _load_memory()
                    memory_entry = {
                        "content": content,
                        "metadata": metadata,
                        "timestamp": datetime.now().isoformat()
                    }
                    data["memories"].append(memory_entry)
                    _save_memory(data)
                    return f"Stored in memory: {content[:100]}..."
                except Exception as e:
                    return f"Memory store error: {str(e)}"


            @tool
            def memory_recall(query: str, max_results: int = 5) -> str:
                """
                Recall information from long-term memory.

                Args:
                    query: Search query to find relevant memories
                    max_results: Maximum number of memories to return

                Returns:
                    Relevant memories as formatted text
                """
                try:
                    data = _load_memory()
                    memories = data.get("memories", [])

                    if not memories:
                        return "No memories stored yet."

                    # Simple keyword matching (could be enhanced with embeddings)
                    query_lower = query.lower()
                    relevant = []
                    for mem in memories:
                        content = mem.get("content", "").lower()
                        metadata = mem.get("metadata", "").lower()
                        if query_lower in content or query_lower in metadata:
                            relevant.append(mem)

                    # If no keyword matches, return most recent
                    if not relevant:
                        relevant = memories[-max_results:]

                    relevant = relevant[:max_results]

                    if not relevant:
                        return "No relevant memories found."

                    result = "RECALLED MEMORIES:\\n"
                    for i, mem in enumerate(relevant, 1):
                        result += f"\\n{i}. {mem.get('content', '')}\\n"
                        if mem.get('metadata'):
                            result += f"   [Metadata: {mem['metadata']}]\\n"
                        result += f"   [Stored: {mem.get('timestamp', 'unknown')}]\\n"

                    return result
                except Exception as e:
                    return f"Memory recall error: {str(e)}"
        ''').strip()

    async def _generate_custom_tools_module(self) -> str:
        """Generate tools/custom.py with custom tool implementations."""
        # Fetch custom tools from database
        custom_tool_code = []

        if self._used_custom_tools:
            try:
                from db.database import SessionLocal
                from models.custom_tool import CustomTool

                db = SessionLocal()
                try:
                    for tool_id in self._used_custom_tools:
                        custom_tool = db.query(CustomTool).filter(
                            CustomTool.tool_id == tool_id
                        ).first()

                        if custom_tool:
                            code = self._generate_custom_tool_code(custom_tool)
                            custom_tool_code.append(code)
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Failed to fetch custom tools: {e}")

        tools_code = "\n\n\n".join(custom_tool_code) if custom_tool_code else "# No custom tools"

        # Build registry
        registry_entries = []
        for tool_id in self._used_custom_tools:
            safe_name = self._sanitize_name(tool_id)
            registry_entries.append(f'    "{tool_id}": {safe_name}_tool,')
        registry_str = "\n".join(registry_entries) if registry_entries else "    # No tools"

        # Build without dedent to avoid indentation issues
        header = '''"""Custom tools defined by the user."""

import logging
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)


'''
        footer = f'''


# Custom tool registry
CUSTOM_TOOLS = {{
{registry_str}
}}
'''
        return header + tools_code + footer

    def _generate_custom_tool_code(self, custom_tool) -> str:
        """Generate code for a single custom tool."""
        safe_name = self._sanitize_name(custom_tool.tool_id)
        name = custom_tool.name
        description = custom_tool.description or "Custom tool"
        impl_config = custom_tool.implementation_config or {}

        # Generate based on tool type
        tool_type = custom_tool.tool_type.value if hasattr(custom_tool.tool_type, "value") else str(custom_tool.tool_type)

        if tool_type == "api_request":
            return self._generate_api_tool(safe_name, name, description, impl_config)
        elif tool_type == "code_execution":
            return self._generate_code_tool(safe_name, name, description, impl_config)
        elif tool_type == "image_video":
            return self._generate_image_video_tool(safe_name, name, description, impl_config)
        elif tool_type == "notification":
            return self._generate_notification_tool(safe_name, name, description, impl_config)
        else:
            # Default placeholder
            return dedent(f'''
                def {safe_name}_func(input_str: str) -> str:
                    """{description}"""
                    # TODO: Implement custom logic
                    return f"Custom tool '{name}' executed with input: {{input_str}}"

                {safe_name}_tool = StructuredTool.from_function(
                    func={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

    def _generate_api_tool(self, safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate an API request tool."""
        url = config.get("url", "https://example.com/api")
        method = config.get("method", "GET")
        headers = config.get("headers", {})

        return dedent(f'''
            async def {safe_name}_func(input_str: str) -> str:
                """{description}"""
                import httpx

                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.request(
                            method="{method}",
                            url="{url}",
                            headers={repr(headers)},
                            json={{"input": input_str}} if "{method}" in ("POST", "PUT") else None,
                            params={{"q": input_str}} if "{method}" == "GET" else None
                        )
                        response.raise_for_status()
                        return response.text
                except Exception as e:
                    return f"API error: {{str(e)}}"

            {safe_name}_tool = StructuredTool.from_function(
                func={safe_name}_func,
                name="{name}",
                description="{description}",
                coroutine={safe_name}_func
            )
        ''').strip()

    def _generate_code_tool(self, safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate a code execution tool."""
        code = config.get("code", "return input_str")

        return dedent(f'''
            def {safe_name}_func(input_str: str) -> str:
                """{description}"""
                try:
                    # User-defined code
                    {code}
                except Exception as e:
                    return f"Execution error: {{str(e)}}"

            {safe_name}_tool = StructuredTool.from_function(
                func={safe_name}_func,
                name="{name}",
                description="{description}"
            )
        ''').strip()

    def _generate_image_video_tool(self, safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate an image/video generation tool (Gemini, DALL-E, etc.)."""
        provider = config.get("provider", "google")
        model = config.get("model", "gemini-3-pro-image-preview")
        timeout = config.get("timeout", 60)

        if provider == "google":
            # Gemini / Nano Banana image generation
            return dedent(f'''
                # Artifact storage for multimodal content
                from contextvars import ContextVar
                from typing import Optional, List, Dict, Any

                _{safe_name}_artifacts: ContextVar[List[Dict[str, Any]]] = ContextVar('{safe_name}_artifacts', default=[])

                def get_{safe_name}_artifacts() -> List[Dict[str, Any]]:
                    """Get and clear pending artifacts from image generation."""
                    artifacts = _{safe_name}_artifacts.get()
                    _{safe_name}_artifacts.set([])
                    return artifacts

                async def {safe_name}_func(
                    prompt: str,
                    aspect_ratio: Optional[str] = "1:1",
                    style: Optional[str] = None
                ) -> str:
                    """{description}

                    Args:
                        prompt: Description of the image to generate
                        aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
                        style: Optional style modifier (vivid, natural, photorealistic)

                    Returns:
                        Success message (image stored as artifact for UI display)
                    """
                    import httpx
                    import os

                    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                    if not api_key:
                        return "Error: GEMINI_API_KEY or GOOGLE_API_KEY not set in environment"

                    model = "{model}"
                    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{{model}}:generateContent"

                    # Enhance prompt with style if provided
                    enhanced_prompt = prompt
                    if style:
                        enhanced_prompt = f"{{prompt}}, {{style}} style"

                    payload = {{
                        "contents": [{{
                            "parts": [{{"text": enhanced_prompt}}]
                        }}],
                        "generationConfig": {{
                            "responseModalities": ["TEXT", "IMAGE"],
                            "temperature": 0.4,
                            "candidateCount": 1,
                            "maxOutputTokens": 8192,
                        }}
                    }}

                    try:
                        async with httpx.AsyncClient(timeout={timeout}) as client:
                            response = await client.post(
                                f"{{endpoint}}?key={{api_key}}",
                                json=payload,
                                headers={{"Content-Type": "application/json"}}
                            )
                            response.raise_for_status()
                            data = response.json()

                            # Extract image from response
                            if data.get("candidates"):
                                parts = data["candidates"][0].get("content", {{}}).get("parts", [])
                                for part in parts:
                                    if "inlineData" in part:
                                        img_data = part["inlineData"]["data"]
                                        mime_type = part["inlineData"]["mimeType"]
                                        img_size_kb = len(img_data) * 3 // 4 // 1024

                                        # Store artifact for UI display
                                        current = _{safe_name}_artifacts.get()
                                        _{safe_name}_artifacts.set(current + [{{
                                            "type": "image",
                                            "data": img_data,
                                            "mimeType": mime_type
                                        }}])

                                        return f"Image generated successfully ({{img_size_kb}}KB). The image has been created and is displayed to the user."

                            return "Error: No image in response"

                    except httpx.HTTPStatusError as e:
                        return f"API error: {{e.response.status_code}}"
                    except Exception as e:
                        return f"Error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        elif provider == "openai":
            # DALL-E image generation
            return dedent(f'''
                async def {safe_name}_func(
                    prompt: str,
                    size: str = "1024x1024",
                    quality: str = "standard"
                ) -> str:
                    """{description}

                    Args:
                        prompt: Description of the image to generate
                        size: Image size (1024x1024, 1792x1024, 1024x1792)
                        quality: Image quality (standard, hd)

                    Returns:
                        URL of the generated image
                    """
                    import httpx
                    import os

                    api_key = os.getenv("OPENAI_API_KEY")
                    if not api_key:
                        return "Error: OPENAI_API_KEY not set in environment"

                    try:
                        async with httpx.AsyncClient(timeout={timeout}) as client:
                            response = await client.post(
                                "https://api.openai.com/v1/images/generations",
                                headers={{
                                    "Authorization": f"Bearer {{api_key}}",
                                    "Content-Type": "application/json"
                                }},
                                json={{
                                    "model": "dall-e-3",
                                    "prompt": prompt,
                                    "n": 1,
                                    "size": size,
                                    "quality": quality
                                }}
                            )
                            response.raise_for_status()
                            data = response.json()

                            if data.get("data") and len(data["data"]) > 0:
                                image_url = data["data"][0].get("url")
                                return f"Image generated successfully: {{image_url}}"

                            return "Error: No image in response"

                    except httpx.HTTPStatusError as e:
                        return f"API error: {{e.response.status_code}}"
                    except Exception as e:
                        return f"Error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        else:
            # Unknown provider fallback
            return dedent(f'''
                async def {safe_name}_func(prompt: str) -> str:
                    """{description}"""
                    return f"Image generation not implemented for provider: {provider}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

    def _generate_notification_tool(self, safe_name: str, name: str, description: str, config: Dict) -> str:
        """Generate a notification tool (Slack, Discord, etc.)."""
        provider = config.get("provider", "discord")
        webhook_url = config.get("webhook_url", "")

        if provider == "discord":
            return dedent(f'''
                async def {safe_name}_func(message: str, username: str = "Workflow Bot") -> str:
                    """{description}

                    Args:
                        message: The message to send
                        username: Bot username to display

                    Returns:
                        Success or error message
                    """
                    import httpx
                    import os

                    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or "{webhook_url}"
                    if not webhook_url:
                        return "Error: DISCORD_WEBHOOK_URL not configured"

                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            response = await client.post(
                                webhook_url,
                                json={{"content": message, "username": username}}
                            )
                            response.raise_for_status()
                            return "Message sent successfully to Discord"
                    except Exception as e:
                        return f"Discord error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        elif provider == "slack":
            return dedent(f'''
                async def {safe_name}_func(message: str, channel: str = "#general") -> str:
                    """{description}

                    Args:
                        message: The message to send
                        channel: Slack channel to post to

                    Returns:
                        Success or error message
                    """
                    import httpx
                    import os

                    webhook_url = os.getenv("SLACK_WEBHOOK_URL") or "{webhook_url}"
                    if not webhook_url:
                        return "Error: SLACK_WEBHOOK_URL not configured"

                    try:
                        async with httpx.AsyncClient(timeout=30) as client:
                            response = await client.post(
                                webhook_url,
                                json={{"text": message, "channel": channel}}
                            )
                            response.raise_for_status()
                            return "Message sent successfully to Slack"
                    except Exception as e:
                        return f"Slack error: {{str(e)}}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

        else:
            return dedent(f'''
                async def {safe_name}_func(message: str) -> str:
                    """{description}"""
                    return f"Notification not implemented for provider: {provider}"

                {safe_name}_tool = StructuredTool.from_function(
                    coroutine={safe_name}_func,
                    name="{name}",
                    description="{description}"
                )
            ''').strip()

    def _generate_settings_module(self) -> str:
        """Generate config/settings.py."""
        return dedent('''
            """Configuration settings loaded from environment."""

            import os
            from dotenv import load_dotenv

            # Load .env file
            load_dotenv()


            class Settings:
                """Application settings."""

                # API Keys
                OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
                ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
                GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
                GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

                # Notification webhooks
                DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
                SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

                # Workflow settings
                MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "10"))
                TIMEOUT_SECONDS: int = int(os.getenv("TIMEOUT_SECONDS", "600"))

                @classmethod
                def validate(cls) -> bool:
                    """Validate that required settings are configured."""
                    # Check if at least one API key is set
                    has_key = any([
                        cls.OPENAI_API_KEY,
                        cls.ANTHROPIC_API_KEY,
                        cls.GOOGLE_API_KEY
                    ])

                    if not has_key:
                        print("WARNING: No API keys configured. Set at least one in .env file.")
                        return False

                    return True


            settings = Settings()
        ''').strip()

    def _generate_streamlit_app(self) -> str:
        """Generate streamlit_app.py with visual UI."""
        # Build node info for display
        node_names = []
        for node in self.nodes:
            node_data = node.get("data", {})
            name = node_data.get("name") or node_data.get("label") or node.get("id", "Node")
            node_names.append(name)

        nodes_display = ", ".join(f'"{n}"' for n in node_names[:5])
        if len(node_names) > 5:
            nodes_display += f", ... (+{len(node_names) - 5} more)"

        return dedent(f'''
            #!/usr/bin/env python3
            """
            Streamlit UI for {self.workflow_name}

            Run with: streamlit run streamlit_app.py
            """

            import asyncio
            import os
            import time
            from datetime import datetime

            import streamlit as st
            from dotenv import load_dotenv

            from workflow.graph import create_workflow
            from workflow.state import WorkflowState

            # Load environment variables from .env file (as fallback)
            load_dotenv()

            # Page config
            st.set_page_config(
                page_title="{self.workflow_name}",
                layout="wide"
            )

            # Custom CSS for better styling - static layout with minimal scrolling
            st.markdown("""
            <style>
                /* Remove default Streamlit scrolling and padding */
                .main .block-container {{
                    padding-top: 2rem;
                    padding-bottom: 2rem;
                    max-width: 100%;
                }}

                /* Make sidebar static */
                [data-testid="stSidebar"] {{
                    position: fixed;
                    height: 100vh;
                    overflow-y: auto;
                }}
                [data-testid="stSidebar"] > div {{
                    height: 100%;
                    overflow-y: auto;
                }}

                /* Status indicators */
                .status-running {{
                    color: #1f77b4;
                    font-weight: bold;
                }}
                .status-completed {{
                    color: #2ca02c;
                    font-weight: bold;
                }}
                .status-error {{
                    color: #d62728;
                    font-weight: bold;
                }}

                /* Execution progress cards - compact */
                .node-card {{
                    background-color: #1e1e2e;
                    color: #e0e0e0;
                    border-radius: 6px;
                    padding: 8px 12px;
                    margin: 4px 0;
                    border-left: 3px solid #1f77b4;
                    font-size: 14px;
                }}
                .node-card strong {{
                    color: #ffffff;
                }}

                /* Live streaming output - THIS is the scrollable area */
                .streaming-content {{
                    background-color: #1e1e2e;
                    color: #e0e0e0;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 12px 0;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    max-height: 500px;
                    overflow-y: auto;
                }}
                .token-stream {{
                    color: #98c379;
                }}

                /* Final result - scrollable if needed, normal text wrapping */
                .final-result {{
                    background-color: #1a1a2e;
                    color: #e8e8e8;
                    border-radius: 10px;
                    padding: 24px;
                    margin: 16px 0;
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    font-size: 15px;
                    line-height: 1.6;
                    white-space: normal;
                    word-wrap: break-word;
                    border: 1px solid #333;
                    max-height: 600px;
                    overflow-y: auto;
                }}
                .final-result h1, .final-result h2, .final-result h3 {{
                    color: #ffffff;
                    margin-top: 0.8em;
                    margin-bottom: 0.4em;
                }}
                .final-result p {{
                    margin: 0.5em 0;
                }}

                /* Green run button */
                .stButton > button[kind="primary"] {{
                    background-color: #2ca02c !important;
                    border-color: #2ca02c !important;
                }}
                .stButton > button[kind="primary"]:hover {{
                    background-color: #228b22 !important;
                    border-color: #228b22 !important;
                }}

                /* Remove extra padding from expanders */
                .streamlit-expanderContent {{
                    padding: 0.5rem 0;
                }}

                /* Make text areas not have double scroll */
                .stTextArea textarea {{
                    max-height: 400px;
                }}
            </style>
            """, unsafe_allow_html=True)


            def init_session_state():
                """Initialize session state variables."""
                if "messages" not in st.session_state:
                    st.session_state.messages = []
                if "execution_history" not in st.session_state:
                    st.session_state.execution_history = []
                if "is_running" not in st.session_state:
                    st.session_state.is_running = False
                if "current_node" not in st.session_state:
                    st.session_state.current_node = None
                if "show_copy_area" not in st.session_state:
                    st.session_state.show_copy_area = False
                if "last_result" not in st.session_state:
                    st.session_state.last_result = ""
                # API Keys - load from env as defaults
                if "openai_api_key" not in st.session_state:
                    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
                if "anthropic_api_key" not in st.session_state:
                    st.session_state.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
                if "google_api_key" not in st.session_state:
                    st.session_state.google_api_key = os.getenv("GOOGLE_API_KEY", "")


            def apply_api_keys():
                """Apply API keys to environment variables."""
                if st.session_state.openai_api_key:
                    os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
                if st.session_state.anthropic_api_key:
                    os.environ["ANTHROPIC_API_KEY"] = st.session_state.anthropic_api_key
                if st.session_state.google_api_key:
                    os.environ["GOOGLE_API_KEY"] = st.session_state.google_api_key


            async def run_workflow_streaming(query: str, status_container, output_container, stream_container):
                """Run the workflow with streaming updates and live token output."""
                st.session_state.is_running = True
                st.session_state.current_node = None
                execution_log = []
                streaming_text = ""
                final_messages = []

                try:
                    # Create workflow
                    graph = create_workflow()

                    # Initial state
                    initial_state = {{
                        "messages": [],
                        "query": query,
                        "step_history": [],
                    }}

                    start_time = time.time()

                    # Stream execution with astream_events for real-time token streaming
                    status_container.info("Starting workflow execution...")

                    current_node_name = None

                    # Track which nodes we've already logged to avoid duplicates
                    logged_nodes = set()
                    # Names to skip (internal langgraph nodes)
                    skip_names = {{"RunnableSequence", "ChannelRead", "ChannelWrite", "RunnableLambda",
                                  "RunnableParallel", "StateGraph", "CompiledStateGraph", ""}}

                    async for event in graph.astream_events(initial_state, version="v2"):
                        event_type = event.get("event", "")
                        event_data = event.get("data", {{}})

                        # Track node changes - only log actual workflow nodes
                        if event_type == "on_chain_start":
                            node_name = event.get("name", "")
                            # Skip internal nodes and already-logged nodes
                            if (node_name and
                                node_name not in skip_names and
                                node_name not in logged_nodes and
                                not node_name.startswith("_") and
                                node_name != current_node_name):
                                current_node_name = node_name
                                logged_nodes.add(node_name)
                                st.session_state.current_node = node_name
                                execution_log.append({{
                                    "node": node_name,
                                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                                    "status": "running"
                                }})
                                # Update progress display
                                with output_container:
                                    output_container.empty()
                                    for step in execution_log:
                                        status_icon = "OK" if step.get("status") == "completed" else "..."
                                        st.markdown(f"""
                                        <div class="node-card">
                                            <strong>[{{status_icon}}] {{step.get("node", "Unknown")}}</strong>
                                            <span style="float: right; color: #888;">{{step.get("timestamp", "")}}</span>
                                        </div>
                                        """, unsafe_allow_html=True)

                        # Stream tokens in real-time
                        elif event_type == "on_chat_model_stream":
                            chunk = event_data.get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                # Handle both string and list content (Claude can return list for tool calls)
                                content = chunk.content
                                if isinstance(content, list):
                                    # Extract text from content blocks
                                    text_parts = []
                                    for item in content:
                                        if isinstance(item, dict) and item.get("type") == "text":
                                            text_parts.append(item.get("text", ""))
                                        elif isinstance(item, str):
                                            text_parts.append(item)
                                    content = "".join(text_parts)
                                if content and isinstance(content, str):
                                    streaming_text += content
                                    # Clean up excessive newlines for display
                                    import re
                                    display_text = streaming_text.strip()
                                    # Collapse multiple newlines to max 1 blank line
                                    display_text = re.sub(r'\\n\\s*\\n', '\\n\\n', display_text)
                                    # Remove trailing spaces from lines
                                    display_text = re.sub(r' +\\n', '\\n', display_text)
                                    # Update streaming display
                                    with stream_container:
                                        stream_container.markdown(display_text)

                        # Handle tool calls - only show tool name once
                        elif event_type == "on_tool_start":
                            tool_name = event.get("name", "tool")
                            if tool_name not in logged_nodes:
                                logged_nodes.add(tool_name)
                                execution_log.append({{
                                    "node": f"Tool: {{tool_name}}",
                                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                                    "status": "running",
                                    "tool": tool_name
                                }})

                        elif event_type == "on_tool_end":
                            # Mark last tool as completed
                            for step in reversed(execution_log):
                                if step.get("tool"):
                                    step["status"] = "completed"
                                    break

                        # Node completed
                        elif event_type == "on_chain_end":
                            node_name = event.get("name", "")
                            output = event_data.get("output", {{}})

                            # Mark node as completed (only if it's in our log)
                            if node_name not in skip_names:
                                for step in execution_log:
                                    if step.get("node") == node_name and step.get("status") == "running":
                                        step["status"] = "completed"

                            # Capture messages from output
                            if isinstance(output, dict) and "messages" in output:
                                final_messages = output.get("messages", [])

                    # Get final result
                    elapsed = time.time() - start_time

                    status_container.success(f"Workflow completed in {{elapsed:.2f}}s")

                    # Display final result
                    st.markdown("---")
                    st.markdown("### Final Result")

                    def extract_text_content(content):
                        """Extract text from content that may be string or list."""
                        if isinstance(content, str):
                            return content
                        elif isinstance(content, list):
                            text_parts = []
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                                elif isinstance(item, str):
                                    text_parts.append(item)
                            return "".join(text_parts)
                        return str(content) if content else ""

                    # Get final result text
                    result_text = ""
                    if final_messages:
                        for msg in reversed(final_messages):
                            if hasattr(msg, "content"):
                                result_text = extract_text_content(msg.content)
                                break
                    elif streaming_text:
                        result_text = streaming_text

                    if result_text:
                        # Clean up excessive newlines for better formatting
                        import re
                        clean_text = re.sub(r'\\n{{3,}}', '\\n\\n', result_text)  # Max 2 newlines
                        clean_text = clean_text.strip()

                        # Store result in session state for copy functionality
                        st.session_state.last_result = clean_text

                        # Display with nice formatting (use markdown for rendering)
                        st.markdown(clean_text)

                        # Copy section
                        st.markdown("---")
                        copy_col1, copy_col2 = st.columns([1, 3])
                        with copy_col1:
                            # Use st.code which has built-in copy button
                            if st.button("Show Copyable Text", key="show_copy"):
                                st.session_state.show_copy_area = True

                        if st.session_state.get("show_copy_area", False):
                            st.code(clean_text, language=None)
                            st.caption("Click the copy icon in the top-right of the code block above")
                    else:
                        st.info("No output message generated.")
                    st.session_state.execution_history.append({{
                        "query": query,
                        "result": result_text,
                        "elapsed": elapsed,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "steps": len(execution_log)
                    }})

                except Exception as e:
                    status_container.error(f"Workflow failed: {{str(e)}}")
                    st.exception(e)

                finally:
                    st.session_state.is_running = False
                    st.session_state.current_node = None


            def main():
                """Main Streamlit app."""
                init_session_state()

                # Header
                st.title("{self.workflow_name}")
                st.markdown("*Exported from LangConfig*")

                # Sidebar with workflow info and settings
                with st.sidebar:
                    st.header("Workflow Info")
                    st.markdown(f"""
                    - **Nodes**: {len(self.nodes)}
                    - **Edges**: {len(self.edges)}
                    - **Nodes**: [{nodes_display}]
                    """)

                    st.divider()

                    # API Key Configuration
                    st.header("API Keys")
                    st.caption("Enter your API keys below")

                    st.session_state.openai_api_key = st.text_input(
                        "OpenAI API Key",
                        value=st.session_state.openai_api_key,
                        type="password",
                        placeholder="sk-..."
                    )

                    st.session_state.anthropic_api_key = st.text_input(
                        "Anthropic API Key",
                        value=st.session_state.anthropic_api_key,
                        type="password",
                        placeholder="sk-ant-..."
                    )

                    st.session_state.google_api_key = st.text_input(
                        "Google API Key",
                        value=st.session_state.google_api_key,
                        type="password",
                        placeholder="AI..."
                    )

                    st.divider()

                    # Execution history - compact, no expanders
                    st.markdown("**Recent Runs**")
                    if st.session_state.execution_history:
                        for run in reversed(st.session_state.execution_history[-3:]):
                            st.caption(f"{{run['timestamp']}} - {{run['elapsed']:.1f}}s")
                        if st.button("Clear", key="clear_history"):
                            st.session_state.execution_history = []
                            st.rerun()
                    else:
                        st.caption("No runs yet")

                # Main content area - full width for better output display
                st.header("Run Workflow")

                # Tips in an expander to save space
                with st.expander("How to use", expanded=False):
                    st.markdown("""
                    1. **Configure API keys** in the sidebar (or use `.env` file)
                    2. **Enter your query** in the text box below
                    3. **Click "Run Workflow"** to start execution
                    4. **Watch live output** as the agents work
                    5. **Copy the result** using the copy buttons or expander
                    """)

                # Use a form so the button works without clicking out of text area
                with st.form(key="workflow_form", clear_on_submit=False):
                    # Query input - wider
                    query = st.text_area(
                        "Enter your query:",
                        height=120,
                        placeholder="Type your question or task here...",
                        disabled=st.session_state.is_running
                    )

                    # Run button (green via CSS, form submit)
                    submitted = st.form_submit_button(
                        "Run Workflow" if not st.session_state.is_running else "Running...",
                        disabled=st.session_state.is_running,
                        type="primary",
                        use_container_width=True
                    )

                # Handle form submission
                if submitted and query.strip():
                    # Apply API keys to environment before running
                    apply_api_keys()

                    # Status at top
                    status_container = st.empty()

                    # Two column layout: output on left, progress on right
                    out_col, prog_col = st.columns([3, 1])

                    with out_col:
                        st.markdown("#### Live Output")
                        stream_container = st.empty()

                    with prog_col:
                        st.markdown("#### Progress")
                        output_container = st.container()

                    # Run the workflow
                    asyncio.run(run_workflow_streaming(query, status_container, output_container, stream_container))

                # Footer
                st.divider()
                st.caption("Generated with LangConfig | Powered by LangChain and LangGraph")


            if __name__ == "__main__":
                main()
        ''').strip()
