# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for workflow node caching configuration."""
import pytest


class TestBuildCachePolicy:
    def test_returns_none_when_cache_disabled(self):
        from core.workflows.cache_config import build_cache_policy
        policy = build_cache_policy({"cache_enabled": False})
        assert policy is None

    def test_returns_none_when_cache_not_specified(self):
        from core.workflows.cache_config import build_cache_policy
        policy = build_cache_policy({})
        assert policy is None

    def test_returns_policy_with_default_ttl(self):
        from core.workflows.cache_config import build_cache_policy, CACHE_AVAILABLE
        if not CACHE_AVAILABLE:
            pytest.skip("LangGraph cache module not available")
        policy = build_cache_policy({"cache_enabled": True})
        assert policy is not None
        assert policy.ttl == 300

    def test_returns_policy_with_custom_ttl(self):
        from core.workflows.cache_config import build_cache_policy, CACHE_AVAILABLE
        if not CACHE_AVAILABLE:
            pytest.skip("LangGraph cache module not available")
        policy = build_cache_policy({"cache_enabled": True, "cache_ttl": 60})
        assert policy is not None
        assert policy.ttl == 60


class TestGetCacheBackend:
    def test_returns_in_memory_by_default(self):
        from core.workflows.cache_config import get_cache_backend, CACHE_AVAILABLE
        if not CACHE_AVAILABLE:
            pytest.skip("LangGraph cache module not available")
        cache = get_cache_backend({})
        assert cache is not None
        assert "InMemory" in type(cache).__name__ or "Memory" in type(cache).__name__

    def test_returns_none_when_disabled(self):
        from core.workflows.cache_config import get_cache_backend
        cache = get_cache_backend({"cache_backend": "disabled"})
        assert cache is None
