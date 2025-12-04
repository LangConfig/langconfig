# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Action Presets API

Exposes the action presets library with enhanced metadata including:
- Runtime context requirements (LangGraph ToolRuntime)
- Execution constraints (timeouts, exclusive execution)
- Performance estimates
- Output validation schemas
- Recommended middleware
- Compatibility requirements
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from core.presets.actions import (
    ActionPresetRegistry,
    ActionCategory,
    ActionType,
    RiskLevel,
    get_action_library,
    get_recommended_actions_for_agent
)

router = APIRouter(prefix="/api/action-presets", tags=["action-presets"])


# Response Models
class ActionPresetSummary(BaseModel):
    """Summary view of an action preset"""
    preset_id: str
    name: str
    description: str
    category: str
    action_type: str
    tags: List[str]
    risk_level: str
    requires_approval: bool

    # Enhanced fields
    has_runtime_requirements: bool
    has_execution_constraints: bool
    has_output_schema: bool
    recommended_middleware: List[str]
    estimated_duration_seconds: Optional[float]
    is_io_bound: bool


class ActionPresetDetail(BaseModel):
    """Detailed view of an action preset with all metadata"""
    preset_id: str
    name: str
    description: str
    category: str
    action_type: str
    config: Dict[str, Any]
    input_schema: Dict[str, Any]
    usage_example: Optional[str]
    best_practices: List[str]
    tags: List[str]
    version: str
    is_public: bool

    # Safety
    risk_level: str
    requires_approval: bool

    # Runtime requirements
    runtime: Optional[Dict[str, Any]]

    # Execution constraints
    constraints: Optional[Dict[str, Any]]

    # Output validation
    output_schema: Optional[Dict[str, Any]]

    # Middleware
    recommended_middleware: List[str]

    # Performance
    performance: Optional[Dict[str, Any]]

    # Compatibility
    compatibility: Optional[Dict[str, Any]]


class ActionLibraryResponse(BaseModel):
    """Action library organized by category"""
    categories: Dict[str, List[ActionPresetSummary]]
    total_presets: int


class RecommendedActionsResponse(BaseModel):
    """Recommended actions for an agent type"""
    agent_type: str
    recommended_presets: List[ActionPresetSummary]
    count: int


# Endpoints
@router.get("/", response_model=ActionLibraryResponse)
async def list_action_presets(
    category: Optional[str] = None,
    action_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    requires_runtime: Optional[bool] = None
):
    """
    Get all action presets, optionally filtered by category, type, risk level, or runtime requirements.

    Returns action presets organized by category with enhanced metadata.

    Query Parameters:
        - category: Filter by ActionCategory (e.g., "file_operations", "version_control")
        - action_type: Filter by ActionType (e.g., "MCP_TOOL", "CUSTOM_ACTION")
        - risk_level: Filter by RiskLevel (e.g., "LOW", "MEDIUM", "HIGH")
        - requires_runtime: Filter by runtime requirements (true/false)
    """
    registry = ActionPresetRegistry

    # Get all presets
    if category:
        try:
            cat_enum = ActionCategory(category)
            presets = registry.list_by_category(cat_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    else:
        presets = registry.list_all()

    # Apply filters
    if action_type:
        try:
            type_enum = ActionType(action_type)
            presets = [p for p in presets if p.action_type == type_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid action_type: {action_type}")

    if risk_level:
        try:
            risk_enum = RiskLevel(risk_level)
            presets = [p for p in presets if p.risk_level == risk_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid risk_level: {risk_level}")

    if requires_runtime is not None:
        presets = [p for p in presets if p.runtime.requires_runtime == requires_runtime]

    # Organize by category
    categories_dict = {}
    for preset in presets:
        cat_value = preset.category.value
        if cat_value not in categories_dict:
            categories_dict[cat_value] = []

        categories_dict[cat_value].append(ActionPresetSummary(
            preset_id=preset.preset_id,
            name=preset.name,
            description=preset.description,
            category=preset.category.value,
            action_type=preset.action_type.value,
            tags=preset.tags,
            risk_level=preset.risk_level.value,
            requires_approval=preset.requires_approval,
            has_runtime_requirements=preset.runtime.requires_runtime,
            has_execution_constraints=(
                preset.constraints.max_duration_seconds is not None or
                preset.constraints.exclusive or
                not preset.constraints.allow_parallel
            ),
            has_output_schema=preset.output_schema is not None,
            recommended_middleware=preset.recommended_middleware,
            estimated_duration_seconds=preset.performance.typical_duration_seconds,
            is_io_bound=preset.performance.is_io_bound
        ))

    return ActionLibraryResponse(
        categories=categories_dict,
        total_presets=len(presets)
    )


@router.get("/{preset_id}", response_model=ActionPresetDetail)
async def get_action_preset(preset_id: str):
    """
    Get detailed information about a specific action preset.

    Returns complete metadata including configuration, schemas, examples, and best practices.
    """
    registry = ActionPresetRegistry
    preset = registry.get(preset_id)

    if not preset:
        raise HTTPException(status_code=404, detail=f"Action preset not found: {preset_id}")

    return ActionPresetDetail(
        preset_id=preset.preset_id,
        name=preset.name,
        description=preset.description,
        category=preset.category.value,
        action_type=preset.action_type.value,
        config=preset.config,
        input_schema=preset.input_schema,
        usage_example=preset.usage_example,
        best_practices=preset.best_practices,
        tags=preset.tags,
        version=preset.version,
        is_public=preset.is_public,
        risk_level=preset.risk_level.value,
        requires_approval=preset.requires_approval,
        runtime={
            "requires_runtime": preset.runtime.requires_runtime,
            "features": preset.runtime.features,
            "example_code": preset.runtime.example_code
        } if preset.runtime.requires_runtime else None,
        constraints={
            "max_duration_seconds": preset.constraints.max_duration_seconds,
            "max_retries": preset.constraints.max_retries,
            "timeout_strategy": preset.constraints.timeout_strategy,
            "allow_parallel": preset.constraints.allow_parallel,
            "exclusive": preset.constraints.exclusive
        } if (preset.constraints.max_duration_seconds or preset.constraints.exclusive or not preset.constraints.allow_parallel) else None,
        output_schema=preset.output_schema,
        recommended_middleware=preset.recommended_middleware,
        performance={
            "typical_duration_seconds": preset.performance.typical_duration_seconds,
            "is_io_bound": preset.performance.is_io_bound
        } if preset.performance.typical_duration_seconds else None,
        compatibility={
            "min_langchain_version": preset.compatibility.min_langchain_version,
            "required_features": preset.compatibility.required_features
        } if preset.compatibility.required_features else None
    )


@router.get("/categories/list")
async def list_categories():
    """
    Get all available action categories.

    Returns list of ActionCategory enum values with descriptions.
    """
    return {
        "categories": [
            {
                "value": cat.value,
                "name": cat.name,
                "description": _get_category_description(cat)
            }
            for cat in ActionCategory
        ]
    }


@router.get("/recommended/{agent_type}")
async def get_recommended_actions(agent_type: str):
    """
    Get recommended action presets for a specific agent type.

    Uses intelligent matching based on agent capabilities and common workflows.

    Supported agent types:
        - code_generation, code_review, code_refactoring
        - research, documentation, testing
        - debugging, deployment, security_audit
        - data_analysis, general_purpose
    """
    try:
        recommended_ids = get_recommended_actions_for_agent(agent_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    registry = ActionPresetRegistry
    presets = []

    for preset_id in recommended_ids:
        preset = registry.get(preset_id)
        if preset:
            presets.append(ActionPresetSummary(
                preset_id=preset.preset_id,
                name=preset.name,
                description=preset.description,
                category=preset.category.value,
                action_type=preset.action_type.value,
                tags=preset.tags,
                risk_level=preset.risk_level.value,
                requires_approval=preset.requires_approval,
                has_runtime_requirements=preset.runtime.requires_runtime,
                has_execution_constraints=(
                    preset.constraints.max_duration_seconds is not None or
                    preset.constraints.exclusive or
                    not preset.constraints.allow_parallel
                ),
                has_output_schema=preset.output_schema is not None,
                recommended_middleware=preset.recommended_middleware,
                estimated_duration_seconds=preset.performance.typical_duration_seconds,
                is_io_bound=preset.performance.is_io_bound
            ))

    return RecommendedActionsResponse(
        agent_type=agent_type,
        recommended_presets=presets,
        count=len(presets)
    )


def _get_category_description(category: ActionCategory) -> str:
    """Get human-readable description for action category"""
    descriptions = {
        ActionCategory.FILESYSTEM: "File and directory operations (read, write, search)",
        ActionCategory.CODE_ANALYSIS: "Code review, linting, and static analysis",
        ActionCategory.VERSION_CONTROL: "Git and version control operations",
        ActionCategory.TESTING: "Test execution, coverage analysis, and quality assurance",
        ActionCategory.RESEARCH: "Web search, RAG, document search, and information retrieval",
        ActionCategory.DATABASE: "Database queries and data operations",
        ActionCategory.INFRASTRUCTURE: "Deployment, CI/CD, Docker, and infrastructure operations",
        ActionCategory.EXECUTION: "Shell command execution, terminal operations, and code interpreters",
        ActionCategory.COMMUNICATION: "External communication, notifications, and integrations",
        ActionCategory.AGENTIC: "Agent reflection, agent-to-agent communication, and multi-agent systems",
        ActionCategory.DOCUMENTATION: "Documentation generation and management",
        ActionCategory.CUSTOM: "Custom user-defined actions and tools"
    }
    return descriptions.get(category, "")
