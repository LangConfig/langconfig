"""Tests for langgraph-bigtool integration."""
import pytest


class TestBigtoolImport:
    def test_module_imports(self):
        from core.tools.bigtool_registry import BIGTOOL_AVAILABLE
        assert isinstance(BIGTOOL_AVAILABLE, bool)

    def test_build_bigtool_agent_exists(self):
        from core.tools.bigtool_registry import build_bigtool_agent
        assert callable(build_bigtool_agent)

    def test_should_suggest_bigtool_below_threshold(self):
        from core.tools.bigtool_registry import should_suggest_bigtool
        assert should_suggest_bigtool(5) is False

    def test_should_suggest_bigtool_above_threshold(self):
        from core.tools.bigtool_registry import should_suggest_bigtool, BIGTOOL_AVAILABLE
        result = should_suggest_bigtool(20)
        # Only suggests if bigtool is actually installed
        assert result == BIGTOOL_AVAILABLE
