"""Tests for model profile capability detection."""
import pytest


class TestModelProfiles:
    def test_module_imports(self):
        from core.agents.model_profiles import get_model_capabilities
        assert callable(get_model_capabilities)

    def test_returns_capabilities_for_known_model(self):
        from core.agents.model_profiles import get_model_capabilities, clear_profile_cache
        clear_profile_cache()
        caps = get_model_capabilities("gpt-4o")
        assert caps is not None
        assert isinstance(caps.get("function_calling"), bool)
        assert caps["function_calling"] is True

    def test_returns_defaults_for_unknown_model(self):
        from core.agents.model_profiles import get_model_capabilities, clear_profile_cache
        clear_profile_cache()
        caps = get_model_capabilities("nonexistent-model-xyz")
        assert caps is not None
        assert isinstance(caps.get("function_calling"), bool)

    def test_profiles_available_flag(self):
        from core.agents.model_profiles import PROFILES_AVAILABLE
        assert isinstance(PROFILES_AVAILABLE, bool)

    def test_date_suffix_stripping(self):
        from core.agents.model_profiles import get_model_capabilities, clear_profile_cache
        clear_profile_cache()
        caps = get_model_capabilities("claude-opus-4-5-20250514")
        assert caps is not None
        assert caps.get("function_calling") is True

    def test_caching_works(self):
        from core.agents.model_profiles import get_model_capabilities, clear_profile_cache
        clear_profile_cache()
        caps1 = get_model_capabilities("gpt-4o")
        caps2 = get_model_capabilities("gpt-4o")
        assert caps1 is caps2  # Same object from cache
