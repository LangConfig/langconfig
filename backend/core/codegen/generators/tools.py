# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Native tool generators for the Executable Workflow Exporter.

Generates native Python tool implementations for workflows.
"""

import logging
from textwrap import dedent
from typing import Set

logger = logging.getLogger(__name__)


class ToolGenerators:
    """Generators for native tool implementations."""

    @staticmethod
    def generate_tools_init() -> str:
        """Generate tools/__init__.py."""
        return dedent('''
            """Tools package - native and custom tools."""

            from .native import NATIVE_TOOLS, get_tool_by_name
            from .custom import CUSTOM_TOOLS

            __all__ = ["NATIVE_TOOLS", "CUSTOM_TOOLS", "get_tools_for_node", "get_tool_by_name"]


            def get_tools_for_node(tool_names: list) -> list:
                """
                Get tools by name for a specific node.

                Args:
                    tool_names: List of tool names to load

                Returns:
                    List of tool instances
                """
                tools = []

                for name in tool_names:
                    # Check native tools first
                    if name in NATIVE_TOOLS:
                        tools.append(NATIVE_TOOLS[name])
                    # Then check custom tools
                    elif name in CUSTOM_TOOLS:
                        tools.append(CUSTOM_TOOLS[name])
                    else:
                        import logging
                        logging.warning(f"Tool not found: {name}")

                return tools
        ''').strip()

    @staticmethod
    def get_web_search_impl() -> str:
        """Get web_search tool implementation."""
        return dedent('''
            @tool
            async def web_search(query: str, max_results: int = 5) -> str:
                """
                Search the web using DuckDuckGo.

                Args:
                    query: The search query
                    max_results: Maximum results to return

                Returns:
                    Search results as formatted text
                """
                import re
                import httpx

                try:
                    url = "https://html.duckduckgo.com/html/"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }

                    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                        response = await client.post(url, data={"q": query})
                        response.raise_for_status()

                        html = response.text
                        results = []

                        # Extract snippets
                        snippet_pattern = r'class="result__snippet"[^>]*>([^<]+(?:<b>[^<]+</b>[^<]*)*)</'
                        matches = re.findall(snippet_pattern, html, re.IGNORECASE)

                        for match in matches[:max_results]:
                            snippet = re.sub(r'<[^>]+>', '', match)
                            snippet = snippet.replace('&quot;', '"').replace('&amp;', '&')
                            snippet = snippet.strip()
                            if snippet and len(snippet) > 10:
                                results.append(snippet)

                        if not results:
                            return f"No results found for: {query}"

                        result_text = f"Search results for '{query}':\\n\\n"
                        for i, snippet in enumerate(results, 1):
                            result_text += f"{i}. {snippet}\\n\\n"

                        return result_text

                except Exception as e:
                    return f"Search error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_web_fetch_impl() -> str:
        """Get web_fetch tool implementation."""
        return dedent('''
            @tool
            async def web_fetch(url: str, timeout: int = 10) -> str:
                """
                Fetch content from a URL.

                Args:
                    url: The URL to fetch
                    timeout: Request timeout in seconds

                Returns:
                    Page content as text
                """
                import httpx

                try:
                    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                        response = await client.get(url)
                        response.raise_for_status()

                        content_type = response.headers.get("content-type", "")
                        if "text" in content_type or "html" in content_type:
                            return response.text
                        else:
                            return f"Content type '{content_type}' is not text-based"

                except Exception as e:
                    return f"Fetch error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_read_file_impl() -> str:
        """Get read_file tool implementation."""
        return dedent('''
            @tool
            def read_file(file_path: str, max_chars: int = 50000) -> str:
                """
                Read file contents with optional line numbers.

                Args:
                    file_path: Path to the file
                    max_chars: Maximum characters to read

                Returns:
                    File contents
                """
                try:
                    path = Path(file_path).resolve()

                    if not path.exists():
                        return f"File not found: {file_path}"

                    content = path.read_text(encoding="utf-8")

                    if len(content) > max_chars:
                        content = content[:max_chars] + f"\\n\\n[Truncated - {len(content)} chars total]"

                    return content

                except Exception as e:
                    return f"Read error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_write_file_impl() -> str:
        """Get write_file tool implementation."""
        return dedent('''
            @tool
            def write_file(file_path: str, content: str) -> str:
                """
                Create a new file with the specified content.

                Args:
                    file_path: Path to write to
                    content: Content to write

                Returns:
                    Success message
                """
                try:
                    path = Path(file_path)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")

                    return f"Wrote {len(content)} chars to {file_path}"

                except Exception as e:
                    return f"Write error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_ls_impl() -> str:
        """Get ls tool implementation."""
        return dedent('''
            @tool
            def ls(directory_path: str = ".", pattern: str = "*") -> str:
                """
                List directory contents with metadata.

                Args:
                    directory_path: Path to the directory (default: current dir)
                    pattern: Glob pattern for filtering

                Returns:
                    List of files with metadata
                """
                try:
                    path = Path(directory_path).resolve()

                    if not path.exists():
                        return f"Directory not found: {directory_path}"

                    files = list(path.glob(pattern))

                    if not files:
                        return f"No files matching pattern in {directory_path}"

                    results = []
                    for f in sorted(files):
                        file_type = "DIR" if f.is_dir() else "FILE"
                        size = f.stat().st_size if f.is_file() else 0
                        results.append(f"[{file_type}] {f.name} ({size} bytes)")

                    return "\\n".join(results)

                except Exception as e:
                    return f"List error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_edit_file_impl() -> str:
        """Get edit_file tool implementation."""
        return dedent('''
            @tool
            def edit_file(file_path: str, old_string: str, new_string: str) -> str:
                """
                Perform exact string replacement in a file.

                Args:
                    file_path: Path to the file to edit
                    old_string: The exact text to find and replace
                    new_string: The text to replace it with

                Returns:
                    Success message or error
                """
                try:
                    path = Path(file_path).resolve()

                    if not path.exists():
                        return f"File not found: {file_path}"

                    content = path.read_text(encoding="utf-8")

                    if old_string not in content:
                        return f"String not found in file: {old_string[:50]}..."

                    # Check for uniqueness
                    count = content.count(old_string)
                    if count > 1:
                        return f"String appears {count} times. Please provide a more unique string."

                    new_content = content.replace(old_string, new_string, 1)
                    path.write_text(new_content, encoding="utf-8")

                    return f"Successfully replaced text in {file_path}"

                except Exception as e:
                    return f"Edit error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_glob_impl() -> str:
        """Get glob tool implementation."""
        return dedent('''
            @tool
            def glob(pattern: str, path: str = ".") -> str:
                """
                Find files matching a glob pattern.

                Args:
                    pattern: Glob pattern (e.g., "**/*.py", "src/*.ts")
                    path: Base path to search from (default: current dir)

                Returns:
                    List of matching file paths
                """
                try:
                    base_path = Path(path).resolve()

                    if not base_path.exists():
                        return f"Path not found: {path}"

                    matches = list(base_path.glob(pattern))

                    if not matches:
                        return f"No files matching pattern: {pattern}"

                    # Sort by modification time (most recent first)
                    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

                    results = []
                    for f in matches[:100]:  # Limit to 100 results
                        rel_path = f.relative_to(base_path) if f.is_relative_to(base_path) else f
                        results.append(str(rel_path))

                    result = "\\n".join(results)
                    if len(matches) > 100:
                        result += f"\\n\\n[{len(matches) - 100} more matches not shown]"

                    return result

                except Exception as e:
                    return f"Glob error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_grep_impl() -> str:
        """Get grep tool implementation."""
        return dedent('''
            @tool
            def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
                """
                Search file contents using regex.

                Args:
                    pattern: Regex pattern to search for
                    path: Directory to search in (default: current dir)
                    file_pattern: Glob pattern to filter files (default: all files)

                Returns:
                    Matching lines with file paths and line numbers
                """
                import re

                try:
                    base_path = Path(path).resolve()

                    if not base_path.exists():
                        return f"Path not found: {path}"

                    regex = re.compile(pattern)
                    results = []
                    files_searched = 0
                    max_results = 50

                    for file_path in base_path.rglob(file_pattern):
                        if not file_path.is_file():
                            continue

                        files_searched += 1

                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                            for line_num, line in enumerate(content.splitlines(), 1):
                                if regex.search(line):
                                    rel_path = file_path.relative_to(base_path)
                                    results.append(f"{rel_path}:{line_num}: {line.strip()}")
                                    if len(results) >= max_results:
                                        break
                        except Exception:
                            continue

                        if len(results) >= max_results:
                            break

                    if not results:
                        return f"No matches found for pattern: {pattern}"

                    result = "\\n".join(results)
                    if len(results) >= max_results:
                        result += f"\\n\\n[Results limited to {max_results} matches]"

                    return result

                except re.error as e:
                    return f"Invalid regex pattern: {str(e)}"
                except Exception as e:
                    return f"Grep error: {str(e)}"
        ''').strip()

    @staticmethod
    def get_reasoning_chain_impl() -> str:
        """Get reasoning_chain tool implementation."""
        return dedent('''
            @tool
            def reasoning_chain(task: str, steps: int = 5) -> str:
                """
                Break down a complex task into reasoning steps.

                Args:
                    task: The task to reason about
                    steps: Number of reasoning steps

                Returns:
                    Structured reasoning framework
                """
                return f"""
            TASK: {task}

            REASONING STEPS:
            1. Analyze the requirements and constraints
            2. Identify key objectives and success criteria
            3. Consider potential approaches and trade-offs
            4. Evaluate risks and mitigation strategies
            5. Synthesize into a concrete action plan

            Note: The agent should fill in the actual analysis for each step.
            """
        ''').strip()

    @staticmethod
    def get_memory_tools_impl() -> str:
        """Get memory_store and memory_recall tool implementations."""
        return dedent('''
            import json
            from pathlib import Path
            from datetime import datetime

            # Memory file path (persists across runs)
            MEMORY_FILE = Path(__file__).parent.parent / "memory_store.json"


            def _load_memory() -> dict:
                """Load memory from file."""
                if MEMORY_FILE.exists():
                    try:
                        return json.loads(MEMORY_FILE.read_text())
                    except Exception:
                        return {"memories": []}
                return {"memories": []}


            def _save_memory(data: dict):
                """Save memory to file."""
                MEMORY_FILE.write_text(json.dumps(data, indent=2))


            @tool
            def memory_store(content: str, metadata: str = "") -> str:
                """
                Store information in long-term memory.

                Args:
                    content: The content to remember
                    metadata: Optional metadata/tags for the memory

                Returns:
                    Confirmation message
                """
                try:
                    data = _load_memory()
                    memory_entry = {
                        "content": content,
                        "metadata": metadata,
                        "timestamp": datetime.now().isoformat()
                    }
                    data["memories"].append(memory_entry)
                    _save_memory(data)
                    return f"Stored in memory: {content[:100]}..."
                except Exception as e:
                    return f"Memory store error: {str(e)}"


            @tool
            def memory_recall(query: str, max_results: int = 5) -> str:
                """
                Recall information from long-term memory.

                Args:
                    query: Search query to find relevant memories
                    max_results: Maximum number of memories to return

                Returns:
                    Relevant memories as formatted text
                """
                try:
                    data = _load_memory()
                    memories = data.get("memories", [])

                    if not memories:
                        return "No memories stored yet."

                    # Simple keyword matching (could be enhanced with embeddings)
                    query_lower = query.lower()
                    relevant = []
                    for mem in memories:
                        content = mem.get("content", "").lower()
                        metadata = mem.get("metadata", "").lower()
                        if query_lower in content or query_lower in metadata:
                            relevant.append(mem)

                    # If no keyword matches, return most recent
                    if not relevant:
                        relevant = memories[-max_results:]

                    relevant = relevant[:max_results]

                    if not relevant:
                        return "No relevant memories found."

                    result = "RECALLED MEMORIES:\\n"
                    for i, mem in enumerate(relevant, 1):
                        result += f"\\n{i}. {mem.get('content', '')}\\n"
                        if mem.get('metadata'):
                            result += f"   [Metadata: {mem['metadata']}]\\n"
                        result += f"   [Stored: {mem.get('timestamp', 'unknown')}]\\n"

                    return result
                except Exception as e:
                    return f"Memory recall error: {str(e)}"
        ''').strip()

    @staticmethod
    def generate_native_tools_module(used_native_tools: Set[str]) -> str:
        """
        Generate tools/native.py with native tool implementations.

        Args:
            used_native_tools: Set of native tool names used in the workflow
        """
        tool_implementations = []

        if "web_search" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_web_search_impl())

        if "web_fetch" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_web_fetch_impl())

        # Filesystem tools (DeepAgents standard naming)
        if "read_file" in used_native_tools or "file_read" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_read_file_impl())

        if "write_file" in used_native_tools or "file_write" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_write_file_impl())

        if "ls" in used_native_tools or "file_list" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_ls_impl())

        if "edit_file" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_edit_file_impl())

        if "glob" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_glob_impl())

        if "grep" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_grep_impl())

        if "reasoning_chain" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_reasoning_chain_impl())

        # Memory tools share helper functions, so include them together
        if "memory_store" in used_native_tools or "memory_recall" in used_native_tools:
            tool_implementations.append(ToolGenerators.get_memory_tools_impl())

        tools_code = "\n\n\n".join(tool_implementations) if tool_implementations else "# No native tools used"

        # Build registry - map LangConfig aliases to actual function names
        tool_name_mapping = {
            "file_read": "read_file",
            "file_write": "write_file",
            "file_list": "ls",
        }
        registry_entries = []
        for tool in used_native_tools:
            # Map alias to actual function name, or use tool name as-is
            func_name = tool_name_mapping.get(tool, tool)
            registry_entries.append(f'    "{tool}": {func_name},')
        registry_str = "\n".join(registry_entries) if registry_entries else "    # No tools"

        header = '''"""Native Python tools for workflow execution."""

import logging
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


'''
        footer = f'''


# Tool registry
NATIVE_TOOLS = {{
{registry_str}
}}


def get_tool_by_name(name: str):
    """Get a native tool by name."""
    return NATIVE_TOOLS.get(name)
'''
        return header + tools_code + footer
