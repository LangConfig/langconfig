# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Test API key loading from .env and database"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from config import settings

def test_api_keys():
    print("Testing API key configuration...")
    print(f"Database URL: {settings.database_url}")
    print()

    # Test OpenAI API key
    openai_key = settings.OPENAI_API_KEY
    if openai_key:
        print(f"[OK] OpenAI API Key loaded: {openai_key[:8]}...{openai_key[-4:]}")
    else:
        print("[MISSING] OpenAI API Key not found")

    # Test Anthropic API key
    anthropic_key = settings.ANTHROPIC_API_KEY
    if anthropic_key:
        print(f"[OK] Anthropic API Key loaded: {anthropic_key[:8]}...{anthropic_key[-4:]}")
    else:
        print("[MISSING] Anthropic API Key not found")

    # Test Google/Gemini API key
    google_key = settings.GOOGLE_API_KEY
    if google_key:
        print(f"[OK] Google API Key loaded: {google_key[:8]}...{google_key[-4:]}")
    else:
        print("[MISSING] Google API Key not found")

    print()
    if all([openai_key, anthropic_key, google_key]):
        print("SUCCESS: All API keys loaded successfully!")
    else:
        print("WARNING: Some API keys are missing")

if __name__ == '__main__':
    test_api_keys()
