"""Tests for dynamic tool registration middleware."""
import pytest


class TestDynamicToolMiddlewareImport:
    def test_module_imports(self):
        from core.middleware.dynamic_tools import DynamicToolMiddleware
        assert DynamicToolMiddleware is not None

    def test_has_required_methods(self):
        from core.middleware.dynamic_tools import DynamicToolMiddleware
        mw = DynamicToolMiddleware(rules=[])
        assert hasattr(mw, 'before_model')
        assert hasattr(mw, 'abefore_model')

    def test_empty_rules_returns_none(self):
        from core.middleware.dynamic_tools import DynamicToolMiddleware
        mw = DynamicToolMiddleware(rules=[])
        result = mw.before_model({}, {})
        assert result is None

    def test_matching_rule_adds_tools(self):
        from core.middleware.dynamic_tools import DynamicToolMiddleware, ToolRule
        rule = ToolRule(condition_field="approved", condition_value=True, action="add", tool_names=["deploy"])
        mw = DynamicToolMiddleware(rules=[rule])
        result = mw.before_model({"approved": True}, {})
        assert result is not None
        assert "add_tools" in result
        assert "deploy" in result["add_tools"]

    def test_non_matching_rule_returns_none(self):
        from core.middleware.dynamic_tools import DynamicToolMiddleware, ToolRule
        rule = ToolRule(condition_field="approved", condition_value=True, action="add", tool_names=["deploy"])
        mw = DynamicToolMiddleware(rules=[rule])
        result = mw.before_model({"approved": False}, {})
        assert result is None
