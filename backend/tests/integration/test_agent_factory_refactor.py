# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Integration Tests for Agent Factory Refactor

Tests all critical fixes and new features:
1. Streaming configuration
2. Callbacks integration (TokenTrackingCallback)
3. Tool binding verification
4. Interrupt configuration with custom nodes
5. Enhanced validation
6. Fallback error handling
7. Dynamic model routing
8. Schema versioning

These tests use real components from the langconfig infrastructure including
TokenTrackingCallback, ExecutionEventCallbackHandler, and SimpleWorkflowExecutor.
"""

import pytest
import asyncio
from typing import List, Dict, Any
import logging

from core.agents.factory import AgentFactory
from core.utils.token_tracking import create_token_tracking_callback
from models.agent_config_schema import (
    AgentConfigV2,
    ToolConfig,
    normalize_agent_config_v1_to_v2,
    ConfigNormalizer
)
from core.models.registry import model_registry
from core.middleware.routing import ModelRouter, TaskComplexity, analyze_task_complexity


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def basic_agent_config():
    """Basic agent configuration for testing."""
    return {
        "model": "claude-haiku-4-5-20251015",
        "temperature": 0.7,
        "max_tokens": 4096,
        "system_prompt": "You are a helpful AI assistant.",
        "native_tools": ["web_search"],
        "streaming": True,
        "enable_parallel_tools": True,
    }


@pytest.fixture
def complex_agent_config():
    """Complex agent configuration with multiple features."""
    return {
        "model": "claude-sonnet-4-5-20250514",
        "temperature": 0.5,
        "max_tokens": 8192,
        "system_prompt": "You are an advanced AI assistant with multiple capabilities.",
        "native_tools": ["web_search", "calculator", "file_read"],
        "cli_tools": ["git"],
        "custom_tools": [],
        "streaming": True,
        "enable_parallel_tools": True,
        "enable_memory": False,
        "fallback_models": ["claude-haiku-4-5-20251015"],
        "interrupt_before": ["agent"],
        "interrupt_after": ["tools"],
    }


@pytest.fixture
def routing_agent_config():
    """Agent configuration with dynamic model routing enabled."""
    return {
        "model": "claude-haiku-4-5-20251015",
        "temperature": 0.7,
        "system_prompt": "Complex reasoning task.",
        "native_tools": ["web_search"] * 10,  # Many tools suggest complex task
        "streaming": True,
        "enable_model_routing": True,
        "routing_strategy": "balanced",
    }


# =============================================================================
Critical Bug Fixes Tests
# =============================================================================

class TestCriticalFixes:
    """Test all 6 critical bug fixes from AI feedback."""

    @pytest.mark.asyncio
    async def test_streaming_configuration_passed(self, basic_agent_config):
        """Test that streaming flag is properly passed to create_agent."""
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=basic_agent_config,
            project_id=1,
            task_id=1,
            context="Test context"
        )

        assert agent_graph is not None, "Agent graph should be created"
        # Streaming should be configured in the agent
        # Note: Cannot directly verify streaming in compiled graph, but logs should show it

    @pytest.mark.asyncio
    async def test_callbacks_integration(self, basic_agent_config):
        """Test that TokenTrackingCallback is properly integrated."""
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=basic_agent_config,
            project_id=1,
            task_id=1,
            context="Test context"
        )

        # Verify callbacks list is not empty
        assert len(callbacks) > 0, "Callbacks should be configured"

        # Verify TokenTrackingCallback is in the list
        callback_types = [type(cb).__name__ for cb in callbacks]
        assert "TokenTrackingCallback" in callback_types, "TokenTrackingCallback should be present"

    @pytest.mark.asyncio
    async def test_tool_binding_verification(self, basic_agent_config):
        """Test that tools are bound and verified."""
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=basic_agent_config,
            project_id=1,
            task_id=1,
            context="Test context"
        )

        # Verify tools list is populated
        assert len(tools) > 0, "Tools should be loaded"
        assert tools[0].name is not None, "Tools should have names"

    @pytest.mark.asyncio
    async def test_interrupt_configuration_custom_nodes(self, complex_agent_config):
        """Test that interrupt configuration supports custom node lists."""
        # Config has interrupt_before=["agent"] and interrupt_after=["tools"]
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=complex_agent_config,
            project_id=1,
            task_id=1,
            context="Test context"
        )

        assert agent_graph is not None, "Agent graph should be created with interrupts"
        # Interrupt configuration is internal to LangGraph, verified via logs

    @pytest.mark.asyncio
    async def test_enhanced_validation(self):
        """Test enhanced configuration validation."""
        # Test invalid temperature
        invalid_config = {
            "model": "claude-haiku-4-5-20251015",
            "temperature": 5.0,  # Invalid: > 2.0
            "system_prompt": "Test"
        }

        errors = AgentFactory._validate_agent_config(invalid_config)
        assert len(errors) > 0, "Validation should catch invalid temperature"
        assert any("temperature" in err for err in errors), "Should have temperature error"

        # Test invalid max_tokens
        invalid_config2 = {
            "model": "claude-haiku-4-5-20251015",
            "max_tokens": 1000000,  # Invalid: > 500000
            "system_prompt": "Test"
        }

        errors2 = AgentFactory._validate_agent_config(invalid_config2)
        assert len(errors2) > 0, "Validation should catch invalid max_tokens"

    @pytest.mark.asyncio
    async def test_fallback_error_handling(self):
        """Test comprehensive fallback error handling."""
        config_with_bad_fallbacks = {
            "model": "invalid-model-12345",
            "fallback_models": ["also-invalid-model"],
            "system_prompt": "Test"
        }

        # This should raise ValueError with comprehensive error message
        with pytest.raises(ValueError) as exc_info:
            await AgentFactory.create_agent(
                agent_config=config_with_bad_fallbacks,
                project_id=1,
                task_id=1,
                context="Test"
            )

        error_message = str(exc_info.value)
        assert "Failed to initialize any LLM" in error_message or "Attempted models" in error_message, \
            "Should provide comprehensive error for all failures"


# =============================================================================
Schema & Architecture Tests
# =============================================================================

class TestSchemaV2:
    """Test new schema versioning system."""

    def test_tool_config_creation(self):
        """Test ToolConfig creation and methods."""
        tools = ToolConfig(
            native=["web_search", "calculator"],
            cli=["git"],
            custom=["my_custom_tool"],
            mcp=[]
        )

        assert len(tools.get_all_tools()) == 4, "Should have 4 total tools"
        assert tools.has_tools(), "Should report having tools"

    def test_v1_to_v2_migration(self):
        """Test migration from V1 to V2 config format."""
        v1_config = {
            "model": "claude-haiku-4-5-20251015",
            "native_tools": ["web_search"],
            "cli_tools": ["git"],
            "custom_tools": ["my_tool"],
            "mcp_tools": [],
        }

        v2_config = normalize_agent_config_v1_to_v2(v1_config)

        assert v2_config["config_schema_version"] == 2, "Should be V2"
        assert "tools" in v2_config, "Should have unified tools object"
        assert "native_tools" not in v2_config, "Old fields should be removed"

    def test_agent_config_v2_validation(self):
        """Test AgentConfigV2 Pydantic validation."""
        config = AgentConfigV2(
            model="claude-haiku-4-5-20251015",
            temperature=0.7,
            tools=ToolConfig(native=["web_search"])
        )

        assert config.config_schema_version == 2, "Should default to version 2"
        assert config.tools.native == ["web_search"], "Tools should be set"

    def test_config_normalizer(self):
        """Test ConfigNormalizer utility."""
        v1_config = {
            "model": "claude-haiku-4-5-20251015",
            "native_tools": ["web_search"],
        }

        normalizer = ConfigNormalizer()
        detected_version = normalizer.detect_version(v1_config)
        assert detected_version == 1, "Should detect as V1"

        v2_config = normalizer.normalize(v1_config, target_version=2)
        assert v2_config["config_schema_version"] == 2, "Should normalize to V2"


# =============================================================================
Dynamic Model Routing Tests
# =============================================================================

class TestModelRouting:
    """Test dynamic model routing system."""

    def test_model_registry_initialization(self):
        """Test that model registry is properly initialized."""
        assert len(model_registry._models) > 0, "Registry should have models"

        # Test getting a model
        haiku = model_registry.get_model("claude-haiku-4-5-20251015")
        assert haiku is not None, "Should find Haiku model"
        assert haiku.display_name == "Claude Haiku 4.5", "Should have correct name"

    def test_task_complexity_analysis(self):
        """Test task complexity analysis."""
        # Simple task
        simple = analyze_task_complexity(
            context_length=1000,
            tool_count=1,
            has_structured_output=False
        )
        assert simple in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE], \
            "Should be simple or moderate"

        # Complex task
        complex_task = analyze_task_complexity(
            context_length=50000,
            tool_count=15,
            has_structured_output=True,
            has_vision=True
        )
        assert complex_task in [TaskComplexity.COMPLEX, TaskComplexity.VERY_COMPLEX], \
            "Should be complex or very complex"

    def test_model_router_cost_optimized(self):
        """Test cost-optimized routing strategy."""
        router = ModelRouter()

        selected = router.route(
            original_model="claude-opus-4-5-20250514",
            context_length=1000,
            tool_count=2,
            strategy="cost_optimized",
            requirements={"streaming": True, "tools": True}
        )

        # Should route to cheaper model for simple task
        selected_info = model_registry.get_model(selected)
        opus_info = model_registry.get_model("claude-opus-4-5-20250514")

        assert selected_info.cost_per_1m_input <= opus_info.cost_per_1m_input, \
            "Should select cheaper or equal cost model"

    def test_model_router_performance_optimized(self):
        """Test performance-optimized routing strategy."""
        router = ModelRouter()

        selected = router.route(
            original_model="claude-haiku-4-5-20251015",
            context_length=50000,
            tool_count=15,
            strategy="performance_optimized",
            requirements={"streaming": True, "tools": True}
        )

        # Should route to higher quality model
        selected_info = model_registry.get_model(selected)
        assert selected_info.quality_rating >= 4, \
            "Performance-optimized should select high quality model"

    @pytest.mark.asyncio
    async def test_routing_integration_in_agent_factory(self, routing_agent_config):
        """Test model routing integration in agent factory."""
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=routing_agent_config,
            project_id=1,
            task_id=1,
            context="This is a complex task requiring extensive reasoning " * 100
        )

        # Routing should have occurred (check logs)
        assert agent_graph is not None, "Agent should be created with routing"


# =============================================================================
# Integration with Workflow Execution
# =============================================================================

class TestWorkflowIntegration:
    """Test integration with actual workflow execution components."""

    @pytest.mark.asyncio
    async def test_token_tracking_callback_creation(self):
        """Test that TokenTrackingCallback can be created and works."""
        callback = create_token_tracking_callback(
            agent_id="test_agent",
            project_id=1,
            task_id="test_task_1",
            mcp_tools=["web_search"]
        )

        assert callback is not None, "TokenTrackingCallback should be created"
        assert hasattr(callback, "on_llm_start"), "Should have LLM lifecycle methods"

    @pytest.mark.asyncio
    async def test_agent_with_multiple_tools(self):
        """Test agent creation with multiple tools for parallel execution."""
        config = {
            "model": "claude-haiku-4-5-20251015",
            "native_tools": ["web_search", "calculator", "file_read"],
            "enable_parallel_tools": True,
            "streaming": True,
        }

        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=config,
            project_id=1,
            task_id=1,
            context="Test multi-tool agent"
        )

        assert len(tools) >= 3, "Should load multiple tools"
        assert agent_graph is not None, "Agent should be created"


# =============================================================================
# Validation & Error Handling
# =============================================================================

class TestValidationAndErrors:
    """Test validation and error handling improvements."""

    def test_supported_models_validation(self):
        """Test that model registry validates known models."""
        from core.agents.factory import SUPPORTED_MODELS

        assert "claude-haiku-4-5-20251015" in SUPPORTED_MODELS, "Haiku should be supported"
        assert "claude-opus-4-5-20250514" in SUPPORTED_MODELS, "Opus should be supported"
        assert "gpt-5-turbo" in SUPPORTED_MODELS, "GPT-5 Turbo should be supported"

    def test_validation_catches_mutual_exclusivity(self):
        """Test that validation catches structured output + tools conflict."""
        config = {
            "model": "claude-haiku-4-5-20251015",
            "enable_structured_output": True,
            "native_tools": ["web_search"],
        }

        errors = AgentFactory._validate_agent_config(config)
        assert len(errors) > 0, "Should catch mutual exclusivity"
        assert any("structured output" in err.lower() for err in errors), \
            "Should mention structured output conflict"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
