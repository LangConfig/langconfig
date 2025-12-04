# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for Agent Templates (Preset Agents).

Serves the built-in agent templates defined in orchestration/agent_templates.py.
These are the preset agents that users can drag into their workflows.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from core.agents.templates import AgentTemplateRegistry

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/templates")
async def get_agent_templates() -> List[Dict[str, Any]]:
    """
    Get all available agent templates (preset agents).

    Returns a list of agent configurations that users can add to their workflows.
    These are read from the AgentTemplateRegistry.
    """
    try:
        templates = AgentTemplateRegistry.list_all()

        # Convert to frontend-friendly format
        result = []
        for template in templates:
            result.append({
                "id": template.template_id,
                "name": template.name,
                "description": template.description,
                "icon": _get_icon_for_category(template.category.value),
                "model": template.model,
                "fallback_models": list(template.fallback_models) if template.fallback_models else [],
                "temperature": template.temperature,
                "max_tokens": template.max_tokens,
                "system_prompt": template.system_prompt,
                "mcp_tools": template.mcp_tools,
                "cli_tools": template.cli_tools,
                "custom_tools": template.custom_tools,  # FIX: Include custom tools
                "timeout_seconds": template.timeout_seconds,
                "max_retries": template.max_retries,
                "enable_model_routing": template.enable_model_routing,
                "enable_parallel_tools": template.enable_parallel_tools,
                "enable_memory": template.enable_memory,
                "enable_rag": template.enable_rag,
                "requires_human_approval": template.requires_human_approval,
                "middleware": template.middleware,  # NEW: LangGraph v1.0 middleware
                "tags": template.capabilities,
                "category": template.category.value
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load agent templates: {str(e)}")


@router.get("/templates/{template_id}")
async def get_agent_template(template_id: str) -> Dict[str, Any]:
    """Get a specific agent template by ID."""
    try:
        template = AgentTemplateRegistry.get(template_id)

        return {
            "id": template.template_id,
            "name": template.name,
            "description": template.description,
            "icon": _get_icon_for_category(template.category.value),
            "model": template.model,
            "fallback_models": list(template.fallback_models) if template.fallback_models else [],
            "temperature": template.temperature,
            "max_tokens": template.max_tokens,
            "system_prompt": template.system_prompt,
            "mcp_tools": template.mcp_tools,
            "cli_tools": template.cli_tools,
            "custom_tools": template.custom_tools,  # FIX: Include custom tools
            "timeout_seconds": template.timeout_seconds,
            "max_retries": template.max_retries,
            "enable_model_routing": template.enable_model_routing,
            "enable_parallel_tools": template.enable_parallel_tools,
            "enable_memory": template.enable_memory,
            "enable_rag": template.enable_rag,
            "requires_human_approval": template.requires_human_approval,
            "middleware": template.middleware,  # NEW: LangGraph v1.0 middleware
            "tags": template.capabilities,
            "category": template.category.value
        }

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent template '{template_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load agent template: {str(e)}")


@router.get("/recipes")
async def get_workflow_recipes() -> List[Dict[str, Any]]:
    """
    Get all available workflow recipes.

    Workflow recipes are pre-configured multi-node workflow templates
    that can be inserted into the canvas as a complete set of nodes and edges.
    """
    try:
        from core.templates.workflow_recipes import get_all_recipes, recipe_to_dict
        recipes = get_all_recipes()
        return [recipe_to_dict(recipe) for recipe in recipes]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load workflow recipes: {str(e)}")


@router.get("/recipes/{recipe_id}")
async def get_workflow_recipe(recipe_id: str) -> Dict[str, Any]:
    """
    Get a specific workflow recipe by ID.

    Returns the complete recipe with nodes and edges for canvas insertion.
    """
    try:
        from core.templates.workflow_recipes import get_recipe_by_id, recipe_to_dict
        recipe = get_recipe_by_id(recipe_id)
        return recipe_to_dict(recipe)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Workflow recipe '{recipe_id}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load workflow recipe: {str(e)}")


def _get_icon_for_category(category: str) -> str:
    """Map category to Material Symbols icon name."""
    icon_map = {
        "code_generation": "code",
        "code_review": "rate_review",
        "testing": "science",
        "devops": "settings_suggest",
        "research": "biotech",
        "architecture": "architecture",
        "documentation": "description",
        "planning": "checklist",
        "qa_validation": "task_alt"
    }
    return icon_map.get(category, "psychology")
