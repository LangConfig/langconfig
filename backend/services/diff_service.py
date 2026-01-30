# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Diff Service - Generate diffs for file version comparison.

Provides utilities for generating unified diffs, side-by-side comparisons,
and diff statistics for the file viewer.
"""
import difflib
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiffLine:
    """Represents a single line in a diff view."""
    line_type: str  # 'context', 'add', 'remove', 'info'
    content: str
    old_line_num: Optional[int] = None
    new_line_num: Optional[int] = None


@dataclass
class DiffHunk:
    """A hunk of changes in a diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine]


@dataclass
class DiffStats:
    """Statistics about a diff."""
    lines_added: int
    lines_removed: int
    lines_changed: int
    total_changes: int
    similarity_ratio: float


@dataclass
class SideBySideLine:
    """Represents a line in side-by-side view."""
    left_num: Optional[int]
    left_content: Optional[str]
    left_type: str  # 'normal', 'removed', 'empty'
    right_num: Optional[int]
    right_content: Optional[str]
    right_type: str  # 'normal', 'added', 'empty'


class DiffService:
    """Service for generating file diffs."""

    def __init__(self, context_lines: int = 3):
        """
        Initialize the diff service.

        Args:
            context_lines: Number of context lines around changes (default: 3)
        """
        self.context_lines = context_lines

    def generate_unified_diff(
        self,
        old_content: str,
        new_content: str,
        old_name: str = "original",
        new_name: str = "modified"
    ) -> str:
        """
        Generate a unified diff string (git-style).

        Args:
            old_content: The original file content
            new_content: The new file content
            old_name: Label for the original file
            new_name: Label for the modified file

        Returns:
            Unified diff as a string
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_name,
            tofile=new_name,
            n=self.context_lines
        )

        return ''.join(diff)

    def generate_structured_diff(
        self,
        old_content: str,
        new_content: str
    ) -> List[DiffHunk]:
        """
        Generate a structured diff with hunks.

        Args:
            old_content: The original file content
            new_content: The new file content

        Returns:
            List of DiffHunk objects
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        hunks = []

        for group in matcher.get_grouped_opcodes(self.context_lines):
            hunk_lines = []
            old_start = group[0][1]
            old_end = group[-1][2]
            new_start = group[0][3]
            new_end = group[-1][4]

            for tag, i1, i2, j1, j2 in group:
                if tag == 'equal':
                    for i, line in enumerate(old_lines[i1:i2]):
                        hunk_lines.append(DiffLine(
                            line_type='context',
                            content=line,
                            old_line_num=i1 + i + 1,
                            new_line_num=j1 + i + 1
                        ))
                elif tag == 'delete':
                    for i, line in enumerate(old_lines[i1:i2]):
                        hunk_lines.append(DiffLine(
                            line_type='remove',
                            content=line,
                            old_line_num=i1 + i + 1,
                            new_line_num=None
                        ))
                elif tag == 'insert':
                    for i, line in enumerate(new_lines[j1:j2]):
                        hunk_lines.append(DiffLine(
                            line_type='add',
                            content=line,
                            old_line_num=None,
                            new_line_num=j1 + i + 1
                        ))
                elif tag == 'replace':
                    for i, line in enumerate(old_lines[i1:i2]):
                        hunk_lines.append(DiffLine(
                            line_type='remove',
                            content=line,
                            old_line_num=i1 + i + 1,
                            new_line_num=None
                        ))
                    for i, line in enumerate(new_lines[j1:j2]):
                        hunk_lines.append(DiffLine(
                            line_type='add',
                            content=line,
                            old_line_num=None,
                            new_line_num=j1 + i + 1
                        ))

            hunks.append(DiffHunk(
                old_start=old_start + 1,
                old_count=old_end - old_start,
                new_start=new_start + 1,
                new_count=new_end - new_start,
                lines=hunk_lines
            ))

        return hunks

    def generate_side_by_side(
        self,
        old_content: str,
        new_content: str
    ) -> List[SideBySideLine]:
        """
        Generate a side-by-side diff view.

        Args:
            old_content: The original file content
            new_content: The new file content

        Returns:
            List of SideBySideLine objects for display
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        result = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for i in range(i2 - i1):
                    result.append(SideBySideLine(
                        left_num=i1 + i + 1,
                        left_content=old_lines[i1 + i],
                        left_type='normal',
                        right_num=j1 + i + 1,
                        right_content=new_lines[j1 + i],
                        right_type='normal'
                    ))
            elif tag == 'delete':
                for i in range(i2 - i1):
                    result.append(SideBySideLine(
                        left_num=i1 + i + 1,
                        left_content=old_lines[i1 + i],
                        left_type='removed',
                        right_num=None,
                        right_content=None,
                        right_type='empty'
                    ))
            elif tag == 'insert':
                for i in range(j2 - j1):
                    result.append(SideBySideLine(
                        left_num=None,
                        left_content=None,
                        left_type='empty',
                        right_num=j1 + i + 1,
                        right_content=new_lines[j1 + i],
                        right_type='added'
                    ))
            elif tag == 'replace':
                # For replace, show both sides
                max_len = max(i2 - i1, j2 - j1)
                for i in range(max_len):
                    left_idx = i1 + i if i < (i2 - i1) else None
                    right_idx = j1 + i if i < (j2 - j1) else None

                    result.append(SideBySideLine(
                        left_num=left_idx + 1 if left_idx is not None else None,
                        left_content=old_lines[left_idx] if left_idx is not None else None,
                        left_type='removed' if left_idx is not None else 'empty',
                        right_num=right_idx + 1 if right_idx is not None else None,
                        right_content=new_lines[right_idx] if right_idx is not None else None,
                        right_type='added' if right_idx is not None else 'empty'
                    ))

        return result

    def calculate_stats(self, old_content: str, new_content: str) -> DiffStats:
        """
        Calculate statistics about the difference between two contents.

        Args:
            old_content: The original file content
            new_content: The new file content

        Returns:
            DiffStats object with statistics
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

        lines_added = 0
        lines_removed = 0
        lines_changed = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                lines_removed += i2 - i1
            elif tag == 'insert':
                lines_added += j2 - j1
            elif tag == 'replace':
                old_count = i2 - i1
                new_count = j2 - j1
                lines_changed += min(old_count, new_count)
                if old_count > new_count:
                    lines_removed += old_count - new_count
                else:
                    lines_added += new_count - old_count

        return DiffStats(
            lines_added=lines_added,
            lines_removed=lines_removed,
            lines_changed=lines_changed,
            total_changes=lines_added + lines_removed + lines_changed,
            similarity_ratio=matcher.ratio()
        )

    def highlight_inline_changes(
        self,
        old_line: str,
        new_line: str
    ) -> Tuple[List[Tuple[int, int, str]], List[Tuple[int, int, str]]]:
        """
        Highlight character-level changes within a line.

        Args:
            old_line: The original line
            new_line: The modified line

        Returns:
            Tuple of (old_highlights, new_highlights) where each is a list
            of (start, end, type) tuples indicating highlighted regions
        """
        matcher = difflib.SequenceMatcher(None, old_line, new_line)
        old_highlights = []
        new_highlights = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'delete':
                old_highlights.append((i1, i2, 'delete'))
            elif tag == 'insert':
                new_highlights.append((j1, j2, 'insert'))
            elif tag == 'replace':
                old_highlights.append((i1, i2, 'change'))
                new_highlights.append((j1, j2, 'change'))

        return old_highlights, new_highlights


def generate_unified_diff(old: str, new: str, filename: str = "file") -> str:
    """
    Convenience function to generate a unified diff.

    Args:
        old: The original content
        new: The new content
        filename: Name to use in diff headers

    Returns:
        Unified diff string
    """
    service = DiffService()
    return service.generate_unified_diff(old, new, f"a/{filename}", f"b/{filename}")


def generate_side_by_side(old: str, new: str) -> List[Dict[str, Any]]:
    """
    Convenience function to generate a side-by-side diff.

    Args:
        old: The original content
        new: The new content

    Returns:
        List of line dictionaries for side-by-side view
    """
    service = DiffService()
    lines = service.generate_side_by_side(old, new)

    return [
        {
            'left_num': line.left_num,
            'left_content': line.left_content,
            'left_type': line.left_type,
            'right_num': line.right_num,
            'right_content': line.right_content,
            'right_type': line.right_type,
        }
        for line in lines
    ]


def get_diff_stats(old: str, new: str) -> Dict[str, Any]:
    """
    Convenience function to get diff statistics.

    Args:
        old: The original content
        new: The new content

    Returns:
        Dictionary with diff statistics
    """
    service = DiffService()
    stats = service.calculate_stats(old, new)

    return {
        'lines_added': stats.lines_added,
        'lines_removed': stats.lines_removed,
        'lines_changed': stats.lines_changed,
        'total_changes': stats.total_changes,
        'similarity_ratio': round(stats.similarity_ratio * 100, 1),
    }
