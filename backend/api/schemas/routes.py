# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for Structured Output Schemas.

Manage built-in and custom output schemas for agent structured responses.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from db.database import get_db
from models.custom_schema import CustomOutputSchema, OutputSchemaRegistry, json_schema_to_pydantic
from core.utils.structured_outputs import STRUCTURED_OUTPUT_SCHEMAS, list_available_schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/output-schemas", tags=["output-schemas"])


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================

class SchemaFieldInfo(BaseModel):
    """Information about a single field in a schema"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class SchemaInfo(BaseModel):
    """Schema summary for listing"""
    name: str
    description: str
    is_builtin: bool
    category: str
    fields: List[SchemaFieldInfo]
    usage_count: int = 0


class CustomSchemaCreate(BaseModel):
    """Request model for creating a custom schema"""
    name: str = Field(..., description="Unique schema name")
    description: Optional[str] = Field(None, description="Schema description")
    json_schema: Dict[str, Any] = Field(..., description="JSON Schema definition")
    category: str = Field("custom", description="Schema category")
    tags: List[str] = Field(default_factory=list, description="Tags for organization")


class CustomSchemaUpdate(BaseModel):
    """Request model for updating a custom schema"""
    description: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


# =============================================================================
# Helper Functions
# =============================================================================

def get_schema_fields(schema_class) -> List[Dict[str, Any]]:
    """Extract field information from a Pydantic model or JSON schema"""
    fields = []

    # Handle Pydantic model
    if hasattr(schema_class, 'model_fields'):
        from pydantic_core import PydanticUndefined

        for name, field_info in schema_class.model_fields.items():
            # Check if default is PydanticUndefined (can't be serialized)
            default_value = field_info.default
            if default_value is PydanticUndefined:
                default_value = None

            fields.append({
                "name": name,
                "type": str(field_info.annotation.__name__) if hasattr(field_info.annotation, '__name__') else str(field_info.annotation),
                "description": field_info.description or "",
                "required": field_info.is_required(),
                "default": default_value
            })

    return fields


def get_fields_from_json_schema(json_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract field information from a JSON schema"""
    fields = []
    properties = json_schema.get("properties", {})
    required_fields = set(json_schema.get("required", []))

    for name, prop in properties.items():
        fields.append({
            "name": name,
            "type": prop.get("type", "string"),
            "description": prop.get("description", ""),
            "required": name in required_fields,
            "default": prop.get("default")
        })

    return fields


# =============================================================================
# Schema Endpoints
# =============================================================================

@router.get("")
async def list_output_schemas(
    include_builtin: bool = True,
    include_custom: bool = True,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    List all available structured output schemas.

    Query params:
    - include_builtin: Include built-in schemas (default: true)
    - include_custom: Include user-defined schemas (default: true)
    - category: Filter by category
    """
    try:
        result = []

        # Add built-in schemas
        if include_builtin:
            for name, schema_class in STRUCTURED_OUTPUT_SCHEMAS.items():
                schema_info = {
                    "name": name,
                    "description": schema_class.__doc__ or "",
                    "is_builtin": True,
                    "category": "builtin",
                    "fields": get_schema_fields(schema_class),
                    "usage_count": 0,
                    "created_at": None
                }

                if category is None or schema_info["category"] == category:
                    result.append(schema_info)

        # Add custom schemas from database
        if include_custom:
            query = db.query(CustomOutputSchema).filter(CustomOutputSchema.is_public == True)

            if category:
                query = query.filter(CustomOutputSchema.category == category)

            custom_schemas = query.all()

            for schema in custom_schemas:
                result.append({
                    "id": schema.id,
                    "name": schema.name,
                    "description": schema.description or "",
                    "is_builtin": False,
                    "category": schema.category,
                    "fields": get_fields_from_json_schema(schema.json_schema),
                    "usage_count": schema.usage_count,
                    "tags": schema.tags or [],
                    "created_at": schema.created_at.isoformat() if schema.created_at else None
                })

        # Sort: built-in first, then by name
        result.sort(key=lambda x: (not x["is_builtin"], x["name"]))

        return result

    except Exception as e:
        logger.error(f"Failed to list output schemas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list output schemas: {str(e)}")


@router.get("/{schema_name}")
async def get_output_schema(
    schema_name: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a specific output schema by name."""
    try:
        # Check built-in schemas first
        if schema_name in STRUCTURED_OUTPUT_SCHEMAS:
            schema_class = STRUCTURED_OUTPUT_SCHEMAS[schema_name]

            # Get JSON schema from Pydantic model
            json_schema = schema_class.model_json_schema()

            return {
                "name": schema_name,
                "description": schema_class.__doc__ or "",
                "is_builtin": True,
                "category": "builtin",
                "json_schema": json_schema,
                "fields": get_schema_fields(schema_class)
            }

        # Check custom schemas
        custom_schema = db.query(CustomOutputSchema).filter(
            CustomOutputSchema.name == schema_name
        ).first()

        if custom_schema:
            return {
                "id": custom_schema.id,
                "name": custom_schema.name,
                "description": custom_schema.description or "",
                "is_builtin": False,
                "category": custom_schema.category,
                "json_schema": custom_schema.json_schema,
                "fields": get_fields_from_json_schema(custom_schema.json_schema),
                "tags": custom_schema.tags or [],
                "usage_count": custom_schema.usage_count,
                "created_at": custom_schema.created_at.isoformat() if custom_schema.created_at else None
            }

        raise HTTPException(status_code=404, detail=f"Output schema '{schema_name}' not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get output schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get output schema: {str(e)}")


@router.post("")
async def create_custom_schema(
    schema_data: CustomSchemaCreate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a new custom output schema."""
    try:
        # Check for name conflicts with built-in schemas
        if schema_data.name in STRUCTURED_OUTPUT_SCHEMAS:
            raise HTTPException(
                status_code=409,
                detail=f"Schema name '{schema_data.name}' conflicts with a built-in schema"
            )

        # Check for existing custom schema with same name
        existing = db.query(CustomOutputSchema).filter(
            CustomOutputSchema.name == schema_data.name
        ).first()

        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Custom schema '{schema_data.name}' already exists"
            )

        # Validate JSON schema by attempting conversion to Pydantic
        try:
            test_model = json_schema_to_pydantic(schema_data.name, schema_data.json_schema)
            logger.info(f"Schema validation passed: {schema_data.name} -> {test_model}")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON schema: {str(e)}"
            )

        # Create database record
        custom_schema = CustomOutputSchema(
            name=schema_data.name,
            description=schema_data.description,
            json_schema=schema_data.json_schema,
            category=schema_data.category,
            tags=schema_data.tags,
            is_public=True,
            is_builtin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(custom_schema)
        db.commit()
        db.refresh(custom_schema)

        # Register in runtime registry
        OutputSchemaRegistry.register_custom(
            custom_schema.name,
            custom_schema.to_pydantic_model()
        )

        logger.info(f"Created custom output schema: {custom_schema.name}")

        return {
            "id": custom_schema.id,
            "name": custom_schema.name,
            "message": "Custom output schema created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create custom schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create custom schema: {str(e)}")


@router.put("/{schema_name}")
async def update_custom_schema(
    schema_name: str,
    schema_data: CustomSchemaUpdate,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Update an existing custom output schema."""
    try:
        # Cannot update built-in schemas
        if schema_name in STRUCTURED_OUTPUT_SCHEMAS:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify built-in schemas"
            )

        schema = db.query(CustomOutputSchema).filter(
            CustomOutputSchema.name == schema_name
        ).first()

        if not schema:
            raise HTTPException(status_code=404, detail=f"Custom schema '{schema_name}' not found")

        # Update fields
        if schema_data.description is not None:
            schema.description = schema_data.description
        if schema_data.json_schema is not None:
            # Validate new schema
            try:
                json_schema_to_pydantic(schema_name, schema_data.json_schema)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON schema: {str(e)}")
            schema.json_schema = schema_data.json_schema
        if schema_data.category is not None:
            schema.category = schema_data.category
        if schema_data.tags is not None:
            schema.tags = schema_data.tags

        schema.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(schema)

        # Update runtime registry
        OutputSchemaRegistry.register_custom(
            schema.name,
            schema.to_pydantic_model()
        )

        logger.info(f"Updated custom output schema: {schema.name}")

        return {
            "name": schema.name,
            "message": "Custom output schema updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update custom schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update custom schema: {str(e)}")


@router.delete("/{schema_name}")
async def delete_custom_schema(
    schema_name: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Delete a custom output schema."""
    try:
        # Cannot delete built-in schemas
        if schema_name in STRUCTURED_OUTPUT_SCHEMAS:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete built-in schemas"
            )

        schema = db.query(CustomOutputSchema).filter(
            CustomOutputSchema.name == schema_name
        ).first()

        if not schema:
            raise HTTPException(status_code=404, detail=f"Custom schema '{schema_name}' not found")

        db.delete(schema)
        db.commit()

        logger.info(f"Deleted custom output schema: {schema_name}")

        return {
            "name": schema_name,
            "message": "Custom output schema deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete custom schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete custom schema: {str(e)}")


@router.post("/{schema_name}/validate")
async def validate_schema_output(
    schema_name: str,
    output_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Validate output data against a schema."""
    try:
        # Get schema class
        schema_class = OutputSchemaRegistry.get(schema_name)

        if not schema_class:
            # Check database for custom schema
            custom_schema = db.query(CustomOutputSchema).filter(
                CustomOutputSchema.name == schema_name
            ).first()

            if custom_schema:
                schema_class = custom_schema.to_pydantic_model()
            else:
                raise HTTPException(status_code=404, detail=f"Schema '{schema_name}' not found")

        # Validate
        try:
            validated = schema_class.model_validate(output_data)
            return {
                "valid": True,
                "message": "Output matches schema",
                "validated_data": validated.model_dump()
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Validation failed: {str(e)}",
                "errors": str(e)
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate schema output: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate: {str(e)}")
