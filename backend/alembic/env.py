# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Alembic Environment Configuration for LangConfig.

This file configures Alembic to work with LangConfig's database models.
It imports all models to ensure they're registered with SQLAlchemy's metadata.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add backend directory to path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base from database setup
from db.database import Base

# Import ALL models to ensure they're registered with Base.metadata
# Core models
from models.core import Directive, Project, Task, ContextDocument, SearchHistory

# Workflow models
from models.workflow import WorkflowProfile, WorkflowVersion, WorkflowExecution

# DeepAgent models
from models.deep_agent import DeepAgentTemplate, AgentExport, ChatSession

# System models
from models.audit_log import AuditLog
from models.settings import Settings
from models.execution_event import ExecutionEvent
from models.background_task import BackgroundTask
from models.custom_tool import CustomTool, ToolExecutionLog

# Set target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from environment variable
# This allows us to use different databases for development, testing, and production
database_url = os.getenv(
    'DATABASE_URL',
    'postgresql://langconfig:langconfig_dev@localhost:5433/langconfig'  # Default from database.py
)
config.set_main_option('sqlalchemy.url', database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
