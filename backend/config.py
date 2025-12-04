# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
LangConfig Configuration
Supports both .env file (local dev) and settings page (prod app)
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file from project root
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)


def get_api_key_from_db(key_name: str) -> Optional[str]:
    """
    Get API key from database (settings page).
    Falls back to .env if not found in database.

    Priority: Database > .env file > None
    """
    try:
        # Import here to avoid circular dependency
        from db.database import SessionLocal
        from sqlalchemy import text
        from services.encryption import encryption_service

        # Map key_name to the provider name used in api_keys JSONB
        # e.g., "openai_api_key" -> "openai"
        provider_map = {
            "openai_api_key": "openai",
            "anthropic_api_key": "anthropic",
            "google_api_key": "google",
            "cohere_api_key": "cohere",
            "replicate_api_key": "replicate",
        }
        provider = provider_map.get(key_name)

        if provider:
            with SessionLocal() as db:
                # Query the settings table's api_keys JSONB column
                # Use ->> operator to extract as text (not JSON)
                result = db.execute(
                    text(f"SELECT api_keys->>'{provider}' FROM settings WHERE id = 1")
                ).fetchone()

                if result and result[0]:
                    # Keys are stored encrypted - decrypt before returning
                    encrypted_key = result[0]
                    decrypted_key = encryption_service.decrypt(encrypted_key)
                    if decrypted_key:
                        return decrypted_key
    except Exception as e:
        # Database not available or error - fall back to .env
        pass

    # Fall back to .env file - try uppercase version
    env_key = os.getenv(key_name.upper())
    if not env_key:
        # Try the exact key name as fallback
        env_key = os.getenv(key_name)
    return env_key


class Settings(BaseSettings):
    """Application settings with dual-source API key support"""

    # Environment configuration
    environment: str = os.getenv("ENVIRONMENT", "development")  # development, production, or testing
    debug: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # Database - PostgreSQL for LangGraph checkpointing support
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://langconfig:langconfig_dev@localhost:5433/langconfig"
    )

    # API Keys - Stored as private attributes, accessed via properties
    _openai_api_key: Optional[str] = None
    _anthropic_api_key: Optional[str] = None
    _google_api_key: Optional[str] = None

    def get_api_key(self, key_name: str, env_fallback: Optional[str] = None) -> Optional[str]:
        """
        Get API key with priority: Database > .env > None

        Args:
            key_name: Name of the key (e.g., 'openai_api_key')
            env_fallback: Optional environment variable name to check
        """
        return get_api_key_from_db(key_name)

    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        """Get OpenAI API key from database or .env"""
        return self.get_api_key("openai_api_key")

    @property
    def ANTHROPIC_API_KEY(self) -> Optional[str]:
        """Get Anthropic API key from database or .env"""
        return self.get_api_key("anthropic_api_key")

    @property
    def GOOGLE_API_KEY(self) -> Optional[str]:
        """Get Google/Gemini API key from database or .env"""
        return self.get_api_key("google_api_key") or os.getenv("GEMINI_API_KEY")

    # Keep lowercase versions for backward compatibility
    @property
    def openai_api_key(self) -> Optional[str]:
        return self.OPENAI_API_KEY

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return self.ANTHROPIC_API_KEY

    @property
    def google_api_key(self) -> Optional[str]:
        return self.GOOGLE_API_KEY

    # LangSmith (optional)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "langconfig"

    # Defaults
    default_model: str = "gpt-4o"
    default_temperature: float = 0.7
    max_tokens: int = 4096

    # Middleware configuration
    enable_default_middleware: bool = True  # Enable default middleware by default

    # Execution History Configuration
    max_execution_history_per_workflow: int = int(os.getenv("MAX_EXECUTION_HISTORY_PER_WORKFLOW", "100"))
    execution_history_retention_days: int = int(os.getenv("EXECUTION_HISTORY_RETENTION_DAYS", "90"))
    auto_cleanup_execution_history: bool = os.getenv("AUTO_CLEANUP_EXECUTION_HISTORY", "true").lower() in ("true", "1", "yes")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"

    # Embeddings
    embedding_model: str = "text-embedding-3-small"

    # RAG
    chunk_size: int = 1000
    chunk_overlap: int = 200

    class Config:
        # Look for .env in parent directory (project root)
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields from .env file


# Global settings instance
settings = Settings()
