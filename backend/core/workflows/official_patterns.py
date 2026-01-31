"""
Official LangGraph multi-agent pattern wrappers.

Wraps langgraph-supervisor and langgraph-swarm as workflow strategy types.
These integrate alongside existing custom implementations -- new strategy options, not replacements.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful imports for optional multi-agent packages
# ---------------------------------------------------------------------------

try:
    from langgraph_supervisor import create_supervisor
    SUPERVISOR_AVAILABLE = True
except ImportError:
    SUPERVISOR_AVAILABLE = False
    logger.info("langgraph-supervisor not installed. Supervisor strategy unavailable.")

try:
    from langgraph_swarm import create_swarm, create_handoff_tool
    SWARM_AVAILABLE = True
except ImportError:
    SWARM_AVAILABLE = False
    logger.info("langgraph-swarm not installed. Swarm strategy unavailable.")

# Agent constructor -- prefer langgraph.prebuilt.create_react_agent which is
# the canonical API in langgraph >= 0.2.  Fall back to the re-export that
# newer langchain packages may provide at langchain.agents.create_agent.
try:
    from langgraph.prebuilt import create_react_agent as _create_agent
except ImportError:
    try:
        from langchain.agents import create_agent as _create_agent  # type: ignore[no-redef]
    except ImportError:
        _create_agent = None  # type: ignore[assignment]
        logger.warning(
            "Neither langgraph.prebuilt.create_react_agent nor "
            "langchain.agents.create_agent could be imported. "
            "build_supervisor_graph / build_swarm_graph will not work."
        )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_supervisor_graph(
    model: BaseChatModel,
    agents: List[Dict[str, Any]],
    supervisor_prompt: Optional[str] = None,
) -> Any:
    """Build a supervisor graph using langgraph-supervisor.

    Parameters
    ----------
    model:
        The chat model that the supervisor itself will use.
    agents:
        A list of dicts, each containing at minimum a ``"name"`` key and
        optionally ``"model"``, ``"tools"``, and ``"prompt"`` keys.
    supervisor_prompt:
        Optional system-level prompt for the supervisor.

    Returns
    -------
    A compiled LangGraph supervisor graph.

    Raises
    ------
    ImportError
        If ``langgraph-supervisor`` is not installed.
    RuntimeError
        If no suitable agent constructor could be imported.
    """
    if not SUPERVISOR_AVAILABLE:
        raise ImportError(
            "langgraph-supervisor is required. Install with: pip install langgraph-supervisor"
        )
    if _create_agent is None:
        raise RuntimeError(
            "No agent constructor available. Install langgraph or langchain."
        )

    workers = []
    for agent_cfg in agents:
        worker_model = agent_cfg.get("model", model)
        worker = _create_agent(
            model=worker_model,
            tools=agent_cfg.get("tools", []),
            prompt=agent_cfg.get("prompt", "You are a helpful assistant."),
        )
        workers.append({"agent": worker, "name": agent_cfg["name"]})

    kwargs: Dict[str, Any] = {"workers": workers, "model": model}
    if supervisor_prompt:
        kwargs["prompt"] = supervisor_prompt
    return create_supervisor(**kwargs)


def build_swarm_graph(
    model: BaseChatModel,
    agents: List[Dict[str, Any]],
) -> Any:
    """Build a swarm graph using langgraph-swarm.

    Parameters
    ----------
    model:
        Default chat model passed to agents that do not specify their own.
    agents:
        A list of dicts, each with at minimum a ``"name"`` key and optionally
        ``"model"``, ``"tools"``, ``"prompt"``, and ``"handoff_targets"`` keys.

    Returns
    -------
    A compiled LangGraph swarm graph.

    Raises
    ------
    ImportError
        If ``langgraph-swarm`` is not installed.
    RuntimeError
        If no suitable agent constructor could be imported.
    """
    if not SWARM_AVAILABLE:
        raise ImportError(
            "langgraph-swarm is required. Install with: pip install langgraph-swarm"
        )
    if _create_agent is None:
        raise RuntimeError(
            "No agent constructor available. Install langgraph or langchain."
        )

    agent_graphs = []
    for agent_cfg in agents:
        agent_model = agent_cfg.get("model", model)
        handoff_tools = [
            create_handoff_tool(agent_name=target)
            for target in agent_cfg.get("handoff_targets", [])
        ]
        all_tools = list(agent_cfg.get("tools", [])) + handoff_tools
        agent = _create_agent(
            model=agent_model,
            tools=all_tools,
            prompt=agent_cfg.get("prompt", "You are a helpful assistant."),
        )
        agent_graphs.append({"agent": agent, "name": agent_cfg["name"]})

    return create_swarm(agents=agent_graphs)
