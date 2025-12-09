#!/usr/bin/env python
# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
List All Available Tools
========================

This script lists all available tools that agents can use.
"""

# Hardcoded list since imports may fail
# DeepAgents standard filesystem tool names
AVAILABLE_TOOLS = [
    "web_search",
    "web_fetch",
    "browser",
    "read_file",
    "write_file",
    "ls",
    "edit_file",
    "glob",
    "grep",
    "memory_store",
    "memory_recall",
    "reasoning_chain",
]

TOOL_NAME_MAP = {
    "web": "web_search",
    "fetch": "web_fetch",
    "filesystem": "read_file",
    "memory": "memory_store",
    "sequential_thinking": "reasoning_chain",
    "thinking": "reasoning_chain",
    "reasoning": "reasoning_chain",
    # Legacy aliases for backwards compatibility
    "file_read": "read_file",
    "file_write": "write_file",
    "file_list": "ls",
}

def main():
    print("=" * 60)
    print("AVAILABLE TOOLS FOR AGENTS")
    print("=" * 60)
    
    # Get available tools
    tools = AVAILABLE_TOOLS
    
    print("\n✅ DIRECTLY AVAILABLE TOOLS:")
    print("-" * 30)
    for i, tool in enumerate(tools, 1):
        print(f"{i}. {tool}")
    
    print(f"\nTotal: {len(tools)} tools available")
    
    print("\n📝 TOOL NAME MAPPINGS (for backward compatibility):")
    print("-" * 30)
    unique_mappings = {}
    for old_name, new_name in TOOL_NAME_MAP.items():
        if old_name != new_name:
            if new_name not in unique_mappings:
                unique_mappings[new_name] = []
            unique_mappings[new_name].append(old_name)
    
    for new_name, old_names in unique_mappings.items():
        print(f"• {new_name} <- {', '.join(old_names)}")
    
    print("\n💡 USAGE IN AGENT TEMPLATES:")
    print("-" * 30)
    print("mcp_tools=[")
    for tool in tools:
        print(f'    "{tool}",')
    print("]")
    
    print("\n📚 TOOL DESCRIPTIONS:")
    print("-" * 30)
    descriptions = {
        "web_search": "Search the web using DuckDuckGo (FREE, no API key)",
        "web_fetch": "Fetch webpage content via HTTP",
        "browser": "Playwright browser automation (navigate, click, extract)",
        "read_file": "Read file contents with line numbers",
        "write_file": "Create new files",
        "ls": "List directory contents with metadata",
        "edit_file": "Perform exact string replacements in files",
        "glob": "Find files matching patterns",
        "grep": "Search file contents with regex",
        "memory_store": "Store information in PostgreSQL for long-term memory",
        "memory_recall": "Recall information from PostgreSQL memory",
        "reasoning_chain": "Structured reasoning and task decomposition"
    }
    
    for tool in tools:
        desc = descriptions.get(tool, "No description available")
        print(f"• {tool}: {desc}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()