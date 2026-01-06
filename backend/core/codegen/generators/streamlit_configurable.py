# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Configurable Streamlit app generator - Mini-LangConfig UI.

Generates a full-featured Streamlit app with:
- Dynamic agent node management
- Runtime tool/middleware configuration
- Organized artifact storage
- Condensed execution output
- Model switching at runtime
"""

import json
from typing import Any, Dict, List


class ConfigurableStreamlitGenerator:
    """Generator for configurable mini-LangConfig Streamlit apps."""

    @staticmethod
    def generate(
        workflow_name: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> str:
        """
        Generate streamlit_app.py with mini-LangConfig configurable UI.

        Args:
            workflow_name: Name of the workflow
            nodes: List of node configurations
            edges: List of edge configurations

        Returns:
            Complete streamlit_app.py content
        """
        # Extract agent configs from nodes
        agent_configs = []
        all_tools = set()

        # Aggregate workflow-level settings from first agent node
        workflow_temperature = 0.7
        workflow_max_tokens = 4096
        workflow_reasoning_effort = "low"
        workflow_middleware = []
        workflow_guardrails = {}

        for node in nodes:
            node_id = node.get("id", "unknown")
            node_data = node.get("data", {})
            node_config = {
                **node_data.get("config", {}),
                **node.get("config", {})
            }

            agent_type = node_data.get("agentType", "").upper()
            if agent_type in ("START_NODE", "END_NODE"):
                continue

            name = node_data.get("name") or node_data.get("label") or node_id
            system_prompt = node_config.get("system_prompt", "You are a helpful assistant.")
            model = node_config.get("model") or node_data.get("model") or "gpt-4o"
            native_tools = node_config.get("native_tools", [])
            custom_tools = node_config.get("custom_tools", [])

            # Extract additional config fields
            temperature = node_config.get("temperature", 0.7)
            max_tokens = node_config.get("max_tokens", 4096)
            reasoning_effort = node_config.get("reasoning_effort", "low")
            modalities = node_config.get("modalities", [])
            middleware = node_config.get("middleware", [])
            guardrails = node_config.get("guardrails", {})
            use_deepagents = node_config.get("use_deepagents", False)
            subagents = node_config.get("subagents", [])

            all_tools.update(native_tools)
            all_tools.update(custom_tools)

            # Use first agent's settings as workflow defaults
            if not agent_configs:
                workflow_temperature = temperature
                workflow_max_tokens = max_tokens
                workflow_reasoning_effort = reasoning_effort
                workflow_middleware = middleware
                workflow_guardrails = guardrails

            agent_configs.append({
                "id": node_id,
                "name": name,
                "system_prompt": system_prompt,
                "model": model,
                "tools": list(native_tools) + list(custom_tools),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
                "modalities": modalities,
                "use_deepagents": use_deepagents,
            })

        # Serialize for embedding
        agent_configs_json = json.dumps(agent_configs, indent=4)
        tools_list = sorted(all_tools)

        # Build middleware config from workflow
        middleware_config = ConfigurableStreamlitGenerator._build_middleware_config(workflow_middleware)
        guardrails_config = ConfigurableStreamlitGenerator._build_guardrails_config(workflow_guardrails)

        # Build tool definitions
        tool_defs = []
        for tool in tools_list:
            desc = ConfigurableStreamlitGenerator._get_tool_description(tool)
            tool_defs.append(f'    "{tool}": {{"name": "{tool}", "description": "{desc}", "enabled": True}},')
        tools_dict_str = "{\n" + "\n".join(tool_defs) + "\n}" if tool_defs else "{}"

        template = f'''#!/usr/bin/env python3
"""
{workflow_name} - Configurable Agent Interface

Mini-LangConfig exported workflow with:
- Dynamic agent configuration
- Runtime tool toggles
- Middleware options
- Organized artifact storage

Run with: streamlit run streamlit_app.py
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

WORKFLOW_NAME = "{workflow_name}"

# Artifact storage (like canvas)
ARTIFACTS_DIR = Path("./artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)
for subdir in ["files", "images", "code", "data"]:
    (ARTIFACTS_DIR / subdir).mkdir(exist_ok=True)

# Initial agent configs from workflow
DEFAULT_AGENTS = {agent_configs_json}

# Tools with descriptions
NATIVE_TOOLS = {tools_dict_str}

# Middleware options
MIDDLEWARE = {{
    "todo_list": {{"name": "Todo List", "description": "Track tasks automatically", "enabled": True}},
    "filesystem": {{"name": "Filesystem", "description": "Auto-evict large outputs", "enabled": True}},
    "subagent": {{"name": "Subagent", "description": "Spawn child agents", "enabled": False}},
}}

MODELS = {{
    "gpt-5.2": {{"provider": "openai", "display": "GPT-5.2"}},
    "gpt-4o": {{"provider": "openai", "display": "GPT-4o"}},
    "claude-opus-4-5": {{"provider": "anthropic", "display": "Claude Opus 4.5"}},
    "claude-haiku-4-5": {{"provider": "anthropic", "display": "Claude Haiku 4.5"}},
    "gemini-3-pro-preview": {{"provider": "google", "display": "Gemini 3 Pro"}},
}}

# ============================================================
# IMPORTS - Workflow execution
# ============================================================

try:
    from workflow.graph import create_workflow
    from tools.native import NATIVE_TOOLS as TOOL_REGISTRY
    WORKFLOW_AVAILABLE = True
except ImportError as e:
    print(f"Workflow import error: {{e}}")
    WORKFLOW_AVAILABLE = False
    TOOL_REGISTRY = {{}}

# ============================================================
# STYLING
# ============================================================

def apply_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

    /* CSS Variables for theming */
    :root {{
        --bg-main: white;
        --bg-panel: #f8fafc;
        --bg-card: white;
        --text-primary: #1e293b;
        --text-secondary: #64748b;
        --border-color: #e2e8f0;
    }}

    @media (prefers-color-scheme: dark) {{
        :root {{
            --bg-main: #0f172a;
            --bg-panel: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border-color: #334155;
        }}
    }}

    .stApp {{ font-family: 'Space Grotesk', sans-serif; background: var(--bg-main) !important; }}
    #MainMenu, footer, header, .stDeployButton {{ display: none; }}
    .block-container {{ padding-top: 1.5rem; }}

    .section-title {{
        font-size: 0.7rem; font-weight: 700; color: var(--text-secondary);
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 1rem 0 0.5rem 0; padding-bottom: 0.25rem;
        border-bottom: 1px solid var(--border-color);
    }}

    .status-ready {{
        background: rgba(34, 197, 94, 0.1); color: #16a34a;
        padding: 0.25rem 0.75rem; border-radius: 100px;
        font-size: 0.75rem; display: inline-block;
    }}

    /* Condensed execution output */
    .step-row {{
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.25rem 0; font-size: 0.8rem;
        border-bottom: 1px solid var(--border-color);
    }}
    .step-icon {{ width: 20px; text-align: center; }}
    .step-name {{ flex: 1; color: var(--text-primary); }}
    .step-time {{ color: var(--text-secondary); font-size: 0.7rem; }}

    .artifact-item {{
        background: var(--bg-panel); color: var(--text-primary);
        border-radius: 4px; padding: 0.25rem 0.5rem;
        margin: 0.25rem 0; font-size: 0.75rem; font-family: monospace;
    }}
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# STATE
# ============================================================

def init_state():
    defaults = {{
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "google_api_key": os.getenv("GOOGLE_API_KEY", ""),
        "app_mode": "chat",
        "agents": [a.copy() for a in DEFAULT_AGENTS],
        "tools": {{k: v.copy() for k, v in NATIVE_TOOLS.items()}},
        "middleware": {{k: v.copy() for k, v in MIDDLEWARE.items()}},
        "temperature": {workflow_temperature},
        "max_tokens": {workflow_max_tokens},
        # Context configuration from workflow guardrails
        "context_config": {{
            "show_token_count": True,
            "auto_summarize": {guardrails_config.get('auto_summarize', True)},
            "summarize_threshold": {guardrails_config.get('summarize_threshold', 60000)},
            "max_context_tokens": {guardrails_config.get('max_context_tokens', 100000)},
        }},
        "context_tokens": 0,
        "messages": [],
        "execution_steps": [],
        "artifacts": [],
    }}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    scan_artifacts()


def scan_artifacts():
    """Refresh artifacts list."""
    arts = []
    for sub in ["files", "images", "code", "data"]:
        p = ARTIFACTS_DIR / sub
        if p.exists():
            for f in p.iterdir():
                if f.is_file():
                    arts.append({{
                        "name": f.name, "path": str(f), "category": sub,
                        "size": f.stat().st_size,
                    }})
    st.session_state.artifacts = sorted(arts, key=lambda x: x["name"])


def get_api_key(model: str) -> Optional[str]:
    """Get API key based on model name - uses pattern matching for flexibility."""
    model_lower = model.lower() if model else ""

    # Pattern match for provider
    if "gpt" in model_lower or "openai" in model_lower:
        return st.session_state.openai_api_key or os.getenv("OPENAI_API_KEY")
    elif "claude" in model_lower or "anthropic" in model_lower:
        return st.session_state.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    elif "gemini" in model_lower or "google" in model_lower:
        return st.session_state.google_api_key or os.getenv("GOOGLE_API_KEY")

    # Fallback to MODELS dict
    provider = MODELS.get(model, {{}}).get("provider")
    if provider == "openai":
        return st.session_state.openai_api_key or os.getenv("OPENAI_API_KEY")
    elif provider == "anthropic":
        return st.session_state.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    elif provider == "google":
        return st.session_state.google_api_key or os.getenv("GOOGLE_API_KEY")

    return None


def apply_api_keys():
    """Apply API keys from session state to environment variables."""
    if st.session_state.openai_api_key:
        os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
    if st.session_state.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = st.session_state.anthropic_api_key
    if st.session_state.google_api_key:
        os.environ["GOOGLE_API_KEY"] = st.session_state.google_api_key


def is_ready() -> bool:
    if not st.session_state.agents:
        return False
    return bool(get_api_key(st.session_state.agents[0].get("model", "")))


# ============================================================
# EXECUTION (Condensed Output)
# ============================================================

async def run_agent(prompt: str):
    """Execute agent with condensed step tracking."""
    if not WORKFLOW_AVAILABLE:
        return "Workflow not available - check imports"

    # Apply API keys to environment before running
    apply_api_keys()

    steps = []
    start = datetime.now()

    # Add thinking step
    steps.append({{"icon": "🔄", "name": "Processing...", "time": ""}})
    st.session_state.execution_steps = steps

    try:
        # Create the workflow graph (uses exported configuration)
        graph = create_workflow()

        # Get the appropriate API key based on current model
        current_model = st.session_state.agents[0].get("model", "") if st.session_state.agents else ""
        api_key = get_api_key(current_model)

        # Run with user message and runtime config
        result = await graph.ainvoke({{
            "messages": [],
            "query": prompt,
            "step_history": [],
            "runtime_config": {{
                "api_key": api_key,
                "model": current_model,
            }}
        }})

        # Handle Overwrite object from deepagents/langgraph
        if hasattr(result, 'value'):
            result = result.value

        elapsed = (datetime.now() - start).total_seconds()
        steps = [{{"icon": "✓", "name": "Completed", "time": f"{{elapsed:.1f}}s"}}]
        st.session_state.execution_steps = steps

        # Extract response
        if isinstance(result, dict):
            messages = result.get("messages", [])
            # Handle Overwrite object
            if hasattr(messages, 'value'):
                messages = messages.value
            if messages and isinstance(messages, list) and len(messages) > 0:
                last_msg = messages[-1]
                return last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        return str(result)

    except Exception as e:
        steps = [{{"icon": "✗", "name": f"Error: {{str(e)[:50]}}", "time": ""}}]
        st.session_state.execution_steps = steps
        return f"Error: {{e}}"


# ============================================================
# MAIN UI
# ============================================================

def main():
    st.set_page_config(page_title=WORKFLOW_NAME, layout="wide", initial_sidebar_state="collapsed")
    init_state()
    apply_css()

    chat_col, config_col = st.columns([3, 1], gap="medium")

    # ========== CHAT ==========
    with chat_col:
        st.markdown(f"## {{WORKFLOW_NAME}}")

        if is_ready():
            model = MODELS.get(st.session_state.agents[0]["model"], {{}}).get("display", "")
            st.markdown(f'<span class="status-ready">● Ready · {{model}}</span>', unsafe_allow_html=True)
        else:
            st.warning("Configure API key")

        with st.container(border=True):
            msgs = st.container(height=350)
            with msgs:
                for m in st.session_state.messages:
                    with st.chat_message(m["role"]):
                        st.write(m["content"])

            # Execution steps (condensed)
            if st.session_state.execution_steps:
                for step in st.session_state.execution_steps:
                    st.markdown(f'<div class="step-row"><span class="step-icon">{{step["icon"]}}</span><span class="step-name">{{step["name"]}}</span><span class="step-time">{{step["time"]}}</span></div>', unsafe_allow_html=True)

            if prompt := st.chat_input("Message...", disabled=not is_ready()):
                st.session_state.messages.append({{"role": "user", "content": prompt}})

                with st.spinner(""):
                    response = asyncio.run(run_agent(prompt))

                st.session_state.messages.append({{"role": "assistant", "content": response}})
                st.rerun()

        # Artifacts
        st.markdown('<div class="section-title">Artifacts</div>', unsafe_allow_html=True)
        if st.session_state.artifacts:
            for a in st.session_state.artifacts[:5]:
                st.markdown(f'<div class="artifact-item">{{a["category"]}}/{{a["name"]}}</div>', unsafe_allow_html=True)
        else:
            st.caption("No artifacts yet")
        if st.button("Refresh"):
            scan_artifacts()
            st.rerun()

    # ========== CONFIG ==========
    with config_col:
        with st.container(border=True):
            # Mode + Model (same row)
            st.markdown('<div class="section-title">Mode & Model</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.radio("Mode", ["Chat", "Task"], horizontal=True, label_visibility="collapsed")
            with c2:
                if st.session_state.agents:
                    models = list(MODELS.keys())
                    current = st.session_state.agents[0].get("model", "gpt-4o")
                    idx = models.index(current) if current in models else 0
                    st.session_state.agents[0]["model"] = st.selectbox(
                        "Model", models, idx,
                        format_func=lambda x: MODELS[x]["display"],
                        label_visibility="collapsed"
                    )

            st.divider()

            # Agents
            st.markdown('<div class="section-title">Agents</div>', unsafe_allow_html=True)
            for i, agent in enumerate(st.session_state.agents):
                with st.expander(agent["name"], expanded=(i == 0)):
                    agent["name"] = st.text_input("Name", agent["name"], key=f"an_{{i}}")
                    agent["system_prompt"] = st.text_area("Prompt", agent["system_prompt"], height=80, key=f"ap_{{i}}")
                    if len(st.session_state.agents) > 1:
                        if st.button("Remove", key=f"ar_{{i}}"):
                            st.session_state.agents.pop(i)
                            st.rerun()

            if st.button("+ Add Agent"):
                st.session_state.agents.append({{
                    "id": f"agent_{{len(st.session_state.agents)+1}}",
                    "name": f"Agent {{len(st.session_state.agents)+1}}",
                    "system_prompt": "You are helpful.",
                    "model": "gpt-4o",
                    "tools": [],
                }})
                st.rerun()

            st.divider()

            # Tools
            st.markdown('<div class="section-title">Tools</div>', unsafe_allow_html=True)
            cols = st.columns(2)
            for i, (tid, tool) in enumerate(st.session_state.tools.items()):
                with cols[i % 2]:
                    tool["enabled"] = st.checkbox(tool["name"], tool["enabled"], key=f"t_{{tid}}")

            st.divider()

            # Middleware
            st.markdown('<div class="section-title">Middleware</div>', unsafe_allow_html=True)
            for mid, mw in st.session_state.middleware.items():
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.caption(f"**{{mw['name']}}**")
                with c2:
                    mw["enabled"] = st.checkbox("", mw["enabled"], key=f"m_{{mid}}", label_visibility="collapsed")

            st.divider()

            # Params
            st.markdown('<div class="section-title">Parameters</div>', unsafe_allow_html=True)
            st.session_state.temperature = st.slider("Temp", 0.0, 1.0, st.session_state.temperature, 0.1)
            st.session_state.max_tokens = st.slider("Tokens", 256, 32768, st.session_state.max_tokens, 256)

            st.divider()

            # Context Management
            st.markdown('<div class="section-title">Context</div>', unsafe_allow_html=True)
            ctx = st.session_state.context_config
            tokens = st.session_state.context_tokens
            max_ctx = ctx["max_context_tokens"]
            pct = min(100, int((tokens / max_ctx) * 100)) if max_ctx > 0 else 0
            st.caption(f"**Context:** {{tokens:,}} / {{max_ctx:,}} tokens ({{pct}}%)")
            st.progress(pct / 100)
            ctx["auto_summarize"] = st.checkbox("Auto-summarize", ctx.get("auto_summarize", True))
            with st.expander("Token Limits"):
                ctx["summarize_threshold"] = st.slider("Summarize at", 10000, 100000, ctx["summarize_threshold"], 5000)
                ctx["max_context_tokens"] = st.slider("Max context", 50000, 200000, ctx["max_context_tokens"], 10000)
                if st.button("Clear Context"):
                    st.session_state.messages = []
                    st.session_state.context_tokens = 0
                    st.rerun()

            st.divider()

            # Keys - apply to environment on change
            with st.expander("API Keys", expanded=True):
                st.text_input("OpenAI", type="password", key="openai_api_key", on_change=apply_api_keys)
                st.text_input("Anthropic", type="password", key="anthropic_api_key", on_change=apply_api_keys)
                st.text_input("Google", type="password", key="google_api_key", on_change=apply_api_keys)

                # Show status
                if st.session_state.anthropic_api_key or st.session_state.openai_api_key or st.session_state.google_api_key:
                    st.success("✓ API key(s) configured")
                else:
                    st.warning("Enter API key to run workflow")


if __name__ == "__main__":
    main()
'''
        return template

    @staticmethod
    def _get_tool_description(tool_name: str) -> str:
        """Get description for a tool."""
        descriptions = {
            "web_search": "Search the web with DuckDuckGo",
            "web_fetch": "Fetch and parse URLs",
            "read_file": "Read from artifacts directory",
            "write_file": "Write content to artifacts (requires: file_path, content)",
            "image_generation": "Generate images with Gemini",
            "code_interpreter": "Execute Python code",
            "browser": "Browser automation",
        }
        return descriptions.get(tool_name, tool_name.replace("_", " ").title())

    @staticmethod
    def _build_middleware_config(workflow_middleware: list) -> dict:
        """Build middleware config dict from workflow middleware list."""
        # Default middleware with enabled based on workflow config
        mw_types = {"todo_list", "filesystem", "subagent"}
        enabled_types = set()

        for mw in workflow_middleware:
            if isinstance(mw, dict):
                mw_type = mw.get("type", "")
                if mw.get("enabled", True):
                    enabled_types.add(mw_type)
            elif isinstance(mw, str):
                enabled_types.add(mw)

        return {
            "todo_list": enabled_types.get("todo_list", False) if workflow_middleware else True,
            "filesystem": enabled_types.get("filesystem", False) if workflow_middleware else True,
            "subagent": enabled_types.get("subagent", False) if workflow_middleware else False,
        }

    @staticmethod
    def _build_guardrails_config(workflow_guardrails: dict) -> dict:
        """Build guardrails config from workflow guardrails."""
        defaults = {
            "auto_summarize": True,
            "summarize_threshold": 60000,
            "max_context_tokens": 100000,
            "eviction_threshold": 80000,
        }

        if not workflow_guardrails:
            return defaults

        token_limits = workflow_guardrails.get("token_limits", {})
        return {
            "auto_summarize": workflow_guardrails.get("enable_summarization", True),
            "summarize_threshold": token_limits.get("summarization_threshold", 60000),
            "max_context_tokens": token_limits.get("max_total_tokens", 100000),
            "eviction_threshold": token_limits.get("eviction_threshold", 80000),
        }
