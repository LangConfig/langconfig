# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Template generators for the Executable Workflow Exporter.

Generates static template files like README, requirements, settings, etc.
"""

import logging
from datetime import datetime
from textwrap import dedent
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class TemplateGenerators:
    """Generators for static template files."""

    @staticmethod
    def generate_readme(
        workflow_name: str,
        nodes: List[Dict],
        edges: List[Dict],
        include_ui: bool,
        sanitize_name_func,
        include_api: bool = True
    ) -> str:
        """Generate README.md with setup instructions."""
        ui_section = ""
        if include_ui:
            ui_section = """
            ## Run with Streamlit UI

            For a visual interface with live streaming output:
            ```bash
            streamlit run streamlit_app.py
            ```

            This opens a browser with:
            - **Agent Thinking Display** - Watch agents reason in real-time
            - **Tool Call Cards** - See tool execution with status indicators
            - **Structured Output** - Clean markdown rendering of results
            - **API Key Configuration** - Enter keys directly in the sidebar
            - **Execution History** - Track previous runs
            """

        api_section = ""
        if include_api:
            api_section = """
            ## Run as API Server

            For programmatic access via REST API:
            ```bash
            python api_server.py
            ```

            Or with auto-reload for development:
            ```bash
            uvicorn api_server:app --reload --port 8000
            ```

            **Available Endpoints:**
            - `POST /run` - Execute workflow with JSON body `{"query": "your prompt"}`
            - `POST /run/stream` - Execute with SSE streaming for real-time updates
            - `GET /health` - Health check endpoint
            - `GET /info` - Get workflow metadata
            - Interactive docs at `http://localhost:8000/docs`

            **Example curl:**
            ```bash
            curl -X POST http://localhost:8000/run \
              -H "Content-Type: application/json" \
              -d '{"query": "Your prompt here"}'
            ```
            """

        return dedent(f'''
            # {workflow_name}

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
            {api_section}
            ## Workflow Details

            - **Name**: {workflow_name}
            - **Nodes**: {len(nodes)}
            - **Edges**: {len(edges)}

            ## Requirements

            - Python 3.10+
            - API keys for your chosen model provider(s)

            ## LangSmith Observability (Optional)

            This workflow supports [LangSmith](https://smith.langchain.com) for production monitoring and debugging.

            **Quick Setup:**
            1. Get a free API key at [smith.langchain.com](https://smith.langchain.com)
            2. Add to your `.env` file:
               ```
               LANGSMITH_TRACING=true
               LANGSMITH_API_KEY=lsv2_pt_your-key-here
               LANGSMITH_PROJECT={sanitize_name_func(workflow_name)}
               ```
            3. Run your workflow - traces appear automatically!

            **What you get:**
            - 📊 Execution traces with timing for every step
            - 🔍 Debug failed runs with full input/output context
            - 📈 Token usage and cost tracking
            - 🧪 Evaluation and A/B testing tools
            - 🔄 Compare runs across different configurations

            ## Generated with LangConfig

            This workflow was exported using LangConfig's executable export feature.
            Learn more at: https://github.com/langconfig/langconfig
        ''').strip()

    @staticmethod
    def generate_requirements(
        used_models: Set[str],
        used_native_tools: Set[str],
        has_deepagents: bool,
        include_ui: bool,
        include_api: bool = True
    ) -> str:
        """Generate requirements.txt based on workflow features."""
        requirements = [
            "# Core dependencies",
            "langgraph>=1.0.4",
            "langchain>=1.1.2",
            "langchain-core>=1.1.1",
            "python-dotenv>=1.0.0",
            "pydantic>=2.0.0",
            "",
            "# Observability (optional - enable with LANGSMITH_API_KEY)",
            "langsmith>=0.1.0",
            "",
        ]

        # Streamlit UI
        if include_ui:
            requirements.extend([
                "# Streamlit UI",
                "streamlit>=1.28.0",
                "",
            ])

        # FastAPI Server
        if include_api:
            requirements.extend([
                "# API Server",
                "fastapi>=0.104.0",
                "uvicorn>=0.24.0",
                "",
            ])

        # Model-specific dependencies
        model_deps = []
        for model in used_models:
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
        if has_deepagents:
            requirements.append("# DeepAgents")
            requirements.append("deepagents>=0.3.0")
            requirements.append("")

        # Tool-specific dependencies
        tool_deps = []
        if used_native_tools & {"web_search", "web_fetch"}:
            tool_deps.append("httpx")
        if "browser" in used_native_tools:
            tool_deps.append("playwright")
            tool_deps.append("langchain-community")

        if tool_deps:
            requirements.append("# Tool dependencies")
            requirements.extend(sorted(set(tool_deps)))
            requirements.append("")

        return "\n".join(requirements)

    @staticmethod
    def generate_env_example(
        used_models: Set[str],
        used_custom_tools: Set[str],
        workflow_name: str,
        sanitize_name_func
    ) -> str:
        """Generate .env.example with API key placeholders."""
        env_vars = [
            "# API Keys - Add your keys here",
            "",
        ]

        # Detect which API keys are needed based on models
        for model in used_models:
            model_lower = model.lower()
            if "gpt" in model_lower or "openai" in model_lower:
                env_vars.append("OPENAI_API_KEY=sk-your-openai-key-here")
            elif "claude" in model_lower or "anthropic" in model_lower:
                env_vars.append("ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here")
            elif "gemini" in model_lower or "google" in model_lower:
                env_vars.append("GOOGLE_API_KEY=your-google-api-key-here")

        # Detect custom tool requirements
        if used_custom_tools:
            env_vars.append("")
            env_vars.append("# Custom Tool API Keys (add as needed)")
            env_vars.append("GEMINI_API_KEY=your-gemini-api-key-here  # For image generation")
            env_vars.append("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
            env_vars.append("SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...")

        # Add LangSmith observability section
        langsmith_project = f"langconfig-{sanitize_name_func(workflow_name)}"
        env_vars.extend([
            "",
            "# LangSmith Observability (optional - get free key at smith.langchain.com)",
            "# Traces appear automatically when API key is set",
            "LANGSMITH_TRACING=true",
            "LANGSMITH_API_KEY=lsv2_pt_your-langsmith-key-here",
            f"LANGSMITH_PROJECT={langsmith_project}",
        ])

        # Remove duplicates while preserving order
        seen = set()
        unique_vars = []
        for var in env_vars:
            if var not in seen:
                seen.add(var)
                unique_vars.append(var)

        return "\n".join(unique_vars)

    @staticmethod
    def generate_main() -> str:
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
            import os
            from dotenv import load_dotenv

            from workflow.graph import create_workflow

            # Load environment variables
            load_dotenv()

            # Enable LangSmith tracing if configured
            # LangChain/LangGraph automatically traces when these env vars are set
            if os.getenv("LANGSMITH_API_KEY"):
                os.environ.setdefault("LANGSMITH_TRACING", "true")
                project = os.getenv("LANGSMITH_PROJECT", "default")
                print(f"🔍 LangSmith tracing enabled (project: {project})")
                print("   View traces at: https://smith.langchain.com")

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

    @staticmethod
    def generate_workflow_init() -> str:
        """Generate workflow/__init__.py."""
        return dedent('''
            """Workflow package - contains graph definition and node implementations."""
            from .graph import create_workflow
            from .state import WorkflowState

            __all__ = ["create_workflow", "WorkflowState"]
        ''').strip()

    @staticmethod
    def generate_state_module() -> str:
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

                # Runtime configuration (API keys, model overrides, etc.)
                runtime_config: Optional[Dict[str, Any]] = None

                # HITL
                approval_status: Optional[str] = None
                approval_route: Optional[str] = None
        ''').strip()

    @staticmethod
    def generate_graph_module(
        nodes: List[Dict],
        edges: List[Dict],
        sanitize_name_func
    ) -> str:
        """
        Generate workflow/graph.py with StateGraph definition.

        Handles workflows with or without explicit START_NODE/END_NODE.
        """
        # Filter out START_NODE and END_NODE
        executable_nodes = []
        start_node_ids = set()
        end_node_ids = set()

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            agent_type = node_data.get("agentType", "").upper()

            if agent_type == "START_NODE":
                start_node_ids.add(node_id)
            elif agent_type == "END_NODE":
                end_node_ids.add(node_id)
            else:
                executable_nodes.append(node)

        # Build node additions
        node_additions = []
        for node in executable_nodes:
            node_id = node.get("id", "unknown")
            safe_id = sanitize_name_func(node_id)
            node_additions.append(f'graph.add_node("{node_id}", execute_{safe_id})')

        # Build edge additions and track connections
        edge_additions = []
        nodes_with_incoming = set()
        nodes_connecting_to_end = set()

        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")

            if not source or not target:
                continue

            # Skip edges FROM START_NODE
            if source in start_node_ids:
                nodes_with_incoming.add(target)
                continue

            # Edge TO END_NODE
            if target in end_node_ids:
                nodes_connecting_to_end.add(source)
                continue

            # Normal edge between executable nodes
            edge_additions.append(f'graph.add_edge("{source}", "{target}")')
            nodes_with_incoming.add(target)

        # Determine entry point
        entry_node = None

        if start_node_ids:
            for edge in edges:
                if edge.get("source") in start_node_ids:
                    target = edge.get("target")
                    if target and target not in end_node_ids:
                        entry_node = target
                        break

        if not entry_node:
            executable_node_ids = {n.get("id") for n in executable_nodes}
            for node in executable_nodes:
                nid = node.get("id")
                has_incoming_from_executable = any(
                    e.get("target") == nid and e.get("source") in executable_node_ids
                    for e in edges
                )
                if not has_incoming_from_executable:
                    entry_node = nid
                    break

        if not entry_node and executable_nodes:
            entry_node = executable_nodes[0].get("id")

        # Determine terminal nodes
        terminal_nodes = set(nodes_connecting_to_end)
        executable_node_ids = {n.get("id") for n in executable_nodes}

        for node in executable_nodes:
            nid = node.get("id")
            has_outgoing_to_executable = any(
                e.get("source") == nid and e.get("target") in executable_node_ids
                for e in edges
            )
            if not has_outgoing_to_executable and nid not in nodes_connecting_to_end:
                terminal_nodes.add(nid)

        if not terminal_nodes and executable_nodes:
            terminal_nodes = {executable_nodes[-1].get("id")}

        # Add END edges for terminal nodes
        for terminal_node in terminal_nodes:
            edge_additions.append(f'graph.add_edge("{terminal_node}", END)')

        # Import node functions
        node_imports = []
        for node in executable_nodes:
            node_id = node.get("id", "unknown")
            safe_id = sanitize_name_func(node_id)
            node_imports.append(f"execute_{safe_id}")

        imports_str = ", ".join(node_imports) if node_imports else "pass"

        # Join with proper indentation
        nodes_str = "\n    ".join(node_additions) if node_additions else "# No nodes"
        edges_str = "\n    ".join(edge_additions) if edge_additions else "# No edges"

        start_edge = f'graph.add_edge(START, "{entry_node}")' if entry_node else "# No entry node found"

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

    @staticmethod
    def generate_agents_init() -> str:
        """Generate agents/__init__.py."""
        return dedent('''
            """Agents package - agent factory functions."""
            from .factory import create_node_agent, create_deepagent

            __all__ = ["create_node_agent", "create_deepagent"]
        ''').strip()

    @staticmethod
    def generate_agents_module() -> str:
        """Generate agents/factory.py with agent creation functions."""
        return dedent('''
            """Agent factory for creating LangChain agents."""

            import logging
            from typing import List, Optional

            from langchain.agents import create_agent
            from langchain_core.tools import BaseTool

            logger = logging.getLogger(__name__)


            def create_node_agent(
                llm,
                tools: Optional[List[BaseTool]] = None,
                system_prompt: str = "You are a helpful assistant."
            ):
                """
                Create a LangGraph agent for a workflow node.

                Args:
                    llm: Language model instance
                    tools: List of tools available to the agent
                    system_prompt: System prompt for the agent

                Returns:
                    Configured agent
                """
                return create_agent(
                    model=llm,
                    tools=tools or [],
                    system_prompt=system_prompt
                )


            def create_deepagent(
                model: str = "gpt-4o",
                system_prompt: str = "You are a helpful assistant.",
                **kwargs
            ):
                """
                Create a DeepAgent for complex autonomous tasks.

                Args:
                    model: Model name to use (string like "gpt-4o" or "claude-sonnet-4-20250514")
                    system_prompt: System prompt for the agent
                    **kwargs: Additional configuration

                Returns:
                    Configured DeepAgent
                """
                try:
                    from langchain.chat_models import init_chat_model
                    from deepagents import create_deep_agent

                    # Create model instance from string
                    model_instance = init_chat_model(model)

                    return create_deep_agent(
                        model=model_instance,
                        system_prompt=system_prompt,
                        **kwargs
                    )
                except ImportError as e:
                    logger.warning(f"DeepAgents import error: {e}. Install with: pip install deepagents")
                    raise
        ''').strip()

    @staticmethod
    def generate_settings_module() -> str:
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

                # LangSmith Observability (optional)
                LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
                LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
                LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "exported-workflow")

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

                @classmethod
                def langsmith_enabled(cls) -> bool:
                    """Check if LangSmith tracing is enabled."""
                    return bool(cls.LANGSMITH_API_KEY) and cls.LANGSMITH_TRACING


            settings = Settings()
        ''').strip()
