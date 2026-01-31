"""
Dynamic Tool Registration Middleware.

LangChain 1.2.7 supports adding/removing tools during execution via middleware.
This middleware evaluates rules against the current state and modifies the
available tool set accordingly.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from core.middleware.core import AgentMiddleware
except ImportError:
    # Fallback base class when langchain is not installed.
    # Mirrors the AgentMiddleware interface from core.py so that
    # DynamicToolMiddleware can be used and tested independently.
    from abc import ABC

    class AgentMiddleware(ABC):
        """Minimal fallback when core.middleware.core cannot be imported."""
        tools: list = []

        def __init__(self):
            if not hasattr(self, 'name'):
                self.name = self.__class__.__name__

        def before_model(self, state, runtime):
            return None

        async def abefore_model(self, state, runtime):
            return self.before_model(state, runtime)

logger = logging.getLogger(__name__)


@dataclass
class ToolRule:
    condition_field: str
    condition_value: Any
    action: str  # "add" or "remove"
    tool_names: List[str]


class DynamicToolMiddleware(AgentMiddleware):
    name = "dynamic_tools"

    def __init__(self, rules: List[ToolRule] = None):
        super().__init__()
        self.rules = rules or []

    def _evaluate_rules(self, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tools_to_add = []
        tools_to_remove = []
        for rule in self.rules:
            if state.get(rule.condition_field) == rule.condition_value:
                if rule.action == "add":
                    tools_to_add.extend(rule.tool_names)
                elif rule.action == "remove":
                    tools_to_remove.extend(rule.tool_names)
        if not tools_to_add and not tools_to_remove:
            return None
        result = {}
        if tools_to_add:
            result["add_tools"] = tools_to_add
        if tools_to_remove:
            result["remove_tools"] = tools_to_remove
        return result

    def before_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        return self._evaluate_rules(state)

    async def abefore_model(self, state: Dict[str, Any], runtime: Any) -> Optional[Dict[str, Any]]:
        return self._evaluate_rules(state)
