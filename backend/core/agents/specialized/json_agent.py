# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
JSON Query Agent for LangConfig

Enables natural language querying of complex, nested JSON structures.
Uses LangChain's JsonToolkit for navigating and extracting data from JSON.

Features:
- Navigate nested JSON structures
- Extract specific values or patterns
- Count, filter, and aggregate JSON data
- Explain JSON schema
- Handle large JSON documents

Example:
    >>> api_response = {"users": [...], "metadata": {...}}
    >>> agent = await create_json_agent(api_response)
    >>> result = await agent.ainvoke({
    ...     "messages": [HumanMessage(content="How many users are active?")]
    ... })
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union
from langchain_community.agent_toolkits import JsonToolkit, create_json_agent
from langchain_community.tools.json.tool import JsonSpec
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# System prompt for JSON agent
JSON_AGENT_PROMPT = """You are a JSON data specialist.

Your capabilities:
- Navigate complex nested JSON structures
- Extract specific values or patterns
- Count, filter, and aggregate JSON data
- Explain JSON schema and structure
- Handle large JSON documents efficiently

WORKFLOW:
1. Understand the JSON structure first (examine keys and nesting)
2. Navigate to relevant sections
3. Extract or compute what's needed
4. Provide clear answers in plain English

When working with JSON:
- Show your navigation path (e.g., "data.users[0].profile.email")
- Handle missing keys gracefully
- Provide examples of extracted data
- Explain the structure when relevant

Available operations:
- Get value at path: json_spec_get_value
- List keys at path: json_spec_list_keys
- Navigate nested objects
- Search for patterns
- Count array elements
- Filter and aggregate

Always explain:
- What you're looking for
- Where you found it (path)
- The structure around it
"""


async def create_json_agent(
    json_data: Union[Dict, List, str],
    llm_model: str = "gpt-4o",
    temperature: float = 0.0,
    max_value_length: int = 4000
) -> CompiledStateGraph:
    """
    Create an agent for working with complex JSON data.

    This agent can navigate, query, and explain JSON structures using
    natural language.

    Args:
        json_data: JSON object to work with (dict, list, or JSON string)
        llm_model: LLM to use (default: gpt-4o for precise extraction)
        temperature: Temperature for generation (default: 0.0 for deterministic results)
        max_value_length: Maximum length of values to return (default: 4000)

    Returns:
        Compiled LangGraph agent ready to query JSON

    Example:
        >>> # From dict
        >>> data = {"users": [{"name": "Alice", "age": 30}], "count": 1}
        >>> agent = await create_json_agent(data)

        >>> # From JSON string
        >>> json_str = '{"status": "success", "data": {...}}'
        >>> agent = await create_json_agent(json_str)

        >>> # Query the data
        >>> result = await agent.ainvoke({
        ...     "messages": [HumanMessage(content="What is the first user's name?")]
        ... })
        >>> print(result["messages"][-1].content)
        # "The first user's name is Alice, found at path: users[0].name"

    Use Cases:
        - API response analysis
        - Config file querying
        - Log file parsing
        - Data extraction from nested structures
        - JSON schema exploration
    """

    logger.info(f"Creating JSON query agent (max_value_length={max_value_length})")

    try:
        # Parse JSON if string
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
                logger.info("✓ Parsed JSON string")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string: {e}")

        # Validate JSON data
        if not isinstance(json_data, (dict, list)):
            raise ValueError(f"json_data must be dict, list, or JSON string, got {type(json_data)}")

        # Log structure info
        if isinstance(json_data, dict):
            logger.info(f"JSON object with {len(json_data)} top-level keys: {list(json_data.keys())[:5]}")
        elif isinstance(json_data, list):
            logger.info(f"JSON array with {len(json_data)} elements")

        # Create JSON spec
        json_spec = JsonSpec(dict_=json_data, max_value_length=max_value_length)

        # Create toolkit
        toolkit = JsonToolkit(spec=json_spec)
        tools = toolkit.get_tools()

        logger.info(f"✓ Loaded {len(tools)} JSON tools")
        for tool in tools:
            logger.debug(f"  - {tool.name}: {tool.description}")

        # Create LLM instance
        if llm_model.startswith("claude"):
            llm = ChatAnthropic(
                model=llm_model,
                temperature=temperature,
                max_tokens=4096
            )
        else:
            llm = ChatOpenAI(
                model=llm_model,
                temperature=temperature,
                max_tokens=4096
            )

        logger.info(f"✓ Using LLM: {llm_model} (temperature={temperature})")

        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", JSON_AGENT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ])

        # Create agent (v1.0: no pre-binding)
        agent = create_agent(
            model=llm,  # v1.0: Pass unbound model
            tools=tools,
            state_modifier=prompt_template  # v1.0: use state_modifier
        )

        logger.info("✓ JSON query agent created successfully")

        return agent

    except Exception as e:
        logger.error(f"Failed to create JSON agent: {e}", exc_info=True)
        raise ValueError(f"Failed to create JSON agent: {e}")


async def query_json(
    json_data: Union[Dict, List, str],
    query: str,
    llm_model: str = "gpt-4o",
    include_schema: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to query JSON with natural language.

    Args:
        json_data: JSON data (dict, list, or string)
        query: Natural language question
        llm_model: LLM to use
        include_schema: Include JSON schema in response

    Returns:
        Dictionary with query, answer, and optional schema

    Example:
        >>> data = {"users": [{"name": "Alice", "active": True}]}
        >>> result = await query_json(data, "How many active users?")
        >>> print(result["answer"])
    """

    # Create agent
    agent = await create_json_agent(json_data, llm_model=llm_model)

    # Execute query
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=query)]
    })

    # Extract response
    response = {
        "query": query,
        "answer": result["messages"][-1].content if result.get("messages") else "No response",
        "model": llm_model
    }

    if include_schema:
        response["schema"] = get_json_schema(json_data)

    return response


def get_json_schema(json_data: Union[Dict, List]) -> Dict[str, Any]:
    """
    Generate a schema description for JSON data.

    Args:
        json_data: JSON data

    Returns:
        Schema information

    Example:
        >>> schema = get_json_schema({"users": [...], "count": 1})
        >>> print(schema["structure"])
    """

    def analyze_structure(data, depth=0, max_depth=3):
        """Recursively analyze JSON structure."""

        if depth > max_depth:
            return "..."

        if isinstance(data, dict):
            return {
                key: analyze_structure(value, depth + 1, max_depth)
                for key, value in list(data.items())[:10]  # Limit to first 10 keys
            }
        elif isinstance(data, list):
            if len(data) == 0:
                return []
            elif len(data) == 1:
                return [analyze_structure(data[0], depth + 1, max_depth)]
            else:
                # Show first item structure
                return [analyze_structure(data[0], depth + 1, max_depth), f"... {len(data) - 1} more items"]
        else:
            return type(data).__name__

    return {
        "type": "object" if isinstance(json_data, dict) else "array",
        "structure": analyze_structure(json_data),
        "size": {
            "keys": len(json_data) if isinstance(json_data, dict) else None,
            "items": len(json_data) if isinstance(json_data, list) else None,
            "estimated_bytes": len(json.dumps(json_data))
        }
    }


def extract_json_paths(json_data: Union[Dict, List], max_depth: int = 5) -> List[str]:
    """
    Extract all JSON paths from data.

    Args:
        json_data: JSON data
        max_depth: Maximum depth to traverse

    Returns:
        List of paths (e.g., ["users[0].name", "users[0].age", ...])

    Example:
        >>> paths = extract_json_paths({"users": [{"name": "Alice"}]})
        >>> print(paths)
        # ["users", "users[0]", "users[0].name"]
    """

    paths = []

    def traverse(data, current_path="", depth=0):
        """Recursively traverse JSON and collect paths."""

        if depth > max_depth:
            return

        if isinstance(data, dict):
            if current_path:
                paths.append(current_path)

            for key, value in data.items():
                new_path = f"{current_path}.{key}" if current_path else key
                traverse(value, new_path, depth + 1)

        elif isinstance(data, list):
            if current_path:
                paths.append(current_path)

            for i, item in enumerate(data[:100]):  # Limit array traversal
                new_path = f"{current_path}[{i}]"
                traverse(item, new_path, depth + 1)

        else:
            # Leaf node
            if current_path:
                paths.append(current_path)

    traverse(json_data)
    return paths


async def analyze_json_structure(
    json_data: Union[Dict, List, str],
    include_paths: bool = True,
    include_sample_values: bool = True
) -> Dict[str, Any]:
    """
    Analyze and describe JSON structure.

    Args:
        json_data: JSON data
        include_paths: Include all JSON paths
        include_sample_values: Include sample values

    Returns:
        Comprehensive structure analysis

    Example:
        >>> analysis = await analyze_json_structure({"users": [...]})
        >>> print(f"Type: {analysis['type']}")
        >>> print(f"Depth: {analysis['max_depth']}")
    """

    # Parse if string
    if isinstance(json_data, str):
        json_data = json.loads(json_data)

    def get_max_depth(data, current_depth=0):
        """Calculate maximum nesting depth."""
        if isinstance(data, dict):
            if not data:
                return current_depth
            return max(get_max_depth(v, current_depth + 1) for v in data.values())
        elif isinstance(data, list):
            if not data:
                return current_depth
            return max(get_max_depth(item, current_depth + 1) for item in data[:10])
        else:
            return current_depth

    analysis = {
        "type": "object" if isinstance(json_data, dict) else "array",
        "max_depth": get_max_depth(json_data),
        "size_bytes": len(json.dumps(json_data)),
        "schema": get_json_schema(json_data)
    }

    if include_paths:
        analysis["paths"] = extract_json_paths(json_data)
        analysis["path_count"] = len(analysis["paths"])

    if include_sample_values and isinstance(json_data, dict):
        # Get sample values for top-level keys
        analysis["sample_values"] = {
            key: str(value)[:100]
            for key, value in list(json_data.items())[:5]
        }

    return analysis
