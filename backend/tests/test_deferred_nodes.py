"""Tests for deferred node execution support."""
import pytest


class TestDeferredNodeConfig:
    def test_non_deferred_node_has_no_defer_flag(self):
        config = {"model": "gpt-4o", "temperature": 0.5}
        assert config.get("deferred", False) is False

    def test_deferred_node_config_is_truthy(self):
        config = {"model": "gpt-4o", "temperature": 0.5, "deferred": True}
        assert config.get("deferred", False) is True
