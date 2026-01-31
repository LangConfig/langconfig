# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model Capabilities API Router
REST API endpoint for querying model capability flags (function calling, vision, etc.)
"""
from fastapi import APIRouter
from typing import Any, Dict

from core.agents.model_profiles import get_model_capabilities

router = APIRouter()


@router.get("/{model_name}/capabilities")
async def get_capabilities(model_name: str) -> Dict[str, Any]:
    """
    Get capability flags for a model (function calling, vision, etc.).

    Returns a dictionary of capability flags for the specified model.
    Uses local defaults from the model_profiles module, with conservative
    fallbacks for unknown models.

    Args:
        model_name: The model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-5')
    """
    capabilities = get_model_capabilities(model_name)
    return {"model": model_name, "capabilities": capabilities}
