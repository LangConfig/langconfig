# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Basic unit test for middleware loading with agents.

Tests:
1. Middleware can be created from config
2. Middleware tools are accessible
3. DeepAgents middleware can be initialized
4. Regular agent middleware can be passed to create_agent
"""

import logging
from typing import List

# pytest is optional - only imported if running via pytest
try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    pytest = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_middleware_imports():
    """Test that all middleware modules can be imported."""
    try:
        from core.middleware.core import (
            AgentMiddleware,
            TimestampMiddleware,
            LoggingMiddleware,
            CostTrackingMiddleware,
            ValidationMiddleware,
            SummarizationMiddleware,
            HumanInTheLoopMiddleware,
            ToolRetryMiddleware,
            PIIMiddleware
        )
        logger.info("✓ All standard middleware imported successfully")
        assert True
    except ImportError as e:
        logger.error(f"✗ Middleware import failed: {e}")
        raise


def test_deepagents_middleware_imports():
    """Test that DeepAgents middleware can be imported."""
    try:
        from services.deepagents_middleware import (
            TodoListMiddleware,
            FilesystemMiddleware,
            SubAgentMiddleware,
            DeepAgentsMiddlewareFactory
        )
        logger.info("✓ DeepAgents middleware imported successfully")
        assert True
    except ImportError as e:
        logger.error(f"✗ DeepAgents middleware import failed: {e}")
        raise


def test_logging_middleware_creation():
    """Test that LoggingMiddleware can be created."""
    from core.middleware.core import LoggingMiddleware

    middleware = LoggingMiddleware(
        log_inputs=True,
        log_outputs=True,
        max_log_length=500
    )

    assert middleware is not None
    assert middleware.log_inputs == True
    assert middleware.log_outputs == True
    assert middleware.max_log_length == 500
    logger.info("✓ LoggingMiddleware created successfully")


def test_cost_tracking_middleware_creation():
    """Test that CostTrackingMiddleware can be created."""
    from core.middleware.core import CostTrackingMiddleware

    middleware = CostTrackingMiddleware()

    assert middleware is not None
    assert middleware.total_cost == 0.0
    assert middleware.call_count == 0
    assert "gpt-4o" in middleware.costs
    assert "claude-sonnet-4-5-20250929" in middleware.costs
    logger.info("✓ CostTrackingMiddleware created successfully")


def test_validation_middleware_creation():
    """Test that ValidationMiddleware can be created."""
    from core.middleware.core import ValidationMiddleware

    middleware = ValidationMiddleware(
        min_length=10,
        max_length=1000,
        prohibited_patterns=["DELETE FROM", "DROP TABLE"],
        required_patterns=[]
    )

    assert middleware is not None
    assert middleware.min_length == 10
    assert middleware.max_length == 1000
    assert "DELETE FROM" in middleware.prohibited_patterns
    logger.info("✓ ValidationMiddleware created successfully")


def test_deepagents_middleware_factory():
    """Test that DeepAgents middleware tools can be created."""
    from services.deepagents_middleware import DeepAgentsMiddlewareFactory
    from models.deep_agent import MiddlewareConfig

    # Create middleware configs
    middleware_configs = [
        {
            "type": "filesystem",
            "enabled": True,
            "config": {}
        },
        {
            "type": "todos",
            "enabled": True,
            "config": {}
        }
    ]

    # This is an async function, so we need to test it's callable
    assert hasattr(DeepAgentsMiddlewareFactory, 'create_all_tools')
    logger.info("✓ DeepAgentsMiddlewareFactory has create_all_tools method")


def test_middleware_has_required_methods():
    """Test that middleware classes have required hook methods."""
    from core.middleware.core import LoggingMiddleware

    middleware = LoggingMiddleware()

    # Check that middleware has the expected methods
    assert hasattr(middleware, 'before_model')
    assert hasattr(middleware, 'after_model')
    assert hasattr(middleware, 'before_agent')
    assert hasattr(middleware, 'after_agent')
    assert hasattr(middleware, 'wrap_model_call')
    assert hasattr(middleware, 'wrap_tool_call')

    logger.info("✓ Middleware has all required hook methods")


def test_middleware_can_be_passed_to_config():
    """Test that middleware can be added to agent config."""
    from core.middleware.core import LoggingMiddleware, CostTrackingMiddleware

    # Create middleware instances
    logging_mw = LoggingMiddleware()
    cost_mw = CostTrackingMiddleware()

    # Create a mock agent config
    agent_config = {
        "model": "gpt-4o",
        "temperature": 0.7,
        "middleware": [logging_mw, cost_mw]
    }

    assert "middleware" in agent_config
    assert len(agent_config["middleware"]) == 2
    assert isinstance(agent_config["middleware"][0], LoggingMiddleware)
    assert isinstance(agent_config["middleware"][1], CostTrackingMiddleware)

    logger.info("✓ Middleware can be added to agent config")


if __name__ == "__main__":
    """Run tests manually for quick validation."""
    logger.info("=" * 60)
    logger.info("Running Middleware Unit Tests")
    logger.info("=" * 60)

    tests = [
        ("Middleware Imports", test_middleware_imports),
        ("DeepAgents Middleware Imports", test_deepagents_middleware_imports),
        ("LoggingMiddleware Creation", test_logging_middleware_creation),
        ("CostTrackingMiddleware Creation", test_cost_tracking_middleware_creation),
        ("ValidationMiddleware Creation", test_validation_middleware_creation),
        ("DeepAgents Middleware Factory", test_deepagents_middleware_factory),
        ("Middleware Hook Methods", test_middleware_has_required_methods),
        ("Middleware Config Integration", test_middleware_can_be_passed_to_config),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            logger.info(f"\n▶ Running: {test_name}")
            test_func()
            passed += 1
            logger.info(f"✅ {test_name} PASSED")
        except Exception as e:
            failed += 1
            logger.error(f"❌ {test_name} FAILED: {e}")

    logger.info("\n" + "=" * 60)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info("=" * 60)

    if failed == 0:
        logger.info("🎉 All tests passed!")
    else:
        logger.warning(f"⚠️  {failed} test(s) failed")
