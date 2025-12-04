# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Local Models API Router
REST API endpoints for managing local LLM configurations (Ollama, LM Studio, vLLM, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import httpx
import logging

from db.database import get_db
from models.local_model import LocalModel
from services.encryption import encryption_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Pydantic Schemas
# ============================================================================

class LocalModelCreate(BaseModel):
    """Schema for creating a new local model"""
    name: str = Field(..., description="Unique identifier (e.g., 'ollama-llama3')")
    display_name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(None, description="Optional description")
    provider: str = Field(..., description="Provider: ollama, lmstudio, vllm, litellm, custom")
    base_url: str = Field(..., description="Base URL (e.g., 'http://localhost:11434/v1')")
    model_name: str = Field(..., description="Provider's model identifier")
    api_key: Optional[str] = Field(None, description="Optional API key")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for categorization")

    @validator('name')
    def validate_name(cls, v):
        """Validate name format"""
        if not v or not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("Name must be alphanumeric with hyphens/underscores only")
        return v.lower()

    @validator('base_url')
    def validate_base_url(cls, v):
        """Validate base URL format"""
        if not v.endswith('/v1'):
            raise ValueError("Base URL should end with /v1 for OpenAI compatibility")
        if not v.startswith('http://') and not v.startswith('https://'):
            raise ValueError("Base URL must start with http:// or https://")
        return v

    @validator('provider')
    def validate_provider(cls, v):
        """Validate provider value"""
        valid_providers = ['ollama', 'lmstudio', 'vllm', 'litellm', 'custom']
        if v.lower() not in valid_providers:
            raise ValueError(f"Provider must be one of: {', '.join(valid_providers)}")
        return v.lower()


class LocalModelUpdate(BaseModel):
    """Schema for updating a local model"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    tags: Optional[List[str]] = None

    @validator('base_url')
    def validate_base_url(cls, v):
        if v and not v.endswith('/v1'):
            raise ValueError("Base URL should end with /v1")
        return v


class LocalModelResponse(BaseModel):
    """Schema for local model response"""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    provider: str
    base_url: str
    model_name: str
    is_validated: bool
    last_validated_at: Optional[datetime]
    validation_error: Optional[str]
    capabilities: dict
    usage_count: int
    last_used_at: Optional[datetime]
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ValidationResult(BaseModel):
    """Schema for validation result"""
    success: bool
    message: str
    model_count: Optional[int] = None
    capabilities: Optional[dict] = None
    error_details: Optional[str] = None


# ============================================================================
# Validation Service
# ============================================================================

class LocalModelValidator:
    """Service for validating local model connections"""

    @staticmethod
    async def test_connection(
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 10.0
    ) -> ValidationResult:
        """
        Test connection to local model endpoint.

        Args:
            base_url: Base URL of the local model server
            api_key: Optional API key for authentication
            timeout: Timeout in seconds

        Returns:
            ValidationResult with success status and details
        """
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Try to fetch models endpoint
                response = await client.get(f"{base_url}/models", headers=headers)

                if response.status_code != 200:
                    return ValidationResult(
                        success=False,
                        message=f"Endpoint returned {response.status_code}: {response.text[:100]}",
                        error_details=response.text
                    )

                # Parse response
                data = response.json()
                models = data.get("data", []) or data.get("models", [])

                # Try to infer capabilities
                capabilities = {
                    "streaming": True,  # Most local servers support streaming
                    "tools": False,     # Conservative default
                    "max_context": 4096  # Conservative default
                }

                return ValidationResult(
                    success=True,
                    message=f"Connected successfully! Found {len(models)} model(s).",
                    model_count=len(models),
                    capabilities=capabilities
                )

        except httpx.TimeoutException:
            return ValidationResult(
                success=False,
                message="Connection timeout - is the server running?",
                error_details="Request timed out after {timeout} seconds"
            )
        except httpx.ConnectError as e:
            return ValidationResult(
                success=False,
                message="Cannot connect to server - check if it's running",
                error_details=str(e)
            )
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return ValidationResult(
                success=False,
                message=f"Validation failed: {str(e)}",
                error_details=str(e)
            )


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.get("/", response_model=List[LocalModelResponse])
async def list_local_models(
    only_validated: bool = False,
    only_active: bool = True,
    db: Session = Depends(get_db)
):
    """
    List all local models.

    Args:
        only_validated: If True, only return validated models
        only_active: If True, only return active (non-deleted) models
    """
    query = db.query(LocalModel)

    if only_validated:
        query = query.filter(LocalModel.is_validated == True)

    if only_active:
        query = query.filter(LocalModel.is_active == True)

    models = query.order_by(LocalModel.created_at.desc()).all()
    return models


@router.get("/{model_id}", response_model=LocalModelResponse)
async def get_local_model(model_id: int, db: Session = Depends(get_db)):
    """Get a specific local model by ID."""
    model = db.query(LocalModel).filter(
        LocalModel.id == model_id,
        LocalModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local model with ID {model_id} not found"
        )

    return model


@router.post("/", response_model=LocalModelResponse, status_code=status.HTTP_201_CREATED)
async def create_local_model(
    model_data: LocalModelCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new local model configuration.

    The model will be created with is_validated=False.
    Use the /validate endpoint to test and validate the connection.
    """
    # Check if name already exists
    existing = db.query(LocalModel).filter(LocalModel.name == model_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A local model with name '{model_data.name}' already exists"
        )

    # Encrypt API key if provided
    encrypted_api_key = None
    if model_data.api_key:
        encrypted_api_key = encryption_service.encrypt(model_data.api_key)

    # Create new model
    new_model = LocalModel(
        name=model_data.name,
        display_name=model_data.display_name,
        description=model_data.description,
        provider=model_data.provider,
        base_url=model_data.base_url,
        model_name=model_data.model_name,
        api_key=encrypted_api_key,
        tags=model_data.tags or [],
        is_validated=False
    )

    db.add(new_model)
    db.commit()
    db.refresh(new_model)

    logger.info(f"Created local model: {new_model.name} (ID: {new_model.id})")

    return new_model


@router.patch("/{model_id}", response_model=LocalModelResponse)
async def update_local_model(
    model_id: int,
    model_data: LocalModelUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a local model configuration.

    Note: Changing connection details (base_url, api_key) will reset validation status.
    """
    model = db.query(LocalModel).filter(
        LocalModel.id == model_id,
        LocalModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local model with ID {model_id} not found"
        )

    # Track if connection details changed
    connection_changed = False

    # Update fields
    if model_data.display_name is not None:
        model.display_name = model_data.display_name

    if model_data.description is not None:
        model.description = model_data.description

    if model_data.base_url is not None:
        model.base_url = model_data.base_url
        connection_changed = True

    if model_data.model_name is not None:
        model.model_name = model_data.model_name

    if model_data.api_key is not None:
        model.api_key = encryption_service.encrypt(model_data.api_key)
        connection_changed = True

    if model_data.tags is not None:
        model.tags = model_data.tags

    # Reset validation if connection details changed
    if connection_changed:
        model.is_validated = False
        model.last_validated_at = None
        model.validation_error = "Configuration changed - revalidation required"

    model.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(model)

    logger.info(f"Updated local model: {model.name} (ID: {model.id})")

    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_local_model(
    model_id: int,
    hard_delete: bool = False,
    db: Session = Depends(get_db)
):
    """
    Delete a local model.

    Args:
        model_id: ID of the model to delete
        hard_delete: If True, permanently delete. If False (default), soft delete.
    """
    model = db.query(LocalModel).filter(LocalModel.id == model_id).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local model with ID {model_id} not found"
        )

    if hard_delete:
        # Permanent deletion
        db.delete(model)
        logger.info(f"Permanently deleted local model: {model.name} (ID: {model.id})")
    else:
        # Soft delete
        model.is_active = False
        model.updated_at = datetime.utcnow()
        logger.info(f"Soft deleted local model: {model.name} (ID: {model.id})")

    db.commit()


# ============================================================================
# Validation Endpoints
# ============================================================================

@router.post("/{model_id}/validate", response_model=ValidationResult)
async def validate_local_model(model_id: int, db: Session = Depends(get_db)):
    """
    Test connection to a local model and update validation status.

    This endpoint will:
    1. Test the connection to the model server
    2. Update the model's validation status
    3. Store capabilities if successful
    """
    model = db.query(LocalModel).filter(
        LocalModel.id == model_id,
        LocalModel.is_active == True
    ).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local model with ID {model_id} not found"
        )

    # Decrypt API key if present
    api_key = None
    if model.api_key:
        try:
            api_key = encryption_service.decrypt(model.api_key)
        except Exception as e:
            logger.error(f"Failed to decrypt API key for model {model_id}: {e}")

    # Test connection
    validation_result = await LocalModelValidator.test_connection(
        base_url=model.base_url,
        api_key=api_key,
        timeout=10.0
    )

    # Update model based on validation result
    model.is_validated = validation_result.success
    model.updated_at = datetime.utcnow()

    if validation_result.success:
        model.last_validated_at = datetime.utcnow()
        model.validation_error = None
        if validation_result.capabilities:
            model.capabilities = validation_result.capabilities
        logger.info(f"✓ Validated local model: {model.name}")
    else:
        model.validation_error = validation_result.message
        logger.warning(f"✗ Validation failed for {model.name}: {validation_result.message}")

    db.commit()
    db.refresh(model)

    return validation_result


@router.post("/validate-config", response_model=ValidationResult)
async def validate_config_without_saving(
    base_url: str,
    api_key: Optional[str] = None
):
    """
    Test a local model configuration without saving to database.

    Useful for validating settings before creating a new model.
    """
    if not base_url.endswith('/v1'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base URL should end with /v1"
        )

    validation_result = await LocalModelValidator.test_connection(
        base_url=base_url,
        api_key=api_key,
        timeout=10.0
    )

    return validation_result
