# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skill Loader - Parses SKILL.md files and validates structure.

Responsible for:
- Discovering SKILL.md files in known locations
- Parsing YAML frontmatter + markdown content
- Validating required fields
- Creating ParsedSkill dataclass instances

SKILL.md Format:
```markdown
---
name: skill-name
description: "What this skill does and when to use it"
version: 1.0.0
tags: [tag1, tag2]
triggers:
  - "when user mentions X"
  - "when file extension is .py"
allowed_tools: [tool1, tool2]  # Optional
---

## Instructions
[Instructions injected into agent system prompt]

## Examples
[Optional usage examples]
```
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ParsedSkill:
    """Parsed skill data from a SKILL.md file."""
    skill_id: str
    name: str
    description: str
    version: str
    author: Optional[str]
    tags: List[str]
    triggers: List[str]
    allowed_tools: Optional[List[str]]
    required_context: List[str]
    instructions: str
    examples: Optional[str]
    source_path: str
    file_modified_at: datetime


@dataclass
class SkillDiscoveryResult:
    """Result of discovering a skill directory."""
    skill_path: str
    source_type: str  # builtin, personal, project
    project_path: Optional[str] = None


class SkillLoader:
    """
    Load and parse SKILL.md files from filesystem.

    Discovers skills from three locations:
    1. Built-in skills (shipped with app)
    2. Personal skills (~/.langconfig/skills)
    3. Project skills (<project>/.langconfig/skills)
    """

    SKILL_FILENAME = "SKILL.md"

    def __init__(
        self,
        builtin_path: Optional[str] = None,
        personal_path: Optional[str] = None,
        project_paths: Optional[List[str]] = None
    ):
        """
        Initialize loader with skill discovery paths.

        Args:
            builtin_path: Path to built-in skills (shipped with app)
            personal_path: Path to user's personal skills (~/.langconfig/skills)
            project_paths: List of project-specific skill directories
        """
        self.builtin_path = builtin_path or self._default_builtin_path()
        self.personal_path = personal_path or self._default_personal_path()
        self.project_paths = project_paths or []

    def _default_builtin_path(self) -> str:
        """Get default path for built-in skills."""
        # backend/skills/builtin/
        return str(Path(__file__).parent.parent.parent / "skills" / "builtin")

    def _default_personal_path(self) -> str:
        """Get default path for personal skills."""
        home = Path.home()
        return str(home / ".langconfig" / "skills")

    def discover_all(self) -> List[SkillDiscoveryResult]:
        """
        Discover all SKILL.md files across all locations.

        Returns:
            List of SkillDiscoveryResult with skill paths and source info
        """
        discovered = []

        # Built-in skills
        if os.path.exists(self.builtin_path):
            for skill_dir in self._find_skill_dirs(self.builtin_path):
                discovered.append(SkillDiscoveryResult(
                    skill_path=skill_dir,
                    source_type="builtin"
                ))

        # Personal skills
        if os.path.exists(self.personal_path):
            for skill_dir in self._find_skill_dirs(self.personal_path):
                discovered.append(SkillDiscoveryResult(
                    skill_path=skill_dir,
                    source_type="personal"
                ))

        # Project skills
        for project_path in self.project_paths:
            skill_base = os.path.join(project_path, ".langconfig", "skills")
            if os.path.exists(skill_base):
                for skill_dir in self._find_skill_dirs(skill_base):
                    discovered.append(SkillDiscoveryResult(
                        skill_path=skill_dir,
                        source_type="project",
                        project_path=project_path
                    ))

        logger.info(f"Discovered {len(discovered)} skill directories")
        return discovered

    def _find_skill_dirs(self, base_path: str) -> List[str]:
        """Find all directories containing SKILL.md files."""
        skill_dirs = []
        try:
            for entry in os.scandir(base_path):
                if entry.is_dir():
                    skill_file = os.path.join(entry.path, self.SKILL_FILENAME)
                    if os.path.exists(skill_file):
                        skill_dirs.append(entry.path)
        except OSError as e:
            logger.warning(f"Error scanning directory {base_path}: {e}")
        return skill_dirs

    def load_skill(self, skill_dir: str) -> Optional[ParsedSkill]:
        """
        Load and parse a single skill from its directory.

        Args:
            skill_dir: Path to skill directory containing SKILL.md

        Returns:
            ParsedSkill if successful, None if parsing fails
        """
        skill_file = os.path.join(skill_dir, self.SKILL_FILENAME)

        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse frontmatter and content
            frontmatter, body = self._parse_frontmatter(content)

            # Extract sections
            instructions, examples = self._parse_body_sections(body)

            # Validate required fields
            if not frontmatter.get('name'):
                raise ValueError("Missing required 'name' field in frontmatter")
            if not frontmatter.get('description'):
                raise ValueError("Missing required 'description' field in frontmatter")
            if not instructions:
                raise ValueError("Missing required '## Instructions' section")

            # Get file modification time (timezone-aware for DB comparison)
            file_stat = os.stat(skill_file)
            file_modified = datetime.fromtimestamp(file_stat.st_mtime).astimezone()

            # Build human-readable name from skill_id if not provided
            skill_id = frontmatter['name']
            display_name = frontmatter.get('display_name') or skill_id.replace('-', ' ').title()

            return ParsedSkill(
                skill_id=skill_id,
                name=display_name,
                description=frontmatter['description'],
                version=frontmatter.get('version', '1.0.0'),
                author=frontmatter.get('author'),
                tags=frontmatter.get('tags', []),
                triggers=frontmatter.get('triggers', []),
                allowed_tools=frontmatter.get('allowed_tools'),
                required_context=frontmatter.get('required_context', []),
                instructions=instructions,
                examples=examples,
                source_path=skill_dir,
                file_modified_at=file_modified
            )

        except Exception as e:
            logger.error(f"Failed to load skill from {skill_dir}: {e}")
            return None

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.

        Frontmatter is delimited by --- at start and end.

        Args:
            content: Full SKILL.md file content

        Returns:
            Tuple of (frontmatter dict, remaining body content)
        """
        if not content.startswith('---'):
            return {}, content

        # Find end of frontmatter
        end_idx = content.find('---', 3)
        if end_idx == -1:
            return {}, content

        frontmatter_str = content[3:end_idx].strip()
        body = content[end_idx + 3:].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Invalid YAML in frontmatter: {e}")
            frontmatter = {}

        return frontmatter, body

    def _parse_body_sections(self, body: str) -> Tuple[str, Optional[str]]:
        """
        Extract Instructions and Examples sections from body.

        Looks for ## Instructions and ## Examples headers.

        Args:
            body: Markdown body after frontmatter

        Returns:
            Tuple of (instructions, examples or None)
        """
        instructions_lines = []
        examples_lines = []

        current_section = None
        lines = body.split('\n')

        for line in lines:
            # Check for section headers
            if line.startswith('## Instructions'):
                current_section = 'instructions'
                continue
            elif line.startswith('## Examples'):
                current_section = 'examples'
                continue
            elif line.startswith('## '):
                # Other section - stop capturing
                current_section = None
                continue

            # Capture content for current section
            if current_section == 'instructions':
                instructions_lines.append(line)
            elif current_section == 'examples':
                examples_lines.append(line)

        instructions = '\n'.join(instructions_lines).strip()
        examples = '\n'.join(examples_lines).strip() if examples_lines else None

        return instructions, examples

    def validate_skill_id(self, skill_id: str) -> bool:
        """
        Validate skill ID format (kebab-case).

        Args:
            skill_id: The skill identifier to validate

        Returns:
            True if valid, False otherwise
        """
        import re
        if not skill_id:
            return False
        return bool(re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', skill_id))
