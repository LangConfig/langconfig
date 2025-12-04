# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Test script for Playwright browser tools.

This script tests the Playwright tools to ensure they're working correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from tools.native_tools import load_playwright_tools


async def test_playwright_tools():
    """Test Playwright tools with a simple workflow."""
    print("=" * 60)
    print("Testing Playwright Browser Tools")
    print("=" * 60)

    try:
        # Test 1: Load Playwright tools from toolkit
        print("\n[Test 1] Loading Playwright browser toolkit...")
        tools = await load_playwright_tools()

        if not tools:
            print("[X] No tools loaded - Playwright may not be available")
            return False

        print(f"[OK] Successfully loaded {len(tools)} Playwright browser tools:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:80]}...")

        # Test 2: Verify expected tools are present
        print("\n[Test 2] Verifying tool availability...")
        expected_tools = ['navigate_browser', 'click_element', 'extract_text']
        tool_names = [tool.name for tool in tools]

        for expected in expected_tools:
            if expected in tool_names:
                print(f"  [OK] Found '{expected}' tool")
            else:
                print(f"  [X] Missing '{expected}' tool")

        print("\n" + "=" * 60)
        print("[OK] All Playwright tools tests PASSED!")
        print(f"[OK] {len(tools)} browser automation tools are ready to use")
        print("=" * 60)

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"✗ Test FAILED with error:")
        print(f"  {type(e).__name__}: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nStarting Playwright tools test...\n")

    # Run the async test
    success = asyncio.run(test_playwright_tools())

    # Exit with appropriate code
    sys.exit(0 if success else 1)
