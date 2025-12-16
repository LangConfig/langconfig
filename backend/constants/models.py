# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model constants for LangConfig
Updated December 16, 2025
"""
from enum import Enum


class ModelChoice(str, Enum):
    """Available AI models - Updated December 16, 2025"""

    # OpenAI - GPT-5 Series (Current)
    GPT_5_2 = "gpt-5.2"  # Latest flagship model
    GPT_5_1 = "gpt-5.1"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"  # Lean/fast model

    # Anthropic - Claude 4.5 (Current)
    CLAUDE_OPUS_4_5 = "claude-opus-4-5"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"

    # Google - Gemini 3 (Current)
    GEMINI_3_PRO = "gemini-3-pro-preview"

    # Google - Gemini 2.5
    GEMINI_25_FLASH = "gemini-2.5-flash"


# Default model
DEFAULT_MODEL = ModelChoice.GPT_4O
