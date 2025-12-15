# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skill Registry - In-memory registry with database persistence.

Responsible for:
- Maintaining indexed skills in memory for fast lookup
- Syncing with database on changes
- Providing query APIs (by ID, by tags, semantic search)
- Managing skill lifecycle (load, reload, invalidate)
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.skill import Skill, SkillExecution, SkillSourceType, SkillInvocationType
from core.skills.loader import SkillLoader, ParsedSkill, SkillDiscoveryResult
from db.database import get_async_session, AsyncSessionLocal

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Central registry for skills with in-memory caching.

    Provides fast in-memory lookups while persisting to database.
    Automatically syncs skills from filesystem on initialization.

    Usage:
        registry = SkillRegistry()
        await registry.initialize()

        skill = registry.get_skill("python-testing")
        matching = registry.find_by_tags(["python", "testing"])
    """

    _instance: Optional['SkillRegistry'] = None

    def __init__(self):
        self._skills: Dict[str, Skill] = {}  # skill_id -> Skill
        self._by_tag: Dict[str, Set[str]] = {}  # tag -> set of skill_ids
        self._loader = SkillLoader()
        self._initialized = False
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'SkillRegistry':
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (useful for testing)."""
        cls._instance = None

    async def initialize(self, project_paths: Optional[List[str]] = None) -> int:
        """
        Initialize registry by scanning filesystem and syncing with database.

        Args:
            project_paths: Optional list of project paths to scan for skills

        Returns:
            Number of skills loaded
        """
        async with self._lock:
            if self._initialized:
                return len(self._skills)

            logger.info("Initializing skill registry...")

            # Update loader with project paths
            if project_paths:
                self._loader.project_paths = project_paths

            # Discover all skills from filesystem
            discovered = self._loader.discover_all()

            # Load and index each skill
            loaded_count = 0
            async with AsyncSessionLocal() as session:
                for discovery in discovered:
                    success = await self._load_and_index_skill(
                        session,
                        discovery.skill_path,
                        discovery.source_type,
                        discovery.project_path
                    )
                    if success:
                        loaded_count += 1
                await session.commit()

            self._initialized = True
            logger.info(f"Skill registry initialized with {loaded_count} skills")
            return loaded_count

    async def _load_and_index_skill(
        self,
        session: AsyncSession,
        skill_dir: str,
        source_type: str,
        project_path: Optional[str]
    ) -> bool:
        """
        Load a skill from filesystem and sync to database.

        Returns True if skill was successfully loaded.
        """
        parsed = self._loader.load_skill(skill_dir)
        if not parsed:
            logger.error(f"Failed to parse skill from {skill_dir}")
            return False

        logger.info(f"Parsed skill '{parsed.skill_id}' from {skill_dir}")

        try:
            # Check if skill exists in database
            result = await session.execute(
                select(Skill).where(Skill.skill_id == parsed.skill_id)
            )
            existing_skill = result.scalar_one_or_none()

            if existing_skill:
                # Update if file changed
                if existing_skill.file_modified_at < parsed.file_modified_at:
                    existing_skill.name = parsed.name
                    existing_skill.description = parsed.description
                    existing_skill.version = parsed.version
                    existing_skill.author = parsed.author
                    existing_skill.tags = parsed.tags
                    existing_skill.triggers = parsed.triggers
                    existing_skill.allowed_tools = parsed.allowed_tools
                    existing_skill.required_context = parsed.required_context
                    existing_skill.instructions = parsed.instructions
                    existing_skill.examples = parsed.examples
                    existing_skill.file_modified_at = parsed.file_modified_at
                    existing_skill.indexed_at = datetime.utcnow()
                    logger.debug(f"Updated skill '{parsed.skill_id}' from filesystem")
                skill = existing_skill
            else:
                # Create new skill record
                skill = Skill(
                    skill_id=parsed.skill_id,
                    name=parsed.name,
                    description=parsed.description,
                    version=parsed.version,
                    author=parsed.author,
                    source_type=SkillSourceType(source_type),
                    source_path=parsed.source_path,
                    tags=parsed.tags,
                    triggers=parsed.triggers,
                    allowed_tools=parsed.allowed_tools,
                    required_context=parsed.required_context,
                    instructions=parsed.instructions,
                    examples=parsed.examples,
                    file_modified_at=parsed.file_modified_at
                )
                session.add(skill)
                logger.debug(f"Created new skill '{parsed.skill_id}'")

            # Index in memory
            self._skills[parsed.skill_id] = skill

            # Build tag index
            for tag in parsed.tags:
                tag_lower = tag.lower()
                if tag_lower not in self._by_tag:
                    self._by_tag[tag_lower] = set()
                self._by_tag[tag_lower].add(parsed.skill_id)

            return True

        except Exception as e:
            import traceback
            logger.error(f"Failed to index skill '{parsed.skill_id}': {e}")
            logger.error(traceback.format_exc())
            return False

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get skill by ID."""
        return self._skills.get(skill_id)

    def list_all(self) -> List[Skill]:
        """List all registered skills."""
        return list(self._skills.values())

    def find_by_tags(self, tags: List[str], match_all: bool = False) -> List[Skill]:
        """
        Find skills matching tags.

        Args:
            tags: List of tags to match
            match_all: If True, skill must have all tags. If False, any tag matches.

        Returns:
            List of matching skills
        """
        if not tags:
            return []

        tags_lower = [t.lower() for t in tags]

        if match_all:
            # Intersection of all tag sets
            matching_ids: Optional[Set[str]] = None
            for tag in tags_lower:
                tag_skills = self._by_tag.get(tag, set())
                if matching_ids is None:
                    matching_ids = tag_skills.copy()
                else:
                    matching_ids &= tag_skills
            matching_ids = matching_ids or set()
        else:
            # Union of all tag sets
            matching_ids = set()
            for tag in tags_lower:
                matching_ids |= self._by_tag.get(tag, set())

        return [self._skills[sid] for sid in matching_ids if sid in self._skills]

    def find_by_source(self, source_type: str) -> List[Skill]:
        """Find skills by source type (builtin, personal, project)."""
        return [s for s in self._skills.values() if s.source_type.value == source_type]

    def search(self, query: str) -> List[Skill]:
        """
        Simple text search across skill names and descriptions.

        For semantic search, use SkillMatcher instead.
        """
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                query_lower in skill.skill_id.lower()):
                results.append(skill)
        return results

    async def reload_skill(self, skill_id: str) -> bool:
        """
        Reload a single skill from filesystem.

        Returns True if skill was successfully reloaded.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            logger.warning(f"Cannot reload unknown skill '{skill_id}'")
            return False

        async with self._lock:
            async with AsyncSessionLocal() as session:
                # Remove from tag index
                for tag in skill.tags:
                    tag_lower = tag.lower()
                    if tag_lower in self._by_tag:
                        self._by_tag[tag_lower].discard(skill_id)

                # Reload
                success = await self._load_and_index_skill(
                    session,
                    skill.source_path,
                    skill.source_type.value,
                    None  # project_path not tracked on reload
                )
                await session.commit()
                return success

    async def reload_all(self, project_paths: Optional[List[str]] = None) -> int:
        """
        Reload all skills from filesystem.

        Returns number of skills loaded.
        """
        async with self._lock:
            # Clear in-memory state
            self._skills.clear()
            self._by_tag.clear()
            self._initialized = False

        # Re-initialize
        return await self.initialize(project_paths)

    async def update_skill(self, skill: Skill) -> bool:
        """
        Update a skill's data in the database.

        Args:
            skill: The skill object with updated fields

        Returns:
            True if successfully updated
        """
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Skill).where(Skill.skill_id == skill.skill_id)
                )
                db_skill = result.scalar_one_or_none()

                if not db_skill:
                    logger.warning(f"Cannot update unknown skill '{skill.skill_id}'")
                    return False

                # Update fields
                db_skill.name = skill.name
                db_skill.description = skill.description
                db_skill.triggers = skill.triggers
                db_skill.instructions = skill.instructions
                db_skill.updated_at = skill.updated_at

                await session.commit()

                # Update in-memory cache
                self._skills[skill.skill_id] = skill
                logger.info(f"Updated skill '{skill.skill_id}'")
                return True

            except Exception as e:
                logger.error(f"Failed to update skill '{skill.skill_id}': {e}")
                await session.rollback()
                return False

    async def delete_skill(self, skill_id: str) -> bool:
        """
        Delete a skill from the database and in-memory cache.

        Args:
            skill_id: The skill ID to delete

        Returns:
            True if successfully deleted
        """
        from db.models import Skill as SkillModel

        async with AsyncSessionLocal() as session:
            try:
                # Find the skill in database
                result = await session.execute(
                    select(SkillModel).where(SkillModel.skill_id == skill_id)
                )
                db_skill = result.scalar_one_or_none()

                if not db_skill:
                    logger.warning(f"Skill '{skill_id}' not found in database")
                    # Still remove from memory if present
                    if skill_id in self._skills:
                        del self._skills[skill_id]
                    return True

                # Delete from database
                await session.delete(db_skill)
                await session.commit()

                # Remove from in-memory cache
                if skill_id in self._skills:
                    del self._skills[skill_id]

                logger.info(f"Deleted skill '{skill_id}'")
                return True

            except Exception as e:
                logger.error(f"Failed to delete skill '{skill_id}': {e}")
                await session.rollback()
                return False

    async def create_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        tags: List[str],
        triggers: List[str],
        instructions: str
    ) -> Skill:
        """
        Create a new skill in the database.

        Args:
            skill_id: Unique identifier for the skill
            name: Display name
            description: Brief description
            tags: Categorization tags
            triggers: Auto-trigger conditions
            instructions: Detailed skill instructions

        Returns:
            The created Skill object
        """
        async with AsyncSessionLocal() as session:
            # Create new skill record
            skill = Skill(
                skill_id=skill_id,
                name=name,
                description=description,
                version="1.0.0",
                author="User",
                source_type=SkillSourceType.PERSONAL,
                source_path="",
                tags=tags,
                triggers=triggers,
                allowed_tools=[],
                required_context=[],
                instructions=instructions,
                examples=None,
                file_modified_at=datetime.utcnow()
            )
            session.add(skill)
            await session.commit()
            await session.refresh(skill)

            # Index in memory
            self._skills[skill_id] = skill

            # Build tag index
            for tag in tags:
                tag_lower = tag.lower()
                if tag_lower not in self._by_tag:
                    self._by_tag[tag_lower] = set()
                self._by_tag[tag_lower].add(skill_id)

            logger.info(f"Created new skill '{skill_id}'")
            return skill

    async def record_execution(
        self,
        skill_id: str,
        invocation_type: str,
        status: str,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        match_score: Optional[float] = None,
        match_reason: Optional[str] = None,
        context: Optional[dict] = None,
        agent_id: Optional[str] = None,
        workflow_id: Optional[int] = None,
        task_id: Optional[int] = None
    ):
        """
        Record a skill execution for analytics.

        Args:
            skill_id: The skill that was executed
            invocation_type: 'automatic' or 'explicit'
            status: 'success', 'failed', or 'partial'
            execution_time_ms: How long execution took
            error_message: Error details if failed
            match_score: Confidence score for auto-invocation
            match_reason: Why this skill was selected
            context: Additional context information
            agent_id: Which agent used the skill
            workflow_id: Workflow context
            task_id: Task context
        """
        async with AsyncSessionLocal() as session:
            # Get skill from database
            result = await session.execute(
                select(Skill).where(Skill.skill_id == skill_id)
            )
            skill_obj = result.scalar_one_or_none()

            if not skill_obj:
                logger.warning(f"Cannot record execution for unknown skill '{skill_id}'")
                return

            # Create execution record
            execution = SkillExecution(
                skill_id=skill_obj.id,
                agent_id=agent_id,
                workflow_id=workflow_id,
                task_id=task_id,
                invocation_type=SkillInvocationType(invocation_type),
                trigger_context=context,
                match_score=match_score,
                match_reason=match_reason,
                status=status,
                execution_time_ms=execution_time_ms,
                error_message=error_message
            )
            session.add(execution)

            # Update skill usage metrics
            skill_obj.usage_count += 1
            skill_obj.last_used_at = datetime.utcnow()

            # Update success rate (rolling average)
            if status == 'success':
                skill_obj.avg_success_rate = (
                    skill_obj.avg_success_rate * 0.9 + 1.0 * 0.1
                )
            elif status == 'failed':
                skill_obj.avg_success_rate = (
                    skill_obj.avg_success_rate * 0.9 + 0.0 * 0.1
                )

            await session.commit()

            # Update in-memory cache
            if skill_id in self._skills:
                self._skills[skill_id].usage_count = skill_obj.usage_count
                self._skills[skill_id].last_used_at = skill_obj.last_used_at
                self._skills[skill_id].avg_success_rate = skill_obj.avg_success_rate

    @property
    def is_initialized(self) -> bool:
        """Check if registry has been initialized."""
        return self._initialized

    @property
    def skill_count(self) -> int:
        """Get number of registered skills."""
        return len(self._skills)


# Singleton accessor
_registry_instance: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry instance."""
    return SkillRegistry.get_instance()
