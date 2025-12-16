# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Custom Output Schema Models - User-defined structured output schemas

Allows users to define custom Pydantic-style schemas for agent responses,
enabling structured output beyond the built-in schemas.
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, Text, Boolean
from sqlalchemy.orm import validates
from db.database import Base
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, create_model
import json
import logging

logger = logging.getLogger(__name__)


class CustomOutputSchema(Base):
    """
    User-defined output schemas for structured agent responses.

    Stores JSON Schema definitions that can be converted to Pydantic models
    at runtime for use with LangChain's structured output features.
    """
    __tablename__ = "custom_output_schemas"

    id = Column(Integer, primary_key=True, index=True)

    # Schema identification
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # JSON Schema definition
    json_schema = Column(JSON, nullable=False)

    # Visibility
    is_public = Column(Boolean, default=True)
    is_builtin = Column(Boolean, default=False)  # True for system-provided schemas

    # Metadata
    category = Column(String(50), default="custom")
    tags = Column(JSON, default=list)

    # Usage tracking
    usage_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @validates('json_schema')
    def validate_json_schema(self, key, schema):
        """Validate the JSON schema structure"""
        if not isinstance(schema, dict):
            raise ValueError("json_schema must be a dictionary")

        # Basic JSON Schema validation
        if "type" not in schema:
            raise ValueError("json_schema must have a 'type' field")

        if schema.get("type") != "object":
            raise ValueError("Root schema type must be 'object'")

        if "properties" not in schema:
            raise ValueError("json_schema must have 'properties' field")

        return schema

    def to_pydantic_model(self) -> type[BaseModel]:
        """
        Convert JSON Schema to a dynamic Pydantic model.

        Returns:
            A Pydantic model class generated from the JSON schema
        """
        return json_schema_to_pydantic(self.name, self.json_schema)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "json_schema": self.json_schema,
            "is_public": self.is_public,
            "is_builtin": self.is_builtin,
            "category": self.category,
            "tags": self.tags or [],
            "usage_count": self.usage_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# =============================================================================
# JSON Schema to Pydantic Conversion
# =============================================================================

def json_type_to_python(json_type: str, format: Optional[str] = None) -> type:
    """Map JSON Schema types to Python types"""
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None)
    }
    return type_map.get(json_type, Any)


def json_schema_to_pydantic(
    model_name: str,
    schema: Dict[str, Any]
) -> type[BaseModel]:
    """
    Convert a JSON Schema to a Pydantic model dynamically.

    Args:
        model_name: Name for the generated model class
        schema: JSON Schema dictionary

    Returns:
        A dynamically created Pydantic model class
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    field_definitions = {}

    for field_name, field_schema in properties.items():
        field_type = json_type_to_python(
            field_schema.get("type", "string"),
            field_schema.get("format")
        )

        # Handle arrays with items
        if field_schema.get("type") == "array":
            items_type = field_schema.get("items", {}).get("type", "string")
            field_type = List[json_type_to_python(items_type)]

        # Build field with description and default
        description = field_schema.get("description", "")
        default = field_schema.get("default", ...)

        if field_name not in required and default is ...:
            default = None
            field_type = Optional[field_type]

        field_definitions[field_name] = (
            field_type,
            Field(default=default, description=description)
        )

    # Create the dynamic model
    model = create_model(
        model_name,
        __doc__=schema.get("description", f"Dynamic schema: {model_name}"),
        **field_definitions
    )

    logger.debug(f"Created dynamic Pydantic model: {model_name} with {len(field_definitions)} fields")

    return model


# =============================================================================
# Schema Registry Helper
# =============================================================================

class OutputSchemaRegistry:
    """
    Registry for managing both built-in and custom output schemas.

    Provides a unified interface for accessing all available schemas.
    """

    _custom_schemas: Dict[str, type[BaseModel]] = {}

    @classmethod
    def register_custom(cls, name: str, schema: type[BaseModel]):
        """Register a custom schema"""
        cls._custom_schemas[name] = schema
        logger.info(f"Registered custom output schema: {name}")

    @classmethod
    def get(cls, name: str) -> Optional[type[BaseModel]]:
        """
        Get a schema by name.

        First checks built-in schemas, then custom schemas.
        """
        # Import here to avoid circular dependency
        from core.utils.structured_outputs import STRUCTURED_OUTPUT_SCHEMAS

        # Check built-in first
        if name in STRUCTURED_OUTPUT_SCHEMAS:
            return STRUCTURED_OUTPUT_SCHEMAS[name]

        # Check custom schemas
        if name in cls._custom_schemas:
            return cls._custom_schemas[name]

        return None

    @classmethod
    def list_all(cls) -> Dict[str, str]:
        """
        List all available schemas (built-in + custom).

        Returns:
            Dictionary mapping schema names to descriptions
        """
        from core.utils.structured_outputs import STRUCTURED_OUTPUT_SCHEMAS

        all_schemas = {}

        # Add built-in schemas
        for name, schema in STRUCTURED_OUTPUT_SCHEMAS.items():
            all_schemas[name] = {
                "description": schema.__doc__ or "",
                "is_builtin": True
            }

        # Add custom schemas
        for name, schema in cls._custom_schemas.items():
            all_schemas[name] = {
                "description": schema.__doc__ or "",
                "is_builtin": False
            }

        return all_schemas
