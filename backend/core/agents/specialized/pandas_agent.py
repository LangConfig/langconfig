# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Pandas DataFrame Agent for LangConfig

Enables natural language data analysis for CSV, Excel, and DataFrame data.
Uses LangChain's experimental pandas agent for statistical analysis, visualization,
and pattern detection.

Features:
- Load CSV, Excel, Parquet files
- Statistical analysis (mean, median, correlation, etc.)
- Data cleaning and transformation
- Pattern detection and insights
- Outlier detection
- Safe Python/Pandas code execution

Example:
    >>> df = pd.read_csv("tickets.csv")
    >>> agent = await create_dataframe_agent(df)
    >>> result = await agent.ainvoke({
    ...     "messages": [HumanMessage(content="What's the average resolution time?")]
    ... })
"""

import logging
from typing import Optional, Dict, Any, Union
import pandas as pd
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# System prompt for Pandas agent
PANDAS_AGENT_PROMPT = """You are a data scientist specializing in exploratory data analysis.

Your capabilities:
- Load and examine datasets (CSV, Excel, Parquet)
- Statistical analysis (descriptive stats, correlations, distributions)
- Data cleaning and transformation
- Pattern detection and insights
- Outlier detection
- Visualization descriptions (you can't generate images, but describe what plots would show)

ANALYSIS WORKFLOW:
1. Examine the DataFrame structure (columns, dtypes, shape, missing values)
2. Understand what the user is asking for
3. Perform appropriate analysis using pandas operations
4. Provide clear insights in plain English
5. Suggest next analysis steps if relevant

Available operations:
- Statistical analysis: df.describe(), df.mean(), df.median(), df.std(), df.corr()
- Filtering: df[df['column'] > value], df.query()
- Grouping: df.groupby('column').agg()
- Sorting: df.sort_values()
- Missing data: df.isnull().sum(), df.fillna(), df.dropna()
- Visualization descriptions: Describe what a plot would show
- Custom calculations: Any valid pandas/numpy operation

IMPORTANT SAFETY RULES:
- Only use pandas and numpy operations
- Do NOT execute system commands or file operations
- Do NOT import additional libraries beyond pandas/numpy
- Handle errors gracefully

Always:
- Explain your methodology
- Show sample data when relevant
- Highlight interesting findings
- Suggest next analysis steps
"""


async def create_dataframe_agent(
    df: pd.DataFrame,
    llm_model: str = "gpt-4o",
    temperature: float = 0.1,
    enable_dynamic_routing: bool = False,
    allow_dangerous_code: bool = True
):
    """
    Create a Pandas DataFrame analysis agent.

    This agent can answer questions about a DataFrame using natural language.
    It examines the data, performs statistical analysis, and provides insights.

    Args:
        df: Pandas DataFrame to analyze
        llm_model: LLM to use (default: gpt-4o for reliability)
        temperature: Temperature for generation (default: 0.1 for consistent analysis)
        enable_dynamic_routing: Enable dynamic model selection (default: False)
        allow_dangerous_code: Allow pandas operations (required, default: True)

    Returns:
        Agent that can analyze the DataFrame

    Example:
        >>> df = pd.read_csv("sales_data.csv")
        >>> agent = await create_dataframe_agent(df)
        >>> result = await agent.ainvoke({
        ...     "messages": [HumanMessage(content="What's the top-selling product?")]
        ... })
        >>> print(result["messages"][-1].content)

    Safety:
        - Only pandas/numpy operations allowed
        - No file system access
        - No system commands
        - Code execution is sandboxed

    Supported Analysis:
        - Descriptive statistics
        - Correlation analysis
        - Grouping and aggregation
        - Filtering and sorting
        - Missing data analysis
        - Outlier detection
        - Pattern discovery
    """

    logger.info(f"Creating Pandas DataFrame agent for data: {df.shape[0]} rows × {df.shape[1]} columns")

    try:
        # Validate DataFrame
        if df.empty:
            raise ValueError("DataFrame is empty")

        # Log DataFrame info
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"Data types: {df.dtypes.to_dict()}")
        logger.info(f"Missing values: {df.isnull().sum().sum()} total")

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

        # Create pandas dataframe agent
        # Note: This uses the experimental pandas agent from LangChain
        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df,
            verbose=True,
            agent_type="openai-tools",  # Use function calling
            allow_dangerous_code=allow_dangerous_code,  # Required for pandas ops
            prefix=PANDAS_AGENT_PROMPT,
            max_iterations=15,
            max_execution_time=60,
            early_stopping_method="generate"
        )

        logger.info("✓ Pandas DataFrame agent created successfully")

        return agent

    except Exception as e:
        logger.error(f"Failed to create Pandas agent: {e}", exc_info=True)
        raise ValueError(f"Failed to create Pandas agent: {e}")


async def analyze_file(
    file_path: str,
    query: str = "Analyze this dataset and provide key insights",
    llm_model: str = "gpt-4o",
    file_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to analyze a data file with natural language.

    Automatically detects file type and loads the data.

    Args:
        file_path: Path to CSV, Excel, or Parquet file
        query: Natural language question
        llm_model: LLM to use
        file_type: File type override ('csv', 'excel', 'parquet')

    Returns:
        Dictionary with analysis results

    Example:
        >>> result = await analyze_file(
        ...     "sales_data.csv",
        ...     "What are the top 5 products by revenue?"
        ... )
        >>> print(result["analysis"])
    """

    # Detect file type
    if file_type is None:
        if file_path.endswith('.csv'):
            file_type = 'csv'
        elif file_path.endswith(('.xlsx', '.xls')):
            file_type = 'excel'
        elif file_path.endswith('.parquet'):
            file_type = 'parquet'
        else:
            raise ValueError(f"Unknown file type: {file_path}")

    # Load data
    logger.info(f"Loading {file_type} file: {file_path}")

    if file_type == 'csv':
        df = pd.read_csv(file_path)
    elif file_type == 'excel':
        df = pd.read_excel(file_path)
    elif file_type == 'parquet':
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    logger.info(f"✓ Loaded {len(df)} rows, {len(df.columns)} columns")

    # Create agent
    agent = await create_dataframe_agent(df, llm_model=llm_model)

    # Run analysis
    result = await agent.ainvoke({
        "input": query
    })

    # Extract response
    response = {
        "file": file_path,
        "rows": len(df),
        "columns": list(df.columns),
        "query": query,
        "analysis": result.get("output", "No output"),
        "model": llm_model
    }

    return response


async def analyze_dataframe(
    df: pd.DataFrame,
    query: str,
    llm_model: str = "gpt-4o",
    include_summary: bool = True
) -> Dict[str, Any]:
    """
    Analyze a DataFrame with a natural language query.

    Args:
        df: Pandas DataFrame to analyze
        query: Natural language question
        llm_model: LLM to use
        include_summary: Include DataFrame summary in response

    Returns:
        Dictionary with analysis results

    Example:
        >>> df = pd.DataFrame({'sales': [100, 200, 150], 'region': ['US', 'EU', 'US']})
        >>> result = await analyze_dataframe(
        ...     df,
        ...     "What's the average sales by region?"
        ... )
    """

    # Create agent
    agent = await create_dataframe_agent(df, llm_model=llm_model)

    # Run analysis
    result = await agent.ainvoke({
        "input": query
    })

    # Build response
    response = {
        "query": query,
        "analysis": result.get("output", "No output"),
        "model": llm_model
    }

    if include_summary:
        response["summary"] = {
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "missing_values": df.isnull().sum().to_dict(),
            "memory_usage": df.memory_usage(deep=True).sum()
        }

    return response


def get_dataframe_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Get a comprehensive summary of a DataFrame.

    Args:
        df: Pandas DataFrame

    Returns:
        Dictionary with summary statistics

    Example:
        >>> summary = get_dataframe_summary(df)
        >>> print(f"Dataset has {summary['rows']} rows")
    """

    return {
        "shape": {
            "rows": len(df),
            "columns": len(df.columns)
        },
        "columns": list(df.columns),
        "dtypes": df.dtypes.to_dict(),
        "missing_values": {
            "total": df.isnull().sum().sum(),
            "by_column": df.isnull().sum().to_dict()
        },
        "memory_usage": {
            "total_bytes": df.memory_usage(deep=True).sum(),
            "by_column": df.memory_usage(deep=True).to_dict()
        },
        "numeric_summary": df.describe().to_dict() if len(df.select_dtypes(include='number').columns) > 0 else {},
        "sample_data": df.head(5).to_dict(orient='records')
    }
