# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Skill Models - Modular, context-aware capabilities for agents.

Skills are inspired by Claude Code's skills system - they package expertise
into discoverable, reusable components that agents can automatically leverage.
"""
from sqlalchemy import Column, Integer, String, JSON, Enum as SQLEnum, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import validates, relationship
from db.database import Base
from enum import Enum
import datetime
import re


class SkillSourceType(str, Enum):
    """Where the skill originates from"""
    BUILTIN = "builtin"      # Shipped with the application
    PERSONAL = "personal"    # User's personal skills (~/.langconfig/skills)
    PROJECT = "project"      # Project-specific skills (<project>/.langconfig/skills)


class SkillInvocationType(str, Enum):
    """How the skill was invoked"""
    AUTOMATIC = "automatic"  # Agent auto-detected and used the skill
    EXPLICIT = "explicit"    # User/workflow explicitly requested the skill


class Skill(Base):
    """
    Indexed skill metadata from SKILL.md files.

    Skills are synced from filesystem on startup and file changes.
    The database provides fast lookup, semantic search, and usage metrics.
    """
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)

    # Identity (from SKILL.md frontmatter)
    skill_id = Column(String(100), unique=True, nullable=False, index=True)  # kebab-case name
    name = Column(String(200), nullable=False)  # Human-readable name
    description = Column(Text, nullable=False)  # For semantic search and matching
    version = Column(String(20), nullable=False, default="1.0.0")
    author = Column(String(100), nullable=True)

    # Source location
    source_type = Column(
        SQLEnum(SkillSourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    source_path = Column(String(500), nullable=False)  # Absolute path to skill directory
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    # Matching metadata
    tags = Column(JSON, default=lambda: [], nullable=False)  # For tag-based filtering
    triggers = Column(JSON, default=lambda: [], nullable=False)  # Auto-invocation hints
    allowed_tools = Column(JSON, nullable=True)  # Tool restrictions (null = all tools)
    required_context = Column(JSON, default=lambda: [], nullable=False)  # Context requirements

    # Content
    instructions = Column(Text, nullable=False)  # Injected into agent system prompt
    examples = Column(Text, nullable=True)  # Optional usage examples

    # Usage metrics
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    avg_success_rate = Column(Float, default=1.0, nullable=False)

    # File tracking for sync
    file_modified_at = Column(DateTime(timezone=True), nullable=False)
    indexed_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False
    )

    # Relationships
    executions = relationship("SkillExecution", back_populates="skill", cascade="all, delete-orphan")

    @validates('skill_id')
    def validate_skill_id(self, key, value):
        """Ensure skill_id is valid kebab-case."""
        if not value or not value.strip():
            raise ValueError("Skill ID cannot be empty")
        value = value.strip().lower()
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', value):
            raise ValueError("Skill ID must be kebab-case (lowercase letters, numbers, hyphens)")
        if len(value) > 100:
            raise ValueError("Skill ID too long (max 100 characters)")
        return value

    @validates('description')
    def validate_description(self, key, value):
        """Ensure description exists (critical for matching)."""
        if not value or not value.strip():
            raise ValueError("Skill description is required for matching")
        return value.strip()

    @validates('instructions')
    def validate_instructions(self, key, value):
        """Ensure instructions exist."""
        if not value or not value.strip():
            raise ValueError("Skill instructions are required")
        return value.strip()

    def __repr__(self):
        return f"<Skill(id={self.id}, skill_id='{self.skill_id}', source={self.source_type.value})>"


class SkillExecution(Base):
    """
    Track skill invocations for analytics and optimization.

    Records each time a skill is used, enabling:
    - Usage statistics per skill
    - Success/failure tracking
    - Context analysis for improving matching
    """
    __tablename__ = "skill_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Skill reference
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False, index=True)

    # Execution context
    agent_id = Column(String(100), nullable=True)
    workflow_id = Column(Integer, ForeignKey("workflow_profiles.id"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)

    # Invocation details
    invocation_type = Column(
        SQLEnum(SkillInvocationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )
    trigger_context = Column(JSON, nullable=True)  # What triggered auto-invocation
    match_score = Column(Float, nullable=True)  # Confidence score for auto-invocation
    match_reason = Column(String(200), nullable=True)  # Why this skill was selected

    # Results
    status = Column(String(50), nullable=False)  # success, failed, partial
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    skill = relationship("Skill", back_populates="executions")

    def __repr__(self):
        return f"<SkillExecution(id={self.id}, skill_id={self.skill_id}, status='{self.status}')>"
