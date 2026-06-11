# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model constants for LangConfig
Updated June 5, 2026
"""
from enum import Enum


class ModelChoice(str, Enum):
    """Selectable AI models - updated June 5, 2026."""

    # OpenAI - GPT-5 frontier series
    GPT_5_5 = "gpt-5.5"
    GPT_5_4 = "gpt-5.4"
    GPT_5_4_MINI = "gpt-5.4-mini"
    GPT_5_4_NANO = "gpt-5.4-nano"

    # Anthropic - Claude current generation
    CLAUDE_OPUS_4_8 = "claude-opus-4-8"
    CLAUDE_SONNET_4_6 = "claude-sonnet-4-6"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5"

    # Google - Gemini 3 (Current)
    GEMINI_3_PRO = "gemini-3-pro-preview"

    # Google - Gemini 2.5
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_25_FLASH = "gemini-2.5-flash"
    GEMINI_25_FLASH_LITE = "gemini-2.5-flash-lite"


# Default model
DEFAULT_MODEL = ModelChoice.GPT_5_4
