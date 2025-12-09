# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Simple AI-powered agent configuration generator for v1 alpha.
Uses OpenAI API directly to generate agent configs quickly.
"""
import json
import os
from typing import Optional
from pydantic import BaseModel
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class GenerateAgentRequest(BaseModel):
    """Request model for agent generation"""
    name: str
    description: str
    agent_type: str  # "regular" or "deep"
    category: Optional[str] = None


class GeneratedAgentConfig(BaseModel):
    """Generated agent configuration"""
    model: str
    temperature: float
    system_prompt: str
    mcp_tools: list[str]
    reasoning: str
    confidence_score: float = 0.8


async def generate_agent_config(request: GenerateAgentRequest) -> dict:
    """
    Generate agent configuration using OpenAI GPT-4o.

    Args:
        request: Generation request with name, description, agent_type

    Returns:
        Generated agent configuration as dict
    """
    # Available options
    available_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5",
        "gemini-2.0-flash-exp"
    ]

    # DeepAgents standard filesystem tool names
    available_tools = [
        "read_file",
        "write_file",
        "ls",
        "edit_file",
        "glob",
        "grep",
        "web_search",
        "web_fetch",
        "browser",
        "reasoning_chain",
        "memory_store",
        "memory_recall"
    ]

    # Build context-aware prompt
    agent_type_context = ""
    if request.agent_type == "regular":
        agent_type_context = """
This is a REGULAR AGENT (LangChain AgentExecutor):
- Simple, single-agent tasks
- Tool calling with basic iteration control
- Suitable for focused tasks like code generation, testing, research
- Keep configuration simple and focused
"""
    else:  # deep
        agent_type_context = """
This is a DEEP AGENT (LangGraph StateGraph):
- Complex multi-step workflows
- Can use middleware, subagents, persistent storage
- Suitable for long-running tasks, multi-agent coordination
- More advanced configuration available
"""

    prompt = f"""You are an expert AI agent configuration specialist for LangConfig.

Generate an optimal agent configuration for:
**Name:** {request.name}
**Description:** {request.description}
**Category:** {request.category or 'Not specified'}

{agent_type_context}

**Available Models:** {', '.join(available_models)}
**Available MCP Tools:** {', '.join(available_tools)}

INSTRUCTIONS:
1. Select the best model for this task:
   - gpt-4o: Complex reasoning, code generation, architecture
   - gpt-4o-mini: Simple tasks, cost-effective
   - claude-sonnet-4-5-20250929: Long context, detailed analysis
   - claude-haiku-4-5: Fast, simple tasks
   - gemini-2.0-flash-exp: Multimodal, fast prototyping

2. Choose appropriate temperature (0.0-1.0):
   - 0.0-0.3: Deterministic tasks (code, SQL, testing)
   - 0.4-0.7: Balanced creativity (general tasks, research)
   - 0.8-1.0: Creative tasks (brainstorming, content generation)

3. Select ONLY the MCP tools actually needed (from available list above)
   - read_file: Read file contents with line numbers
   - write_file: Create new files
   - ls: List directory contents with metadata
   - edit_file: Perform exact string replacements in files
   - glob: Find files matching patterns
   - grep: Search file contents with regex
   - web_search: Search the web for information
   - web_fetch: Fetch content from URLs
   - browser: Automated browser actions (scraping, screenshots)
   - reasoning_chain: Step-by-step reasoning and planning
   - memory_store: Save information for later recall
   - memory_recall: Retrieve stored memories

4. Create a comprehensive, role-based system prompt that:
   - Clearly defines the agent's role and expertise
   - Specifies expected output format
   - Includes relevant constraints or guidelines
   - Is 2-4 paragraphs, detailed but focused

5. Provide clear reasoning for your choices

Return ONLY valid JSON with this exact structure:
{{
    "model": "selected_model_id",
    "temperature": 0.7,
    "system_prompt": "Detailed system prompt here...",
    "mcp_tools": ["tool1", "tool2"],
    "reasoning": "I chose gpt-4o because... temperature 0.7 for... tools selected because...",
    "confidence_score": 0.85
}}

IMPORTANT: Return ONLY the JSON object, no markdown, no explanations outside the JSON.
"""

    try:
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        client = OpenAI(api_key=api_key)

        logger.info(f"Generating agent config for: {request.name}")

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert AI agent configuration specialist. You generate optimal agent configurations based on requirements. Always return valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        # Parse response
        generated_json = response.choices[0].message.content
        generated_config = json.loads(generated_json)

        logger.info(f"Successfully generated config. Model: {generated_config.get('model')}, Tools: {generated_config.get('mcp_tools')}")

        # Validate the generated config
        validated_config = GeneratedAgentConfig(**generated_config)

        return validated_config.model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from OpenAI response: {e}")
        raise ValueError(f"AI generated invalid JSON: {str(e)}")
    except Exception as e:
        logger.error(f"Agent generation failed: {e}")
        raise ValueError(f"Agent generation failed: {str(e)}")
