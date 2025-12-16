# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Custom Tool Models - User-defined tool configurations
"""
from sqlalchemy import Column, Integer, String, JSON, Enum as SQLEnum, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import validates, relationship
from db.database import Base
from enum import Enum
import datetime


class ToolType(str, Enum):
    """Types of custom tools available"""
    API = "api"
    NOTIFICATION = "notification"
    IMAGE_VIDEO = "image_video"
    DATABASE = "database"
    DATA_TRANSFORM = "data_transform"


class ToolTemplateType(str, Enum):
    """Available tool templates"""
    NOTIFICATION_SLACK = "notification_slack"
    NOTIFICATION_DISCORD = "notification_discord"
    API_WEBHOOK = "api_webhook"
    IMAGE_OPENAI_DALLE3 = "image_openai_dalle3"
    IMAGE_OPENAI_SORA = "image_openai_sora"
    IMAGE_OPENAI_GPT_IMAGE_1_5 = "image_openai_gpt_image_1_5"  # GPT-Image-1.5 (December 2025)
    IMAGE_GEMINI_IMAGEN3 = "image_gemini_imagen3"
    IMAGE_GEMINI_NANO_BANANA = "image_gemini_nano_banana"  # Nano Banana (Gemini 2.5 Flash Image)
    VIDEO_GEMINI_VEO3 = "video_gemini_veo3"
    VIDEO_GEMINI_VEO31 = "video_gemini_veo31"
    DATABASE_POSTGRES = "database_postgres"
    DATABASE_MYSQL = "database_mysql"
    DATABASE_MONGODB = "database_mongodb"
    DATA_TRANSFORM_JSON = "data_transform_json"
    CUSTOM = "custom"


class CustomTool(Base):
    """
    User-defined custom tools that can be attached to agents.

    Stores tool configurations with LangChain compatibility,
    supporting multiple tool types and templates.
    """
    __tablename__ = "custom_tools"

    id = Column(Integer, primary_key=True, index=True)

    # Tool identification
    tool_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)  # Critical for LLM understanding

    # Tool type and template
    tool_type = Column(
        SQLEnum(ToolType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    template_type = Column(
        SQLEnum(ToolTemplateType, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=ToolTemplateType.CUSTOM.value,
        index=True
    )

    # Configuration
    implementation_config = Column(JSON, nullable=False)  # Tool-specific config
    input_schema = Column(JSON, nullable=False)  # JSON Schema for inputs
    output_format = Column(String(50), nullable=True, default="string")  # string, json, url
    validation_rules = Column(JSON, nullable=True)  # Additional validation rules

    # Mode tracking
    is_template_based = Column(Boolean, default=True, nullable=False)  # Template vs Advanced mode
    is_advanced_mode = Column(Boolean, default=False, nullable=False)  # User switched to advanced

    # Ownership and sharing
    created_by = Column(String(100), nullable=True)  # User ID
    is_public = Column(Boolean, default=False, nullable=False)  # Future: public tool library
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # Optional project scope

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, default=0, nullable=False)  # Track failures
    last_error_at = Column(DateTime(timezone=True), nullable=True)

    # Versioning
    version = Column(String(20), default="1.0.0", nullable=False)
    parent_tool_id = Column(Integer, ForeignKey("custom_tools.id"), nullable=True)  # For forked tools

    # Metadata
    category = Column(String(50), nullable=True)  # User-defined category
    tags = Column(JSON, default=lambda: [], nullable=False)  # Searchable tags

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False
    )

    # Relationships
    execution_logs = relationship("ToolExecutionLog", back_populates="tool", cascade="all, delete-orphan")

    @validates('name')
    def validate_name(self, key, value):
        """Ensure name is not empty and reasonable length"""
        if not value or not value.strip():
            raise ValueError("Tool name cannot be empty")
        if len(value.strip()) > 200:
            raise ValueError("Tool name too long (max 200 characters)")
        return value.strip()

    @validates('description')
    def validate_description(self, key, value):
        """Ensure description exists (critical for LLM)"""
        if not value or not value.strip():
            raise ValueError("Tool description is required for LangChain compatibility")
        return value.strip()

    @validates('tool_id')
    def validate_tool_id(self, key, value):
        """Ensure tool_id is valid (alphanumeric + underscores)"""
        if not value or not value.strip():
            raise ValueError("Tool ID cannot be empty")
        # Basic validation - alphanumeric and underscores only
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', value.strip()):
            raise ValueError("Tool ID must contain only letters, numbers, and underscores")
        return value.strip()

    def __repr__(self):
        return f"<CustomTool(id={self.id}, tool_id='{self.tool_id}', name='{self.name}', type={self.tool_type.value})>"


class ToolExecutionLog(Base):
    """
    Logs of custom tool executions for debugging and monitoring.

    Tracks successful and failed tool calls to help users debug
    their custom tool configurations.
    """
    __tablename__ = "tool_execution_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Tool reference
    tool_id = Column(Integer, ForeignKey("custom_tools.id"), nullable=False, index=True)

    # Execution context
    agent_id = Column(String(100), nullable=True)  # Which agent used the tool
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    workflow_id = Column(String(100), nullable=True)

    # Execution details
    input_params = Column(JSON, nullable=False)  # What params were passed
    output_result = Column(JSON, nullable=True)  # What was returned

    # Status and errors
    status = Column(String(50), nullable=False)  # success, error, timeout
    error_message = Column(Text, nullable=True)  # Error details if failed
    stack_trace = Column(Text, nullable=True)  # Full stack trace for debugging

    # Performance
    execution_time_ms = Column(Integer, nullable=True)  # How long it took
    retry_count = Column(Integer, default=0, nullable=False)  # How many retries

    # Resolution tracking
    resolved = Column(Boolean, default=False, nullable=False)  # User marked as fixed
    resolution_notes = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    tool = relationship("CustomTool", back_populates="execution_logs")
    task = relationship("Task")

    def __repr__(self):
        return f"<ToolExecutionLog(id={self.id}, tool_id={self.tool_id}, status='{self.status}')>"
