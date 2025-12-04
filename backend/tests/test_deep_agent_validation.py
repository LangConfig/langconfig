# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Focused Unit Tests for DeepAgent Configuration Validation.

Tests all validators and enum usage added in the code review fixes:
1. SubAgentConfig - workflow_id consistency validation
2. GuardrailsConfig - token limits ordering validation
3. BackendConfig - composite mappings validation
4. Enum type safety and string-to-enum conversion
5. Token limits default dict independence
"""

import pytest
from pydantic import ValidationError

from models.deep_agent import (
    SubAgentConfig,
    MiddlewareConfig,
    BackendConfig,
    GuardrailsConfig,
    DeepAgentConfig,
    create_default_middleware_config,
    create_default_backend_config,
    create_default_guardrails_config
)
from models.enums import (
    SubAgentType,
    MiddlewareType,
    BackendType,
    ReasoningEffort
)


# =============================================================================
# SubAgentConfig Validation Tests
# =============================================================================

class TestSubAgentConfigValidation:
    """Test SubAgentConfig validator for workflow_id consistency."""

    def test_compiled_requires_workflow_id(self):
        """Compiled subagents must have workflow_id."""
        with pytest.raises(ValidationError) as exc_info:
            SubAgentConfig(
                name="test_agent",
                description="Test compiled agent",
                type=SubAgentType.COMPILED
                # Missing workflow_id
            )
        error_msg = str(exc_info.value)
        assert "workflow_id" in error_msg
        assert "requires" in error_msg

    def test_compiled_with_workflow_id_valid(self):
        """Compiled subagent with workflow_id should be valid."""
        config = SubAgentConfig(
            name="test_agent",
            description="Test compiled agent",
            type=SubAgentType.COMPILED,
            workflow_id=123
        )
        assert config.type == SubAgentType.COMPILED
        assert config.workflow_id == 123

    def test_dictionary_without_workflow_id_valid(self):
        """Dictionary subagent without workflow_id should be valid."""
        config = SubAgentConfig(
            name="test_agent",
            description="Test dictionary agent",
            type=SubAgentType.DICTIONARY
        )
        assert config.type == SubAgentType.DICTIONARY
        assert config.workflow_id is None

    def test_dictionary_with_workflow_id_invalid(self):
        """Dictionary subagents cannot have workflow_id."""
        with pytest.raises(ValidationError) as exc_info:
            SubAgentConfig(
                name="test_agent",
                description="Test dictionary agent",
                type=SubAgentType.DICTIONARY,
                workflow_id=123  # Invalid for dictionary type
            )
        error_msg = str(exc_info.value)
        assert "cannot have workflow_id" in error_msg

    def test_string_to_enum_conversion(self):
        """Pydantic should auto-convert strings to enums."""
        config = SubAgentConfig(
            name="test_agent",
            description="Test agent",
            type="dictionary"  # String input
        )
        assert config.type == SubAgentType.DICTIONARY
        assert isinstance(config.type, SubAgentType)


# =============================================================================
# GuardrailsConfig Validation Tests
# =============================================================================

class TestGuardrailsConfigValidation:
    """Test GuardrailsConfig validator for token limits ordering."""

    def test_default_token_limits_valid(self):
        """Default token limits should be in correct order."""
        config = GuardrailsConfig()
        assert config.token_limits["summarization_threshold"] < config.token_limits["eviction_threshold"]
        assert config.token_limits["eviction_threshold"] < config.token_limits["max_total_tokens"]

    def test_token_limits_ordering_invalid(self):
        """Token limits must be in ascending order."""
        with pytest.raises(ValidationError) as exc_info:
            GuardrailsConfig(
                token_limits={
                    "max_total_tokens": 100000,
                    "eviction_threshold": 50000,
                    "summarization_threshold": 80000  # ERROR: > eviction
                }
            )
        error_msg = str(exc_info.value)
        assert "summarization_threshold" in error_msg
        assert "eviction_threshold" in error_msg
        assert "must satisfy" in error_msg

    def test_token_limits_custom_valid(self):
        """Custom valid token limits should pass."""
        config = GuardrailsConfig(
            token_limits={
                "max_total_tokens": 200000,
                "eviction_threshold": 150000,
                "summarization_threshold": 100000
            }
        )
        assert config.token_limits["summarization_threshold"] == 100000
        assert config.token_limits["eviction_threshold"] == 150000
        assert config.token_limits["max_total_tokens"] == 200000

    def test_token_limits_equal_values_invalid(self):
        """Equal threshold values should fail (strict less-than required)."""
        with pytest.raises(ValidationError):
            GuardrailsConfig(
                token_limits={
                    "max_total_tokens": 100000,
                    "eviction_threshold": 100000,  # Equal to max
                    "summarization_threshold": 80000
                }
            )

    def test_token_limits_default_dict_independence(self):
        """Each instance should get independent default dict."""
        config1 = GuardrailsConfig()
        config2 = GuardrailsConfig()

        # Modify config1's token_limits
        config1.token_limits["max_total_tokens"] = 200000

        # config2 should not be affected
        assert config2.token_limits["max_total_tokens"] == 100000
        assert config1.token_limits["max_total_tokens"] == 200000


# =============================================================================
# BackendConfig Validation Tests
# =============================================================================

class TestBackendConfigValidation:
    """Test BackendConfig validator for composite mappings."""

    def test_composite_requires_mappings(self):
        """Composite backends must have path mappings."""
        with pytest.raises(ValidationError) as exc_info:
            BackendConfig(
                type=BackendType.COMPOSITE
                # Missing mappings
            )
        error_msg = str(exc_info.value)
        assert "mappings" in error_msg
        assert "requires" in error_msg

    def test_composite_empty_mappings_invalid(self):
        """Composite backend with empty mappings should fail."""
        with pytest.raises(ValidationError) as exc_info:
            BackendConfig(
                type=BackendType.COMPOSITE,
                mappings={}  # Empty
            )
        error_msg = str(exc_info.value)
        assert "mappings" in error_msg

    def test_composite_with_mappings_valid(self):
        """Composite backend with valid mappings should pass."""
        config = BackendConfig(
            type=BackendType.COMPOSITE,
            mappings={
                "/memory/": {"type": "vectordb", "config": {}},
                "/state/": {"type": "state", "config": {}}
            }
        )
        assert config.type == BackendType.COMPOSITE
        assert len(config.mappings) == 2

    def test_non_composite_without_mappings_valid(self):
        """Non-composite backends don't need mappings."""
        for backend_type in [BackendType.STATE, BackendType.STORE, BackendType.FILESYSTEM, BackendType.VECTORDB]:
            config = BackendConfig(type=backend_type)
            assert config.type == backend_type
            assert config.mappings is None


# =============================================================================
# Enum Validation Tests
# =============================================================================

class TestEnumValidation:
    """Test enum type safety and conversion."""

    def test_subagent_type_enum_values(self):
        """Test SubAgentType enum has correct values."""
        assert SubAgentType.DICTIONARY.value == "dictionary"
        assert SubAgentType.COMPILED.value == "compiled"

    def test_middleware_type_enum_values(self):
        """Test MiddlewareType enum has correct values."""
        assert MiddlewareType.TODO_LIST.value == "todo_list"
        assert MiddlewareType.FILESYSTEM.value == "filesystem"
        assert MiddlewareType.SUBAGENT.value == "subagent"

    def test_backend_type_enum_values(self):
        """Test BackendType enum has correct values."""
        assert BackendType.STATE.value == "state"
        assert BackendType.STORE.value == "store"
        assert BackendType.FILESYSTEM.value == "filesystem"
        assert BackendType.VECTORDB.value == "vectordb"
        assert BackendType.COMPOSITE.value == "composite"

    def test_reasoning_effort_enum_values(self):
        """Test ReasoningEffort enum has correct values."""
        assert ReasoningEffort.NONE.value == "none"
        assert ReasoningEffort.LOW.value == "low"
        assert ReasoningEffort.MEDIUM.value == "medium"
        assert ReasoningEffort.HIGH.value == "high"

    def test_middleware_type_string_conversion(self):
        """Middleware type should convert strings to enums."""
        config = MiddlewareConfig(type="todo_list")
        assert config.type == MiddlewareType.TODO_LIST
        assert isinstance(config.type, MiddlewareType)

    def test_backend_type_string_conversion(self):
        """Backend type should convert strings to enums."""
        config = BackendConfig(type="state")
        assert config.type == BackendType.STATE
        assert isinstance(config.type, BackendType)

    def test_reasoning_effort_string_conversion(self):
        """Reasoning effort should convert strings to enums."""
        config = DeepAgentConfig(
            system_prompt="Test",
            reasoning_effort="medium"
        )
        assert config.reasoning_effort == ReasoningEffort.MEDIUM

    def test_invalid_enum_value_rejected(self):
        """Invalid enum values should be rejected."""
        with pytest.raises(ValidationError):
            MiddlewareConfig(type="invalid_type")

        with pytest.raises(ValidationError):
            BackendConfig(type="invalid_backend")

        with pytest.raises(ValidationError):
            SubAgentConfig(
                name="test",
                description="test",
                type="invalid_subagent_type"
            )


# =============================================================================
# DeepAgentConfig Integration Tests
# =============================================================================

class TestDeepAgentConfigIntegration:
    """Integration tests for complete DeepAgentConfig."""

    def test_full_config_with_enums_valid(self):
        """Full config with all enum types should work."""
        config = DeepAgentConfig(
            model="claude-sonnet-4-5-20250929",
            system_prompt="Test agent",
            reasoning_effort=ReasoningEffort.LOW,
            middleware=[
                MiddlewareConfig(type=MiddlewareType.TODO_LIST),
                MiddlewareConfig(type=MiddlewareType.FILESYSTEM)
            ],
            subagents=[
                SubAgentConfig(
                    name="test_subagent",
                    description="Test",
                    type=SubAgentType.DICTIONARY
                )
            ],
            backend=BackendConfig(type=BackendType.STATE),
            guardrails=GuardrailsConfig()
        )

        assert config.reasoning_effort == ReasoningEffort.LOW
        assert config.middleware[0].type == MiddlewareType.TODO_LIST
        assert config.subagents[0].type == SubAgentType.DICTIONARY
        assert config.backend.type == BackendType.STATE

    def test_full_config_with_strings_converts_to_enums(self):
        """Full config with string values should convert to enums."""
        config = DeepAgentConfig(
            model="claude-sonnet-4-5-20250929",
            system_prompt="Test agent",
            reasoning_effort="high",  # String
            middleware=[
                MiddlewareConfig(type="todo_list")  # String
            ],
            subagents=[
                SubAgentConfig(
                    name="test",
                    description="Test",
                    type="dictionary"  # String
                )
            ],
            backend=BackendConfig(type="state")  # String
        )

        assert config.reasoning_effort == ReasoningEffort.HIGH
        assert config.middleware[0].type == MiddlewareType.TODO_LIST
        assert config.subagents[0].type == SubAgentType.DICTIONARY
        assert config.backend.type == BackendType.STATE


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Test helper functions use enums correctly."""

    def test_create_default_middleware_config_uses_enums(self):
        """Helper should create configs with enum types."""
        configs = create_default_middleware_config()

        assert len(configs) == 3
        assert configs[0].type == MiddlewareType.TODO_LIST
        assert configs[1].type == MiddlewareType.FILESYSTEM
        assert configs[2].type == MiddlewareType.SUBAGENT

        # Verify they're actually enum instances
        for config in configs:
            assert isinstance(config.type, MiddlewareType)

    def test_create_default_backend_config_uses_enums(self):
        """Helper should create config with enum type."""
        config = create_default_backend_config()

        assert config.type == BackendType.COMPOSITE
        assert isinstance(config.type, BackendType)
        assert config.mappings is not None
        assert len(config.mappings) == 3

    def test_create_default_guardrails_config_valid_token_limits(self):
        """Helper should create config with valid token limits."""
        config = create_default_guardrails_config()

        # Should pass validation
        assert config.token_limits["summarization_threshold"] < config.token_limits["eviction_threshold"]
        assert config.token_limits["eviction_threshold"] < config.token_limits["max_total_tokens"]
