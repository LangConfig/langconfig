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
    Reasoning effort for Gemini models.
    Maps to thinking_level (Gemini 3+) or thinking_budget (Gemini 2.x).
    """
    NONE = "none"       # 96% cheaper - minimal reasoning
    LOW = "low"         # Balanced cost/quality (default)
    MEDIUM = "medium"   # More thorough reasoning
    HIGH = "high"       # Maximum reasoning capability
