# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Agent runtime registry.

Resolves a runtime name (stored on chat_sessions.runtime /
deep_agent_templates.runtime) to an :class:`AgentRuntime` implementation.
'langgraph' is the default and is registered lazily on first lookup;
'google_adk' and 'anthropic_managed' are also registered lazily (so their
optional dependencies only matter when selected). Future runtimes register
via :func:`register_runtime`.
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
        elif resolved == "google_adk":
            # Lazy import so a missing/broken google-adk install never breaks
            # startup - it only fails when this runtime is actually selected.
            try:
                from core.runtimes.adk_runtime import GoogleADKRuntime
            except ImportError as e:
                raise ValueError(
                    "The 'google_adk' runtime requires the 'google-adk' "
                    "package. Install it with: pip install 'google-adk>=1.22,<2' "
                    f"(import failed: {e})"
                ) from e
            register_runtime(GoogleADKRuntime())
        elif resolved == "anthropic_managed":
            # Lazy import so a missing/old anthropic SDK (Managed Agents beta
            # surface ships in anthropic>=0.92) never breaks startup - it
            # only fails when this runtime is actually selected.
            try:
                from core.runtimes.anthropic_managed_runtime import (
                    AnthropicManagedRuntime,
                )
            except ImportError as e:
                raise ValueError(
                    "The 'anthropic_managed' runtime requires the 'anthropic' "
                    "package with the Managed Agents beta surface. Install it "
                    "with: pip install -U 'anthropic>=0.92,<1' "
                    f"(import failed: {e})"
                ) from e
            register_runtime(AnthropicManagedRuntime())
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
