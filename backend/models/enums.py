# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Shared Enums for DeepAgent Configuration.

Provides type-safe enum values for all configuration fields in DeepAgent models.
Using str inheritance ensures JSON serialization compatibility and Pydantic auto-conversion.
"""

from enum import Enum


class SubAgentType(str, Enum):
    """Type of subagent implementation."""
    DICTIONARY = "dictionary"  # Simple dictionary-based subagent
    COMPILED = "compiled"      # Workflow-based compiled subagent


class MiddlewareType(str, Enum):
    """Type of middleware to enable."""
    TODO_LIST = "todo_list"     # Task tracking middleware
    FILESYSTEM = "filesystem"   # File eviction middleware
    SUBAGENT = "subagent"       # Subagent spawning middleware


class BackendType(str, Enum):
    """Type of backend storage."""
    STATE = "state"              # Ephemeral LangGraph State
    STORE = "store"              # Persistent LangGraph Store
    FILESYSTEM = "filesystem"     # Local filesystem storage
    VECTORDB = "vectordb"        # pgvector semantic storage
    COMPOSITE = "composite"      # Combination of backends with path mappings


class ReasoningEffort(str, Enum):
    """
    Reasoning effort for model thinking depth.

    Gemini: maps to thinking_level (Gemini 3+) or thinking_budget (Gemini 2.x).
    Anthropic: maps to the `effort` parameter (low/medium/high/xhigh/max);
    xhigh/max degrade to high on Gemini.
    """
    NONE = "none"       # 96% cheaper - minimal reasoning (Gemini); omits effort (Anthropic)
    LOW = "low"         # Balanced cost/quality (default)
    MEDIUM = "medium"   # More thorough reasoning
    HIGH = "high"       # Maximum reasoning capability (Gemini ceiling)
    XHIGH = "xhigh"     # Anthropic-only: between high and max (best for coding/agentic)
    MAX = "max"         # Anthropic-only: correctness over cost
