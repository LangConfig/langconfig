# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Debug API endpoints for development
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import json

from db.database import get_db
from models.workflow import WorkflowProfile
from models.custom_tool import CustomTool

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/workflow/{workflow_id}")
async def get_workflow_debug(workflow_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Get detailed debug information about a workflow's configuration.
    Shows tool assignments, node configs, and validates setup.
    """
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()

    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    nodes = workflow.configuration.get('nodes', [])

    # Analyze each node
    node_analysis = []
    for node in nodes:
        node_id = node.get('id')
        node_type = node.get('type', 'unknown')
        node_config = node.get('config', {})

        # Remove emojis for display
        safe_type = ''.join(c for c in node_type if ord(c) < 128) if node_type else 'unknown'

        custom_tools = node_config.get('custom_tools', [])
        # Prefer native_tools; fall back to legacy mcp_tools for older configs
        native_tools = node_config.get('native_tools', node_config.get('mcp_tools', []))

        node_analysis.append({
            "node_id": node_id,
            "type": safe_type,
            "native_tools": native_tools,
            "custom_tools": custom_tools,
            "has_image_generation": "image_generation" in custom_tools,
            "model": node_config.get('model'),
            "config_keys": list(node_config.keys())
        })

    # Get all available custom tools
    all_custom_tools = db.query(CustomTool).all()
    custom_tools_list = [
        {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "tool_type": tool.tool_type.value
        }
        for tool in all_custom_tools
    ]

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow.name,
        "nodes": node_analysis,
        "available_custom_tools": custom_tools_list,
        "raw_configuration": workflow.configuration
    }
