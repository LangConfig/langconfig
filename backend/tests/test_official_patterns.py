"""Tests for official LangGraph multi-agent pattern wrappers."""
import pytest


class TestOfficialPatternsImport:
    def test_module_imports(self):
        from core.workflows.official_patterns import SUPERVISOR_AVAILABLE, SWARM_AVAILABLE
        assert isinstance(SUPERVISOR_AVAILABLE, bool)
        assert isinstance(SWARM_AVAILABLE, bool)

    def test_build_supervisor_graph_exists(self):
        from core.workflows.official_patterns import build_supervisor_graph
        assert callable(build_supervisor_graph)

    def test_build_swarm_graph_exists(self):
        from core.workflows.official_patterns import build_swarm_graph
        assert callable(build_swarm_graph)
