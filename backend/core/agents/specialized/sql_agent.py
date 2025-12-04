# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
SQL Database Agent for LangConfig

Enables natural language SQL database queries using LangChain's SQLDatabaseToolkit.
This allows users to query databases without writing SQL directly.

Features:
- Read-only operations (SELECT only)
- Schema examination
- Safe query execution
- Results explanation

Example:
    >>> agent = await create_sql_agent("postgresql://user:pass@localhost:5432/mydb")
    >>> result = await agent.ainvoke({
    ...     "messages": [HumanMessage(content="Show me all users who signed up last week")]
    ... })
"""

import logging
from typing import Optional, Dict, Any
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_agent
from langgraph.graph.state import CompiledStateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

logger = logging.getLogger(__name__)


# System prompt for SQL agent
SQL_AGENT_PROMPT = """You are a SQL database expert assistant.

Your capabilities:
- Examine database schemas to understand table structure
- Write and execute precise SQL queries
- Analyze query results and provide insights
- Explain queries in plain English

SAFETY RULES (CRITICAL):
1. ONLY execute SELECT queries (read-only operations)
2. NEVER execute UPDATE, DELETE, DROP, INSERT, or any data-modifying operations
3. Always use LIMIT clauses for large tables (default: LIMIT 100)
4. Never expose sensitive data like passwords or API keys
5. Explain your queries in plain English before executing

WORKFLOW:
1. Examine the database schema first to understand available tables and columns
2. Write a precise SQL query based on the user's question
3. Execute the query safely
4. Analyze and explain the results clearly
5. Provide insights and recommendations if applicable

When the user asks a question:
- First understand what data they need
- Check the schema to find relevant tables
- Write an efficient SQL query
- Execute and explain the results
"""


async def create_sql_agent(
    database_uri: str,
    llm_model: str = "gpt-4o",
    temperature: float = 0.0,
    enable_dynamic_routing: bool = False
) -> CompiledStateGraph:
    """
    Create a SQL database query agent.

    This agent can answer questions about a database using natural language.
    It examines schemas, writes SQL queries, executes them safely, and explains results.

    Args:
        database_uri: Database connection string (e.g., "postgresql://user:pass@localhost:5432/mydb")
        llm_model: LLM to use for query generation (default: gpt-4o for reliability)
        temperature: Temperature for generation (default: 0.0 for deterministic SQL)
        enable_dynamic_routing: Enable dynamic model selection (default: False, use consistent model for SQL)

    Returns:
        Compiled LangGraph agent ready to execute SQL queries

    Example:
        >>> # PostgreSQL
        >>> agent = await create_sql_agent(
        ...     "postgresql://user:pass@localhost:5432/mydb"
        ... )
        >>> result = await agent.ainvoke({
        ...     "messages": [HumanMessage(content="Show top 10 users by signup date")]
        ... })

        >>> # SQLite
        >>> agent = await create_sql_agent("sqlite:///path/to/database.db")

        >>> # MySQL
        >>> agent = await create_sql_agent(
        ...     "mysql+pymysql://user:pass@localhost:3306/mydb"
        ... )

    Safety Features:
        - Read-only operations (SELECT only)
        - Automatic LIMIT clauses for large result sets
        - Schema examination before queries
        - Query explanation in plain English

    Supported Databases:
        - PostgreSQL
        - MySQL
        - SQLite
        - Microsoft SQL Server
        - Oracle
        - Any SQLAlchemy-compatible database
    """

    logger.info(f"Creating SQL agent for database: {database_uri.split('@')[0]}...")

    try:
        # Connect to database (LangChain handles connection pooling)
        db = SQLDatabase.from_uri(database_uri)
        logger.info(f"✓ Connected to database (dialect: {db.dialect})")

        # Get table names for logging
        table_names = db.get_usable_table_names()
        logger.info(f"✓ Found {len(table_names)} tables: {', '.join(table_names[:5])}{'...' if len(table_names) > 5 else ''}")

        # Create LLM instance
        if llm_model.startswith("claude"):
            llm = ChatAnthropic(
                model=llm_model,
                temperature=temperature,
                max_tokens=4096
            )
        else:
            # Default to OpenAI-compatible models
            llm = ChatOpenAI(
                model=llm_model,
                temperature=temperature,
                max_tokens=4096
            )

        logger.info(f"✓ Using LLM: {llm_model} (temperature={temperature})")

        # Create SQL toolkit with tools for schema examination and query execution
        toolkit = SQLDatabaseToolkit(
            db=db,
            llm=llm
        )

        # Get tools from toolkit
        tools = toolkit.get_tools()
        logger.info(f"✓ Loaded {len(tools)} SQL tools")

        # Log available tools
        for tool in tools:
            logger.debug(f"  - {tool.name}: {tool.description}")

        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", SQL_AGENT_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ])

        # Create agent
        if enable_dynamic_routing:
            # Use dynamic model selection (not recommended for SQL - consistency is important)
            logger.warning("Dynamic routing enabled for SQL agent - this may cause inconsistent query generation")
            from core.models.selector import ModelSelector

            model_selector = ModelSelector(
                primary_model=llm_model,
                temperature=temperature,
                enable_routing=True,
                agent_config={"model": llm_model, "temperature": temperature}
            )
            model_fn = model_selector.create_selector(tools)

            agent = create_agent(
                model=model_fn,
                tools=tools,
                state_modifier=prompt_template  # v1.0: use state_modifier
            )
        else:
            # Static model (recommended for SQL) - v1.0: no pre-binding
            agent = create_agent(
                model=llm,  # v1.0: Pass unbound model
                tools=tools,
                state_modifier=prompt_template  # v1.0: use state_modifier
            )

        logger.info("✓ SQL agent created successfully")

        return agent

    except Exception as e:
        logger.error(f"Failed to create SQL agent: {e}", exc_info=True)
        raise ValueError(f"Failed to create SQL agent: {e}")


async def query_database(
    database_uri: str,
    query: str,
    llm_model: str = "gpt-4o",
    include_schema: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to query a database with natural language.

    Args:
        database_uri: Database connection string
        query: Natural language question
        llm_model: LLM to use
        include_schema: Include database schema in response

    Returns:
        Dictionary with query, SQL executed, results, and explanation

    Example:
        >>> result = await query_database(
        ...     "postgresql://localhost/mydb",
        ...     "How many active users do we have?"
        ... )
        >>> print(result["explanation"])
    """

    from langchain_core.messages import HumanMessage

    # Create agent
    agent = await create_sql_agent(
        database_uri=database_uri,
        llm_model=llm_model,
        temperature=0.0
    )

    # Execute query
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=query)]
    })

    # Extract results
    response = {
        "query": query,
        "response": result["messages"][-1].content if result.get("messages") else "No response",
        "model": llm_model
    }

    if include_schema:
        # Add schema information
        db = SQLDatabase.from_uri(database_uri)
        response["schema"] = {
            "tables": db.get_usable_table_names(),
            "dialect": db.dialect
        }

    return response
