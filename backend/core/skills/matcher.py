# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skill Matcher - Context-aware skill selection.

Responsible for:
- Semantic matching of user context to skills
- Evaluating trigger conditions
- Ranking skills by relevance
- Caching embeddings for performance

Matching Strategies:
1. Semantic: Compare context embedding to skill description embeddings
2. Trigger: Evaluate skill trigger conditions against context
3. Tag: Match context keywords to skill tags
4. Explicit: Direct skill invocation by name
"""

import logging
import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

import numpy as np

from models.skill import Skill
from core.skills.registry import get_skill_registry

logger = logging.getLogger(__name__)


@dataclass
class SkillMatch:
    """A skill match with relevance score and explanation."""
    skill: Skill
    score: float
    match_reason: str  # 'semantic', 'trigger', 'tag', 'explicit'


class SkillMatcher:
    """
    Match user context to relevant skills.

    Supports multiple matching strategies:
    1. Semantic: Compare context embedding to skill description embeddings
    2. Trigger: Evaluate skill trigger conditions against context
    3. Tag: Match context keywords to skill tags
    4. Explicit: Direct skill invocation by name

    Example usage:
        matcher = SkillMatcher()

        # Find skills for a user query
        matches = await matcher.find_relevant_skills({
            "query": "help me write pytest tests",
            "file_path": "tests/test_api.py",
            "project_type": "python"
        })

        for match in matches:
            print(f"{match.skill.name}: {match.score:.2f} ({match.match_reason})")
    """

    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        """
        Initialize matcher with optional embedding model.

        Args:
            embedding_model: OpenAI embedding model name for semantic matching
        """
        self._embedding_model = embedding_model
        self._embeddings = None  # Lazy initialization
        self._registry = get_skill_registry()
        self._embedding_cache: Dict[str, np.ndarray] = {}

    def _get_embeddings(self):
        """Lazy initialize embeddings client."""
        if self._embeddings is None:
            try:
                from langchain_openai import OpenAIEmbeddings
                self._embeddings = OpenAIEmbeddings(model=self._embedding_model)
            except Exception as e:
                logger.warning(f"Could not initialize embeddings: {e}")
                self._embeddings = False  # Mark as failed
        return self._embeddings if self._embeddings else None

    async def find_relevant_skills(
        self,
        context: Dict[str, Any],
        max_results: int = 5,
        min_score: float = 0.5,
        strategies: Optional[List[str]] = None
    ) -> List[SkillMatch]:
        """
        Find skills relevant to the given context.

        Args:
            context: Dictionary with context information:
                - query: User's query/input text (required for semantic)
                - file_path: Current file path (for trigger evaluation)
                - file_content: Current file content (optional)
                - project_type: Type of project (e.g., 'python', 'nodejs')
                - tags: Explicit tags to match
            max_results: Maximum number of skills to return
            min_score: Minimum relevance score (0-1)
            strategies: List of strategies to use ['semantic', 'trigger', 'tag']
                        Defaults to all strategies.

        Returns:
            List of SkillMatch sorted by relevance score (highest first)
        """
        strategies = strategies or ['semantic', 'trigger', 'tag']
        all_matches: Dict[str, SkillMatch] = {}

        skills = self._registry.list_all()

        # Strategy 1: Semantic matching (if query provided and embeddings available)
        if 'semantic' in strategies and context.get('query'):
            try:
                semantic_matches = await self._semantic_match(
                    context['query'], skills, max_results * 2
                )
                for match in semantic_matches:
                    if match.skill.skill_id not in all_matches or \
                       match.score > all_matches[match.skill.skill_id].score:
                        all_matches[match.skill.skill_id] = match
            except Exception as e:
                logger.warning(f"Semantic matching failed: {e}")

        # Strategy 2: Trigger evaluation
        if 'trigger' in strategies:
            trigger_matches = self._evaluate_triggers(context, skills)
            for match in trigger_matches:
                if match.skill.skill_id not in all_matches or \
                   match.score > all_matches[match.skill.skill_id].score:
                    all_matches[match.skill.skill_id] = match

        # Strategy 3: Tag matching
        if 'tag' in strategies:
            # Extract implicit tags from context
            implicit_tags = self._extract_implicit_tags(context)
            explicit_tags = context.get('tags', [])
            all_tags = list(set(implicit_tags + explicit_tags))

            if all_tags:
                tag_matches = self._match_tags(all_tags, skills)
                for match in tag_matches:
                    if match.skill.skill_id not in all_matches:
                        all_matches[match.skill.skill_id] = match

        # Filter by minimum score and sort
        results = [m for m in all_matches.values() if m.score >= min_score]
        results.sort(key=lambda m: m.score, reverse=True)

        return results[:max_results]

    async def _semantic_match(
        self,
        query: str,
        skills: List[Skill],
        max_results: int
    ) -> List[SkillMatch]:
        """Match query semantically against skill descriptions."""
        embeddings = self._get_embeddings()
        if not embeddings:
            # Fallback to keyword matching
            return self._keyword_match(query, skills, max_results)

        try:
            # Get query embedding
            query_embedding = await self._get_embedding(query)

            matches = []
            for skill in skills:
                # Get or compute skill description embedding
                skill_embedding = await self._get_skill_embedding(skill)

                # Compute cosine similarity
                similarity = self._cosine_similarity(query_embedding, skill_embedding)

                if similarity > 0.3:  # Basic threshold before scoring
                    matches.append(SkillMatch(
                        skill=skill,
                        score=similarity,
                        match_reason='semantic'
                    ))

            matches.sort(key=lambda m: m.score, reverse=True)
            return matches[:max_results]

        except Exception as e:
            logger.warning(f"Semantic embedding failed, using keyword fallback: {e}")
            return self._keyword_match(query, skills, max_results)

    def _keyword_match(
        self,
        query: str,
        skills: List[Skill],
        max_results: int
    ) -> List[SkillMatch]:
        """Fallback keyword matching when embeddings unavailable."""
        matches = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for skill in skills:
            score = 0.0
            reasons = []

            # Check description
            desc_lower = skill.description.lower()
            desc_words = set(desc_lower.split())
            word_overlap = len(query_words & desc_words) / max(len(query_words), 1)
            if word_overlap > 0:
                score += 0.4 * word_overlap
                reasons.append("description keywords")

            # Check name
            if query_lower in skill.name.lower():
                score += 0.3
                reasons.append("name match")

            # Check skill_id
            if query_lower in skill.skill_id:
                score += 0.2
                reasons.append("skill_id match")

            if score > 0:
                matches.append(SkillMatch(
                    skill=skill,
                    score=min(score, 1.0),
                    match_reason=f"keywords: {', '.join(reasons)}"
                ))

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:max_results]

    def _evaluate_triggers(
        self,
        context: Dict[str, Any],
        skills: List[Skill]
    ) -> List[SkillMatch]:
        """Evaluate skill triggers against context."""
        matches = []

        for skill in skills:
            if not skill.triggers:
                continue

            for trigger in skill.triggers:
                matched, details = self._trigger_matches(trigger, context)
                if matched:
                    matches.append(SkillMatch(
                        skill=skill,
                        score=0.85,  # High confidence for trigger match
                        match_reason=f'trigger: {details}'
                    ))
                    break  # One trigger match is enough

        return matches

    def _trigger_matches(self, trigger: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Evaluate a single trigger condition against context.

        Trigger format examples:
        - "when user mentions python testing"
        - "when file extension is .py"
        - "when project type is nodejs"
        - "when working with pytest"

        Returns:
            Tuple of (matched: bool, details: str)
        """
        trigger_lower = trigger.lower().strip()

        # File extension trigger: "when file extension is .py"
        if "file extension is" in trigger_lower:
            ext = trigger_lower.split("file extension is")[-1].strip()
            file_path = context.get('file_path', '')
            if file_path.lower().endswith(ext):
                return True, f"file extension {ext}"

        # Project type trigger: "when project type is python"
        if "project type is" in trigger_lower:
            proj_type = trigger_lower.split("project type is")[-1].strip()
            if context.get('project_type', '').lower() == proj_type:
                return True, f"project type {proj_type}"

        # Working with trigger: "when working with pytest"
        if "working with" in trigger_lower:
            tool = trigger_lower.split("working with")[-1].strip()
            query = context.get('query', '').lower()
            file_content = context.get('file_content', '').lower()
            if tool in query or tool in file_content:
                return True, f"working with {tool}"

        # Keyword mention trigger: "when user mentions X Y Z"
        if "mentions" in trigger_lower:
            keywords_str = trigger_lower.split("mentions")[-1].strip()
            keywords = [k.strip() for k in keywords_str.split() if k.strip()]
            query = context.get('query', '').lower()
            if all(kw in query for kw in keywords):
                return True, f"mentions {keywords_str}"

        # Generic "when" trigger with keyword matching
        if trigger_lower.startswith("when "):
            # Extract key terms and check against query
            terms = trigger_lower[5:].strip().split()
            query = context.get('query', '').lower()
            if any(term in query for term in terms if len(term) > 3):
                return True, trigger

        return False, ""

    def _match_tags(
        self,
        context_tags: List[str],
        skills: List[Skill]
    ) -> List[SkillMatch]:
        """Match context tags against skill tags."""
        matches = []
        context_tags_lower = set(t.lower() for t in context_tags)

        for skill in skills:
            skill_tags_lower = set(t.lower() for t in (skill.tags or []))
            matching_tags = context_tags_lower & skill_tags_lower

            if matching_tags:
                # Score based on tag overlap
                overlap_ratio = len(matching_tags) / max(len(context_tags_lower), len(skill_tags_lower))
                score = min(0.3 + (overlap_ratio * 0.5), 0.8)  # Cap at 0.8

                matches.append(SkillMatch(
                    skill=skill,
                    score=score,
                    match_reason=f'tags: {", ".join(matching_tags)}'
                ))

        return matches

    def _extract_implicit_tags(self, context: Dict[str, Any]) -> List[str]:
        """
        Extract implicit tags from context.

        Analyzes file paths, queries, and project type to infer relevant tags.
        """
        tags = []

        # From file path
        file_path = context.get('file_path', '')
        if file_path:
            # Extract extension
            if '.' in file_path:
                ext = file_path.rsplit('.', 1)[-1].lower()
                ext_tag_map = {
                    'py': 'python',
                    'js': 'javascript',
                    'ts': 'typescript',
                    'tsx': 'typescript',
                    'jsx': 'javascript',
                    'go': 'golang',
                    'rs': 'rust',
                    'rb': 'ruby',
                    'java': 'java',
                    'kt': 'kotlin',
                    'md': 'documentation',
                    'yaml': 'configuration',
                    'yml': 'configuration',
                    'json': 'configuration',
                }
                if ext in ext_tag_map:
                    tags.append(ext_tag_map[ext])

            # Check for common patterns
            path_lower = file_path.lower()
            if 'test' in path_lower or 'spec' in path_lower:
                tags.append('testing')
            if 'api' in path_lower:
                tags.append('api')
            if 'component' in path_lower:
                tags.append('frontend')

        # From project type
        project_type = context.get('project_type', '')
        if project_type:
            tags.append(project_type.lower())

        # From query (basic keyword extraction)
        query = context.get('query', '')
        if query:
            query_lower = query.lower()
            keywords_to_tags = {
                'test': 'testing',
                'pytest': 'testing',
                'unittest': 'testing',
                'jest': 'testing',
                'api': 'api',
                'rest': 'api',
                'graphql': 'api',
                'database': 'database',
                'sql': 'database',
                'docker': 'devops',
                'kubernetes': 'devops',
                'deploy': 'devops',
                'debug': 'debugging',
                'error': 'debugging',
                'document': 'documentation',
                'readme': 'documentation',
            }
            for keyword, tag in keywords_to_tags.items():
                if keyword in query_lower:
                    tags.append(tag)

        return list(set(tags))  # Deduplicate

    async def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text."""
        embeddings = self._get_embeddings()
        if not embeddings:
            raise RuntimeError("Embeddings not available")

        result = await embeddings.aembed_query(text)
        return np.array(result)

    async def _get_skill_embedding(self, skill: Skill) -> np.ndarray:
        """Get or compute embedding for skill description."""
        if skill.skill_id not in self._embedding_cache:
            # Create rich text for embedding
            text = f"{skill.name}: {skill.description}"
            if skill.tags:
                text += f" Tags: {', '.join(skill.tags)}"

            embedding = await self._get_embedding(text)
            self._embedding_cache[skill.skill_id] = embedding

        return self._embedding_cache[skill.skill_id]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()


# Singleton instance
_matcher_instance: Optional[SkillMatcher] = None


def get_skill_matcher() -> SkillMatcher:
    """Get the global skill matcher instance."""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = SkillMatcher()
    return _matcher_instance
