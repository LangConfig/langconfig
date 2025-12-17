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


@router.post("/emit-test-subagent-events/{workflow_id}")
async def emit_test_subagent_events(workflow_id: int):
    """
    Emit sample subagent events to test SubAgentPanel UI.

    This creates a realistic sequence of subagent events that will appear
    in the RealtimeExecutionPanel so you can iterate on the UI.
    """
    import asyncio
    import uuid
    from datetime import datetime
    from services.event_bus import get_event_bus

    event_bus = get_event_bus()
    channel = f"workflow:{workflow_id}"

    # Generate unique IDs for this test run
    parent_run_id = str(uuid.uuid4())
    subagent_run_id = str(uuid.uuid4())
    subagent_name = "Research Assistant"

    events_emitted = []

    # 1. Emit subagent_start event
    start_event = {
        "type": "subagent_start",
        "data": {
            "subagent_name": subagent_name,
            "subagent_run_id": subagent_run_id,
            "parent_agent_label": "Deep Research Agent",
            "parent_run_id": parent_run_id,
            "input_preview": "Research the latest trends in AI agent frameworks for 2024",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    await event_bus.publish(channel, start_event)
    events_emitted.append("subagent_start")
    await asyncio.sleep(0.1)

    # 2. Emit some thinking tokens from the subagent
    thinking_tokens = [
        "I'll research ",
        "the latest ",
        "AI agent frameworks ",
        "by searching ",
        "for recent articles ",
        "and comparing ",
        "different approaches."
    ]
    for token in thinking_tokens:
        token_event = {
            "type": "on_chat_model_stream",
            "data": {
                "token": token,
                "content": token,
                "agent_label": subagent_name,
                "node_id": f"subagent-{subagent_run_id[:8]}",
                "subagent_run_id": subagent_run_id,
                "parent_run_id": parent_run_id
            }
        }
        await event_bus.publish(channel, token_event)
        await asyncio.sleep(0.05)
    events_emitted.append("subagent_tokens")

    # 3. Emit a tool call from the subagent
    tool_start_event = {
        "type": "on_tool_start",
        "data": {
            "tool_name": "web_search",
            "input": {"query": "best AI agent frameworks 2024 comparison LangGraph AutoGen CrewAI"},
            "agent_label": subagent_name,
            "node_id": f"subagent-{subagent_run_id[:8]}",
            "run_id": str(uuid.uuid4()),
            "subagent_run_id": subagent_run_id,
            "parent_run_id": parent_run_id
        }
    }
    await event_bus.publish(channel, tool_start_event)
    events_emitted.append("subagent_tool_start")
    await asyncio.sleep(0.3)

    # 4. Emit tool result
    tool_end_event = {
        "type": "on_tool_end",
        "data": {
            "tool_name": "web_search",
            "output": "Found 5 relevant articles comparing AI agent frameworks:\n1. LangGraph - Best for complex multi-agent workflows\n2. AutoGen - Great for code generation tasks\n3. CrewAI - Role-based agent collaboration\n4. LangConfig - Visual workflow builder with LangGraph\n5. Semantic Kernel - Microsoft's orchestration framework",
            "agent_label": subagent_name,
            "node_id": f"subagent-{subagent_run_id[:8]}",
            "run_id": tool_start_event["data"]["run_id"],
            "subagent_run_id": subagent_run_id,
            "parent_run_id": parent_run_id
        }
    }
    await event_bus.publish(channel, tool_end_event)
    events_emitted.append("subagent_tool_end")
    await asyncio.sleep(0.1)

    # 5. More thinking after tool result
    analysis_tokens = [
        "\n\nBased on my research, ",
        "LangGraph and LangConfig ",
        "appear to be the most comprehensive ",
        "for building visual agent workflows. ",
        "I'll compile a detailed comparison."
    ]
    for token in analysis_tokens:
        token_event = {
            "type": "on_chat_model_stream",
            "data": {
                "token": token,
                "content": token,
                "agent_label": subagent_name,
                "node_id": f"subagent-{subagent_run_id[:8]}",
                "subagent_run_id": subagent_run_id,
                "parent_run_id": parent_run_id
            }
        }
        await event_bus.publish(channel, token_event)
        await asyncio.sleep(0.05)
    events_emitted.append("subagent_analysis_tokens")

    # 6. Emit subagent_end event
    end_event = {
        "type": "subagent_end",
        "data": {
            "subagent_name": subagent_name,
            "subagent_run_id": subagent_run_id,
            "parent_agent_label": "Deep Research Agent",
            "parent_run_id": parent_run_id,
            "output_preview": "Research complete: LangGraph is best for complex workflows, LangConfig provides visual building...",
            "full_output": """# AI Agent Frameworks Comparison 2024

## Top Frameworks:

1. **LangGraph** - Best for complex multi-agent workflows with state management
2. **LangConfig** - Visual workflow builder built on LangGraph
3. **AutoGen** - Excellent for code generation and multi-turn conversations
4. **CrewAI** - Role-based collaboration between specialized agents
5. **Semantic Kernel** - Microsoft's orchestration framework

## Recommendation:
For visual workflow building with full control over agent interactions, LangConfig with LangGraph backend provides the best developer experience.""",
            "success": True,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    await event_bus.publish(channel, end_event)
    events_emitted.append("subagent_end")

    return {
        "status": "success",
        "workflow_id": workflow_id,
        "channel": channel,
        "subagent_run_id": subagent_run_id,
        "events_emitted": events_emitted,
        "message": f"Emitted {len(events_emitted)} test subagent event groups. Check the execution panel for workflow {workflow_id}."
    }
