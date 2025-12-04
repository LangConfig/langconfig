# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Core Database Models - Simplified for LangConfig
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Enum, DateTime, Text, Boolean, Float
from sqlalchemy.orm import relationship
from db.database import Base
import enum
import datetime

# Status Enums
class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    IDLE = "idle"
    COMPLETED = "completed"

class IndexingStatus(str, enum.Enum):
    NOT_INDEXED = "not_indexed"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"

class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, enum.Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    CODE = "code"
    JSON = "json"
    HTML = "html"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"
    DOCX = "docx"
    IMAGE = "image"
    OTHER = "other"

# Directive Model
class Directive(Base):
    __tablename__ = 'directives'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    goal_description = Column(Text, nullable=False)
    status = Column(Enum(ProjectStatus, values_callable=lambda x: [e.value for e in x]), default=ProjectStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    # Store the execution plan
    execution_plan = Column(JSON, nullable=True)


# Project Model (Simplified)
class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(ProjectStatus, values_callable=lambda x: [e.value for e in x]), default=ProjectStatus.IDLE)

    # Configuration
    configuration = Column(JSON, default=lambda: {
        "default_model": "gpt-4o"
    })

    # RAG/Indexing fields
    indexing_status = Column(Enum(IndexingStatus, values_callable=lambda x: [e.value for e in x]), default=IndexingStatus.NOT_INDEXED)
    last_indexed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_nodes_count = Column(Integer, nullable=True, default=0)
    embedding_dimension = Column(Integer, nullable=True, default=384)

    # Workflow profile link
    workflow_profile_id = Column(Integer, ForeignKey('workflow_profiles.id'), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("ContextDocument", back_populates="project", cascade="all, delete-orphan")

# Task Model (Simplified)
class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)  # Optional - for standalone workflow execution
    description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus, values_callable=lambda x: [e.value for e in x]), default=TaskStatus.QUEUED)
    assigned_model = Column(String, nullable=True)

    # Workflow tracking
    workflow_id = Column(String, nullable=True, index=True)
    workflow_profile_id = Column(Integer, ForeignKey('workflow_profiles.id'), nullable=True)

    # Execution logs
    execution_logs = Column(JSON, default=lambda: {"entries": []})

    # Result/output
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    execution_events = relationship("ExecutionEvent", back_populates="task", cascade="all, delete-orphan")

# Context Document Model (for RAG)
class ContextDocument(Base):
    __tablename__ = 'context_documents'

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=True)
    document_type = Column(Enum(DocumentType, values_callable=lambda x: [e.value for e in x]), default=DocumentType.TEXT)

    # Vector indexing
    indexing_status = Column(Enum(IndexingStatus, values_callable=lambda x: [e.value for e in x]), default=IndexingStatus.NOT_INDEXED)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    indexed_chunks_count = Column(Integer, nullable=True, default=0)

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=lambda: [])
    content_preview = Column(Text, nullable=True)

    # Project association
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationship
    project = relationship("Project", back_populates="documents")

# Search History Model (for RAG search metrics tracking)
class SearchHistory(Base):
    __tablename__ = 'search_history'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    user_id = Column(Integer, nullable=True)  # For future multi-user support

    # Search configuration
    query = Column(Text, nullable=False)
    use_hyde = Column(Boolean, default=False)
    hyde_auto_detected = Column(Boolean, default=False)
    use_toon = Column(Boolean, default=False)
    top_k = Column(Integer, default=10)

    # Measured results (factual data only)
    results_count = Column(Integer, nullable=False)
    retrieval_duration_ms = Column(Float, nullable=False)
    query_tokens = Column(Integer, nullable=False)
    total_context_tokens = Column(Integer, nullable=False)

    # Measured quality metrics
    avg_similarity = Column(Float, nullable=True)
    max_similarity = Column(Float, nullable=True)
    min_similarity = Column(Float, nullable=True)

    # Full results storage (JSONB for detailed analysis)
    results_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    # Relationship
    project = relationship("Project")
