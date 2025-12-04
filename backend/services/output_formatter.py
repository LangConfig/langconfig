# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Output Formatting Service for Workflow Results

Transforms raw workflow outputs into beautifully formatted, structured data
optimized for frontend rendering with markdown, code highlighting, and rich visualizations.

Supports:
- Automatic content-type detection (code, markdown, research, analysis)
- Markdown extraction and formatting
- Code block detection and language identification
- Structured output transformation
- Multi-format output (JSON, markdown, HTML preview)

Inspired by AG-UI Protocol (2025) for real-time AI agent UI generation.
"""

import logging
import re
import json
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class OutputType(str, Enum):
    """Detected output content type"""
    MARKDOWN = "markdown"
    CODE = "code"
    JSON_DATA = "json"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    TASK_PLAN = "task_plan"
    DOCUMENTATION = "documentation"
    MIXED = "mixed"
    PLAIN_TEXT = "plain_text"


class CodeBlock:
    """Represents a detected code block"""
    def __init__(
        self,
        language: str,
        code: str,
        line_start: Optional[int] = None,
        filename: Optional[str] = None
    ):
        self.language = language
        self.code = code
        self.line_start = line_start
        self.filename = filename

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "code": self.code,
            "line_start": self.line_start,
            "filename": self.filename,
            "line_count": len(self.code.split('\n'))
        }


class FormattedOutput:
    """Container for formatted workflow output"""
    def __init__(
        self,
        raw_output: Any,
        output_type: OutputType,
        formatted_content: str,
        metadata: Dict[str, Any],
        code_blocks: Optional[List[CodeBlock]] = None,
        sections: Optional[List[Dict[str, Any]]] = None
    ):
        self.raw_output = raw_output
        self.output_type = output_type
        self.formatted_content = formatted_content
        self.metadata = metadata
        self.code_blocks = code_blocks or []
        self.sections = sections or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to frontend-friendly dictionary"""
        return {
            "output_type": self.output_type.value,
            "formatted_content": self.formatted_content,
            "metadata": {
                **self.metadata,
                "formatted_at": datetime.utcnow().isoformat(),
                "has_code": len(self.code_blocks) > 0,
                "code_block_count": len(self.code_blocks),
                "section_count": len(self.sections)
            },
            "code_blocks": [cb.to_dict() for cb in self.code_blocks],
            "sections": self.sections
        }


class OutputFormatter:
    """
    Format workflow outputs for optimal frontend display.

    Detects content type, extracts code blocks, formats markdown,
    and structures data for UI rendering.
    """

    # Code fence patterns
    CODE_FENCE_PATTERN = re.compile(
        r'```(\w+)?\n(.*?)```',
        re.DOTALL | re.MULTILINE
    )

    # Inline code pattern
    INLINE_CODE_PATTERN = re.compile(r'`([^`]+)`')

    # Markdown heading pattern
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

    # Language detection keywords
    LANGUAGE_KEYWORDS = {
        'python': ['def ', 'import ', 'class ', 'async ', 'await '],
        'javascript': ['const ', 'let ', 'var ', 'function ', '=>', 'async '],
        'typescript': ['interface ', 'type ', 'enum ', 'const ', ': '],
        'java': ['public class', 'private ', 'protected ', 'import '],
        'sql': ['SELECT ', 'FROM ', 'WHERE ', 'JOIN ', 'INSERT '],
        'bash': ['#!/bin/bash', 'echo ', 'export ', 'sudo '],
        'json': ['{', '[', '":', '"}'],
        'yaml': ['---', '  -', 'key:'],
    }

    def format_output(
        self,
        raw_output: Any,
        workflow_name: Optional[str] = None,
        task_id: Optional[int] = None
    ) -> FormattedOutput:
        """
        Format workflow output for frontend display.

        Args:
            raw_output: Raw output from workflow execution
            workflow_name: Optional workflow name for context
            task_id: Optional task ID for tracking

        Returns:
            FormattedOutput object with structured data
        """
        logger.info(f"Formatting output for workflow '{workflow_name}' (task {task_id})")

        try:
            # Extract text content from various output formats
            text_content = self._extract_text_content(raw_output)

            # Detect output type
            output_type = self._detect_output_type(text_content, raw_output)
            logger.debug(f"Detected output type: {output_type}")

            # Extract code blocks
            code_blocks = self._extract_code_blocks(text_content)
            logger.debug(f"Extracted {len(code_blocks)} code blocks")

            # Extract sections if markdown
            sections = []
            if output_type in [OutputType.MARKDOWN, OutputType.RESEARCH, OutputType.DOCUMENTATION]:
                sections = self._extract_sections(text_content)
                logger.debug(f"Extracted {len(sections)} sections")

            # Format content based on type
            formatted_content = self._format_content(text_content, output_type)

            # Build metadata
            metadata = {
                "workflow_name": workflow_name,
                "task_id": task_id,
                "detected_type": output_type.value,
                "char_count": len(text_content),
                "word_count": len(text_content.split()),
                "line_count": len(text_content.split('\n'))
            }

            return FormattedOutput(
                raw_output=raw_output,
                output_type=output_type,
                formatted_content=formatted_content,
                metadata=metadata,
                code_blocks=code_blocks,
                sections=sections
            )

        except Exception as e:
            logger.error(f"Output formatting failed: {e}", exc_info=True)
            # Return fallback formatted output
            return FormattedOutput(
                raw_output=raw_output,
                output_type=OutputType.PLAIN_TEXT,
                formatted_content=str(raw_output),
                metadata={"error": str(e)},
                code_blocks=[],
                sections=[]
            )

    def _extract_text_content(self, raw_output: Any) -> str:
        """Extract text content from various output formats."""
        if isinstance(raw_output, str):
            return raw_output

        if isinstance(raw_output, dict):
            # Check for formatted_output structure
            if "formatted_output" in raw_output:
                formatted = raw_output["formatted_output"]
                if isinstance(formatted, dict) and "messages" in formatted:
                    # Join messages
                    messages = formatted["messages"]
                    if isinstance(messages, list):
                        return "\n\n".join(str(msg) for msg in messages)
                    return str(messages)
                return str(formatted)

            # Check for messages field
            if "messages" in raw_output:
                messages = raw_output["messages"]
                if isinstance(messages, list) and len(messages) > 0:
                    # Extract ALL AI messages (for multi-agent workflows)
                    # Each agent in the workflow produces valuable output
                    ai_messages = []
                    
                    for msg in messages:
                        # Check if it's an AI message
                        is_ai = False
                        if hasattr(msg, '__class__'):
                            is_ai = msg.__class__.__name__ in ['AIMessage', 'SystemMessage']
                        elif isinstance(msg, dict):
                            is_ai = msg.get('type') in ['ai', 'system', 'AIMessage']

                        if is_ai:
                            content = None
                            if hasattr(msg, 'content'):
                                content = msg.content
                                # Handle content as list of blocks (Claude API format)
                                if isinstance(content, list):
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            text_parts.append(block.get('text', ''))
                                        elif isinstance(block, str):
                                            text_parts.append(block)
                                    content = '\n'.join(text_parts) if text_parts else str(content)
                            elif isinstance(msg, dict) and "content" in msg:
                                content = msg["content"]
                                # Handle content as list of blocks
                                if isinstance(content, list):
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict) and block.get('type') == 'text':
                                            text_parts.append(block.get('text', ''))
                                        elif isinstance(block, str):
                                            text_parts.append(block)
                                    content = '\n'.join(text_parts) if text_parts else str(content)
                            else:
                                content = str(msg)
                            
                            if content:
                                ai_messages.append(content)
                    
                    # Return final AI message (the final product/result)
                    # For multi-agent workflows, this is the synthesized final output
                    # Full conversation history is shown in LiveExecutionPanel
                    if ai_messages:
                        # Return the LAST AI message (the final agent's output)
                        # This is the final product/result for display
                        return ai_messages[-1]
                    
                    # Fallback: if no AI message found, return last message
                    last_msg = messages[-1]
                    if hasattr(last_msg, 'content'):
                        return last_msg.content
                    elif isinstance(last_msg, dict) and "content" in last_msg:
                        return last_msg["content"]
                    else:
                        return str(last_msg)

            # Fallback to JSON string (with datetime serialization support)
            return json.dumps(raw_output, indent=2, default=str)

        if isinstance(raw_output, list):
            # Extract content from LangChain message objects
            contents = []
            for item in raw_output:
                if hasattr(item, 'content'):
                    # LangChain message object
                    contents.append(item.content)
                elif isinstance(item, dict) and "content" in item:
                    contents.append(item["content"])
                else:
                    contents.append(str(item))
            return "\n\n".join(contents)

        # Check if it's a LangChain message object
        if hasattr(raw_output, 'content'):
            return raw_output.content

        return str(raw_output)

    def _detect_output_type(self, content: str, raw_output: Any) -> OutputType:
        """Detect the type of output content."""
        # Check for code blocks
        has_code_blocks = bool(self.CODE_FENCE_PATTERN.search(content))

        # Check for markdown headings
        has_headings = bool(self.HEADING_PATTERN.search(content))

        # Check for structured data
        is_json = isinstance(raw_output, dict)

        # Research paper indicators
        research_keywords = ["abstract", "introduction", "methodology", "conclusion", "references"]
        has_research_structure = sum(
            kw in content.lower() for kw in research_keywords
        ) >= 3

        # Documentation indicators
        doc_keywords = ["## ", "### ", "#### ", "**Note:**", "**Example:**"]
        has_doc_structure = sum(kw in content for kw in doc_keywords) >= 2

        # Task plan indicators
        task_keywords = ["- [ ]", "- [x]", "TODO:", "DONE:", "Step "]
        has_task_structure = sum(kw in content for kw in task_keywords) >= 2

        # Decision logic
        if has_research_structure:
            return OutputType.RESEARCH
        elif has_doc_structure and has_headings:
            return OutputType.DOCUMENTATION
        elif has_task_structure:
            return OutputType.TASK_PLAN
        elif has_code_blocks and not has_headings:
            return OutputType.CODE
        elif has_headings and has_code_blocks:
            return OutputType.MIXED
        elif has_headings or content.count('\n') > 5:
            return OutputType.MARKDOWN
        elif is_json and not isinstance(raw_output, str):
            return OutputType.JSON_DATA
        else:
            return OutputType.PLAIN_TEXT

    def _extract_code_blocks(self, content: str) -> List[CodeBlock]:
        """Extract all code blocks from content."""
        code_blocks = []

        for match in self.CODE_FENCE_PATTERN.finditer(content):
            language = match.group(1) or "plaintext"
            code = match.group(2).strip()

            # Auto-detect language if not specified
            if language == "plaintext" or not language:
                language = self._detect_language(code)

            code_blocks.append(CodeBlock(
                language=language.lower(),
                code=code
            ))

        return code_blocks

    def _detect_language(self, code: str) -> str:
        """Auto-detect programming language from code content."""
        code_lower = code.lower()

        # Count keyword matches for each language
        scores = {}
        for lang, keywords in self.LANGUAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in code_lower)
            if score > 0:
                scores[lang] = score

        # Return language with highest score
        if scores:
            return max(scores, key=scores.get)

        return "plaintext"

    def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """Extract markdown sections based on headings."""
        sections = []
        lines = content.split('\n')

        current_section = None
        current_content = []

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(line)

            if heading_match:
                # Save previous section
                if current_section:
                    sections.append({
                        **current_section,
                        "content": '\n'.join(current_content).strip()
                    })

                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_section = {
                    "level": level,
                    "title": title,
                    "id": self._slugify(title)
                }
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_section:
            sections.append({
                **current_section,
                "content": '\n'.join(current_content).strip()
            })

        return sections

    def _format_content(self, content: str, output_type: OutputType) -> str:
        """Apply formatting based on output type."""
        # For most types, return content as-is (frontend will render markdown)
        if output_type in [OutputType.MARKDOWN, OutputType.RESEARCH, OutputType.DOCUMENTATION]:
            return content

        # For code-only, wrap in code fence if not already
        if output_type == OutputType.CODE:
            if not content.startswith('```'):
                language = self._detect_language(content)
                return f"```{language}\n{content}\n```"

        return content

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')


# Global formatter instance
_formatter: Optional[OutputFormatter] = None


def get_output_formatter() -> OutputFormatter:
    """Get or create the global output formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = OutputFormatter()
        logger.info("Initialized global OutputFormatter")
    return _formatter


def format_workflow_output(
    raw_output: Any,
    workflow_name: Optional[str] = None,
    task_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Convenience function to format workflow output.

    Returns frontend-ready dictionary.
    """
    formatter = get_output_formatter()
    formatted = formatter.format_output(raw_output, workflow_name, task_id)
    return formatted.to_dict()
