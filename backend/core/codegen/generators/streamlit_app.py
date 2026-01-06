# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Streamlit app generator for the Executable Workflow Exporter.

Generates a complete Streamlit UI for running exported workflows with:
- Agent sections with thinking display
- Tool call cards with status indicators
- Structured output blocks
- File operation cards
- Execution metrics and history
"""

from textwrap import dedent
from typing import Any, Dict, List


class StreamlitAppGenerator:
    """Generator for Streamlit app UI."""

    @staticmethod
    def generate_streamlit_app(
        workflow_name: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> str:
        """
        Generate streamlit_app.py with visual UI.

        Args:
            workflow_name: Name of the workflow
            nodes: List of node configurations
            edges: List of edge configurations

        Returns:
            Complete streamlit_app.py content
        """
        # Build node info for display
        node_names = []
        for node in nodes:
            node_data = node.get("data", {})
            name = node_data.get("name") or node_data.get("label") or node.get("id", "Node")
            node_names.append(name)

        nodes_display = ", ".join(node_names[:5])
        if len(node_names) > 5:
            nodes_display += f", ... (+{len(node_names) - 5} more)"

        node_count = len(nodes)
        edge_count = len(edges)

        # Build the template without f-string to avoid escaping issues
        # Then format only the specific values we need
        template = '''#!/usr/bin/env python3
"""
Streamlit UI for WORKFLOW_NAME

Features:
- Real-time agent thinking display
- Tool call cards with status indicators
- Structured output with markdown rendering
- Execution metrics and history

Run with: streamlit run streamlit_app.py
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv

from workflow.graph import create_workflow
from workflow.state import WorkflowState

# Load environment variables from .env file (as fallback)
load_dotenv()


# ============================================================
# Page Config and Styling
# ============================================================

st.set_page_config(
    page_title="WORKFLOW_NAME",
    page_icon="🔷",
    layout="wide"
)

# Custom CSS for enhanced UI
st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0e1117;
    }

    /* Agent section container */
    .agent-section {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
        border: 1px solid #2d3548;
    }

    .agent-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .agent-name {
        font-weight: 600;
        font-size: 16px;
        color: #ffffff;
    }

    .status-badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
    }

    .status-running {
        background-color: #f59e0b;
        color: #000;
    }

    .status-completed {
        background-color: #10b981;
        color: #fff;
    }

    .status-error {
        background-color: #ef4444;
        color: #fff;
    }

    /* Thinking block */
    .thinking-block {
        background-color: rgba(31, 119, 180, 0.1);
        border-left: 3px solid #1f77b4;
        border-radius: 6px;
        padding: 12px 16px;
        margin: 8px 0;
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 14px;
        line-height: 1.6;
        color: #e0e0e0;
        white-space: pre-wrap;
        max-height: 300px;
        overflow-y: auto;
    }

    /* Tool call card */
    .tool-card {
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        border: 2px solid;
    }

    .tool-card-running {
        border-color: #f59e0b;
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
    }

    .tool-card-completed {
        border-color: #10b981;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
    }

    .tool-card-error {
        border-color: #ef4444;
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(239, 68, 68, 0.05) 100%);
    }

    .tool-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }

    .tool-name {
        font-weight: 600;
        font-size: 13px;
        color: #ffffff;
        font-family: monospace;
    }

    .tool-content {
        background-color: rgba(0,0,0,0.2);
        border-radius: 4px;
        padding: 8px;
        font-family: monospace;
        font-size: 12px;
        color: #a0a0a0;
        max-height: 150px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* File created card */
    .file-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        border-radius: 8px;
        background-color: rgba(16, 185, 129, 0.1);
        border: 2px solid rgba(16, 185, 129, 0.3);
        margin: 8px 0;
    }

    .file-icon {
        font-size: 24px;
    }

    .file-info {
        flex: 1;
    }

    .file-name {
        font-weight: 600;
        color: #ffffff;
        font-size: 14px;
    }

    .file-meta {
        color: #a0a0a0;
        font-size: 12px;
    }

    /* Output block */
    .output-block {
        background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1a 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 16px 0;
        border: 1px solid #2d3548;
    }

    .output-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }

    .output-title {
        font-weight: 600;
        font-size: 16px;
        color: #ffffff;
    }

    /* Run button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        border: none !important;
        font-weight: 600 !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    }

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #1a1a2e;
    }

    ::-webkit-scrollbar-thumb {
        background: #4a5568;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #718096;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Data Classes for Tracking
# ============================================================

@dataclass
class ToolCall:
    """Represents a tool call during execution."""
    name: str
    status: str  # "running", "completed", "error"
    input_data: str = ""
    result: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_ms(self) -> int:
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0


@dataclass
class AgentStep:
    """Represents an agent's execution step."""
    name: str
    node_id: str
    status: str  # "running", "completed", "error"
    thinking: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


# ============================================================
# Session State Initialization
# ============================================================

def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "messages": [],
        "execution_history": [],
        "is_running": False,
        "current_agent": None,
        "agent_steps": [],
        "show_copy_area": False,
        "last_result": "",
        "total_tokens": 0,
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_api_keys():
    """Apply API keys to environment variables."""
    if st.session_state.openai_api_key:
        os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
    if st.session_state.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = st.session_state.anthropic_api_key
    if st.session_state.google_api_key:
        os.environ["GOOGLE_API_KEY"] = st.session_state.google_api_key


# ============================================================
# UI Helper Functions
# ============================================================

def get_file_icon(filename: str) -> str:
    """Get emoji icon for file type."""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    icons = {
        "md": "📝", "txt": "📄", "py": "🐍", "js": "💛", "ts": "💙",
        "tsx": "⚛️", "jsx": "⚛️", "json": "📋", "html": "🌐", "css": "🎨",
        "sql": "🗃️", "yaml": "⚙️", "yml": "⚙️", "xml": "📰", "sh": "💻",
        "csv": "📊", "pdf": "📕", "png": "🖼️", "jpg": "🖼️", "gif": "🖼️"
    }
    return icons.get(ext, "📄")


def render_tool_card(tool: ToolCall, container):
    """Render a tool call card."""
    status_class = "tool-card-" + tool.status
    status_icons = {"running": "🔄", "completed": "✅", "error": "❌"}
    status_texts = {"running": "Running", "completed": "Done", "error": "Failed"}
    status_icon = status_icons.get(tool.status, "⏳")
    status_text = status_texts.get(tool.status, "Pending")

    # Check if it's a file write operation
    file_ops = ["write_file", "edit_file", "file_write", "create_file"]
    is_file_op = tool.name.lower() in file_ops

    if is_file_op and tool.status == "completed":
        # Render file card
        try:
            input_data = json.loads(tool.input_data) if isinstance(tool.input_data, str) else tool.input_data
            filename = input_data.get("file_path", input_data.get("path", input_data.get("filename", "file")))
            display_name = filename.split("/")[-1].split("\\\\")[-1]
            char_match = re.search(r'(\\d+)\\s*characters', tool.result or "")
            char_count = char_match.group(1) if char_match else None
        except:
            display_name = "file"
            char_count = None

        file_icon = get_file_icon(display_name)
        char_info = f"{int(char_count):,} characters written" if char_count else "File created successfully"
        container.markdown(f"""
            <div class="file-card">
                <div class="file-icon">{file_icon}</div>
                <div class="file-info">
                    <div class="file-name">{display_name}</div>
                    <div class="file-meta">{char_info}</div>
                </div>
                <div>✅</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Render standard tool card
        duration_html = f'<span style="color:#888;font-size:11px">{tool.duration_ms}ms</span>' if tool.duration_ms else ''
        container.markdown(f"""
            <div class="tool-card {status_class}">
                <div class="tool-header">
                    <span>{status_icon}</span>
                    <span class="tool-name">{tool.name}</span>
                    <span class="status-badge status-{tool.status}">{status_text}</span>
                    {duration_html}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Show input (truncated)
        if tool.input_data:
            input_preview = tool.input_data[:300] + "..." if len(tool.input_data) > 300 else tool.input_data
            with container.expander("Input", expanded=False):
                st.code(input_preview, language="json")

        # Show result
        if tool.result and tool.status != "running":
            result_preview = tool.result[:500] + "..." if len(tool.result) > 500 else tool.result
            with container.expander("Result", expanded=(tool.status == "error")):
                st.code(result_preview, language="text")


def render_agent_section(step: AgentStep, container):
    """Render an agent section with thinking and tools."""
    status_icons = {"running": "🔄", "completed": "✅", "error": "❌"}
    status_icon = status_icons.get(step.status, "⏳")

    container.markdown(f"""
        <div class="agent-section">
            <div class="agent-header">
                <span style="font-size:20px">🤖</span>
                <span class="agent-name">{step.name}</span>
                <span class="status-badge status-{step.status}">{status_icon} {step.status.title()}</span>
            </div>
    """, unsafe_allow_html=True)

    # Thinking block
    if step.thinking:
        container.markdown(f"""
            <div style="margin-bottom:8px;font-size:12px;color:#888">💭 Thinking</div>
            <div class="thinking-block">{step.thinking}</div>
        """, unsafe_allow_html=True)

    # Tool calls
    for tool in step.tool_calls:
        render_tool_card(tool, container)

    container.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Workflow Execution
# ============================================================

async def run_workflow_streaming(query: str, status_container, agents_container, output_container):
    """Run the workflow with streaming updates."""
    st.session_state.is_running = True
    st.session_state.agent_steps = []
    st.session_state.total_tokens = 0

    current_step: Optional[AgentStep] = None
    current_tool: Optional[ToolCall] = None
    final_result = ""
    streaming_text = ""

    # Skip internal LangGraph nodes
    skip_names = {"RunnableSequence", "ChannelRead", "ChannelWrite", "RunnableLambda",
                  "RunnableParallel", "StateGraph", "CompiledStateGraph", ""}

    try:
        graph = create_workflow()

        initial_state = {
            "messages": [],
            "query": query,
            "step_history": [],
        }

        start_time = time.time()
        status_container.info("🚀 Starting workflow execution...")

        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event", "")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            # Agent/chain start
            if event_type == "on_chain_start":
                if event_name and event_name not in skip_names:
                    # Complete previous step
                    if current_step:
                        current_step.status = "completed"
                        current_step.end_time = time.time()

                    # Create new step
                    current_step = AgentStep(
                        name=event_name,
                        node_id=event_name,
                        status="running",
                        start_time=time.time()
                    )
                    st.session_state.agent_steps.append(current_step)

                    # Re-render agents
                    with agents_container:
                        for step in st.session_state.agent_steps:
                            render_agent_section(step, st)

            # Tool start
            elif event_type == "on_tool_start":
                tool_name = event_data.get("name", "tool")
                tool_input = event_data.get("input", {})
                if isinstance(tool_input, dict):
                    tool_input = json.dumps(tool_input, indent=2)

                current_tool = ToolCall(
                    name=tool_name,
                    status="running",
                    input_data=str(tool_input),
                    start_time=time.time()
                )
                if current_step:
                    current_step.tool_calls.append(current_tool)

            # Tool end
            elif event_type == "on_tool_end":
                if current_tool:
                    current_tool.status = "completed"
                    current_tool.end_time = time.time()
                    output = event_data.get("output", "")
                    current_tool.result = str(output)[:1000] if output else ""

                # Re-render agents
                with agents_container:
                    for step in st.session_state.agent_steps:
                        render_agent_section(step, st)

            # Tool error
            elif event_type == "on_tool_error":
                if current_tool:
                    current_tool.status = "error"
                    current_tool.end_time = time.time()
                    error = event_data.get("error", "Unknown error")
                    current_tool.result = str(error)

            # Streaming tokens
            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    token = ""

                    if isinstance(content, str):
                        token = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                token += item["text"]
                            elif isinstance(item, str):
                                token += item

                    if token and current_step:
                        current_step.thinking += token
                        streaming_text += token

                        # Update display periodically
                        if len(current_step.thinking) % 50 == 0:
                            with agents_container:
                                for step in st.session_state.agent_steps:
                                    render_agent_section(step, st)

            # Chain end - capture final messages
            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict) and "messages" in output:
                    messages = output["messages"]
                    # Handle Overwrite object from deepagents/langgraph
                    if hasattr(messages, 'value'):
                        messages = messages.value
                    if messages and isinstance(messages, list) and len(messages) > 0:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content"):
                            content = last_msg.content
                            if isinstance(content, str):
                                final_result = content
                            elif isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                final_result = "".join(text_parts)

        # Complete last step
        if current_step:
            current_step.status = "completed"
            current_step.end_time = time.time()

        elapsed = time.time() - start_time
        status_container.success(f"✅ Workflow completed in {elapsed:.1f}s")

        # Render final output
        if final_result or streaming_text:
            result_text = final_result or streaming_text
            clean_text = re.sub(r'\\n{3,}', '\\n\\n', result_text).strip()
            st.session_state.last_result = clean_text

            with output_container:
                st.markdown('<div class="output-block">', unsafe_allow_html=True)
                st.markdown('<div class="output-header"><span class="output-title">📤 Final Output</span></div>', unsafe_allow_html=True)
                st.markdown(clean_text)
                st.markdown('</div>', unsafe_allow_html=True)

                # Copy functionality
                if st.button("📋 Copy Output", key="copy_output"):
                    st.code(clean_text, language=None)
                    st.caption("Click the copy icon in the top-right of the code block above")

        # Save to history
        st.session_state.execution_history.append({
            "query": query,
            "result": final_result or streaming_text,
            "elapsed": elapsed,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": len(st.session_state.agent_steps)
        })

    except Exception as e:
        if current_step:
            current_step.status = "error"
        status_container.error(f"❌ Workflow failed: {str(e)}")
        st.exception(e)

    finally:
        st.session_state.is_running = False


# ============================================================
# Main Application
# ============================================================

def main():
    """Main Streamlit application."""
    init_session_state()

    # Header
    st.markdown("# 🔷 WORKFLOW_NAME")
    st.caption("*Exported from LangConfig*")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # API Keys
        with st.expander("🔑 API Keys", expanded=False):
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

        # Workflow Info
        st.header("📊 Workflow Info")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Nodes", NODE_COUNT)
        with col2:
            st.metric("Edges", EDGE_COUNT)

        st.caption("Agents: [NODES_DISPLAY]")

        # LangSmith status
        if os.getenv("LANGSMITH_API_KEY"):
            project = os.getenv("LANGSMITH_PROJECT", "default")
            st.success(f"🔍 LangSmith: {project}")
            st.caption("[View traces](https://smith.langchain.com)")
        else:
            st.caption("💡 Add LANGSMITH_API_KEY to .env for tracing")

        st.divider()

        # Execution History
        st.header("📜 History")
        if st.session_state.execution_history:
            for run in reversed(st.session_state.execution_history[-5:]):
                with st.container():
                    st.caption(f"{run['timestamp']} • {run['elapsed']:.1f}s • {run['steps']} steps")
            if st.button("🗑️ Clear History", key="clear_history"):
                st.session_state.execution_history = []
                st.rerun()
        else:
            st.caption("No runs yet")

    # Main content
    st.header("▶️ Run Workflow")

    # Query input
    with st.form(key="workflow_form", clear_on_submit=False):
        query = st.text_area(
            "Enter your query:",
            height=100,
            placeholder="Describe what you want the workflow to do...",
            disabled=st.session_state.is_running
        )

        submitted = st.form_submit_button(
            "🚀 Run Workflow" if not st.session_state.is_running else "⏳ Running...",
            disabled=st.session_state.is_running,
            type="primary",
            use_container_width=True
        )

    # Execute workflow
    if submitted and query.strip():
        apply_api_keys()

        status_container = st.empty()
        agents_container = st.container()
        output_container = st.container()

        asyncio.run(run_workflow_streaming(
            query,
            status_container,
            agents_container,
            output_container
        ))

    # Footer
    st.divider()
    st.caption("Generated with [LangConfig](https://langconfig.com) • Powered by LangChain & LangGraph")


if __name__ == "__main__":
    main()
'''

        # Now replace the placeholders with actual values
        result = template.replace("WORKFLOW_NAME", workflow_name)
        result = result.replace("NODE_COUNT", str(node_count))
        result = result.replace("EDGE_COUNT", str(edge_count))
        result = result.replace("NODES_DISPLAY", nodes_display)

        return result

    @staticmethod
    def generate_configurable_streamlit_app(
        workflow_name: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> str:
        """
        Generate streamlit_app.py with configurable UI.

        Creates a modern Streamlit interface with:
        - Config sidebar for runtime tool/prompt configuration
        - Tool toggles to enable/disable tools
        - System prompt editor for testing
        - Temperature and max token sliders
        - Modern chat-style message display

        Args:
            workflow_name: Name of the workflow
            nodes: List of node configurations
            edges: List of edge configurations

        Returns:
            Complete streamlit_app.py content with configurable UI
        """
        # Extract tools and prompts from nodes for the config
        all_native_tools = set()
        all_custom_tools = set()
        agent_configs = []

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            node_config_top = node.get("config", {})
            node_config_nested = node_data.get("config", {})
            node_config = {**node_config_nested, **node_config_top}

            agent_type = node_data.get("agentType", "").upper()
            if agent_type in ("START_NODE", "END_NODE"):
                continue

            name = node_data.get("name") or node_data.get("label") or node_id
            system_prompt = node_config.get("system_prompt", "You are a helpful assistant.")
            model = node_config.get("model") or node_data.get("model") or "gpt-4o"
            native_tools = node_config.get("native_tools", [])
            custom_tools = node_config.get("custom_tools", [])

            all_native_tools.update(native_tools)
            all_custom_tools.update(custom_tools)

            agent_configs.append({
                "id": node_id,
                "name": name,
                "system_prompt": system_prompt,
                "model": model,
                "native_tools": native_tools,
                "custom_tools": custom_tools,
            })

        # Build tools list for the config
        tools_list = []
        tool_id = 0
        for tool in sorted(all_native_tools):
            tools_list.append({
                "id": f"native_{tool_id}",
                "name": tool,
                "type": "native",
                "enabled": True,
            })
            tool_id += 1
        for tool in sorted(all_custom_tools):
            tools_list.append({
                "id": f"custom_{tool_id}",
                "name": tool,
                "type": "custom",
                "enabled": True,
            })
            tool_id += 1

        # Serialize configs for embedding in the template
        # Convert JSON booleans (true/false/null) to Python booleans (True/False/None)
        import json
        agent_configs_json = json.dumps(agent_configs, indent=4)
        agent_configs_json = agent_configs_json.replace(": true", ": True").replace(": false", ": False").replace(": null", ": None")
        tools_list_json = json.dumps(tools_list, indent=4)
        tools_list_json = tools_list_json.replace(": true", ": True").replace(": false", ": False").replace(": null", ": None")

        node_count = len(nodes)
        edge_count = len(edges)

        template = '''#!/usr/bin/env python3
"""
Configurable Streamlit UI for WORKFLOW_NAME

Features:
- Runtime configuration of system prompt
- Tool enable/disable toggles
- Temperature and max token controls
- Modern chat-style interface
- Real-time agent thinking display

Run with: streamlit run streamlit_app.py
"""

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from workflow.graph import create_workflow
from workflow.state import WorkflowState

# Load environment variables from .env file (as fallback)
load_dotenv()


# ============================================================
# Default Configuration (from workflow export)
# ============================================================

DEFAULT_AGENT_CONFIGS = AGENT_CONFIGS_JSON

DEFAULT_TOOLS = TOOLS_LIST_JSON


# ============================================================
# Page Config and Modern Styling
# ============================================================

st.set_page_config(
    page_title="WORKFLOW_NAME",
    page_icon="🔷",
    layout="wide"
)

# Modern CSS inspired by astra-agent-interface (Light Theme)
st.markdown("""
<style>
    /* CSS Variables for theming - Light Theme */
    :root {
        --primary: #3b82f6;
        --primary-hover: #2563eb;
        --bg-main: #ffffff;
        --bg-sidebar: #f8fafc;
        --bg-card: #ffffff;
        --border-color: #e2e8f0;
        --text-primary: #1e293b;
        --text-secondary: #475569;
        --text-muted: #94a3b8;
        --success: #10b981;
        --warning: #f59e0b;
        --error: #ef4444;
    }

    /* Main container */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 100%;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: var(--bg-sidebar);
        border-right: 1px solid var(--border-color);
    }

    [data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--text-primary);
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Config section styling */
    .config-section {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
    }

    .config-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-color);
    }

    .config-title {
        font-weight: 600;
        font-size: 14px;
        color: var(--text-primary);
    }

    /* Tool toggle styling */
    .tool-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 12px;
        background: var(--bg-sidebar);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        margin: 6px 0;
    }

    .tool-name {
        font-weight: 500;
        font-size: 13px;
        color: var(--text-primary);
    }

    .tool-type {
        font-size: 11px;
        color: var(--text-muted);
    }

    /* Message styling */
    .user-message {
        background: var(--primary);
        color: white;
        padding: 14px 18px;
        border-radius: 16px 16px 4px 16px;
        margin: 8px 0;
        max-width: 80%;
        margin-left: auto;
    }

    .assistant-message {
        background: var(--bg-sidebar);
        border: 1px solid var(--border-color);
        color: var(--text-primary);
        padding: 16px 20px;
        border-radius: 16px 16px 16px 4px;
        margin: 8px 0;
        max-width: 90%;
    }

    /* Thinking block */
    .thinking-block {
        background: rgba(59, 130, 246, 0.05);
        border-left: 3px solid var(--primary);
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 8px 0;
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 13px;
        line-height: 1.6;
        color: var(--text-secondary);
    }

    .thinking-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: rgba(59, 130, 246, 0.05);
        border: 1px solid rgba(59, 130, 246, 0.15);
        border-radius: 8px;
        cursor: pointer;
        margin-bottom: 8px;
    }

    .thinking-header:hover {
        background: rgba(59, 130, 246, 0.1);
    }

    .pulse-dot {
        width: 8px;
        height: 8px;
        background: var(--primary);
        border-radius: 50%;
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.2); }
    }

    /* Streaming output */
    .streaming-output {
        font-family: inherit;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* Tool call cards */
    .tool-card {
        background: var(--bg-card);
        border: 2px solid var(--border-color);
        border-radius: 10px;
        padding: 12px 14px;
        margin: 8px 0;
    }

    .tool-card.running {
        border-color: var(--warning);
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.03) 100%);
    }

    .tool-card.completed {
        border-color: var(--success);
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.03) 100%);
    }

    .tool-card.error {
        border-color: var(--error);
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.03) 100%);
    }

    /* Agent section */
    .agent-section {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
    }

    .agent-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
    }

    .agent-avatar {
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
    }

    .agent-name {
        font-weight: 600;
        font-size: 15px;
        color: var(--text-primary);
    }

    .status-badge {
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 500;
    }

    .status-running {
        background: var(--warning);
        color: #000;
    }

    .status-completed {
        background: var(--success);
        color: #fff;
    }

    .status-error {
        background: var(--error);
        color: #fff;
    }

    /* Output block */
    .output-block {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        margin: 16px 0;
    }

    .output-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-color);
    }

    .output-title {
        font-weight: 600;
        font-size: 16px;
        color: var(--text-primary);
    }

    /* Primary button */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-hover) 100%) !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 12px 24px !important;
        border-radius: 10px !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, var(--primary-hover) 0%, #1d4ed8 100%) !important;
    }

    /* Custom scrollbar - Light Theme */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #f1f5f9;
    }

    ::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }

    /* Input styling - Light Theme */
    .stTextArea textarea {
        background: #ffffff !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
    }

    .stTextArea textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Data Classes for Tracking
# ============================================================

@dataclass
class ToolCall:
    """Represents a tool call during execution."""
    name: str
    status: str  # "running", "completed", "error"
    input_data: str = ""
    result: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_ms(self) -> int:
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time) * 1000)
        return 0


@dataclass
class AgentStep:
    """Represents an agent's execution step."""
    name: str
    node_id: str
    status: str  # "running", "completed", "error"
    thinking: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


# ============================================================
# Session State Initialization
# ============================================================

def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "messages": [],
        "execution_history": [],
        "is_running": False,
        "current_agent": None,
        "agent_steps": [],
        "last_result": "",
        "total_tokens": 0,
        # API Keys
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
        # Model selection
        "selected_model": "gpt-5.2",
        # Mode selection (chat vs task)
        "app_mode": "task",  # "chat" or "task"
        # Chat mode state
        "chat_messages": [],
        # Chat history management
        "chat_histories": [],  # List of saved chat sessions
        "current_chat_id": None,  # ID of current chat session
        "chat_counter": 0,  # Counter for generating unique chat IDs
        # Task history viewing
        "viewing_task_history": False,
        "selected_task_idx": None,
        # Configuration
        "agent_configs": DEFAULT_AGENT_CONFIGS.copy(),
        "tools": DEFAULT_TOOLS.copy(),
        "temperature": 0.7,
        "max_tokens": 4096,
        "max_tool_iterations": 6,  # Max rounds of tool calls before forcing response
        # Control node settings
        "control_nodes": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Load persisted history and config on first run
    if "history_loaded" not in st.session_state:
        st.session_state.history_loaded = True
        load_history_from_file()
        load_config_from_file()


def apply_api_keys():
    """Apply API keys to environment variables."""
    if st.session_state.openai_api_key:
        os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
    if st.session_state.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = st.session_state.anthropic_api_key
    if st.session_state.google_api_key:
        os.environ["GOOGLE_API_KEY"] = st.session_state.google_api_key


def get_enabled_tools() -> List[str]:
    """Get list of currently enabled tool names."""
    return [t["name"] for t in st.session_state.tools if t.get("enabled", True)]


def get_current_system_prompt() -> str:
    """Get the current system prompt (from first agent config)."""
    if st.session_state.agent_configs:
        return st.session_state.agent_configs[0].get("system_prompt", "You are a helpful assistant.")
    return "You are a helpful assistant."


# ============================================================
# Chat History Management (with file persistence)
# ============================================================

HISTORY_FILE = ".workflow_history.json"
CONFIG_FILE = ".workflow_config.json"


def load_history_from_file():
    """Load chat and task history from file."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state.chat_histories = data.get("chat_histories", [])
                st.session_state.execution_history = data.get("execution_history", [])
                st.session_state.chat_counter = data.get("chat_counter", 0)
    except Exception as e:
        print(f"Warning: Could not load history: {e}")


def save_history_to_file():
    """Save chat and task history to file."""
    try:
        data = {
            "chat_histories": st.session_state.chat_histories,
            "execution_history": st.session_state.execution_history,
            "chat_counter": st.session_state.chat_counter,
        }
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save history: {e}")


def load_config_from_file():
    """Load agent and app configuration from file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Load agent configs
                if "agent_configs" in data:
                    st.session_state.agent_configs = data["agent_configs"]
                # Load tool settings
                if "tools" in data:
                    st.session_state.tools = data["tools"]
                # Load model settings
                if "selected_model" in data:
                    st.session_state.selected_model = data["selected_model"]
                if "temperature" in data:
                    st.session_state.temperature = data["temperature"]
                if "max_tokens" in data:
                    st.session_state.max_tokens = data["max_tokens"]
                if "max_tool_iterations" in data:
                    st.session_state.max_tool_iterations = data["max_tool_iterations"]
    except Exception as e:
        print(f"Warning: Could not load config: {e}")


def save_config_to_file():
    """Save agent and app configuration to file."""
    try:
        data = {
            "agent_configs": st.session_state.agent_configs,
            "tools": st.session_state.tools,
            "selected_model": st.session_state.selected_model,
            "temperature": st.session_state.temperature,
            "max_tokens": st.session_state.max_tokens,
            "max_tool_iterations": st.session_state.max_tool_iterations,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save config: {e}")


def save_current_chat():
    """Save the current chat to history."""
    if not st.session_state.chat_messages:
        return  # Don't save empty chats

    # Generate title from first user message
    first_msg = next((m["content"] for m in st.session_state.chat_messages if m["role"] == "user"), "New Chat")
    title = first_msg[:50] + "..." if len(first_msg) > 50 else first_msg

    chat_data = {
        "id": st.session_state.chat_counter,
        "title": title,
        "messages": st.session_state.chat_messages.copy(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model": st.session_state.selected_model,
    }

    # Update existing or add new
    existing_idx = next((i for i, c in enumerate(st.session_state.chat_histories)
                        if c["id"] == st.session_state.current_chat_id), None)

    if existing_idx is not None:
        st.session_state.chat_histories[existing_idx] = chat_data
    else:
        st.session_state.chat_histories.insert(0, chat_data)
        st.session_state.current_chat_id = chat_data["id"]
        st.session_state.chat_counter += 1

    # Keep only last 20 chats
    st.session_state.chat_histories = st.session_state.chat_histories[:20]

    # Persist to file
    save_history_to_file()


def save_task_history():
    """Save task execution history to file."""
    save_history_to_file()


def load_chat(chat_id: int):
    """Load a chat from history."""
    chat = next((c for c in st.session_state.chat_histories if c["id"] == chat_id), None)
    if chat:
        st.session_state.chat_messages = chat["messages"].copy()
        st.session_state.current_chat_id = chat_id


def new_chat():
    """Start a new chat, saving current one first."""
    save_current_chat()
    st.session_state.chat_messages = []
    st.session_state.current_chat_id = None


def delete_chat(chat_id: int):
    """Delete a chat from history."""
    st.session_state.chat_histories = [c for c in st.session_state.chat_histories if c["id"] != chat_id]
    if st.session_state.current_chat_id == chat_id:
        st.session_state.chat_messages = []
        st.session_state.current_chat_id = None
    # Persist deletion
    save_history_to_file()


def get_task_run_details(idx: int) -> Optional[Dict]:
    """Get details of a specific task run."""
    if 0 <= idx < len(st.session_state.execution_history):
        return st.session_state.execution_history[idx]
    return None


# Available models for selection
AVAILABLE_MODELS = {
    "claude-opus-4-5": {"provider": "anthropic", "api_key_env": "ANTHROPIC_API_KEY", "display": "Claude Opus 4.5"},
    "claude-haiku-4-5": {"provider": "anthropic", "api_key_env": "ANTHROPIC_API_KEY", "display": "Claude Haiku 4.5"},
    "gpt-5.2": {"provider": "openai", "api_key_env": "OPENAI_API_KEY", "display": "GPT-5.2"},
    "gemini-3-pro-preview": {"provider": "google", "api_key_env": "GOOGLE_API_KEY", "display": "Gemini 3 Pro"},
}


def get_model_api_key(model_name: str) -> Optional[str]:
    """Get the API key for a model, returns None if not set."""
    model_info = AVAILABLE_MODELS.get(model_name, {})
    provider = model_info.get("provider")

    if provider == "openai":
        return st.session_state.openai_api_key or os.getenv("OPENAI_API_KEY")
    elif provider == "anthropic":
        return st.session_state.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    elif provider == "google":
        return st.session_state.google_api_key or os.getenv("GOOGLE_API_KEY")
    return None


def is_model_available(model_name: str) -> bool:
    """Check if a model's API key is configured."""
    return bool(get_model_api_key(model_name))


# ============================================================
# UI Helper Functions
# ============================================================

def render_tool_card(tool: ToolCall, container):
    """Render a tool call card."""
    status_class = tool.status
    status_icons = {"running": "🔄", "completed": "✅", "error": "❌"}
    status_texts = {"running": "Running", "completed": "Done", "error": "Failed"}
    status_icon = status_icons.get(tool.status, "⏳")
    status_text = status_texts.get(tool.status, "Pending")

    duration_html = f'<span style="color:#64748b;font-size:11px;margin-left:8px">{tool.duration_ms}ms</span>' if tool.duration_ms else ''

    container.markdown(f"""
        <div class="tool-card {status_class}">
            <div style="display:flex;align-items:center;gap:8px">
                <span>{status_icon}</span>
                <span style="font-family:monospace;font-weight:600;font-size:13px;color:#f8fafc">{tool.name}</span>
                <span class="status-badge status-{tool.status}">{status_text}</span>
                {duration_html}
            </div>
        </div>
    """, unsafe_allow_html=True)

    if tool.input_data:
        input_preview = tool.input_data[:300] + "..." if len(tool.input_data) > 300 else tool.input_data
        with container.expander("Input", expanded=False):
            st.code(input_preview, language="json")

    if tool.result and tool.status != "running":
        result_preview = tool.result[:500] + "..." if len(tool.result) > 500 else tool.result
        with container.expander("Result", expanded=(tool.status == "error")):
            st.code(result_preview, language="text")


def render_agent_section(step: AgentStep, container):
    """Render an agent section with thinking and tools."""
    status_icons = {"running": "🔄", "completed": "✅", "error": "❌"}
    status_icon = status_icons.get(step.status, "⏳")

    container.markdown(f"""
        <div class="agent-section">
            <div class="agent-header">
                <div class="agent-avatar">🤖</div>
                <span class="agent-name">{step.name}</span>
                <span class="status-badge status-{step.status}">{status_icon} {step.status.title()}</span>
            </div>
    """, unsafe_allow_html=True)

    if step.thinking:
        container.markdown(f"""
            <div class="thinking-header">
                <div class="pulse-dot"></div>
                <span style="font-size:13px;font-weight:500;color:#94a3b8">Thinking Process</span>
            </div>
            <div class="thinking-block">{step.thinking[:800]}{'...' if len(step.thinking) > 800 else ''}</div>
        """, unsafe_allow_html=True)

    for tool in step.tool_calls:
        render_tool_card(tool, container)

    container.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# Direct Chat (Chat Mode) with Streaming and Tools
# ============================================================

async def run_chat_streaming(prompt: str, response_container, tools_container) -> str:
    """Direct LLM chat with streaming output and tool support.

    Uses the first agent's config for model and system prompt,
    maintains conversation history for multi-turn chat.
    Streams tokens to the response_container as they arrive.
    Shows tool calls in tools_container.
    """
    from tools import get_tools_for_node

    try:
        # Get agent config
        agent = st.session_state.agent_configs[0] if st.session_state.agent_configs else {}
        model_name = st.session_state.selected_model or agent.get("model", "gpt-4o")
        system_prompt = agent.get("system_prompt", "You are a helpful assistant.")

        # Get API key for the model
        api_key = get_model_api_key(model_name)

        # Create model instance
        if api_key:
            model = init_chat_model(
                model_name,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens,
                api_key=api_key
            )
        else:
            model = init_chat_model(
                model_name,
                temperature=st.session_state.temperature,
                max_tokens=st.session_state.max_tokens
            )

        # Get enabled tools
        enabled_tools = get_enabled_tools()
        tools = get_tools_for_node(enabled_tools) if enabled_tools else []

        # Bind tools to model if available
        if tools:
            model = model.bind_tools(tools)

        # Build conversation history from chat_messages
        messages = [SystemMessage(content=system_prompt)]
        for m in st.session_state.chat_messages:
            if m["role"] == "user":
                messages.append(HumanMessage(content=m["content"]))
            else:
                messages.append(AIMessage(content=m["content"]))

        # Add current prompt
        messages.append(HumanMessage(content=prompt))

        # Track tool calls for display
        full_response = ""

        # If tools are bound, use ainvoke in a loop to handle multiple rounds of tool calls
        # (streaming fragments tool call args which causes validation errors)
        if tools:
            from langchain_core.messages import ToolMessage
            import traceback

            response_container.markdown("*Thinking...*")

            # Loop until we get a response without tool calls (configurable max)
            max_iterations = st.session_state.get("max_tool_iterations", 6)
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                current_response = await model.ainvoke(messages)

                # Check for tool calls in the response
                if hasattr(current_response, "tool_calls") and current_response.tool_calls:
                    tool_results = []

                    for tool_call in current_response.tool_calls:
                        # Extract tool call info - handle both dict and object formats
                        if isinstance(tool_call, dict):
                            tool_name = tool_call.get("name", "unknown")
                            tool_args = tool_call.get("args", {})
                            tool_id = tool_call.get("id", "")
                        else:
                            tool_name = getattr(tool_call, "name", "unknown")
                            tool_args = getattr(tool_call, "args", {})
                            tool_id = getattr(tool_call, "id", "")

                        # Create tool call tracker
                        tc = ToolCall(
                            name=tool_name,
                            status="running",
                            input_data=json.dumps(tool_args, indent=2) if isinstance(tool_args, dict) else str(tool_args),
                            start_time=time.time()
                        )

                        # Render tool card
                        with tools_container:
                            render_tool_card(tc, st)

                        # Find and execute the tool
                        tool_result = None
                        tool_found = False
                        for tool in tools:
                            if tool.name == tool_name:
                                tool_found = True
                                try:
                                    if hasattr(tool, 'ainvoke'):
                                        tool_result = await tool.ainvoke(tool_args)
                                    else:
                                        tool_result = tool.invoke(tool_args)
                                    tc.status = "completed"
                                    tc.result = str(tool_result)[:1000]
                                except Exception as e:
                                    tc.status = "error"
                                    tc.result = f"{str(e)}"
                                    print(f"Tool execution error: {e}")
                                    traceback.print_exc()
                                tc.end_time = time.time()
                                break

                        if not tool_found:
                            tc.status = "error"
                            tc.result = f"Tool '{tool_name}' not found"
                            tc.end_time = time.time()

                        # Re-render tool card with result
                        with tools_container:
                            render_tool_card(tc, st)

                        tool_results.append({
                            "id": tool_id,
                            "result": str(tool_result) if tool_result is not None else tc.result
                        })

                    # Add AI message and tool results to conversation
                    messages.append(current_response)
                    for tr in tool_results:
                        messages.append(ToolMessage(content=tr["result"], tool_call_id=tr["id"]))

                    # Continue loop to check if model wants more tool calls
                    response_container.markdown(f"*Processing... (round {iteration})*")

                else:
                    # No more tool calls - we have the final response
                    if hasattr(current_response, "content") and current_response.content:
                        content = current_response.content
                        if isinstance(content, str):
                            full_response = content
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    full_response += item.get("text", "")
                                elif isinstance(item, str):
                                    full_response += item
                    break

            # If we hit max iterations, force a final response
            if iteration >= max_iterations and not full_response:
                response_container.markdown("*Summarizing findings...*")
                # Ask the model to summarize what it learned from all the tool calls
                messages.append(HumanMessage(content="Please summarize your findings based on the research you've done so far. Provide a complete response now."))
                try:
                    final_response = await model.ainvoke(messages)
                    if hasattr(final_response, "content") and final_response.content:
                        content = final_response.content
                        if isinstance(content, str):
                            full_response = content
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    full_response += item.get("text", "")
                                elif isinstance(item, str):
                                    full_response += item
                except Exception as e:
                    full_response = f"*(Reached maximum tool iterations. Error getting summary: {e})*"

        else:
            # No tools - just stream directly
            async for chunk in model.astream(messages):
                if hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    if isinstance(content, str):
                        full_response += content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                full_response += item["text"]
                            elif isinstance(item, str):
                                full_response += item
                    response_container.markdown(full_response + "▌")

        # Final update without cursor
        response_container.markdown(full_response)
        return full_response

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        response_container.error(error_msg)
        return error_msg


# ============================================================
# Workflow Execution (Task Mode)
# ============================================================

async def run_workflow_streaming(query: str, status_container, agents_container, output_container):
    """Run the workflow with streaming updates."""
    st.session_state.is_running = True
    st.session_state.agent_steps = []

    current_step: Optional[AgentStep] = None
    current_tool: Optional[ToolCall] = None
    final_result = ""
    streaming_text = ""

    skip_names = {"RunnableSequence", "ChannelRead", "ChannelWrite", "RunnableLambda",
                  "RunnableParallel", "StateGraph", "CompiledStateGraph", ""}

    try:
        # Get current configuration
        enabled_tools = get_enabled_tools()
        system_prompt = get_current_system_prompt()
        temperature = st.session_state.temperature
        max_tokens = st.session_state.max_tokens

        # Create workflow with runtime config
        # Note: The workflow graph uses the configured tools/prompts
        graph = create_workflow()

        initial_state = {
            "messages": [],
            "query": query,
            "step_history": [],
            # Pass runtime config through state
            "runtime_config": {
                "model": st.session_state.selected_model,
                "enabled_tools": enabled_tools,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "control_nodes": st.session_state.control_nodes,
            }
        }

        start_time = time.time()
        status_container.info("🚀 Starting workflow execution...")

        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event", "")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            if event_type == "on_chain_start":
                if event_name and event_name not in skip_names:
                    if current_step:
                        current_step.status = "completed"
                        current_step.end_time = time.time()

                    current_step = AgentStep(
                        name=event_name,
                        node_id=event_name,
                        status="running",
                        start_time=time.time()
                    )
                    st.session_state.agent_steps.append(current_step)

                    with agents_container:
                        for step in st.session_state.agent_steps:
                            render_agent_section(step, st)

            elif event_type == "on_tool_start":
                tool_name = event_data.get("name", "tool")
                tool_input = event_data.get("input", {})
                if isinstance(tool_input, dict):
                    tool_input = json.dumps(tool_input, indent=2)

                current_tool = ToolCall(
                    name=tool_name,
                    status="running",
                    input_data=str(tool_input),
                    start_time=time.time()
                )
                if current_step:
                    current_step.tool_calls.append(current_tool)

                # Show tool card immediately in output stream
                with output_container:
                    render_tool_card(current_tool, st)

            elif event_type == "on_tool_end":
                if current_tool:
                    current_tool.status = "completed"
                    current_tool.end_time = time.time()
                    output = event_data.get("output", "")
                    current_tool.result = str(output)[:1000] if output else ""

                    # Update tool card with result
                    with output_container:
                        render_tool_card(current_tool, st)

                # Also update agent sections
                with agents_container:
                    for step in st.session_state.agent_steps:
                        render_agent_section(step, st)

            elif event_type == "on_tool_error":
                if current_tool:
                    current_tool.status = "error"
                    current_tool.end_time = time.time()
                    error = event_data.get("error", "Unknown error")
                    current_tool.result = str(error)

                    # Show error in output
                    with output_container:
                        render_tool_card(current_tool, st)

            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    token = ""

                    if isinstance(content, str):
                        token = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                token += item["text"]
                            elif isinstance(item, str):
                                token += item

                    if token:
                        streaming_text += token
                        if current_step:
                            current_step.thinking += token

                        # Update output container with streaming text (real-time)
                        with output_container:
                            st.markdown(f"""
                                <div class="streaming-output">{streaming_text}</div>
                            """, unsafe_allow_html=True)

                        # Update agent sections less frequently to avoid flicker
                        if len(streaming_text) % 100 == 0:
                            with agents_container:
                                for step in st.session_state.agent_steps:
                                    render_agent_section(step, st)

            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict) and "messages" in output:
                    messages = output["messages"]
                    if hasattr(messages, 'value'):
                        messages = messages.value
                    if messages and isinstance(messages, list) and len(messages) > 0:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content"):
                            content = last_msg.content
                            if isinstance(content, str):
                                final_result = content
                            elif isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                final_result = "".join(text_parts)

        if current_step:
            current_step.status = "completed"
            current_step.end_time = time.time()

        elapsed = time.time() - start_time
        status_container.success(f"✅ Workflow completed in {elapsed:.1f}s")

        if final_result or streaming_text:
            result_text = final_result or streaming_text
            clean_text = re.sub(r'\\n{3,}', '\\n\\n', result_text).strip()
            st.session_state.last_result = clean_text

            with output_container:
                st.markdown('<div class="output-block">', unsafe_allow_html=True)
                st.markdown('<div class="output-header"><span class="output-title">📤 Final Output</span></div>', unsafe_allow_html=True)
                st.markdown(clean_text)
                st.markdown('</div>', unsafe_allow_html=True)

                if st.button("📋 Copy Output", key="copy_output"):
                    st.code(clean_text, language=None)

        st.session_state.execution_history.append({
            "query": query,
            "result": final_result or streaming_text,
            "elapsed": elapsed,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "steps": len(st.session_state.agent_steps),
            "enabled_tools": enabled_tools,
        })

        # Persist task history to file
        save_task_history()

    except Exception as e:
        if current_step:
            current_step.status = "error"
        status_container.error(f"❌ Workflow failed: {str(e)}")
        st.exception(e)

    finally:
        st.session_state.is_running = False


# ============================================================
# Main Application
# ============================================================

def main():
    \"\"\"Main Streamlit application with config panel on the right (astra UI style).\"\"\"
    # Note: st.set_page_config is already called at the top of the file
    init_session_state()

    # Header
    st.markdown("# 🔷 WORKFLOW_NAME")
    st.caption("*Configurable Workflow • Exported from LangConfig*")

    # Two-column layout: Chat (left, wider) | Config (right, narrower)
    chat_col, config_col = st.columns([3, 1])

    # ========== LEFT COLUMN: CHAT/TASK AREA ==========
    with chat_col:
        model_display = AVAILABLE_MODELS.get(st.session_state.selected_model, {}).get("display", st.session_state.selected_model)
        enabled_count = len([t for t in st.session_state.tools if t.get("enabled")])

        if is_model_available(st.session_state.selected_model):
            st.info(f"🤖 {model_display} • 🔧 {enabled_count} tools • 🌡️ {st.session_state.temperature}")
        else:
            st.warning(f"🔒 {model_display} requires API key • Enter in config panel →")

        if st.session_state.app_mode == "chat":
            # Chat header with New Chat button
            header_col1, header_col2 = st.columns([3, 1])
            with header_col1:
                st.subheader("💬 Chat")
            with header_col2:
                if st.button("➕ New Chat", key="new_chat_btn", use_container_width=True):
                    new_chat()
                    st.rerun()

            st.caption("Direct LLM conversation without workflow overhead")

            chat_container = st.container(height=700)
            with chat_container:
                for msg in st.session_state.chat_messages:
                    with st.chat_message(msg.get("role", "user")):
                        st.markdown(msg.get("content", ""))

            if prompt := st.chat_input("Type your message...", disabled=st.session_state.is_running or not is_model_available(st.session_state.selected_model)):
                st.session_state.chat_messages.append({"role": "user", "content": prompt})
                apply_api_keys()
                st.session_state.is_running = True

                # Display user message immediately
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Create assistant message container for streaming
                    with st.chat_message("assistant"):
                        # Tools container for showing tool calls
                        tools_placeholder = st.container()
                        # Response container for streamed text
                        response_placeholder = st.empty()
                        response = asyncio.run(run_chat_streaming(prompt, response_placeholder, tools_placeholder))

                st.session_state.is_running = False
                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                # Auto-save chat after each response
                save_current_chat()
                st.rerun()

        else:
            # Task mode - check if viewing history
            if st.session_state.viewing_task_history and st.session_state.selected_task_idx is not None:
                task = get_task_run_details(st.session_state.selected_task_idx)
                if task:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader(f"📜 Task Run: {task['timestamp']}")
                    with col2:
                        if st.button("← Back", key="back_from_history"):
                            st.session_state.viewing_task_history = False
                            st.session_state.selected_task_idx = None
                            st.rerun()

                    st.markdown(f"**Query:** {task['query']}")
                    st.markdown(f"**Duration:** {task['elapsed']:.1f}s • **Steps:** {task['steps']}")

                    if task.get('enabled_tools'):
                        st.markdown(f"**Tools:** {', '.join(task['enabled_tools'])}")

                    st.divider()
                    st.markdown("**Result:**")
                    st.markdown(task.get('result', 'No result'))
                else:
                    st.session_state.viewing_task_history = False
                    st.rerun()
            else:
                st.subheader("▶️ Run Workflow")
                with st.form(key="workflow_form", clear_on_submit=False):
                    query = st.text_area("Enter your query:", height=100, placeholder="Describe what you want the workflow to do...", disabled=st.session_state.is_running or not is_model_available(st.session_state.selected_model))
                    submitted = st.form_submit_button("🚀 Run Workflow" if not st.session_state.is_running else "⏳ Running...", disabled=st.session_state.is_running or not is_model_available(st.session_state.selected_model), type="primary", use_container_width=True)
                if submitted and query.strip():
                    apply_api_keys()
                    status_container = st.empty()
                    agents_container = st.container()
                    output_container = st.container()
                    asyncio.run(run_workflow_streaming(query, status_container, agents_container, output_container))

    # ========== RIGHT COLUMN: CONFIG PANEL ==========
    with config_col:
        st.markdown("### ⚙️ Configuration")

        mode = st.radio("Mode", options=["task", "chat"], format_func=lambda x: "🎯 Task" if x == "task" else "💬 Chat", horizontal=True, key="app_mode_radio")
        st.session_state.app_mode = mode

        st.divider()
        st.markdown("**🤖 Model**")
        model_options = list(AVAILABLE_MODELS.keys())
        current_idx = model_options.index(st.session_state.selected_model) if st.session_state.selected_model in model_options else 0
        selected = st.selectbox("Model", options=model_options, index=current_idx, format_func=lambda x: f"{AVAILABLE_MODELS[x]['display']} {'✓' if is_model_available(x) else '🔒'}", key="model_selector", label_visibility="collapsed")
        st.session_state.selected_model = selected
        if not is_model_available(selected):
            st.caption(f"⚠️ Enter {AVAILABLE_MODELS.get(selected, {}).get('provider', '')} key below")

        st.divider()
        st.markdown("**📝 System Prompt**")
        if st.session_state.agent_configs:
            new_prompt = st.text_area("Prompt", value=st.session_state.agent_configs[0].get("system_prompt", ""), height=100, key="system_prompt_input", label_visibility="collapsed")
            st.session_state.agent_configs[0]["system_prompt"] = new_prompt

        st.divider()
        st.markdown("**🔧 Active Tools**")
        for i, tool in enumerate(st.session_state.tools):
            enabled = st.checkbox(tool["name"], value=tool.get("enabled", True), key=f"tool_toggle_{i}")
            st.session_state.tools[i]["enabled"] = enabled

        st.divider()
        st.markdown("**🎛️ Parameters**")
        st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.1, key="temperature")
        st.slider("Max Tokens", 256, 32768, st.session_state.max_tokens, 256, key="max_tokens")
        st.slider("Max Tool Rounds", 1, 10, st.session_state.max_tool_iterations, 1, key="max_tool_iterations", help="Maximum rounds of tool calls before forcing a response")

        st.divider()
        with st.expander("🔑 API Keys"):
            st.text_input("OpenAI", type="password", placeholder="sk-...", key="openai_api_key")
            st.text_input("Anthropic", type="password", placeholder="sk-ant-...", key="anthropic_api_key")
            st.text_input("Google", type="password", placeholder="AI...", key="google_api_key")

        st.divider()

        # ========== HISTORY SECTION ==========
        if st.session_state.app_mode == "chat":
            st.markdown("**📜 Chat History**")
            if st.session_state.chat_histories:
                for chat in st.session_state.chat_histories[:10]:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # Truncate title for display
                        display_title = chat["title"][:30] + "..." if len(chat["title"]) > 30 else chat["title"]
                        is_current = chat["id"] == st.session_state.current_chat_id
                        btn_label = f"{'→ ' if is_current else ''}{display_title}"
                        if st.button(btn_label, key=f"load_chat_{chat['id']}", use_container_width=True):
                            load_chat(chat["id"])
                            st.rerun()
                    with col2:
                        if st.button("🗑️", key=f"del_chat_{chat['id']}"):
                            delete_chat(chat["id"])
                            st.rerun()
                    st.caption(f"{chat['timestamp']} • {chat['model']}")
            else:
                st.caption("No chat history yet")
        else:
            st.markdown("**📜 Task History**")
            if st.session_state.execution_history:
                for idx, run in enumerate(reversed(st.session_state.execution_history[-10:])):
                    actual_idx = len(st.session_state.execution_history) - 1 - idx
                    query_preview = run['query'][:40] + "..." if len(run['query']) > 40 else run['query']
                    if st.button(f"📋 {query_preview}", key=f"view_task_{actual_idx}", use_container_width=True):
                        st.session_state.viewing_task_history = True
                        st.session_state.selected_task_idx = actual_idx
                        st.rerun()
                    st.caption(f"{run['timestamp']} • {run['elapsed']:.1f}s")
                if st.button("🗑️ Clear History", key="clear_task_history"):
                    st.session_state.execution_history = []
                    st.rerun()
            else:
                st.caption("No task runs yet")

        st.divider()
        if st.button("💾 Save Config", key="save_config", use_container_width=True):
            save_config_to_file()
            st.success("Config saved!")

        st.divider()
        st.caption(f"📊 Nodes: {NODE_COUNT} • Edges: {EDGE_COUNT}")


if __name__ == "__main__":
    main()
'''

        # Replace placeholders with actual values
        result = template.replace("WORKFLOW_NAME", workflow_name)
        result = result.replace("NODE_COUNT", str(node_count))
        result = result.replace("EDGE_COUNT", str(edge_count))
        result = result.replace("AGENT_CONFIGS_JSON", agent_configs_json)
        result = result.replace("TOOLS_LIST_JSON", tools_list_json)

        return result
