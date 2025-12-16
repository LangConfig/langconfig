# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Streamlit app generator for the Executable Workflow Exporter.

Generates a complete Streamlit UI for running exported workflows.
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

        return dedent(f'''
            #!/usr/bin/env python3
            """
            Streamlit UI for {workflow_name}

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
                page_title="{workflow_name}",
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
                                    "time": time.time() - start_time
                                }})
                                with output_container:
                                    st.markdown(
                                        f'<div class="node-card"><strong>▶ {{node_name}}</strong></div>',
                                        unsafe_allow_html=True
                                    )

                        # Capture streaming tokens (AI response chunks)
                        if event_type == "on_chat_model_stream":
                            chunk = event_data.get("chunk")
                            if chunk and hasattr(chunk, "content") and chunk.content:
                                streaming_text += chunk.content
                                stream_container.markdown(
                                    f'<div class="streaming-content"><span class="token-stream">{{streaming_text}}</span></div>',
                                    unsafe_allow_html=True
                                )

                        # Capture final messages when chain ends
                        if event_type == "on_chain_end":
                            output = event_data.get("output", {{}})
                            if isinstance(output, dict) and "messages" in output:
                                final_messages = output["messages"]

                    elapsed = time.time() - start_time
                    status_container.success(f"✅ Workflow completed in {{elapsed:.1f}}s")

                    # Show final result
                    with stream_container:
                        st.markdown("---")
                        st.markdown("### Final Result")

                        def extract_text_content(content):
                            if isinstance(content, str):
                                return content
                            elif isinstance(content, list):
                                text_parts = []
                                for item in content:
                                    if isinstance(item, str):
                                        text_parts.append(item)
                                    elif isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
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
                st.title("{workflow_name}")
                st.markdown("*Exported from LangConfig*")

                # Sidebar with workflow info and settings
                with st.sidebar:
                    st.header("Workflow Info")
                    st.markdown(f"""
                    - **Nodes**: {node_count}
                    - **Edges**: {edge_count}
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

                    # LangSmith status indicator
                    if os.getenv("LANGSMITH_API_KEY"):
                        project = os.getenv("LANGSMITH_PROJECT", "default")
                        st.success(f"🔍 LangSmith: {{project}}")
                        st.caption("[View traces](https://smith.langchain.com)")
                    else:
                        st.caption("💡 Add LANGSMITH_API_KEY to .env for production tracing")

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
