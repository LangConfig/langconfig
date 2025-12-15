# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skills System - Modular, context-aware capabilities for agents.

Inspired by Claude Code's skills model, this module provides:
- SkillLoader: Parse and validate SKILL.md files
- SkillRegistry: In-memory cache with database persistence
- SkillMatcher: Context-aware skill selection and matching
"""

from core.skills.loader import SkillLoader, ParsedSkill
from core.skills.registry import SkillRegistry, get_skill_registry
from core.skills.matcher import SkillMatcher, SkillMatch, get_skill_matcher

__all__ = [
    "SkillLoader",
    "ParsedSkill",
    "SkillRegistry",
    "get_skill_registry",
    "SkillMatcher",
    "SkillMatch",
    "get_skill_matcher",
]
