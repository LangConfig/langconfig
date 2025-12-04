# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Settings Database Model
Stores all user preferences and configuration in PostgreSQL
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Float
from db.database import Base
import datetime


class Settings(Base):
    """
    Single-row settings table for storing all application configuration
    There should only ever be one row (id=1) in this table
    """
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True, default=1)  # Always 1

    # API Keys (encrypted in production)
    # Note: Should be moved to OS keychain via Tauri for security
    api_keys = Column(JSON, default=dict)  # {"openai": "sk-...", "anthropic": "sk-ant-..."}

    # General Settings
    app_name = Column(String, default="LangConfig")
    auto_save = Column(Boolean, default=True)
    auto_save_interval = Column(Integer, default=300)  # seconds
    confirm_before_delete = Column(Boolean, default=True)
    show_notifications = Column(Boolean, default=True)
    check_updates = Column(Boolean, default=True)
    telemetry = Column(Boolean, default=False)
    log_level = Column(String, default="info")

    # RAG/Vector Database Settings
    storage_path = Column(String, nullable=True)
    embedding_model = Column(String, default="text-embedding-3-small")
    chunk_size = Column(Integer, default=1000)
    chunk_overlap = Column(Integer, default=200)

    # Model Defaults
    default_model = Column(String, default="gpt-4o")
    default_temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)

    # Local Models Settings
    local_provider = Column(String, default="ollama")
    local_base_url = Column(String, default="http://localhost:11434/v1")
    local_model_name = Column(String, default="llama3.2:latest")
    local_api_key = Column(String, nullable=True)

    # Workspace Settings
    workspace_path = Column(String, default="")
    workspace_allow_read = Column(Boolean, default=True)
    workspace_allow_write = Column(Boolean, default=True)
    workspace_require_approval = Column(Boolean, default=True)
    workspace_auto_detect_git = Column(Boolean, default=True)
    workspace_backup_before_edit = Column(Boolean, default=True)

    # Model Defaults Advanced
    primary_model = Column(String, default="gpt-4o")
    fallback_models = Column(JSON, default=lambda: ["claude-sonnet-4-5"])
    temperature = Column(Float, default=0.7)
    max_tokens_default = Column(Integer, default=4096)
    top_p = Column(Float, default=1.0)
    routing_strategy = Column(String, default="balanced")
    daily_token_limit = Column(Integer, default=0)  # 0 = unlimited
    monthly_token_limit = Column(Integer, default=0)  # 0 = unlimited
    alert_threshold = Column(Integer, default=80)  # percentage

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
