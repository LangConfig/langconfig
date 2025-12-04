# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Local Model Service
Service layer for accessing and caching local model configurations from the database.
Used by agent factory to load local model settings efficiently.
"""
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

from models.local_model import LocalModel
from services.encryption import encryption_service

logger = logging.getLogger(__name__)


# Module-level cache for local model configurations
_local_model_cache: Dict[str, Tuple[dict, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class LocalModelConfig:
    """Configuration for a local model"""
    provider: str
    base_url: str
    model_name: str
    api_key: Optional[str]
    timeout: int = 60
    capabilities: dict = None

    def to_chatmodel_params(self) -> Dict[str, any]:
        """Convert to parameters for ChatOpenAI"""
        return {
            "model": self.model_name,
            "base_url": self.base_url,
            "api_key": self.api_key or "not-needed",
            "timeout": self.timeout
        }


class LocalModelService:
    """Service for managing local model configurations"""

    # List of valid local model providers
    LOCAL_PROVIDERS = ["ollama", "lmstudio", "vllm", "litellm", "local"]

    @classmethod
    def is_local_model(cls, model_name: str) -> bool:
        """
        Check if a model name refers to a local model.

        Args:
            model_name: Model identifier (e.g., "ollama-llama3", "local-llama3")

        Returns:
            True if this is a local model
        """
        if model_name.startswith("local-"):
            return True

        # Check if it starts with any known local provider
        return any(model_name.startswith(f"{provider}-") for provider in cls.LOCAL_PROVIDERS)

    @classmethod
    def parse_model_name(cls, model_name: str) -> Optional[Tuple[str, str]]:
        """
        Parse a local model name into (provider, model).

        Args:
            model_name: Model identifier like "ollama-llama3" or "local-ollama-llama3"

        Returns:
            Tuple of (provider, model_name) or None if invalid
        """
        # Remove "local-" prefix if present
        clean_name = model_name.replace("local-", "")

        # Try to split on first hyphen
        parts = clean_name.split("-", 1)
        if len(parts) >= 2 and parts[0] in cls.LOCAL_PROVIDERS:
            return parts[0], parts[1]

        # If no provider prefix, assume whole thing is the name to look up
        return None, clean_name

    @classmethod
    def get_local_model_config(
        cls,
        model_name: str,
        db: Optional[Session] = None
    ) -> Optional[LocalModelConfig]:
        """
        Get local model configuration, using cache if available.

        Args:
            model_name: Model identifier (e.g., "ollama-llama3", "local-llama3")
            db: Database session (will be created if not provided)

        Returns:
            LocalModelConfig or None if not found
        """
        # Check cache first
        cache_key = model_name.replace("local-", "")
        cached_entry = _local_model_cache.get(cache_key)

        if cached_entry:
            config_dict, cached_at = cached_entry
            age = (datetime.utcnow() - cached_at).total_seconds()

            if age < _CACHE_TTL_SECONDS:
                logger.debug(f"Cache hit for local model: {cache_key} (age: {age:.1f}s)")
                return LocalModelConfig(**config_dict)

        # Cache miss or expired - load from database
        should_close_db = False
        if db is None:
            from db.database import SessionLocal
            db = SessionLocal()
            should_close_db = True

        try:
            # Parse model name to get the lookup key
            parsed = cls.parse_model_name(model_name)
            if parsed:
                _, lookup_name = parsed
            else:
                lookup_name = model_name.replace("local-", "")

            # Query database
            local_model = db.query(LocalModel).filter(
                LocalModel.name == lookup_name,
                LocalModel.is_validated == True,
                LocalModel.is_active == True
            ).first()

            if not local_model:
                logger.warning(f"Local model not found or not validated: {lookup_name}")
                return None

            # Decrypt API key if present
            api_key = None
            if local_model.api_key:
                try:
                    api_key = encryption_service.decrypt(local_model.api_key)
                except Exception as e:
                    logger.error(f"Failed to decrypt API key for {lookup_name}: {e}")

            # Create config
            config = LocalModelConfig(
                provider=local_model.provider,
                base_url=local_model.base_url,
                model_name=local_model.model_name,
                api_key=api_key,
                timeout=60,
                capabilities=local_model.capabilities or {}
            )

            # Cache it
            config_dict = {
                "provider": config.provider,
                "base_url": config.base_url,
                "model_name": config.model_name,
                "api_key": config.api_key,
                "timeout": config.timeout,
                "capabilities": config.capabilities
            }
            _local_model_cache[cache_key] = (config_dict, datetime.utcnow())

            logger.info(f"Loaded local model from database: {local_model.display_name} ({lookup_name})")

            return config

        finally:
            if should_close_db:
                db.close()

    @classmethod
    def get_all_validated_models(cls, db: Optional[Session] = None) -> list:
        """
        Get all validated local models.

        Args:
            db: Database session

        Returns:
            List of LocalModel objects
        """
        should_close_db = False
        if db is None:
            from db.database import SessionLocal
            db = SessionLocal()
            should_close_db = True

        try:
            models = db.query(LocalModel).filter(
                LocalModel.is_validated == True,
                LocalModel.is_active == True
            ).all()

            return models

        finally:
            if should_close_db:
                db.close()

    @classmethod
    def invalidate_cache(cls, model_name: Optional[str] = None):
        """
        Invalidate cache for a specific model or all models.

        Args:
            model_name: Optional model name to invalidate. If None, clears all cache.
        """
        global _local_model_cache

        if model_name:
            cache_key = model_name.replace("local-", "")
            if cache_key in _local_model_cache:
                del _local_model_cache[cache_key]
                logger.info(f"Invalidated cache for: {cache_key}")
        else:
            _local_model_cache = {}
            logger.info("Invalidated entire local model cache")

    @classmethod
    async def check_availability(cls, config: LocalModelConfig) -> bool:
        """
        Check if a local model is available by testing HTTP connection.

        Args:
            config: LocalModelConfig to test

        Returns:
            True if model server is reachable
        """
        import httpx

        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{config.base_url}/models", headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Availability check failed: {e}")
            return False

    @classmethod
    def get_cache_stats(cls) -> dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache stats
        """
        now = datetime.utcnow()
        valid_entries = 0
        expired_entries = 0

        for _, (_, cached_at) in _local_model_cache.items():
            age = (now - cached_at).total_seconds()
            if age < _CACHE_TTL_SECONDS:
                valid_entries += 1
            else:
                expired_entries += 1

        return {
            "total_cached": len(_local_model_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "ttl_seconds": _CACHE_TTL_SECONDS
        }


# Convenience functions for backward compatibility with legacy single local model

def get_legacy_local_model(db: Session) -> Optional[LocalModelConfig]:
    """
    Get local model from legacy Settings.local_* fields.

    This is for backward compatibility during migration.

    Args:
        db: Database session

    Returns:
        LocalModelConfig from Settings table or None
    """
    from models.settings import Settings

    settings = db.query(Settings).filter(Settings.id == 1).first()
    if not settings or not settings.local_provider:
        return None

    # Decrypt API key if present
    api_key = None
    if settings.local_api_key:
        try:
            api_key = encryption_service.decrypt(settings.local_api_key)
        except Exception as e:
            logger.error(f"Failed to decrypt legacy API key: {e}")

    return LocalModelConfig(
        provider=settings.local_provider,
        base_url=settings.local_base_url,
        model_name=settings.local_model_name,
        api_key=api_key,
        timeout=60
    )


async def migrate_legacy_local_model(db: Session) -> bool:
    """
    Migrate legacy Settings.local_* to local_models table.

    Args:
        db: Database session

    Returns:
        True if migration was performed, False if not needed
    """
    from models.settings import Settings

    settings = db.query(Settings).filter(Settings.id == 1).first()
    if not settings or not settings.local_provider:
        return False

    # Check if already migrated
    existing = db.query(LocalModel).filter(
        LocalModel.provider == settings.local_provider
    ).first()

    if existing:
        logger.info("Legacy local model already migrated")
        return False

    # Create new local model from legacy settings
    local_model = LocalModel(
        name=f"{settings.local_provider}-{settings.local_model_name}",
        display_name=f"{settings.local_provider.title()} {settings.local_model_name}",
        provider=settings.local_provider,
        base_url=settings.local_base_url,
        model_name=settings.local_model_name,
        api_key=settings.local_api_key,  # Already encrypted
        is_validated=False,
        description="Migrated from legacy settings"
    )

    db.add(local_model)
    db.commit()

    logger.info(f"Migrated legacy local model: {local_model.name}")

    return True
