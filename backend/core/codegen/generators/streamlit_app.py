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

        nodes_display = ", ".join(f'"{n}"' for n in node_names[:5])
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
                    if messages:
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

        st.caption(f"Agents: [NODES_DISPLAY]")

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
