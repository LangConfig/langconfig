# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Local Model Database Model
Stores configuration for locally-hosted LLM servers (Ollama, LM Studio, vLLM, etc.)
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from db.database import Base
import datetime


class LocalModel(Base):
    """
    LocalModel stores configurations for local LLM servers.
    Each row represents a configured local model that can be selected in agent configs.
    """
    __tablename__ = 'local_models'

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Model Identification (unique identifier used in agent configs)
    name = Column(String, unique=True, nullable=False, index=True)
    # Format: "ollama-llama3", "lmstudio-codellama"
    # Used as model ID in agent configurations

    # Display name (human-readable)
    display_name = Column(String, nullable=False)
    # Example: "My Llama 3.2", "CodeLlama 34B"

    description = Column(String, nullable=True)
    # Optional user description

    # Provider Configuration
    provider = Column(String, nullable=False, index=True)
    # Values: "ollama", "lmstudio", "vllm", "litellm", "custom"

    base_url = Column(String, nullable=False)
    # Example: "http://localhost:11434/v1"

    model_name = Column(String, nullable=False)
    # Provider's internal model identifier
    # Example: "llama3.2:latest" for Ollama

    api_key = Column(String, nullable=True)
    # Optional API key (encrypted at application layer)

    # Validation Status
    is_validated = Column(Boolean, default=False, nullable=False, index=True)
    # True if connection test passed

    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    # Timestamp of last successful validation

    validation_error = Column(String, nullable=True)
    # Last error message if validation failed

    # Model Capabilities (JSON)
    capabilities = Column(JSON, default=dict)
    # Example: {"streaming": true, "tools": false, "max_context": 8192}

    # Usage Tracking
    usage_count = Column(Integer, default=0)
    # Number of times this model has been used

    last_used_at = Column(DateTime(timezone=True), nullable=True)
    # Last time this model was used in agent execution

    # Soft Delete
    is_active = Column(Boolean, default=True, nullable=False)
    # False for soft-deleted models (preserves history)

    # Tags for categorization
    tags = Column(JSON, default=list)
    # Example: ["coding", "fast", "7b"]

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True),
                       default=datetime.datetime.utcnow,
                       onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<LocalModel(id={self.id}, name='{self.name}', provider='{self.provider}', validated={self.is_validated})>"

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "provider": self.provider,
            "base_url": self.base_url,
            "model_name": self.model_name,
            "is_validated": self.is_validated,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
            "validation_error": self.validation_error,
            "capabilities": self.capabilities,
            "usage_count": self.usage_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
