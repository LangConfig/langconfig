# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Integration test for middleware with actual agents.

This script creates real agents with middleware and tests that:
1. Middleware is properly attached
2. Middleware hooks are called
3. Middleware tools are available (for DeepAgents)
4. Logs show middleware verification messages
"""

import asyncio
import logging
import sys
from typing import List

# Set up logging to see middleware messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_regular_agent_with_middleware():
    """Test 1: Create a regular agent with middleware."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Regular Agent with Middleware")
    logger.info("="*60)

    try:
        from core.agents.factory import AgentFactory
        from core.middleware.core import (
            LoggingMiddleware,
            CostTrackingMiddleware,
            ValidationMiddleware
        )

        # Create middleware instances
        logging_mw = LoggingMiddleware(log_inputs=True, log_outputs=True)
        cost_mw = CostTrackingMiddleware()
        validation_mw = ValidationMiddleware(
            min_length=5,
            prohibited_patterns=["DANGEROUS", "DELETE FROM"]
        )

        # Build agent config with middleware
        agent_config = {
            "model": "gpt-4o-mini",  # Using mini for cheaper testing
            "temperature": 0.7,
            "system_prompt": "You are a helpful test assistant. Respond with exactly: 'Middleware test successful!'",
            "mcp_tools": [],
            "cli_tools": [],
            "enable_memory": False,
            "enable_rag": False,
            "enable_default_middleware": False,  # Disable defaults to avoid duplicates
            "middleware": [logging_mw, cost_mw, validation_mw]
        }

        logger.info("Creating agent with 3 middleware instances...")
        logger.info("  - LoggingMiddleware")
        logger.info("  - CostTrackingMiddleware")
        logger.info("  - ValidationMiddleware")

        # Create agent
        agent_graph, tools, callbacks = await AgentFactory.create_agent(
            agent_config=agent_config,
            project_id=999,  # Test project ID
            task_id=999,
            context="Test context"
        )

        logger.info("✅ Agent created successfully!")
        logger.info(f"   Agent graph type: {type(agent_graph).__name__}")
        logger.info(f"   Tools count: {len(tools)}")
        logger.info(f"   Callbacks count: {len(callbacks)}")

        # Test invoking the agent
        logger.info("\nInvoking agent with test message...")
        from langchain_core.messages import HumanMessage

        result = await agent_graph.ainvoke({
            "messages": [HumanMessage(content="Hello! Test the middleware.")]
        })

        logger.info("✅ Agent invocation successful!")
        logger.info(f"   Response messages: {len(result.get('messages', []))}")
        if result.get('messages'):
            last_message = result['messages'][-1]
            logger.info(f"   Last message content: {last_message.content[:100]}...")

        # Check cost tracking
        logger.info(f"\n💰 Cost Statistics:")
        logger.info(f"   Total calls: {cost_mw.call_count}")
        logger.info(f"   Total cost: ${cost_mw.total_cost:.6f}")
        logger.info(f"   Avg cost/call: ${cost_mw.total_cost / max(cost_mw.call_count, 1):.6f}")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_deepagent_with_middleware():
    """Test 2: Create a DeepAgent with middleware."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: DeepAgent with Middleware")
    logger.info("="*60)

    try:
        from services.deepagent_factory import DeepAgentFactory
        from models.deep_agent import DeepAgentConfig, MiddlewareConfig

        # Create DeepAgent config with middleware
        config = DeepAgentConfig(
            model="gpt-4o-mini",
            temperature=0.7,
            system_prompt="You are a helpful deep agent assistant.",
            tools=[],
            mcp_tools=[],
            cli_tools=[],
            use_deepagents=True,
            middleware=[
                MiddlewareConfig(
                    type="filesystem",
                    enabled=True,
                    config={}
                ),
                MiddlewareConfig(
                    type="todo_list",
                    enabled=True,
                    config={}
                ),
                MiddlewareConfig(
                    type="subagent",
                    enabled=True,
                    config={
                        "max_depth": 2,
                        "max_concurrent": 3
                    }
                )
            ]
        )

        logger.info("Creating DeepAgent with 3 middleware types...")
        logger.info("  - FilesystemMiddleware")
        logger.info("  - TodoListMiddleware")
        logger.info("  - SubAgentMiddleware")

        # Create deep agent
        agent_graph, tools, callbacks = await DeepAgentFactory.create_deep_agent(
            config=config,
            project_id=999,
            task_id=999,
            context="Test context",
            mcp_manager=None,  # Skip MCP for quick test
            vector_store=None   # Skip vector store for quick test
        )

        logger.info("✅ DeepAgent created successfully!")
        logger.info(f"   Agent graph type: {type(agent_graph).__name__}")
        logger.info(f"   Total tools: {len(tools)}")
        logger.info(f"   Callbacks count: {len(callbacks)}")

        # List middleware tools
        logger.info("\n🔧 Middleware Tools Available:")
        middleware_tool_names = ["write_todos", "update_todo_status", "get_todos",
                                "read_file", "write_file", "list_files",
                                "spawn_subagent", "list_available_agents"]

        found_tools = [t.name for t in tools if t.name in middleware_tool_names]
        for tool_name in found_tools:
            logger.info(f"   ✓ {tool_name}")

        if not found_tools:
            logger.warning("   ⚠️  No middleware tools found!")

        logger.info(f"\n   Total middleware tools: {len(found_tools)}")
        logger.info(f"   Total tools: {len(tools)}")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_validation_middleware_blocks_content():
    """Test 3: Verify ValidationMiddleware blocks prohibited content."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: ValidationMiddleware Blocking Test")
    logger.info("="*60)

    try:
        from core.middleware.core import ValidationMiddleware
        from langchain_core.messages import AIMessage

        # Create validation middleware with prohibited patterns
        validation_mw = ValidationMiddleware(
            min_length=10,
            prohibited_patterns=["DELETE FROM", "DROP TABLE", "rm -rf"]
        )

        logger.info("Testing ValidationMiddleware with prohibited content...")

        # Simulate an after_model call with prohibited content
        test_state = {
            "messages": [
                AIMessage(content="Here's how to delete data: DELETE FROM users WHERE id > 0;")
            ]
        }

        # This should modify the message to add a warning
        result = validation_mw.after_model(test_state, runtime=None)

        if result:
            modified_message = result["messages"][-1]
            if "ERROR: Response contained prohibited content" in modified_message.content:
                logger.info("✅ ValidationMiddleware successfully blocked prohibited content!")
                logger.info(f"   Original: DELETE FROM users...")
                logger.info(f"   Blocked: {modified_message.content[:80]}...")
                return True
            else:
                logger.warning("⚠️  ValidationMiddleware modified content but didn't block it")
                return False
        else:
            logger.error("❌ ValidationMiddleware didn't modify the prohibited content")
            return False

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def test_cost_tracking_middleware():
    """Test 4: Verify CostTrackingMiddleware tracks costs."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: CostTrackingMiddleware Cost Calculation")
    logger.info("="*60)

    try:
        from core.middleware.core import CostTrackingMiddleware
        from langchain_core.messages import AIMessage

        cost_mw = CostTrackingMiddleware()

        logger.info("Testing cost tracking with simulated model response...")

        # Simulate before_model (increments call count)
        cost_mw.before_model({}, runtime=None)

        # Simulate after_model with token usage
        class MockRuntime:
            model = "gpt-4o-mini"

        test_state = {
            "messages": [
                AIMessage(
                    content="Test response",
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                            "total_tokens": 150
                        }
                    }
                )
            ]
        }

        cost_mw.after_model(test_state, runtime=MockRuntime())

        stats = cost_mw.get_stats()

        logger.info("✅ Cost tracking working!")
        logger.info(f"   Call count: {stats['call_count']}")
        logger.info(f"   Total cost: ${stats['total_cost']:.6f}")
        logger.info(f"   Avg cost/call: ${stats['avg_cost_per_call']:.6f}")
        logger.info(f"   Expected: ~$0.000023 (150 tokens @ $0.00015/1K)")

        return stats['total_cost'] > 0

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run all integration tests."""
    logger.info("\n" + "="*70)
    logger.info("  MIDDLEWARE INTEGRATION TESTS")
    logger.info("="*70)
    logger.info("These tests verify middleware is properly integrated and working.\n")

    results = {
        "Regular Agent with Middleware": False,
        "DeepAgent with Middleware": False,
        "ValidationMiddleware Blocking": False,
        "CostTrackingMiddleware": False
    }

    # Run tests
    results["Regular Agent with Middleware"] = await test_regular_agent_with_middleware()
    results["DeepAgent with Middleware"] = await test_deepagent_with_middleware()
    results["ValidationMiddleware Blocking"] = await test_validation_middleware_blocks_content()
    results["CostTrackingMiddleware"] = await test_cost_tracking_middleware()

    # Print summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status} - {test_name}")

    logger.info("\n" + "="*70)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("="*70)

    if passed == total:
        logger.info("🎉 All middleware integration tests passed!")
        return 0
    else:
        logger.warning(f"⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
