# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""AgentRuntime abstraction.

Decouples the chat API from the engine that actually executes an agent so
additional runtimes (Google ADK, Anthropic Managed Agents, ...) can plug in
behind the same SSE contract.

The :class:`RuntimeEvent` envelope deliberately mirrors the existing chat SSE
frame types emitted by ``api/chat/routes.py``:

    SSE frame        RuntimeEvent type
    ---------        -----------------
    chunk            text_delta
    thinking         thinking_delta
    tool_start       tool_start
    tool_end         tool_end
    tool_artifact    tool_artifact
    custom_event     custom
    error            error
    complete         complete
    (reserved)       usage

The API route owns SSE encoding and DB persistence; runtimes own agent
acquisition, execution, and event normalization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, TypedDict

import json


# =============================================================================
# Shared helpers (runtime-agnostic, also used by the chat routes)
# =============================================================================

def make_json_safe(obj):
    """
    Recursively convert objects to JSON-safe format.
    Filters out non-serializable items like LangGraph Command objects.
    """
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items() if not k.startswith('_')}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    else:
        # Skip non-serializable objects like Command
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return None


def has_multimodal_blocks(blocks: Optional[List[Dict[str, Any]]]) -> bool:
    """Whether content blocks include non-text UI-renderable content."""
    if not blocks:
        return False
    return any(
        block.get("type") in {"image", "audio", "file", "resource"}
        for block in blocks
        if isinstance(block, dict)
    )


# =============================================================================
# Runtime envelope types
# =============================================================================

RuntimeEventType = Literal[
    "text_delta",
    "thinking_delta",
    "tool_start",
    "tool_end",
    "tool_artifact",
    "custom",
    "usage",
    "error",
    "complete",
]


class RuntimeEvent(TypedDict, total=False):
    """Normalized event envelope yielded by runtime streams.

    Field usage by type:
    - text_delta / thinking_delta: ``text`` (already flattened to str)
    - tool_start / tool_end: ``tool_name`` + ``data`` ({input|output, error, namespace})
    - tool_artifact: ``tool_name`` + ``data`` ({"artifact": {...}})
    - custom: ``data`` (sanitized custom event payload)
    - usage: ``data`` (token/cost payload; reserved, not emitted yet)
    - error: ``error`` (message string)
    - complete: ``text`` (full response) + ``data``
      ({"artifacts": [...], "content_blocks": [...], "has_multimodal": bool})
    """

    type: RuntimeEventType
    text: str
    tool_name: str
    data: Dict[str, Any]
    error: str


@dataclass
class RuntimeCapabilities:
    """What a runtime supports. Routes can gate features on these flags."""

    streaming: bool = True
    hitl: bool = False
    custom_tools: bool = True
    checkpoint_resume: bool = True


@dataclass
class RuntimeSessionRef:
    """Opaque handle for a runtime-managed conversation/session.

    ``external_ref`` is the runtime-native identifier (LangGraph thread_id,
    ADK session name, Anthropic managed-agent session id, ...).
    """

    runtime: str
    session_id: str
    external_ref: Optional[str] = None


# =============================================================================
# Runtime interface
# =============================================================================

class AgentRuntime(ABC):
    """Execution engine behind the chat API.

    Implementations own agent acquisition/caching, streaming execution, and
    translation of engine-native events into :class:`RuntimeEvent` envelopes.
    DB persistence of messages/metrics/artifacts stays in the API layer.
    """

    name: str = "abstract"
    capabilities: RuntimeCapabilities = RuntimeCapabilities()

    @abstractmethod
    async def prepare_template(self, template_row: Any, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate/normalize an agent template config for this runtime.

        Returns the (possibly augmented) config dict ready for
        :meth:`create_session`.
        """

    @abstractmethod
    async def create_session(
        self,
        config: Dict[str, Any],
        session_id: str,
        context: str = "",
        project_id: Optional[int] = None,
    ) -> RuntimeSessionRef:
        """Acquire or build the runtime-side session/agent for ``session_id``."""

    @abstractmethod
    def stream(
        self,
        ref: RuntimeSessionRef,
        message: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Stream RuntimeEvents for one user message."""

    def resume(
        self,
        ref: RuntimeSessionRef,
        payload: Dict[str, Any],
    ) -> AsyncIterator[RuntimeEvent]:
        """Resume an interrupted (HITL) run with ``payload``.

        Implementations with ``capabilities.hitl`` override this as an async
        generator (same calling convention as :meth:`stream`); the default
        raises immediately.
        """
        raise NotImplementedError(
            f"Runtime '{self.name}' does not support HITL resume"
        )

    @abstractmethod
    async def destroy_session(self, ref: RuntimeSessionRef) -> Any:
        """Release runtime-side state (checkpoints, remote sessions, ...)."""
