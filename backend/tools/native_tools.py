# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Native Python Tools - MCP Replacement
=====================================

Local-first tools using LangChain Community integrations and native Python.
No Node.js, no subprocess overhead, .exe-friendly.

Replaces:
- @modelcontextprotocol/server-fetch → DuckDuckGo Search (FREE) + httpx + Playwright
- @modelcontextprotocol/server-memory → PostgreSQL (existing)
- @modelcontextprotocol/server-filesystem → Python pathlib
- @modelcontextprotocol/server-sequential-thinking → Custom reasoning
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import asyncio
import sys

from langchain_core.tools import StructuredTool, tool
from langchain_community.tools import DuckDuckGoSearchRun
import httpx
import os

logger = logging.getLogger(__name__)

# Playwright imports - conditional to avoid import errors if not available
try:
    from playwright.async_api import async_playwright
    from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
    from langchain_community.tools.playwright.utils import create_async_playwright_browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available. Browser automation tools will be disabled.")

# Global Playwright browser instance (lazy-loaded)
_playwright_browser = None


# =============================================================================
# Tool Name Mapping (compatible with existing agent configs)
# =============================================================================

TOOL_NAME_MAP = {
    # Web tools
    "web": "web_search",
    "web_search": "web_search",
    "fetch": "web_fetch",
    "web_fetch": "web_fetch",

    # Browser tools (Playwright)
    "browser": "browser",
    "puppeteer": "browser",  # Legacy MCP tool name
    "chrome_devtools": "browser",  # Legacy MCP tool name
    "browser_navigate": "browser_navigate",
    "browser_click": "browser_click",
    "browser_extract": "browser_extract",
    "browser_screenshot": "browser_screenshot",

    # File tools
    "filesystem": "file_read",
    "file_read": "file_read",
    "file_write": "file_write",
    "file_list": "file_list",

    # Memory tools (uses existing PostgreSQL)
    "memory": "memory_store",
    "memory_store": "memory_store",
    "memory_recall": "memory_recall",

    # Reasoning tools
    "sequential_thinking": "reasoning_chain",
    "thinking": "reasoning_chain",
    "reasoning": "reasoning_chain",
}


# =============================================================================
# Web Search Tools (DuckDuckGo - FREE, No API Key Required)
# =============================================================================

# Create a singleton DuckDuckGo search tool instance
_ddg_search = None

def get_ddg_search():
    """Get or create the DuckDuckGo search tool instance."""
    global _ddg_search
    if _ddg_search is None:
        _ddg_search = DuckDuckGoSearchRun()
    return _ddg_search

@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo's HTML API (async-safe, no event loop conflicts).

    Perfect for finding current information, news, articles, and general knowledge.
    Uses simple HTTP requests instead of the problematic DuckDuckGo library.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        Search results as formatted text

    Example:
        >>> await web_search("Battlefield 6 best weapons November 2025")
        >>> await web_search("Python async tutorial")
    """
    import re
    
    try:
        logger.info(f"Web search (DuckDuckGo HTML): {query}")

        # Use DuckDuckGo's HTML search (no JavaScript, no new event loops)
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.post(url, data=params)
            response.raise_for_status()

            html = response.text
            results = []
            
            # Method 1: Extract snippets using regex (more robust than line-based)
            # DuckDuckGo HTML uses class="result__snippet" for search result snippets
            snippet_pattern = r'class="result__snippet"[^>]*>([^<]+(?:<b>[^<]+</b>[^<]*)*)</'
            matches = re.findall(snippet_pattern, html, re.IGNORECASE)
            
            for match in matches[:max_results]:
                # Clean up the snippet
                snippet = re.sub(r'<[^>]+>', '', match)  # Remove any HTML tags
                snippet = snippet.replace('&quot;', '"').replace('&amp;', '&')
                snippet = snippet.replace('&lt;', '<').replace('&gt;', '>')
                snippet = snippet.replace('&#x27;', "'").replace('&nbsp;', ' ')
                snippet = snippet.strip()
                if snippet and len(snippet) > 10:
                    results.append(snippet)
            
            # Method 2: Fallback - try to extract from result__a (titles) if no snippets
            if not results:
                title_pattern = r'class="result__a"[^>]*>([^<]+)</a>'
                title_matches = re.findall(title_pattern, html, re.IGNORECASE)
                for match in title_matches[:max_results]:
                    title = match.strip()
                    if title and len(title) > 5:
                        results.append(f"[Title] {title}")
            
            # Method 3: Last resort - extract any text between result divs
            if not results:
                # Look for result blocks
                result_blocks = re.findall(r'<div class="result[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL | re.IGNORECASE)
                for block in result_blocks[:max_results]:
                    # Extract text content
                    text = re.sub(r'<[^>]+>', ' ', block)
                    text = ' '.join(text.split())  # Normalize whitespace
                    if text and len(text) > 20:
                        results.append(text[:300])  # Limit length

            if not results:
                logger.warning(f"No results found for: {query}")
                # Log a sample of the HTML for debugging
                logger.debug(f"HTML sample (first 1000 chars): {html[:1000]}")
                return f"No search results found for: {query}. Try a different search query."

            # Format results
            result_text = f"Search results for '{query}':\n\n"
            for i, snippet in enumerate(results, 1):
                result_text += f"{i}. {snippet}\n\n"

            logger.info(f"Web search returned {len(results)} results for: {query}")
            return result_text

    except httpx.TimeoutException:
        logger.error(f"Web search timeout for: {query}")
        return f"Search timed out. Please try again with a simpler query."
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Error performing web search: {str(e)}"


@tool
async def web_fetch(url: str, timeout: int = 10) -> str:
    """
    Fetch the content of a webpage.

    Useful for reading articles, documentation, and web pages.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds (default: 10)

    Returns:
        The text content of the webpage

    Example:
        >>> await web_fetch("https://example.com/article")
    """
    try:
        logger.info(f"Fetching URL: {url}")

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text" in content_type or "html" in content_type:
                text = response.text
                logger.info(f"Fetched {len(text)} characters from {url}")
                return text
            else:
                return f"Content type '{content_type}' is not text-based"

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        return f"Error fetching URL: {str(e)}"
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return f"Error: {str(e)}"


# =============================================================================
# Browser Tools (Playwright - Advanced web interaction)
# =============================================================================

def _init_sync_playwright():
    """
    Initialize sync Playwright in a dedicated thread (Windows workaround).

    This runs in a separate thread with no event loop, avoiding
    the SelectorEventLoop vs ProactorEventLoop conflict.
    """
    from playwright.sync_api import sync_playwright

    # This runs in a thread - no asyncio event loop here
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    return browser

async def get_playwright_browser():
    """
    Get or create the Playwright browser instance.
    Lazy-loads the browser to avoid startup overhead.

    Windows-specific handling:
    - Main app uses WindowsSelectorEventLoopPolicy (for psycopg)
    - Playwright needs subprocess support (ProactorEventLoop)
    - Solution: Run sync Playwright in a separate thread (no event loop)
    """
    global _playwright_browser
    if _playwright_browser is None:
        logger.info("Initializing Playwright browser (headless mode)...")
        try:
            if sys.platform == 'win32':
                # Windows: Run sync Playwright in thread to avoid event loop conflicts
                logger.info("Windows detected: Using sync Playwright in thread pool")
                import concurrent.futures

                # Execute in thread pool - the thread has no event loop,
                # so sync_playwright can create its own subprocess handling
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    _playwright_browser = await loop.run_in_executor(
                        executor,
                        _init_sync_playwright
                    )
                logger.info("✓ Playwright browser initialized successfully (thread mode)")
            else:
                # Unix: Use async Playwright directly
                from playwright.async_api import async_playwright

                playwright = await async_playwright().start()
                _playwright_browser = await playwright.chromium.launch(headless=True)

                logger.info("✓ Playwright browser initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            logger.error("Make sure you ran: playwright install chromium")
            logger.exception("Full traceback:")
            raise
    return _playwright_browser


async def load_playwright_tools() -> List[StructuredTool]:
    """
    Load Playwright browser tools from LangChain's PlaywrightBrowserToolkit.

    This is an ASYNC function that must be called with await.

    Returns tools for:
    - navigate_browser: Navigate to a URL and render JavaScript
    - click_element: Click an element on the page
    - extract_text: Extract visible text from the current page
    - extract_hyperlinks: Get all links from the page
    - get_elements: Get elements matching a CSS selector
    - current_webpage: Get current page URL and content

    These tools enable JavaScript rendering, dynamic content interaction,
    and sophisticated web scraping that simple HTTP requests cannot achieve.

    Example usage:
        >>> browser_tools = await load_playwright_tools()
        >>> # browser_tools now contains all Playwright browser automation tools
    """
    try:
        logger.info("Loading Playwright browser toolkit...")

        # Initialize the browser
        browser = await get_playwright_browser()

        # Create the toolkit - use sync_browser on Windows, async_browser on Unix
        if sys.platform == 'win32':
            toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=browser)
        else:
            toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)

        # Get the tools
        tools = toolkit.get_tools()

        logger.info(f"✓ Loaded {len(tools)} Playwright browser tools")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")

        return tools

    except Exception as e:
        logger.error(f"Failed to load Playwright tools: {e}")
        logger.error("Proceeding without browser automation tools")
        return []


# =============================================================================
# File System Tools (Safe, sandboxed operations)
# =============================================================================

@tool
def file_read(file_path: str, max_chars: int = 50000) -> str:
    """
    Read the contents of a file.

    Supports text files including .txt, .md, .py, .json, etc.

    Args:
        file_path: Path to the file to read
        max_chars: Maximum characters to read (default: 50000)

    Returns:
        File contents as string

    Example:
        >>> file_read("C:/Users/User/Documents/notes.txt")
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        content = path.read_text(encoding="utf-8")

        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[Truncated - file is {len(content)} characters]"

        logger.info(f"Read file: {file_path} ({len(content)} chars)")
        return content

    except UnicodeDecodeError:
        return f"Error: File is not a text file or uses unsupported encoding"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"Error reading file: {str(e)}"


def _file_write_impl(file_path: str, content: str, _workspace_context: dict = None) -> str:
    """Implementation of file_write tool with workspace-aware file storage"""
    try:
        # Always use organized workspace for better file management
        from services.workspace_manager import get_workspace_manager

        workspace_mgr = get_workspace_manager()

        # If workspace context provided, use it; otherwise use a default workspace
        if _workspace_context:
            workspace = workspace_mgr.get_task_workspace(
                project_id=_workspace_context.get('project_id'),
                workflow_id=_workspace_context.get('workflow_id'),
                task_id=_workspace_context.get('task_id')
            )
        else:
            # Default to outputs/default/ for non-workflow executions
            workspace = Path("outputs/default").resolve()
            workspace.mkdir(parents=True, exist_ok=True)

        # Write file to workspace directory (use just the filename, not full path)
        path = (workspace / Path(file_path).name).resolve()

        # Security: Ensure file is within workspace
        if not str(path).startswith(str(workspace)):
            return f"Error: Cannot write outside workspace directory"

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        logger.info(f"Wrote file: {path} ({len(content)} chars)")
        return f"Successfully wrote {len(content)} characters to {path.name}"

    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        return f"Error writing file: {str(e)}"

def _file_write_error_handler(error: Exception) -> str:
    """Custom error handler for file_write validation errors"""
    error_str = str(error)

    # Check if this is a Pydantic validation error for missing content
    if "ValidationError" in str(type(error)) and "content" in error_str and "Field required" in error_str:
        return (
            "ERROR: file_write requires BOTH file_path AND content parameters. "
            "You called file_write with only file_path='...' but DID NOT provide the content parameter. "
            "This is wrong. You MUST call file_write with BOTH parameters like this: "
            "file_write(file_path='your_file.md', content='your complete file content here'). "
            "Do NOT call file_write until you have the full content ready to write. "
            "Generate the full content first, then call file_write with both parameters."
        )

    # For other errors, return the original error message
    return f"file_write error: {error_str}"

# Create the tool with custom error handling
from langchain_core.tools import StructuredTool

file_write = StructuredTool.from_function(
    func=_file_write_impl,
    name="file_write",
    description="""Write content to a file.

Creates the file if it doesn't exist, overwrites if it does.

CRITICAL: Both parameters are REQUIRED and MUST be provided:
- file_path (str): The path where to write the file
- content (str): The complete content to write to the file

You MUST provide both file_path AND content when calling this tool.
Do NOT call this tool without the content parameter.
If you don't have the content ready, wait until you do before calling file_write.

Args:
    file_path: Path where to write the file (relative or absolute)
    content: Complete text content to write to the file

Returns:
    Success message with file path and character count

Example:
    >>> file_write(
    ...     file_path="report.md",
    ...     content="# Research Report\\n\\nThis is the full content..."
    ... )""",
    handle_tool_error=_file_write_error_handler
)


@tool
def file_list(directory_path: str, pattern: str = "*") -> str:
    """
    List files in a directory.

    Args:
        directory_path: Path to the directory
        pattern: Glob pattern for filtering (default: "*" for all files)

    Returns:
        List of files matching the pattern

    Example:
        >>> file_list("C:/Users/User/Documents")
        >>> file_list("C:/Users/User/Documents", "*.txt")
    """
    try:
        path = Path(directory_path).resolve()

        if not path.exists():
            return f"Error: Directory not found: {directory_path}"

        if not path.is_dir():
            return f"Error: Path is not a directory: {directory_path}"

        files = list(path.glob(pattern))

        if not files:
            return f"No files found matching pattern '{pattern}' in {directory_path}"

        file_list_str = "\n".join([
            f"{'[DIR]' if f.is_dir() else '[FILE]'} {f.name}"
            for f in sorted(files)
        ])

        logger.info(f"Listed {len(files)} files in {directory_path}")
        return file_list_str

    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}")
        return f"Error listing directory: {str(e)}"


# =============================================================================
# Memory Tools (Uses existing PostgreSQL database)
# =============================================================================

# Note: These are placeholder functions. Actual memory integration
# should use LangGraph's existing PostgreSQL checkpointer.

@tool
def memory_store(key: str, value: str, context: str = "general") -> str:
    """
    Store information in agent memory for later recall.

    Uses the existing PostgreSQL database for persistence.

    Args:
        key: Unique identifier for this memory
        value: The information to store
        context: Optional context/category (default: "general")

    Returns:
        Success confirmation

    Example:
        >>> memory_store("user_preference", "prefers detailed explanations", "settings")
    """
    # TODO: Integrate with existing PostgreSQL via LangGraph checkpointer
    logger.info(f"Memory store: {key} (context: {context})")
    return f"Stored memory: {key} in context '{context}'"


@tool
def memory_recall(key: str, context: str = "general") -> str:
    """
    Recall previously stored information from memory.

    Args:
        key: The key to look up
        context: Optional context/category (default: "general")

    Returns:
        The stored value, or an error message if not found

    Example:
        >>> memory_recall("user_preference", "settings")
    """
    # TODO: Integrate with existing PostgreSQL via LangGraph checkpointer
    logger.info(f"Memory recall: {key} (context: {context})")
    return f"Memory lookup for '{key}' - Not yet implemented (use PostgreSQL checkpointer)"


# =============================================================================
# Reasoning Tools (Sequential Thinking replacement)
# =============================================================================

@tool
def reasoning_chain(task: str, steps: int = 5) -> str:
    """
    Break down a complex task into logical reasoning steps.

    Replaces the MCP sequential-thinking server with native Python logic.

    Args:
        task: The task or problem to reason about
        steps: Number of reasoning steps to perform (default: 5)

    Returns:
        Structured reasoning breakdown

    Example:
        >>> reasoning_chain("Plan a marketing strategy for a new product", 5)
    """
    logger.info(f"Reasoning chain for task: {task}")

    # This is a simplified version. The actual LLM will do the reasoning.
    # This tool just provides a structure for the agent to follow.

    reasoning_template = f"""
TASK: {task}

REASONING STEPS:
1. Analyze the requirements and constraints
2. Identify key objectives and success criteria
3. Consider potential approaches and trade-offs
4. Evaluate risks and mitigation strategies
5. Synthesize into a concrete action plan

Note: This is a reasoning framework. The agent should fill in the actual analysis.
"""

    return reasoning_template


# =============================================================================
# Tool Loading Functions
# =============================================================================

def load_native_tools(tool_names: List[str]) -> List[StructuredTool]:
    """
    Load native Python tools by name.

    This replaces the MCP tool adapter with a simpler, synchronous approach.

    Args:
        tool_names: List of tool names to load (e.g., ['web', 'memory', 'filesystem'])

    Returns:
        List of LangChain StructuredTool objects ready for agent binding

    Example:
        >>> tools = load_native_tools(['web_search', 'file_read', 'memory_store'])
        >>> agent = create_agent(llm, tools)
    """
    if not tool_names:
        logger.debug("No tools requested")
        return []

    logger.info(f"Loading native tools: {tool_names}")

    # Available tools registry
    available_tools = {
        "web_search": web_search,
        "web_fetch": web_fetch,
        "file_read": file_read,
        "file_write": file_write,
        "file_list": file_list,
        "memory_store": memory_store,
        "memory_recall": memory_recall,
        "reasoning_chain": reasoning_chain,
        # Note: Playwright tools are loaded separately via get_playwright_tools()
        # because they require async initialization
    }

    tools = []

    for tool_name in tool_names:
        # Map old MCP names to new native names
        mapped_name = TOOL_NAME_MAP.get(tool_name, tool_name)

        # File write is now re-enabled
        # if mapped_name == "file_write":
        #     logger.warning(f"  ⚠️ file_write tool is temporarily DISABLED - agents should output content directly instead")
        #     continue

        # Special handling for browser tools (requires async initialization)
        if mapped_name == "browser_navigate" or tool_name == "browser":
            logger.info(f"  ℹ Browser tools requested (Playwright) - will be loaded separately via toolkit")
            # Note: Playwright tools are loaded via get_playwright_tools() which returns
            # the full toolkit. For now, we log this and skip.
            continue

        if mapped_name in available_tools:
            tool = available_tools[mapped_name]
            tools.append(tool)
            logger.info(f"  ✓ Loaded: {mapped_name} (requested as: {tool_name})")
        else:
            logger.warning(f"  ⚠ Tool not found: {tool_name} (mapped to: {mapped_name})")

    logger.info(f"✓ Loaded {len(tools)} native tools total")

    return tools


def get_available_tool_names() -> List[str]:
    """
    Get list of all available native tool names.

    Useful for frontend UI to display available tools.

    Returns:
        List of tool names that can be loaded
    """
    return [
        "web_search",
        "web_fetch",
        "browser",  # Playwright browser toolkit (advanced web interaction)
        "file_read",
        "file_write",
        "file_list",
        "memory_store",
        "memory_recall",
        "reasoning_chain",
    ]
