"""
Model profile capability detection.

LangChain 1.1 added .profile on chat models. This module provides a unified
interface with fallback to local defaults when profiles are unavailable.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PROFILES_AVAILABLE = False

# Check if runtime profile queries are possible (requires langchain with init_chat_model).
# Even when available, get_model_capabilities() uses local defaults to avoid requiring
# API keys at lookup time. Set this flag so callers can optionally attempt runtime queries.
try:
    from langchain.chat_models import init_chat_model
    PROFILES_AVAILABLE = True
except ImportError:
    init_chat_model = None

_DEFAULT_CAPABILITIES: Dict[str, Dict[str, bool]] = {
    "gpt-5.1": {"function_calling": True, "structured_output": True, "json_mode": True, "vision": True, "streaming": True},
    "gpt-4o": {"function_calling": True, "structured_output": True, "json_mode": True, "vision": True, "streaming": True},
    "gpt-4o-mini": {"function_calling": True, "structured_output": True, "json_mode": True, "vision": True, "streaming": True},
    "claude-opus-4-5": {"function_calling": True, "structured_output": True, "json_mode": False, "vision": True, "streaming": True},
    "claude-sonnet-4-5": {"function_calling": True, "structured_output": True, "json_mode": False, "vision": True, "streaming": True},
    "claude-haiku-4-5": {"function_calling": True, "structured_output": True, "json_mode": False, "vision": True, "streaming": True},
    "gemini-3-pro-preview": {"function_calling": True, "structured_output": True, "json_mode": True, "vision": True, "streaming": True},
    "gemini-2.5-flash": {"function_calling": True, "structured_output": True, "json_mode": True, "vision": True, "streaming": True},
}

_CONSERVATIVE_DEFAULTS: Dict[str, bool] = {
    "function_calling": True, "structured_output": False, "json_mode": False, "vision": False, "streaming": True,
}

_profile_cache: Dict[str, Dict[str, Any]] = {}


def get_model_capabilities(model_name: str) -> Dict[str, Any]:
    """Get capability flags for a model. Uses local defaults (no API key needed)."""
    if model_name in _profile_cache:
        return _profile_cache[model_name]

    # Use local defaults (profile API requires API keys we may not have)
    base_name = model_name
    for known in _DEFAULT_CAPABILITIES:
        if model_name.startswith(known):
            base_name = known
            break

    capabilities = _DEFAULT_CAPABILITIES.get(base_name, _CONSERVATIVE_DEFAULTS.copy())
    _profile_cache[model_name] = capabilities
    return capabilities


def clear_profile_cache() -> None:
    """Clear the in-memory profile cache."""
    _profile_cache.clear()
