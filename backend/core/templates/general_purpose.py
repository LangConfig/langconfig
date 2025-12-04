# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
General Purpose Agent Template
===============================

A comprehensive agent template with access to all available tools.
This can serve as a foundation for creating specialized agents.
"""

from core.agents.templates import AgentTemplate, AgentCategory

GENERAL_PURPOSE_AGENT = AgentTemplate(
    template_id="general_purpose",
    name="General Purpose Assistant",
    description="""A versatile agent with access to all available tools.
    Can handle research, file operations, web browsing, memory management, and reasoning.
    
    WHEN TO USE:
    - General assistance tasks
    - When you need multiple tool capabilities
    - As a starting point for specialized workflows
    - For complex tasks requiring diverse tools""",
    category=AgentCategory.RESEARCH,
    
    # Model Configuration
    model="gpt-4o",  # Good balance of capability and cost
    fallback_models=["claude-sonnet-4-5-20250929", "gpt-5"],
    temperature=0.5,
    
    # System Prompt
    system_prompt="""ROLE: General Purpose AI Assistant
EXPERTISE: Web research, file operations, browser automation, memory management, structured reasoning.

GOAL: Assist with a wide variety of tasks using all available tools effectively.

AVAILABLE TOOLS:
- web_search: Search the web using DuckDuckGo (free, no API key required)
- web_fetch: Fetch content from URLs
- browser: Advanced browser automation with Playwright
- file_read: Read files from the filesystem
- file_write: Write files to the filesystem
- file_list: List files in directories
- memory_store: Store information for long-term recall
- memory_recall: Retrieve previously stored information
- reasoning_chain: Break down complex problems into steps

WORKFLOW APPROACH:
1. Use reasoning_chain to plan your approach
2. Use memory_recall to check for relevant prior knowledge
3. Execute the task using appropriate tools
4. Store important findings with memory_store
5. Provide clear, actionable results

BEST PRACTICES:
- Always verify information from multiple sources when researching
- Store key findings in memory for future reference
- Use browser tools for dynamic/JavaScript-heavy sites
- Use web_fetch for simple static content
- Organize file operations logically
- Break complex tasks into manageable steps

OUTPUT: Clear, well-structured responses with source citations when applicable.""",
    
    # All Available Tools
    mcp_tools=[
        "web_search",
        "web_fetch",
        "browser",
        "file_read",
        "file_write",
        "file_list",
        "memory_store",
        "memory_recall",
        "reasoning_chain"
    ],
    
    # Enhancement Flags
    enable_model_routing=True,  # Can use cheaper models for simple tasks
    enable_parallel_tools=True,  # Can run multiple tools in parallel
    enable_memory=True,  # Has memory tools enabled
    memory_types=["fact", "learning", "relationship", "pattern"],
    
    timeout_seconds=600,  # 10 minutes for complex tasks
    max_retries=2,
    
    tags=["general", "versatile", "all-tools", "research", "automation"],
    version="1.0.0"
)

# Export for use in other modules
__all__ = ["GENERAL_PURPOSE_AGENT"]