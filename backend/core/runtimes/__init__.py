# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Agent runtime registry.

Resolves a runtime name (stored on chat_sessions.runtime /
deep_agent_templates.runtime) to an :class:`AgentRuntime` implementation.
'langgraph' is the default and is registered lazily on first lookup; future
runtimes (e.g. 'google_adk', 'anthropic_agents') register via
:func:`register_runtime`.
"""

from typing import Dict

from core.runtimes.base import (
    AgentRuntime,
    RuntimeCapabilities,
    RuntimeEvent,
    RuntimeSessionRef,
)

DEFAULT_RUNTIME = "langgraph"

_REGISTRY: Dict[str, AgentRuntime] = {}


def register_runtime(runtime: AgentRuntime) -> None:
    """Register a runtime implementation under its ``name``."""
    _REGISTRY[runtime.name] = runtime


def get_runtime(name: str = None) -> AgentRuntime:
    """Resolve a runtime by name (defaults to 'langgraph').

    Raises:
        ValueError: if the runtime name is not registered.
    """
    resolved = name or DEFAULT_RUNTIME

    if resolved not in _REGISTRY:
        if resolved == DEFAULT_RUNTIME:
            # Lazy import to keep `core.runtimes.base` importable without
            # pulling in the full LangGraph/DeepAgents dependency chain.
            from core.runtimes.langgraph_runtime import LangGraphRuntime
            register_runtime(LangGraphRuntime())
        else:
            raise ValueError(
                f"Unknown agent runtime '{resolved}'. "
                f"Registered runtimes: {sorted(_REGISTRY.keys()) or [DEFAULT_RUNTIME]}"
            )

    return _REGISTRY[resolved]


__all__ = [
    "AgentRuntime",
    "RuntimeCapabilities",
    "RuntimeEvent",
    "RuntimeSessionRef",
    "DEFAULT_RUNTIME",
    "get_runtime",
    "register_runtime",
]
