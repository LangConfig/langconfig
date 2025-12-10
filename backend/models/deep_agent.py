# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
DeepAgent Models for LangConfig.

Extends the agent template system with DeepAgents-specific configuration.
Supports middleware, subagents, backends, and advanced context management.
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import Column, Integer, String, JSON, Boolean, ForeignKey, DateTime, Text, Float, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, model_validator, field_validator
from db.database import Base
from core.versioning import OptimisticLockMixin
from models.enums import SubAgentType, MiddlewareType, BackendType, ReasoningEffort
from models.core import DocumentType, IndexingStatus
import datetime


# =============================================================================
# Pydantic Models for Configuration
# =============================================================================

class SubAgentConfig(BaseModel):
    """Configuration for a specialized subagent."""
    name: str = Field(..., description="Unique subagent identifier")
    description: str = Field(default="", description="What this subagent does")

    # Type of subagent: "dictionary" (simple) or "compiled" (workflow-based)
    # Use string with validator to handle edge cases where type might be missing/invalid
    type: SubAgentType = Field(
        default=SubAgentType.DICTIONARY,
        description="Subagent type: 'dictionary' for simple agents, 'compiled' for workflow-based"
    )

    @field_validator('type', mode='before')
    @classmethod
    def coerce_type(cls, v):
        """Coerce type to SubAgentType enum, defaulting to DICTIONARY if invalid."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SubAgentConfig] Coercing type from: {v!r} (type={type(v).__name__})")

        if v is None or v == '':
            logger.info("[SubAgentConfig] Type is None/empty, defaulting to DICTIONARY")
            return SubAgentType.DICTIONARY
        if isinstance(v, SubAgentType):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower == 'dictionary':
                return SubAgentType.DICTIONARY
            elif v_lower == 'compiled':
                return SubAgentType.COMPILED
            else:
                logger.warning(f"[SubAgentConfig] Unknown type '{v}', defaulting to DICTIONARY")
                return SubAgentType.DICTIONARY
        logger.warning(f"[SubAgentConfig] Unexpected type value {v!r}, defaulting to DICTIONARY")
        return SubAgentType.DICTIONARY

    # For dictionary-based subagents
    template_id: Optional[str] = Field(None, description="Base template to use from AgentTemplateRegistry")
    model: Optional[str] = Field(None, description="Override model (inherits from parent if not set)")
    system_prompt: Optional[str] = Field(None, description="Subagent-specific system prompt")
    tools: List[str] = Field(default_factory=list, description="Tool names for this subagent")
    middleware: List[str] = Field(default_factory=list, description="Middleware to enable")
    interrupt_on: Dict[str, Any] = Field(default_factory=dict, description="HITL configuration")

    # For compiled subagents (workflow-based)
    workflow_id: Optional[int] = Field(None, description="ID of workflow to use as compiled subagent")
    workflow_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Override configuration for the workflow (input mapping, etc.)"
    )

    @model_validator(mode='after')
    def validate_subagent_consistency(self) -> 'SubAgentConfig':
        """Ensure compiled subagents have workflow_id and dictionary subagents don't."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[SubAgentConfig] Validating '{self.name}': type={self.type}, type_value={self.type.value if hasattr(self.type, 'value') else self.type}, workflow_id={self.workflow_id}")

        if self.type == SubAgentType.COMPILED:
            if not self.workflow_id:
                raise ValueError(
                    f"Compiled subagent '{self.name}' requires workflow_id. "
                    f"Set type='dictionary' for simple subagents or provide a workflow_id."
                )
        elif self.type == SubAgentType.DICTIONARY:
            if self.workflow_id:
                raise ValueError(
                    f"Dictionary subagent '{self.name}' cannot have workflow_id. "
                    f"Set type='compiled' to use workflow-based subagents."
                )
        return self


class MiddlewareConfig(BaseModel):
    """Configuration for DeepAgents middleware."""
    type: MiddlewareType = Field(..., description="Middleware type: todo_list, filesystem, subagent")
    enabled: bool = Field(default=True, description="Whether this middleware is active")
    config: Dict[str, Any] = Field(default_factory=dict, description="Middleware-specific configuration")


class BackendConfig(BaseModel):
    """Configuration for DeepAgents backend storage."""
    type: BackendType = Field(
        default=BackendType.STATE,
        description="Backend type: state, store, filesystem, vectordb, composite"
    )
    config: Dict[str, Any] = Field(default_factory=dict, description="Backend-specific settings")
    mappings: Optional[Dict[str, Dict[str, Any]]] = Field(
        None,
        description="Path mappings for composite backends"
    )

    @model_validator(mode='after')
    def validate_composite_backend(self) -> 'BackendConfig':
        """Ensure composite backends have path mappings."""
        if self.type == BackendType.COMPOSITE:
            if not self.mappings or len(self.mappings) == 0:
                raise ValueError(
                    "Composite backend requires 'mappings' configuration. "
                    "Provide path mappings like {'/memory/': {'type': 'vectordb', 'config': {}}}."
                )
        return self


class GuardrailsConfig(BaseModel):
    """Guardrails and safety configuration."""
    interrupts: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tool-specific interrupt configuration"
    )
    token_limits: Dict[str, int] = Field(
        default={
            "max_total_tokens": 100000,
            "eviction_threshold": 80000,
            "summarization_threshold": 60000
        },
        description="Token management thresholds"
    )
    enable_auto_eviction: bool = Field(
        default=True,
        description="Automatically evict large tool results to filesystem"
    )
    enable_summarization: bool = Field(
        default=True,
        description="Automatically summarize conversation history"
    )
    long_term_memory: bool = Field(
        default=False,
        description="Enable workflow-scoped long-term memory via LangGraph Store"
    )

    @model_validator(mode='after')
    def validate_token_limits_ordering(self) -> 'GuardrailsConfig':
        """Ensure token limits are in correct order: summarization < eviction < max_total."""
        limits = self.token_limits
        summarization = limits.get("summarization_threshold", 0)
        eviction = limits.get("eviction_threshold", 0)
        max_total = limits.get("max_total_tokens", 0)

        if not (summarization < eviction < max_total):
            raise ValueError(
                f"Token limits must satisfy: summarization_threshold ({summarization}) < "
                f"eviction_threshold ({eviction}) < max_total_tokens ({max_total}). "
                f"Current order is invalid."
            )
        return self


class DeepAgentConfig(BaseModel):
    """Complete DeepAgent configuration (Pydantic model for validation)."""
    # Base agent settings
    model: str = Field(default="claude-sonnet-4-5-20250929")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    reasoning_effort: Optional[ReasoningEffort] = Field(
        default=ReasoningEffort.LOW,
        description="Reasoning effort for Gemini models: none (96% cheaper), low, medium, or high"
    )
    modalities: Optional[List[str]] = Field(
        default=None,
        description="Modalities for multimodal models (e.g., ['image', 'text'] for Gemini image generation)"
    )
    system_prompt: str = Field(..., description="Agent system prompt")

    # Tools
    tools: List[str] = Field(default_factory=list, description="Tool names")
    native_tools: List[str] = Field(default_factory=list, description="Native Python tool categories")
    cli_tools: List[str] = Field(default_factory=list, description="CLI tool categories")
    custom_tools: List[str] = Field(default_factory=list, description="User-created custom tools")

    # DeepAgents-specific
    use_deepagents: bool = Field(
        default=True,
        description="Whether to use DeepAgents framework"
    )
    enable_compiled_subagents: bool = Field(
        default=True,
        description="Enable CompiledSubAgent support (workflow-based subagents). Set to False to disable."
    )
    middleware: List[MiddlewareConfig] = Field(
        default_factory=list,
        description="Middleware configurations"
    )
    subagents: List[SubAgentConfig] = Field(
        default_factory=list,
        description="Specialized subagent configurations"
    )
    backend: BackendConfig = Field(
        default_factory=BackendConfig,
        description="Storage backend configuration"
    )
    guardrails: GuardrailsConfig = Field(
        default_factory=GuardrailsConfig,
        description="Safety and context management"
    )

    # Export settings
    export_format: str = Field(
        default="standalone",
        description="Export format: standalone or langconfig"
    )
    include_chat_ui: bool = Field(
        default=True,
        description="Include chat interface in standalone export"
    )
    include_docker: bool = Field(
        default=False,
        description="Include Docker support in export"
    )


# =============================================================================
# SQLAlchemy Database Models
# =============================================================================

class DeepAgentTemplate(Base, OptimisticLockMixin):
    """
    Database model for DeepAgent configurations.
    Extends agent templates with DeepAgents-specific features.
    """
    __tablename__ = "deep_agent_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Basic metadata
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)

    # References to base agent template (if extends one)
    base_template_id = Column(String(100), nullable=True, index=True)

    # DeepAgents configuration (stored as JSON)
    config = Column(JSON, nullable=False)

    # Middleware configuration
    middleware_config = Column(JSON, nullable=False, default=list)

    # Subagents configuration
    subagents_config = Column(JSON, nullable=False, default=list)

    # Backend configuration
    backend_config = Column(JSON, nullable=False, default=dict)

    # Guardrails configuration
    guardrails_config = Column(JSON, nullable=False, default=dict)

    # Export settings
    export_settings = Column(JSON, nullable=True, default=dict)

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Versioning
    version = Column(String(20), default="1.0.0", nullable=False)

    # Visibility
    is_public = Column(Boolean, default=True, nullable=False)
    is_community = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    exports = relationship("AgentExport", back_populates="agent", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="agent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DeepAgentTemplate(id={self.id}, name='{self.name}')>"


class AgentExport(Base):
    """
    Tracks exports of DeepAgent configurations.
    Stores export history and generated artifacts.
    """
    __tablename__ = "agent_exports"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to agent
    agent_id = Column(Integer, ForeignKey("deep_agent_templates.id"), nullable=False)

    # Export metadata
    export_type = Column(String(50), nullable=False, index=True)  # 'standalone' or 'langconfig'
    export_format = Column(String(50), nullable=True)  # 'zip', 'json', etc.

    # Export configuration (what was included)
    export_config = Column(JSON, nullable=False)

    # File storage
    file_path = Column(String(500), nullable=True)  # Path to exported artifact
    file_size = Column(Integer, nullable=True)  # Size in bytes

    # Generation metadata
    generated_files = Column(JSON, nullable=True)  # List of files included

    # Download tracking
    download_count = Column(Integer, default=0, nullable=False)
    last_downloaded_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    agent = relationship("DeepAgentTemplate", back_populates="exports")

    def __repr__(self):
        return f"<AgentExport(id={self.id}, type='{self.export_type}', agent_id={self.agent_id})>"


class ChatSession(Base):
    """
    Stores chat testing sessions for DeepAgents.
    Allows users to test agents before exporting.
    """
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to agent
    agent_id = Column(Integer, ForeignKey("deep_agent_templates.id"), nullable=False, index=True)

    # Session metadata
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # Optional user tracking

    # Conversation data
    messages = Column(JSON, nullable=False, default=list)  # List of messages

    # Performance metrics
    metrics = Column(JSON, nullable=True, default=dict)  # Token usage, tool calls, etc.

    # Execution metadata
    tool_calls = Column(JSON, nullable=True, default=list)  # History of tool invocations
    subagent_spawns = Column(JSON, nullable=True, default=list)  # Subagent activity
    context_operations = Column(JSON, nullable=True, default=list)  # Evictions, summarizations

    # Cost tracking
    total_cost_usd = Column(Float, default=0.0, nullable=False)  # Total USD cost for this session
    rag_context_tokens = Column(Integer, default=0, nullable=False)  # RAG-specific token usage

    # Session state
    is_active = Column(Boolean, default=True, nullable=False)
    checkpoint_id = Column(String(200), nullable=True)  # LangGraph checkpoint reference

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("DeepAgentTemplate", back_populates="chat_sessions")
    documents = relationship("SessionDocument", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id='{self.session_id}', active={self.is_active})>"


class SessionDocument(Base):
    """
    Links uploaded documents to chat sessions.
    Session-scoped documents for agent RAG retrieval.
    """
    __tablename__ = "session_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Reference to chat session
    session_id = Column(
        String(100),
        ForeignKey("chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File metadata
    file_path = Column(String(500), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    document_type = Column(
        Enum(DocumentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False
    )

    # Upload metadata
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    message_index = Column(Integer, nullable=True)  # Which message this was attached to

    # Indexing status
    indexing_status = Column(
        Enum(IndexingStatus, values_callable=lambda x: [e.value for e in x]),
        default=IndexingStatus.NOT_INDEXED,
        nullable=False
    )
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_chunks_count = Column(Integer, nullable=True)

    # Relationships
    session = relationship("ChatSession", back_populates="documents")

    def __repr__(self):
        return f"<SessionDocument(id={self.id}, filename='{self.filename}', session_id='{self.session_id}')>"


# =============================================================================
# Helper Functions
# =============================================================================

def create_default_middleware_config() -> List[MiddlewareConfig]:
    """Create default middleware configuration for DeepAgents."""
    return [
        MiddlewareConfig(
            type=MiddlewareType.TODO_LIST,
            enabled=True,
            config={"auto_track": True}
        ),
        MiddlewareConfig(
            type=MiddlewareType.FILESYSTEM,
            enabled=True,
            config={
                "auto_eviction": True,
                "eviction_threshold_bytes": 1000000  # 1MB
            }
        ),
        MiddlewareConfig(
            type=MiddlewareType.SUBAGENT,
            enabled=True,
            config={"max_depth": 3, "max_concurrent": 5}
        )
    ]


def create_default_backend_config() -> BackendConfig:
    """Create default backend configuration."""
    return BackendConfig(
        type=BackendType.COMPOSITE,
        config={},
        mappings={
            "/memory/": {"type": "vectordb", "config": {}},
            "/filesystem/": {"type": "filesystem", "config": {}},
            "/state/": {"type": "state", "config": {}}
        }
    )


def create_default_guardrails_config() -> GuardrailsConfig:
    """Create default guardrails configuration."""
    return GuardrailsConfig(
        interrupts={},
        token_limits={
            "max_total_tokens": 100000,
            "eviction_threshold": 80000,
            "summarization_threshold": 60000
        },
        enable_auto_eviction=True,
        enable_summarization=True
    )
