# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict
from pydantic import BaseModel

from db.database import get_db
from models.settings import Settings as SettingsModel

router = APIRouter(prefix="/api/settings", tags=["settings"])


# Pydantic Schemas
class APIKeySet(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    replicate_api_key: Optional[str] = None


class APIKeyResponse(BaseModel):
    provider: str
    is_set: bool
    masked_key: Optional[str] = None


class SettingsUpdate(BaseModel):
    default_model: Optional[str] = None
    default_temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    storage_path: Optional[str] = None


class SettingsResponse(BaseModel):
    default_model: str
    default_temperature: float
    max_tokens: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    storage_path: str


class GeneralSettings(BaseModel):
    app_name: Optional[str] = "LangConfig"
    auto_save: Optional[bool] = True
    auto_save_interval: Optional[int] = 300
    confirm_before_delete: Optional[bool] = True
    show_notifications: Optional[bool] = True
    check_updates: Optional[bool] = True
    telemetry: Optional[bool] = False
    log_level: Optional[str] = "info"


class LocalModelsSettings(BaseModel):
    provider: Optional[str] = "ollama"
    base_url: Optional[str] = "http://localhost:11434/v1"
    model_name: Optional[str] = "llama3.2:latest"
    api_key: Optional[str] = None


class WorkspaceSettings(BaseModel):
    workspace_path: Optional[str] = ""
    allow_read: Optional[bool] = True
    allow_write: Optional[bool] = True
    require_approval: Optional[bool] = True
    auto_detect_git: Optional[bool] = True
    backup_before_edit: Optional[bool] = True


class ModelDefaultsSettings(BaseModel):
    primary_model: Optional[str] = "gpt-4o"
    fallback_models: Optional[list[str]] = ["claude-sonnet-4-5"]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    top_p: Optional[float] = 1.0
    routing_strategy: Optional[str] = "balanced"
    daily_token_limit: Optional[int] = 0
    monthly_token_limit: Optional[int] = 0
    alert_threshold: Optional[int] = 80


import os
import platform

# Platform-specific default storage paths
def get_default_storage_path() -> str:
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.getenv("APPDATA", "."), "LangConfig", "documents")
    elif system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/LangConfig/documents")
    else:  # Linux
        return os.path.expanduser("~/.local/share/langconfig/documents")


# Helper functions for database access
def get_or_create_settings(db: Session) -> SettingsModel:
    """Get settings from database or create default row if it doesn't exist"""
    settings = db.query(SettingsModel).filter(SettingsModel.id == 1).first()
    if not settings:
        settings = SettingsModel(
            id=1,
            api_keys={},
            storage_path=get_default_storage_path()
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def mask_api_key(key: str) -> str:
    """Mask API key for display"""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


from services.encryption import encryption_service

# Endpoints
@router.post("/api-keys")
async def set_api_keys(keys: APIKeySet, db: Session = Depends(get_db)):
    """Set API keys (stored encrypted in PostgreSQL)"""
    settings = get_or_create_settings(db)
    api_keys = settings.api_keys or {}

    if keys.openai_api_key:
        api_keys["openai"] = encryption_service.encrypt(keys.openai_api_key)
    if keys.anthropic_api_key:
        api_keys["anthropic"] = encryption_service.encrypt(keys.anthropic_api_key)
    if keys.google_api_key:
        api_keys["google"] = encryption_service.encrypt(keys.google_api_key)
    if keys.cohere_api_key:
        api_keys["cohere"] = encryption_service.encrypt(keys.cohere_api_key)
    if keys.replicate_api_key:
        api_keys["replicate"] = encryption_service.encrypt(keys.replicate_api_key)

    settings.api_keys = api_keys
    db.commit()

    return {"message": "API keys saved successfully"}


@router.get("/api-keys")
async def get_api_keys(db: Session = Depends(get_db)):
    """Get masked API keys status"""
    settings = get_or_create_settings(db)
    api_keys = settings.api_keys or {}
    providers = ["openai", "anthropic", "google", "cohere", "replicate"]

    results = []
    for provider in providers:
        encrypted_key = api_keys.get(provider)
        # Decrypt to check if it's a valid key and for masking
        # Note: We decrypt here to ensure we're masking the actual key,
        # though masking an encrypted string would also work for "is_set" check.
        # But for consistency and future validation, we decrypt.
        key = encryption_service.decrypt(encrypted_key) if encrypted_key else None

        results.append(
            APIKeyResponse(
                provider=provider,
                is_set=key is not None,
                masked_key=mask_api_key(key) if key else None
            )
        )

    return results


@router.get("/available-models")
async def get_available_models(db: Session = Depends(get_db)):
    """Get available models based on configured API keys and validated local models"""
    settings = get_or_create_settings(db)
    api_keys = settings.api_keys or {}
    available = []

    # OpenAI models (require OpenAI API key)
    if api_keys.get("openai"):
        available.extend([
            'gpt-5',
            'gpt-5-pro',
            'gpt-4o',
            'gpt-4o-mini',
        ])

    # Anthropic/Claude models (require Anthropic API key)
    if api_keys.get("anthropic"):
        available.extend([
            'claude-sonnet-4-5',
            'claude-sonnet-4-5-20250929',
            'claude-haiku-4-5',
        ])

    # Google Gemini models (require Google API key)
    if api_keys.get("google"):
        available.extend([
            'gemini-2.5-pro',
            'gemini-2.5-flash',
            'gemini-2.0-flash',
        ])

    # Local models (validated only)
    from models.local_model import LocalModel
    local_models = db.query(LocalModel).filter(
        LocalModel.is_validated == True,
        LocalModel.is_active == True
    ).all()

    # Add local models to available list with "local-" prefix
    local_model_list = []
    for model in local_models:
        model_id = f"local-{model.name}"
        available.append(model_id)
        local_model_list.append({
            "id": model.id,
            "name": model_id,
            "display_name": model.display_name,
            "provider": model.provider,
            "capabilities": model.capabilities,
            "base_url": model.base_url,
            "model_name": model.model_name
        })

    return {
        "models": available,
        "local_models": local_model_list  # Include detailed local model info
    }


@router.delete("/api-keys/{provider}")
async def delete_api_key(provider: str, db: Session = Depends(get_db)):
    """Delete an API key"""
    if provider not in ["openai", "anthropic", "google", "cohere", "replicate"]:
        raise HTTPException(status_code=400, detail="Invalid provider")

    settings = get_or_create_settings(db)
    api_keys = settings.api_keys or {}

    if provider in api_keys:
        del api_keys[provider]
        settings.api_keys = api_keys
        db.commit()
        return {"message": f"{provider} API key deleted"}
    else:
        raise HTTPException(status_code=404, detail="API key not found")


@router.get("/", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    """Get application settings"""
    settings = get_or_create_settings(db)
    return SettingsResponse(
        default_model=settings.default_model,
        default_temperature=settings.default_temperature,
        max_tokens=settings.max_tokens,
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        storage_path=settings.storage_path or get_default_storage_path()
    )


@router.patch("/", response_model=SettingsResponse)
async def update_settings(settings_update: SettingsUpdate, db: Session = Depends(get_db)):
    """Update application settings"""
    settings = get_or_create_settings(db)

    # Update only provided fields
    update_data = settings_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

    return SettingsResponse(
        default_model=settings.default_model,
        default_temperature=settings.default_temperature,
        max_tokens=settings.max_tokens,
        embedding_model=settings.embedding_model,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        storage_path=settings.storage_path or get_default_storage_path()
    )


@router.post("/reset")
async def reset_settings(db: Session = Depends(get_db)):
    """Reset settings to defaults"""
    settings = get_or_create_settings(db)

    settings.default_model = "gpt-4o"
    settings.default_temperature = 0.7
    settings.max_tokens = 4096
    settings.embedding_model = "text-embedding-3-small"
    settings.chunk_size = 1000
    settings.chunk_overlap = 200
    settings.storage_path = get_default_storage_path()

    db.commit()
    return {"message": "Settings reset to defaults"}


@router.get("/models")
async def list_available_models(db: Session = Depends(get_db)):
    """List available AI models (cloud + validated local models)"""
    settings = get_or_create_settings(db)
    api_keys = settings.api_keys or {}
    available = []

    # OpenAI models (always available - users provide keys at runtime if needed)
    available.extend([
        'gpt-5',
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
    ])

    # Anthropic/Claude models (current generation only)
    available.extend([
        'claude-opus-4',
        'claude-sonnet-4-5',
        'claude-haiku-4-5',
    ])

    # Google Gemini models
    available.extend([
        'gemini-2.5-pro',
        'gemini-2.5-flash',
        'gemini-2.0-flash-exp',
    ])

    # Local models (validated only)
    from models.local_model import LocalModel
    local_models = db.query(LocalModel).filter(
        LocalModel.is_validated == True,
        LocalModel.is_active == True
    ).all()

    # Add local models to available list
    local_model_list = []
    for model in local_models:
        model_id = f"local-{model.name}"
        available.append(model_id)
        local_model_list.append({
            "id": model.id,
            "name": model_id,
            "display_name": model.display_name,
            "provider": model.provider,
            "capabilities": model.capabilities,
            "is_validated": model.is_validated
        })

    return {
        "models": available,
        "local_models": local_model_list
    }


# General Settings Endpoints
@router.get("/general", response_model=GeneralSettings)
async def get_general_settings(db: Session = Depends(get_db)):
    """Get general application settings"""
    settings = get_or_create_settings(db)
    return GeneralSettings(
        app_name=settings.app_name,
        auto_save=settings.auto_save,
        auto_save_interval=settings.auto_save_interval,
        confirm_before_delete=settings.confirm_before_delete,
        show_notifications=settings.show_notifications,
        check_updates=settings.check_updates,
        telemetry=settings.telemetry,
        log_level=settings.log_level
    )


@router.post("/general", response_model=GeneralSettings)
async def update_general_settings(general_settings: GeneralSettings, db: Session = Depends(get_db)):
    """Update general application settings"""
    settings = get_or_create_settings(db)

    update_data = general_settings.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)

    return GeneralSettings(
        app_name=settings.app_name,
        auto_save=settings.auto_save,
        auto_save_interval=settings.auto_save_interval,
        confirm_before_delete=settings.confirm_before_delete,
        show_notifications=settings.show_notifications,
        check_updates=settings.check_updates,
        telemetry=settings.telemetry,
        log_level=settings.log_level
    )


# Local Models Settings Endpoints
@router.get("/local-models", response_model=LocalModelsSettings)
async def get_local_models_settings(db: Session = Depends(get_db)):
    """Get local models configuration"""
    settings = get_or_create_settings(db)
    return LocalModelsSettings(
        provider=settings.local_provider,
        base_url=settings.local_base_url,
        model_name=settings.local_model_name,
        api_key=encryption_service.decrypt(settings.local_api_key) if settings.local_api_key else None
    )


@router.post("/local-models", response_model=LocalModelsSettings)
async def update_local_models_settings(local_models: LocalModelsSettings, db: Session = Depends(get_db)):
    """Update local models configuration"""
    settings = get_or_create_settings(db)

    if local_models.provider is not None:
        settings.local_provider = local_models.provider
    if local_models.base_url is not None:
        settings.local_base_url = local_models.base_url
    if local_models.model_name is not None:
        settings.local_model_name = local_models.model_name
    if local_models.api_key is not None:
        settings.local_api_key = encryption_service.encrypt(local_models.api_key)

    db.commit()
    db.refresh(settings)

    return LocalModelsSettings(
        provider=settings.local_provider,
        base_url=settings.local_base_url,
        model_name=settings.local_model_name,
        api_key=encryption_service.decrypt(settings.local_api_key) if settings.local_api_key else None
    )


# Workspace Settings Endpoints
@router.get("/workspace", response_model=WorkspaceSettings)
async def get_workspace_settings(db: Session = Depends(get_db)):
    """Get workspace configuration"""
    settings = get_or_create_settings(db)
    return WorkspaceSettings(
        workspace_path=settings.workspace_path,
        allow_read=settings.workspace_allow_read,
        allow_write=settings.workspace_allow_write,
        require_approval=settings.workspace_require_approval,
        auto_detect_git=settings.workspace_auto_detect_git,
        backup_before_edit=settings.workspace_backup_before_edit
    )


@router.post("/workspace", response_model=WorkspaceSettings)
async def update_workspace_settings(workspace: WorkspaceSettings, db: Session = Depends(get_db)):
    """Update workspace configuration"""
    settings = get_or_create_settings(db)

    if workspace.workspace_path is not None:
        settings.workspace_path = workspace.workspace_path
    if workspace.allow_read is not None:
        settings.workspace_allow_read = workspace.allow_read
    if workspace.allow_write is not None:
        settings.workspace_allow_write = workspace.allow_write
    if workspace.require_approval is not None:
        settings.workspace_require_approval = workspace.require_approval
    if workspace.auto_detect_git is not None:
        settings.workspace_auto_detect_git = workspace.auto_detect_git
    if workspace.backup_before_edit is not None:
        settings.workspace_backup_before_edit = workspace.backup_before_edit

    db.commit()
    db.refresh(settings)

    return WorkspaceSettings(
        workspace_path=settings.workspace_path,
        allow_read=settings.workspace_allow_read,
        allow_write=settings.workspace_allow_write,
        require_approval=settings.workspace_require_approval,
        auto_detect_git=settings.workspace_auto_detect_git,
        backup_before_edit=settings.workspace_backup_before_edit
    )


# Model Defaults Settings Endpoints
@router.get("/model-defaults", response_model=ModelDefaultsSettings)
async def get_model_defaults_settings(db: Session = Depends(get_db)):
    """Get model defaults configuration"""
    settings = get_or_create_settings(db)
    return ModelDefaultsSettings(
        primary_model=settings.primary_model,
        fallback_models=settings.fallback_models,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens_default,
        top_p=settings.top_p,
        routing_strategy=settings.routing_strategy,
        daily_token_limit=settings.daily_token_limit,
        monthly_token_limit=settings.monthly_token_limit,
        alert_threshold=settings.alert_threshold
    )


@router.post("/model-defaults", response_model=ModelDefaultsSettings)
async def update_model_defaults_settings(model_defaults: ModelDefaultsSettings, db: Session = Depends(get_db)):
    """Update model defaults configuration"""
    settings = get_or_create_settings(db)

    if model_defaults.primary_model is not None:
        settings.primary_model = model_defaults.primary_model
    if model_defaults.fallback_models is not None:
        settings.fallback_models = model_defaults.fallback_models
    if model_defaults.temperature is not None:
        settings.temperature = model_defaults.temperature
    if model_defaults.max_tokens is not None:
        settings.max_tokens_default = model_defaults.max_tokens
    if model_defaults.top_p is not None:
        settings.top_p = model_defaults.top_p
    if model_defaults.routing_strategy is not None:
        settings.routing_strategy = model_defaults.routing_strategy
    if model_defaults.daily_token_limit is not None:
        settings.daily_token_limit = model_defaults.daily_token_limit
    if model_defaults.monthly_token_limit is not None:
        settings.monthly_token_limit = model_defaults.monthly_token_limit
    if model_defaults.alert_threshold is not None:
        settings.alert_threshold = model_defaults.alert_threshold

    db.commit()
    db.refresh(settings)

    return ModelDefaultsSettings(
        primary_model=settings.primary_model,
        fallback_models=settings.fallback_models,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens_default,
        top_p=settings.top_p,
        routing_strategy=settings.routing_strategy,
        daily_token_limit=settings.daily_token_limit,
        monthly_token_limit=settings.monthly_token_limit,
        alert_threshold=settings.alert_threshold
    )
