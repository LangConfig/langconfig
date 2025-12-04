# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Verify if image_generation tool is assigned to agents"""
from db.database import SessionLocal
from models.workflow import WorkflowProfile
import json

db = SessionLocal()

workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == 24).first()

if workflow:
    print(f"=== WORKFLOW: {workflow.name} ===\n")
    config = workflow.configuration
    nodes = config.get('nodes', [])

    for node in nodes:
        node_id = node.get('id')
        node_type = node.get('type')
        node_config = node.get('config', {})

        # Get custom tools
        custom_tools = node_config.get('custom_tools', [])
        mcp_tools = node_config.get('mcp_tools', [])

        print(f"Node ID: {node_id}")
        # Remove emojis/non-ASCII from type for display
        safe_type = ''.join(c for c in node_type if ord(c) < 128) if node_type else 'unknown'
        print(f"  Type: {safe_type[:50]}")
        print(f"  MCP Tools: {mcp_tools}")
        print(f"  Custom Tools: {custom_tools}")

        if 'image_generation' in custom_tools:
            print(f"  >>> IMAGE_GENERATION TOOL FOUND! <<<")
        else:
            print(f"  X No image_generation tool")
        print()
else:
    print("Workflow 24 not found")

db.close()
