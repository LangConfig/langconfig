# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from core.utils.structured_outputs import list_available_schemas, STRUCTURED_OUTPUT_SCHEMAS

router = APIRouter(
    prefix="/schemas",
    tags=["schemas"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=Dict[str, Any])
async def get_available_schemas():
    """
    List all available structured output schemas.
    Returns a dictionary mapping schema names to their JSON schema definitions.
    """
    try:
        schemas = {}
        available_names = list_available_schemas()

        for name in available_names:
            schema_class = STRUCTURED_OUTPUT_SCHEMAS.get(name)
            if schema_class:
                # Get the JSON schema for the Pydantic model
                schemas[name] = schema_class.model_json_schema()

        return {
            "schemas": schemas,
            "names": available_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve schemas: {str(e)}")
