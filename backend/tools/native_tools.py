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

    # Filesystem tools (DeepAgents standard naming)
    # See: https://docs.langchain.com/oss/python/deepagents/harness
    "filesystem": "read_file",
    "ls": "ls",
    "read_file": "read_file",
    "write_file": "write_file",
    "edit_file": "edit_file",
    "glob": "glob",
    "grep": "grep",
    # Backwards compatibility aliases (LangConfig legacy naming)
    "file_read": "read_file",
    "file_write": "write_file",
    "file_list": "ls",

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
    import random

    try:
        logger.info(f"Web search (DuckDuckGo HTML): {query}")

        # Use DuckDuckGo's HTML search (no JavaScript, no new event loops)
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        # Rotate User-Agents to reduce CAPTCHA rate
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]

        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            response = await client.post(url, data=params)
            response.raise_for_status()

            html = response.text

            # Check for CAPTCHA/rate limiting (DuckDuckGo returns 202 with anomaly challenge)
            if response.status_code == 202 or 'anomaly' in html.lower() or 'challenge' in html.lower():
                logger.warning(f"DuckDuckGo CAPTCHA/rate limit detected for query: {query}")
                return (
                    f"Web search is temporarily unavailable (rate limited by DuckDuckGo). "
                    f"The search provider has blocked requests from this IP address. "
                    f"Please try again later, or proceed without web search results for: {query}"
                )

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
# File System Tools (DeepAgents standard naming)
# See: https://docs.langchain.com/oss/python/deepagents/harness
# =============================================================================

@tool
def read_file(file_path: str, offset: int = 0, limit: int = None, max_chars: int = 50000) -> str:
    """
    Read the contents of a file with optional line offset and limit.

    Supports text files including .txt, .md, .py, .json, etc.
    Returns content with line numbers for easy reference.

    Args:
        file_path: Path to the file to read
        offset: Line number to start reading from (0-indexed, default: 0)
        limit: Maximum number of lines to read (default: None for all lines)
        max_chars: Maximum characters to read (default: 50000)

    Returns:
        File contents with line numbers

    Example:
        >>> read_file("src/main.py")
        >>> read_file("logs/app.log", offset=100, limit=50)
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        content = path.read_text(encoding="utf-8")
        lines = content.split('\n')

        # Apply offset and limit
        if offset > 0:
            lines = lines[offset:]
        if limit is not None:
            lines = lines[:limit]

        # Add line numbers
        start_line = offset + 1
        numbered_lines = [f"{start_line + i:4d}| {line}" for i, line in enumerate(lines)]
        result = '\n'.join(numbered_lines)

        if len(result) > max_chars:
            result = result[:max_chars] + f"\n\n[Truncated - content exceeds {max_chars} characters]"

        logger.info(f"Read file: {file_path} ({len(lines)} lines)")
        return result

    except UnicodeDecodeError:
        return f"Error: File is not a text file or uses unsupported encoding"
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return f"Error reading file: {str(e)}"

# Backwards compatibility alias
file_read = read_file


def _write_file_impl(
    file_path: str,
    content: str,
    _workspace_context: dict = None,
    _agent_context: dict = None
) -> str:
    """
    Implementation of write_file tool with workspace-aware file storage.

    Args:
        file_path: The filename to create
        content: The content to write
        _workspace_context: Context about the workspace (project_id, workflow_id, task_id)
        _agent_context: Context about the agent creating the file (agent_label, agent_type, node_id, etc.)
    """
    try:
        # SECURITY: Sanitize file path to prevent dangerous directory creation
        # Extract just the filename, stripping ALL directory components
        original_path = file_path
        filename = Path(file_path).name  # Gets just "report.md" from any path

        # Block suspicious filenames or paths that could cause issues
        dangerous_patterns = [
            'langconfig', 'backend', 'src', 'node_modules', '.git',
            'frontend', 'api', 'core', 'services', 'models'
        ]
        path_lower = file_path.lower()
        for pattern in dangerous_patterns:
            if pattern in path_lower and pattern not in filename.lower():
                logger.warning(f"Blocked dangerous path: {file_path} (contains '{pattern}')")
                # Still write the file, but only use the filename
                logger.info(f"Sanitized path: {file_path} -> {filename}")

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
            # Default to outputs/default/ - use workspace manager's base_dir for consistent path
            workspace = workspace_mgr.base_dir / "default"
            workspace.mkdir(parents=True, exist_ok=True)

        # Write file to workspace directory (use just the filename, not full path)
        path = (workspace / filename).resolve()  # Use sanitized filename only
        workspace_resolved = workspace.resolve()

        # Security: Ensure file is within workspace
        # Use Path.is_relative_to() for robust cross-platform comparison
        try:
            path.relative_to(workspace_resolved)
        except ValueError:
            logger.warning(f"Security: Blocked write outside workspace: {path} not in {workspace_resolved}")
            return f"Error: Cannot write outside workspace directory"

        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        logger.info(f"Wrote file: {path} ({len(content)} chars)")

        # Record file metadata in database if we have context
        _record_file_metadata(
            filename=filename,
            file_path=path,
            workspace=workspace,
            content=content,
            workspace_context=_workspace_context,
            agent_context=_agent_context
        )

        return f"Successfully wrote {len(content)} characters to {path.name}"

    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        return f"Error writing file: {str(e)}"


def _record_file_metadata(
    filename: str,
    file_path: Path,
    workspace: Path,
    content: str,
    workspace_context: dict = None,
    agent_context: dict = None
) -> None:
    """
    Record file metadata in the database for tracking and organization.

    This creates a WorkspaceFile record that tracks which agent created the file,
    the workflow context, and other metadata for later retrieval.
    """
    try:
        from db.database import SessionLocal
        from models.workspace_file import WorkspaceFile
        from services.workspace_manager import get_workspace_manager
        import mimetypes

        # Compute relative path from outputs/ directory (use workspace manager for consistent path)
        workspace_mgr = get_workspace_manager()
        outputs_dir = workspace_mgr.base_dir
        try:
            relative_path = str(file_path.relative_to(outputs_dir))
        except ValueError:
            # File is not under outputs/, use absolute path
            relative_path = str(file_path)

        # Get file extension and mime type
        extension = file_path.suffix.lower() if file_path.suffix else None
        mime_type, _ = mimetypes.guess_type(str(file_path))

        # Create database session
        db = SessionLocal()
        try:
            # Check if file record already exists (update if so)
            existing = db.query(WorkspaceFile).filter(
                WorkspaceFile.file_path == relative_path
            ).first()

            if existing:
                # Update existing record
                existing.size_bytes = len(content.encode('utf-8'))
                existing.mime_type = mime_type
                if agent_context:
                    existing.agent_label = agent_context.get('agent_label')
                    existing.agent_type = agent_context.get('agent_type')
                    existing.node_id = agent_context.get('node_id')
                    existing.description = agent_context.get('description')
                    existing.content_type = agent_context.get('content_type')
                    existing.original_query = agent_context.get('original_query')
                db.commit()
                logger.debug(f"Updated file metadata for: {relative_path}")
            else:
                # Create new record
                file_record = WorkspaceFile(
                    filename=filename,
                    file_path=relative_path,
                    size_bytes=len(content.encode('utf-8')),
                    mime_type=mime_type,
                    extension=extension,
                    # Workspace context
                    project_id=workspace_context.get('project_id') if workspace_context else None,
                    workflow_id=workspace_context.get('workflow_id') if workspace_context else None,
                    workflow_name=workspace_context.get('workflow_name') if workspace_context else None,
                    task_id=workspace_context.get('task_id') if workspace_context else None,
                    execution_id=workspace_context.get('execution_id') if workspace_context else None,
                    # Agent context
                    agent_label=agent_context.get('agent_label') if agent_context else None,
                    agent_type=agent_context.get('agent_type') if agent_context else None,
                    node_id=agent_context.get('node_id') if agent_context else None,
                    description=agent_context.get('description') if agent_context else None,
                    content_type=agent_context.get('content_type') if agent_context else None,
                    original_query=agent_context.get('original_query') if agent_context else None,
                    tags=agent_context.get('tags', []) if agent_context else [],
                )
                db.add(file_record)
                db.commit()
                logger.debug(f"Recorded file metadata for: {relative_path}")

        finally:
            db.close()

    except Exception as e:
        # Don't fail the file write if metadata recording fails
        logger.warning(f"Could not record file metadata: {e}")

def _write_file_error_handler(error: Exception) -> str:
    """Custom error handler for write_file validation errors"""
    error_str = str(error)

    # Check if this is a Pydantic validation error for missing content
    if "ValidationError" in str(type(error)) and "content" in error_str and "Field required" in error_str:
        return (
            "ERROR: write_file requires BOTH file_path AND content parameters. "
            "You called write_file with only file_path='...' but DID NOT provide the content parameter. "
            "This is wrong. You MUST call write_file with BOTH parameters like this: "
            "write_file(file_path='your_file.md', content='your complete file content here'). "
            "Do NOT call write_file until you have the full content ready to write. "
            "Generate the full content first, then call write_file with both parameters."
        )

    # For other errors, return the original error message
    return f"write_file error: {error_str}"

# Create the tool with custom error handling and explicit args schema
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field as PydanticField

class WriteFileArgs(BaseModel):
    """Arguments for write_file tool - BOTH are REQUIRED"""
    file_path: str = PydanticField(
        ...,  # ... means required in Pydantic
        description="REQUIRED: The filename to create (e.g., 'report.md', 'data.json'). Directory path is ignored."
    )
    content: str = PydanticField(
        ...,  # ... means required in Pydantic
        description="REQUIRED: The COMPLETE text content to write to the file. You MUST provide this parameter."
    )

write_file = StructuredTool.from_function(
    func=_write_file_impl,
    name="write_file",
    args_schema=WriteFileArgs,
    description="""Write content to a file. REQUIRES 2 PARAMETERS: file_path AND content.

MANDATORY PARAMETERS (you MUST provide BOTH):
1. file_path (str): Filename like 'report.md' (directory ignored for security)
2. content (str): The COMPLETE file content - DO NOT omit this parameter!

WRONG: write_file(file_path='test.md')  ← MISSING content, will ERROR
CORRECT: write_file(file_path='test.md', content='# My Report\\nContent here...')

Files are saved to the workflow's organized output directory.
Users can view, preview, and download files from the 'Files' tab.

Best practice filenames: .md (reports), .json (data), .csv (tables), .py (code)

If you don't have content ready yet, DO NOT call this tool until you do.""",
    handle_tool_error=_write_file_error_handler
)

# Backwards compatibility alias
file_write = write_file


@tool
def ls(directory_path: str = ".") -> str:
    """
    List directory contents with metadata.

    Shows files and directories with their types and sizes.

    Args:
        directory_path: Path to the directory (default: current directory)

    Returns:
        Formatted list of directory contents with metadata

    Example:
        >>> ls()
        >>> ls("/home/user/projects")
    """
    try:
        path = Path(directory_path).resolve()

        if not path.exists():
            return f"Error: Directory not found: {directory_path}"

        if not path.is_dir():
            return f"Error: Path is not a directory: {directory_path}"

        entries = list(path.iterdir())

        if not entries:
            return f"Empty directory: {directory_path}"

        # Format with metadata
        lines = []
        for entry in sorted(entries, key=lambda x: (not x.is_dir(), x.name.lower())):
            if entry.is_dir():
                lines.append(f"[DIR]  {entry.name}/")
            else:
                size = entry.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f}MB"
                lines.append(f"[FILE] {entry.name} ({size_str})")

        logger.info(f"Listed {len(entries)} entries in {directory_path}")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}")
        return f"Error listing directory: {str(e)}"

# Backwards compatibility alias
file_list = ls


@tool
def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    """
    Perform exact string replacement in a file.

    Finds the old_string in the file and replaces it with new_string.
    The old_string must be unique in the file to avoid ambiguous edits.

    Args:
        file_path: Path to the file to edit
        old_string: The exact string to find and replace
        new_string: The string to replace it with

    Returns:
        Success message or error if old_string not found/not unique

    Example:
        >>> edit_file("config.py", "DEBUG = False", "DEBUG = True")
    """
    try:
        path = Path(file_path).resolve()

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        content = path.read_text(encoding="utf-8")

        # Check if old_string exists and is unique
        count = content.count(old_string)
        if count == 0:
            return f"Error: String not found in file: '{old_string[:50]}...'"
        if count > 1:
            return f"Error: String found {count} times. Must be unique for safe replacement."

        # Perform replacement
        new_content = content.replace(old_string, new_string, 1)
        path.write_text(new_content, encoding="utf-8")

        logger.info(f"Edited file: {file_path}")
        return f"Successfully replaced string in {path.name}"

    except UnicodeDecodeError:
        return f"Error: File is not a text file or uses unsupported encoding"
    except Exception as e:
        logger.error(f"Error editing file {file_path}: {e}")
        return f"Error editing file: {str(e)}"


@tool
def glob(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern.

    Supports patterns like "**/*.py" (all Python files) or "src/*.ts" (TypeScript in src).

    Args:
        pattern: Glob pattern to match (e.g., "**/*.py", "*.md", "src/**/*.tsx")
        path: Base directory to search from (default: current directory)

    Returns:
        List of matching file paths

    Example:
        >>> glob("**/*.py")
        >>> glob("*.md", path="/docs")
        >>> glob("src/**/*.tsx")
    """
    try:
        base_path = Path(path).resolve()

        if not base_path.exists():
            return f"Error: Path not found: {path}"

        matches = list(base_path.glob(pattern))

        if not matches:
            return f"No files found matching pattern '{pattern}' in {path}"

        # Format results with relative paths
        result_lines = []
        for match in sorted(matches):
            try:
                rel_path = match.relative_to(base_path)
                result_lines.append(str(rel_path))
            except ValueError:
                result_lines.append(str(match))

        logger.info(f"Glob '{pattern}' found {len(matches)} files")
        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"Error with glob pattern {pattern}: {e}")
        return f"Error searching for files: {str(e)}"


@tool
def grep(pattern: str, path: str = ".", file_pattern: str = None) -> str:
    """
    Search file contents for a regex pattern.

    Searches through files and returns matching lines with context.

    Args:
        pattern: Regular expression pattern to search for
        path: File or directory to search (default: current directory)
        file_pattern: Optional glob pattern to filter files (e.g., "*.py")

    Returns:
        Matching lines with file paths and line numbers

    Example:
        >>> grep("def main", path="src/")
        >>> grep("TODO", file_pattern="*.py")
        >>> grep("import.*requests", path=".", file_pattern="*.py")
    """
    import re

    try:
        base_path = Path(path).resolve()

        if not base_path.exists():
            return f"Error: Path not found: {path}"

        # Compile regex
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        results = []

        # Determine files to search
        if base_path.is_file():
            files_to_search = [base_path]
        else:
            glob_pattern = file_pattern or "**/*"
            files_to_search = [f for f in base_path.glob(glob_pattern) if f.is_file()]

        # Search through files
        for file_path in files_to_search:
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        try:
                            rel_path = file_path.relative_to(base_path)
                        except ValueError:
                            rel_path = file_path.name
                        results.append(f"{rel_path}:{i}: {line.strip()}")

            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

        if not results:
            return f"No matches found for pattern '{pattern}'"

        # Limit results to prevent huge outputs
        max_results = 100
        if len(results) > max_results:
            output = "\n".join(results[:max_results])
            output += f"\n\n... and {len(results) - max_results} more matches"
        else:
            output = "\n".join(results)

        logger.info(f"Grep '{pattern}' found {len(results)} matches")
        return output

    except Exception as e:
        logger.error(f"Error searching with pattern {pattern}: {e}")
        return f"Error searching: {str(e)}"


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
# Subagent Delegation Tools
# =============================================================================

@tool
def task(
    description: str,
    subagent_type: str = "general",
    context: str = "",
    expected_output: str = ""
) -> str:
    """
    Delegate a task to a specialized subagent for execution.

    Use this tool to spawn work to configured subagents. The subagent will
    execute the task and return the result. This enables parallel processing
    and specialization.

    Args:
        description: Clear description of the task to perform
        subagent_type: Type of subagent to use (e.g., "research", "code", "writer", "general")
        context: Additional context or information for the subagent
        expected_output: Description of expected output format/content

    Returns:
        Result from the subagent execution

    Example:
        >>> task(
        ...     description="Research the latest trends in AI image generation",
        ...     subagent_type="research",
        ...     context="Focus on diffusion models released in 2024",
        ...     expected_output="A summary with key findings and links"
        ... )
    """
    logger.info(f"[TASK DELEGATION] Spawning subagent task: {description[:100]}...")
    logger.info(f"  subagent_type: {subagent_type}")
    logger.info(f"  context: {context[:100] if context else 'None'}...")

    # This is a placeholder - actual subagent execution is handled by the DeepAgents framework
    # The framework intercepts this tool call and routes it to the appropriate subagent
    # based on the subagent configurations in the DeepAgentConfig

    # For now, return a message indicating the tool was called
    # The actual implementation is in the DeepAgents middleware
    return f"""[SUBAGENT TASK QUEUED]
Task: {description}
Type: {subagent_type}
Context: {context if context else 'None'}
Expected Output: {expected_output if expected_output else 'Any relevant output'}

Note: This task has been queued for subagent execution. The DeepAgents framework
will route this to the appropriate configured subagent. If no subagents are
configured, this task will be executed by the main agent."""


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

    # Available tools registry (DeepAgents standard naming)
    # See: https://docs.langchain.com/oss/python/deepagents/harness
    available_tools = {
        # Web tools
        "web_search": web_search,
        "web_fetch": web_fetch,
        # Filesystem tools (DeepAgents standard)
        "ls": ls,
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "glob": glob,
        "grep": grep,
        # Backwards compatibility aliases
        "file_read": read_file,
        "file_write": write_file,
        "file_list": ls,
        # Memory tools
        "memory_store": memory_store,
        "memory_recall": memory_recall,
        # Reasoning tools
        "reasoning_chain": reasoning_chain,
        # Subagent delegation tools
        "task": task,
        "delegate": task,  # Alias for task
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
    Uses DeepAgents standard naming.

    See: https://docs.langchain.com/oss/python/deepagents/harness

    Returns:
        List of tool names that can be loaded
    """
    return [
        # Web tools
        "web_search",
        "web_fetch",
        "browser",  # Playwright browser toolkit (advanced web interaction)
        # Filesystem tools (DeepAgents standard)
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "glob",
        "grep",
        # Memory tools
        "memory_store",
        "memory_recall",
        # Reasoning tools
        "reasoning_chain",
        # Subagent delegation tools
        "task",
    ]


# Registry of filesystem tools for DeepAgents harness
FILESYSTEM_TOOLS = ["ls", "read_file", "write_file", "edit_file", "glob", "grep"]
