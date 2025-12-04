# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Model Validators Configuration

Defines validation rules for all models in the application.

Models configured:
- WorkflowProfile: Workflow configurations with complex validation
- DeepAgentTemplate: Agent templates with nested config validation
- CustomTool: Security-critical tool definitions
- Project: Simple project metadata

Usage:
    from core.model_validators import workflow_validator

    # In endpoint
    validated_data = workflow_validator.validate_update(update_data)
    workflow_validator.apply_update(instance, validated_data)
"""

import logging
from typing import Any, Dict
from core.validation import get_validator, PermissionLevel

logger = logging.getLogger(__name__)


# =============================================================================
# Validation Helper Functions
# =============================================================================

def validate_non_empty_string(value: Any, max_length: int = None) -> bool:
    """Validate that value is a non-empty string."""
    if not isinstance(value, str):
        return False
    if not value.strip():
        return False
    if max_length and len(value) > max_length:
        return False
    return True


def validate_json_dict(value: Any) -> bool:
    """Validate that value is a dictionary (JSON object)."""
    return isinstance(value, dict)


def validate_json_list(value: Any) -> bool:
    """Validate that value is a list (JSON array)."""
    return isinstance(value, list)


def validate_positive_integer(value: Any) -> bool:
    """Validate that value is a positive integer."""
    return isinstance(value, int) and value > 0


def validate_workflow_config(value: Any) -> bool:
    """
    Validate workflow configuration structure.

    Expected structure:
    {
        "nodes": [...],
        "edges": [...]
    }
    """
    if not isinstance(value, dict):
        return False

    # Must have nodes and edges
    if "nodes" not in value or "edges" not in value:
        return False

    # Nodes must be a list
    if not isinstance(value["nodes"], list):
        return False

    # Edges must be a list
    if not isinstance(value["edges"], list):
        return False

    return True


def validate_agent_config(value: Any) -> bool:
    """
    Validate agent configuration structure.

    Expected to be a dictionary with various config fields.
    """
    if not isinstance(value, dict):
        return False

    # Add specific validation rules as needed
    return True


# =============================================================================
# WorkflowProfile Validator
# =============================================================================

workflow_validator = get_validator("WorkflowProfile")

# PUBLIC fields - user can modify
workflow_validator.register_fields({
    "name": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: validate_non_empty_string(v, max_length=100),
        "transform": lambda v: v.strip() if isinstance(v, str) else v,
        "error_message": "Name must be a non-empty string (max 100 characters)"
    },
    "description": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str),
        "transform": lambda v: v.strip() if v and isinstance(v, str) else v
    },
    "project_id": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, int)
    },
    "strategy_type": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str)
    },
    "configuration": {
        "permission": PermissionLevel.PUBLIC,
        "validator": validate_workflow_config,
        "error_message": "Configuration must have 'nodes' and 'edges' arrays"
    },
    "schema_output_config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    },
    "output_schema": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str)
    },
    "blueprint": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    }
})

# SYSTEM fields - only backend can modify
workflow_validator.register_fields({
    "usage_count": {
        "permission": PermissionLevel.SYSTEM
    },
    "last_used_at": {
        "permission": PermissionLevel.SYSTEM
    },
    "export_status": {
        "permission": PermissionLevel.SYSTEM
    },
    "export_error": {
        "permission": PermissionLevel.SYSTEM
    },
    "last_export_at": {
        "permission": PermissionLevel.SYSTEM
    }
})

# IMMUTABLE fields - cannot be modified after creation
workflow_validator.register_fields({
    "id": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "created_at": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "updated_at": {
        "permission": PermissionLevel.IMMUTABLE
    }
})

logger.info(
    f"WorkflowProfile validator configured: "
    f"{len(workflow_validator.get_public_fields())} public, "
    f"{len(workflow_validator.get_system_fields())} system, "
    f"{len(workflow_validator.get_immutable_fields())} immutable fields"
)


# =============================================================================
# DeepAgentTemplate Validator
# =============================================================================

deepagent_validator = get_validator("DeepAgentTemplate")

# PUBLIC fields
deepagent_validator.register_fields({
    "name": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: validate_non_empty_string(v, max_length=100),
        "transform": lambda v: v.strip() if isinstance(v, str) else v,
        "error_message": "Name must be a non-empty string (max 100 characters)"
    },
    "description": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str),
        "transform": lambda v: v.strip() if v and isinstance(v, str) else v
    },
    "config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": validate_agent_config,
        "error_message": "Config must be a valid dictionary"
    },
    "middleware_config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    },
    "subagents_config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    },
    "backend_config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    },
    "guardrails_config": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    },
    "category": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str)
    }
})

# SYSTEM fields
deepagent_validator.register_fields({
    "usage_count": {
        "permission": PermissionLevel.SYSTEM
    },
    "last_used_at": {
        "permission": PermissionLevel.SYSTEM
    }
})

# IMMUTABLE fields
deepagent_validator.register_fields({
    "id": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "created_at": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "updated_at": {
        "permission": PermissionLevel.IMMUTABLE
    }
})

logger.info(
    f"DeepAgentTemplate validator configured: "
    f"{len(deepagent_validator.get_public_fields())} public fields"
)


# =============================================================================
# CustomTool Validator (Security-Critical)
# =============================================================================

customtool_validator = get_validator("CustomTool")

# PUBLIC fields
customtool_validator.register_fields({
    "name": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: validate_non_empty_string(v, max_length=100),
        "transform": lambda v: v.strip() if isinstance(v, str) else v,
        "error_message": "Tool name must be a non-empty string (max 100 characters)"
    },
    "description": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str),
        "transform": lambda v: v.strip() if v and isinstance(v, str) else v
    },
    "code": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: validate_non_empty_string(v),
        "error_message": "Tool code cannot be empty"
    },
    "parameters_schema": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or validate_json_dict(v)
    }
})

# IMMUTABLE fields
customtool_validator.register_fields({
    "id": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "created_at": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "updated_at": {
        "permission": PermissionLevel.IMMUTABLE
    }
})

logger.info(
    f"CustomTool validator configured: "
    f"{len(customtool_validator.get_public_fields())} public fields"
)


# =============================================================================
# Project Validator
# =============================================================================

project_validator = get_validator("Project")

# PUBLIC fields
project_validator.register_fields({
    "name": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: validate_non_empty_string(v, max_length=100),
        "transform": lambda v: v.strip() if isinstance(v, str) else v,
        "error_message": "Project name must be a non-empty string (max 100 characters)"
    },
    "description": {
        "permission": PermissionLevel.PUBLIC,
        "validator": lambda v: v is None or isinstance(v, str),
        "transform": lambda v: v.strip() if v and isinstance(v, str) else v
    }
})

# IMMUTABLE fields
project_validator.register_fields({
    "id": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "created_at": {
        "permission": PermissionLevel.IMMUTABLE
    },
    "updated_at": {
        "permission": PermissionLevel.IMMUTABLE
    }
})

logger.info(
    f"Project validator configured: "
    f"{len(project_validator.get_public_fields())} public fields"
)


# =============================================================================
# Export All Validators
# =============================================================================

__all__ = [
    "workflow_validator",
    "deepagent_validator",
    "customtool_validator",
    "project_validator"
]
