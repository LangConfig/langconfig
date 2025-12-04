# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Standalone validation test - no database required.
Tests that our changes work correctly.
"""

import sys
from enum import Enum

# Test 1: Import enums
print("Test 1: Importing enums...")
try:
    from models.enums import SubAgentType, MiddlewareType, BackendType, ReasoningEffort
    assert SubAgentType.DICTIONARY.value == "dictionary"
    assert SubAgentType.COMPILED.value == "compiled"
    assert MiddlewareType.TODO_LIST.value == "todo_list"
    assert BackendType.STATE.value == "state"
    assert ReasoningEffort.LOW.value == "low"
    print("✓ All enums imported and values correct")
except Exception as e:
    print(f"✗ Enum import failed: {e}")
    sys.exit(1)

# Test 2: Import models (syntax check)
print("\nTest 2: Importing models...")
try:
    from models.deep_agent import (
        DeepAgentConfig,
        SubAgentConfig,
        MiddlewareConfig,
        BackendConfig,
        GuardrailsConfig
    )
    print("✓ All models imported successfully")
except Exception as e:
    print(f"✗ Model import failed: {e}")
    sys.exit(1)

# Test 3: Create GuardrailsConfig with default token limits
print("\nTest 3: GuardrailsConfig default token limits...")
try:
    config = GuardrailsConfig()
    assert config.token_limits["summarization_threshold"] == 60000
    assert config.token_limits["eviction_threshold"] == 80000
    assert config.token_limits["max_total_tokens"] == 100000
    print("✓ Default token limits correct")
except Exception as e:
    print(f"✗ GuardrailsConfig failed: {e}")
    sys.exit(1)

# Test 4: Token limits ordering validation
print("\nTest 4: Token limits ordering validation...")
try:
    from pydantic import ValidationError
    try:
        bad_config = GuardrailsConfig(
            token_limits={
                "max_total_tokens": 100000,
                "eviction_threshold": 50000,
                "summarization_threshold": 80000  # Invalid: > eviction
            }
        )
        print("✗ Should have raised ValidationError")
        sys.exit(1)
    except ValidationError as e:
        assert "summarization_threshold" in str(e)
        print("✓ Token limits validator working")
except Exception as e:
    print(f"✗ Token limits validation test failed: {e}")
    sys.exit(1)

# Test 5: SubAgentConfig compiled needs workflow_id
print("\nTest 5: SubAgentConfig compiled needs workflow_id...")
try:
    from pydantic import ValidationError
    try:
        bad_subagent = SubAgentConfig(
            name="test",
            description="test",
            type=SubAgentType.COMPILED
            # Missing workflow_id
        )
        print("✗ Should have raised ValidationError")
        sys.exit(1)
    except ValidationError as e:
        assert "workflow_id" in str(e)
        print("✓ SubAgentConfig validator working")
except Exception as e:
    print(f"✗ SubAgentConfig validation test failed: {e}")
    sys.exit(1)

# Test 6: BackendConfig composite needs mappings
print("\nTest 6: BackendConfig composite needs mappings...")
try:
    from pydantic import ValidationError
    try:
        bad_backend = BackendConfig(type=BackendType.COMPOSITE)
        print("✗ Should have raised ValidationError")
        sys.exit(1)
    except ValidationError as e:
        assert "mappings" in str(e)
        print("✓ BackendConfig validator working")
except Exception as e:
    print(f"✗ BackendConfig validation test failed: {e}")
    sys.exit(1)

# Test 7: String-to-enum conversion
print("\nTest 7: String-to-enum auto-conversion...")
try:
    subagent = SubAgentConfig(
        name="test",
        description="test",
        type="dictionary"  # String input
    )
    assert subagent.type == SubAgentType.DICTIONARY
    assert isinstance(subagent.type, SubAgentType)
    print("✓ String-to-enum conversion working")
except Exception as e:
    print(f"✗ String-to-enum conversion failed: {e}")
    sys.exit(1)

# Test 8: Token limits independence
print("\nTest 8: Token limits default dict independence...")
try:
    config1 = GuardrailsConfig()
    config2 = GuardrailsConfig()
    config1.token_limits["max_total_tokens"] = 200000
    assert config2.token_limits["max_total_tokens"] == 100000
    print("✓ Token limits dicts are independent")
except Exception as e:
    print(f"✗ Token limits independence failed: {e}")
    sys.exit(1)

# Test 9: Valid compiled subagent with workflow_id
print("\nTest 9: Valid compiled subagent...")
try:
    subagent = SubAgentConfig(
        name="test",
        description="test",
        type=SubAgentType.COMPILED,
        workflow_id=123
    )
    assert subagent.type == SubAgentType.COMPILED
    assert subagent.workflow_id == 123
    print("✓ Compiled subagent with workflow_id valid")
except Exception as e:
    print(f"✗ Compiled subagent test failed: {e}")
    sys.exit(1)

# Test 10: Helper functions use enums
print("\nTest 10: Helper functions use enums...")
try:
    from models.deep_agent import create_default_middleware_config, create_default_backend_config
    middleware_configs = create_default_middleware_config()
    assert middleware_configs[0].type == MiddlewareType.TODO_LIST
    assert isinstance(middleware_configs[0].type, MiddlewareType)

    backend_config = create_default_backend_config()
    assert backend_config.type == BackendType.COMPOSITE
    assert isinstance(backend_config.type, BackendType)
    print("✓ Helper functions use enum types")
except Exception as e:
    print(f"✗ Helper functions test failed: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ ALL TESTS PASSED!")
print("="*60)
print("\nSummary:")
print("  ✓ Enums created and working")
print("  ✓ Models updated with enum types")
print("  ✓ Token limits use default dict (not lambda)")
print("  ✓ Three validators working correctly:")
print("    - SubAgentConfig: compiled needs workflow_id")
print("    - GuardrailsConfig: token limits ordering")
print("    - BackendConfig: composite needs mappings")
print("  ✓ String-to-enum auto-conversion working")
print("  ✓ Helper functions use enums")
print("\n🎉 All 10 code review issues fixed successfully!")
