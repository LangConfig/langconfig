# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API Server generator for the Executable Workflow Exporter.

Generates a FastAPI server for programmatic workflow invocation.
"""

from typing import Any, Dict, List


class ApiServerGenerator:
    """Generator for FastAPI server."""

    @staticmethod
    def generate_api_server(
        workflow_name: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]]
    ) -> str:
        """
        Generate api_server.py with FastAPI endpoints for workflow invocation.

        Args:
            workflow_name: Name of the workflow
            nodes: List of node configurations
            edges: List of edge configurations

        Returns:
            Complete api_server.py content
        """
        node_count = len(nodes)
        edge_count = len(edges)

        # Use a regular string template, then replace placeholders
        template = '''#!/usr/bin/env python3
"""
FastAPI Server for WORKFLOW_NAME

Provides REST API endpoints for programmatic workflow invocation.

Run with: python api_server.py
Or with uvicorn: uvicorn api_server:app --reload --port 8000

Endpoints:
    POST /run          - Execute workflow with query
    POST /run/stream   - Execute workflow with SSE streaming
    GET  /health       - Health check
    GET  /info         - Workflow information
"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from workflow.graph import create_workflow

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="WORKFLOW_NAME API",
    description="REST API for executing the WORKFLOW_NAME workflow",
    version="1.0.0"
)

# Enable CORS for browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request/Response Models
# ============================================================

class WorkflowInput(BaseModel):
    """Input for workflow execution."""
    query: str = Field(..., description="The query/prompt to execute")
    config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional configuration overrides"
    )


class ToolCallInfo(BaseModel):
    """Information about a tool call during execution."""
    tool_name: str
    status: str  # "running", "completed", "error"
    input_preview: Optional[str] = None
    result_preview: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentStepInfo(BaseModel):
    """Information about an agent step during execution."""
    agent_name: str
    node_id: str
    status: str  # "running", "completed", "error"
    thinking_preview: Optional[str] = None
    tool_calls: List[ToolCallInfo] = Field(default_factory=list)
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


class WorkflowOutput(BaseModel):
    """Output from workflow execution."""
    success: bool
    result: str
    status: str  # "completed", "error"
    execution_time_seconds: float
    tokens_used: int = 0
    agent_steps: List[AgentStepInfo] = Field(default_factory=list)
    error_message: Optional[str] = None


class WorkflowInfo(BaseModel):
    """Information about the workflow."""
    name: str
    node_count: int
    edge_count: int
    description: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str


# ============================================================
# Execution Logic
# ============================================================

async def execute_workflow_with_tracking(
    query: str,
    config: Dict[str, Any]
) -> WorkflowOutput:
    """Execute workflow and track agent steps."""
    start_time = time.time()
    agent_steps: List[AgentStepInfo] = []
    total_tokens = 0
    final_result = ""
    error_message = None
    success = True

    try:
        # Create workflow graph
        graph = create_workflow()

        # Initial state
        initial_state = {
            "messages": [],
            "query": query,
            "step_history": [],
        }

        # Execute with event streaming for tracking
        current_agent: Optional[AgentStepInfo] = None
        current_tool: Optional[ToolCallInfo] = None

        # Skip internal LangGraph node names
        skip_names = {"RunnableSequence", "ChannelRead", "ChannelWrite",
                      "RunnableLambda", "RunnableParallel", "StateGraph",
                      "CompiledStateGraph", ""}

        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event", "")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            # Track agent/node starts
            if event_type == "on_chain_start":
                if event_name and event_name not in skip_names:
                    if current_agent:
                        current_agent.status = "completed"
                    current_agent = AgentStepInfo(
                        agent_name=event_name,
                        node_id=event_name,
                        status="running"
                    )
                    agent_steps.append(current_agent)

            # Track tool calls
            elif event_type == "on_tool_start":
                tool_name = event_data.get("name", "tool")
                current_tool = ToolCallInfo(
                    tool_name=tool_name,
                    status="running"
                )
                if current_agent:
                    current_agent.tool_calls.append(current_tool)

            elif event_type == "on_tool_end":
                if current_tool:
                    current_tool.status = "completed"
                    output = event_data.get("output", "")
                    if isinstance(output, str) and len(output) > 200:
                        current_tool.result_preview = output[:200] + "..."
                    elif output:
                        current_tool.result_preview = str(output)[:200]

            # Track streaming tokens for thinking preview
            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and current_agent:
                    content = chunk.content
                    if isinstance(content, str):
                        if not current_agent.thinking_preview:
                            current_agent.thinking_preview = ""
                        # Only keep first 500 chars as preview
                        if len(current_agent.thinking_preview) < 500:
                            current_agent.thinking_preview += content

            # Capture final output
            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict) and "messages" in output:
                    messages = output["messages"]
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content"):
                            content = last_msg.content
                            if isinstance(content, str):
                                final_result = content
                            elif isinstance(content, list):
                                # Handle list content (e.g., Claude format)
                                text_parts = []
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif isinstance(item, str):
                                        text_parts.append(item)
                                final_result = "".join(text_parts)

        # Mark last agent as completed
        if current_agent:
            current_agent.status = "completed"

    except Exception as e:
        success = False
        error_message = str(e)
        if current_agent:
            current_agent.status = "error"

    elapsed = time.time() - start_time

    return WorkflowOutput(
        success=success,
        result=final_result,
        status="completed" if success else "error",
        execution_time_seconds=round(elapsed, 2),
        tokens_used=total_tokens,
        agent_steps=agent_steps,
        error_message=error_message
    )


async def stream_workflow_execution(query: str, config: Dict[str, Any]):
    """Generator for SSE streaming of workflow execution."""
    start_time = time.time()

    try:
        graph = create_workflow()

        initial_state = {
            "messages": [],
            "query": query,
            "step_history": [],
        }

        skip_names = {"RunnableSequence", "ChannelRead", "ChannelWrite",
                      "RunnableLambda", "RunnableParallel", "StateGraph",
                      "CompiledStateGraph", ""}

        current_node = None
        streaming_text = ""

        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event.get("event", "")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            # Node start
            if event_type == "on_chain_start" and event_name not in skip_names:
                if event_name:
                    current_node = event_name
                    yield f'event: node_start\\ndata: {{"node": "{event_name}", "timestamp": "{datetime.utcnow().isoformat()}"}}\\n\\n'

            # Tool start
            elif event_type == "on_tool_start":
                tool_name = event_data.get("name", "tool")
                yield f'event: tool_start\\ndata: {{"tool": "{tool_name}", "node": "{current_node}", "status": "running"}}\\n\\n'

            # Tool end
            elif event_type == "on_tool_end":
                tool_name = event_data.get("name", "tool")
                yield f'event: tool_end\\ndata: {{"tool": "{tool_name}", "status": "completed"}}\\n\\n'

            # Streaming tokens
            elif event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    token = ""
                    if isinstance(content, str):
                        token = content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                token += item["text"]
                            elif isinstance(item, str):
                                token += item

                    if token:
                        streaming_text += token
                        # Escape for JSON
                        escaped = token.replace("\\\\", "\\\\\\\\").replace('"', '\\\\"').replace("\\n", "\\\\n")
                        yield f'event: token\\ndata: {{"token": "{escaped}", "node": "{current_node}"}}\\n\\n'

            # Chain end - capture final result
            elif event_type == "on_chain_end":
                output = event_data.get("output", {})
                if isinstance(output, dict) and "messages" in output:
                    messages = output["messages"]
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content"):
                            content = last_msg.content
                            if isinstance(content, str):
                                streaming_text = content

        # Send completion
        elapsed = time.time() - start_time
        yield f'event: complete\\ndata: {{"status": "completed", "execution_time": {elapsed:.2f}}}\\n\\n'

    except Exception as e:
        error_msg = str(e).replace('"', '\\\\"')
        yield f'event: error\\ndata: {{"error": "{error_msg}"}}\\n\\n'


# ============================================================
# API Endpoints
# ============================================================

@app.post("/run", response_model=WorkflowOutput)
async def run_workflow(request: WorkflowInput):
    """
    Execute the workflow with the given query.

    Returns structured output with execution details.
    """
    result = await execute_workflow_with_tracking(
        query=request.query,
        config=request.config
    )

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail=result.error_message or "Workflow execution failed"
        )

    return result


@app.post("/run/stream")
async def run_workflow_stream(request: WorkflowInput):
    """
    Execute the workflow with SSE streaming.

    Returns a stream of events as the workflow executes.

    Event types:
    - node_start: Agent/node started execution
    - tool_start: Tool call started
    - tool_end: Tool call completed
    - token: Streaming token from LLM
    - complete: Workflow completed
    - error: Error occurred
    """
    return StreamingResponse(
        stream_workflow_execution(request.query, request.config),
        media_type="text/event-stream"
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/info", response_model=WorkflowInfo)
async def info():
    """Get workflow information."""
    return WorkflowInfo(
        name="WORKFLOW_NAME",
        node_count=NODE_COUNT,
        edge_count=EDGE_COUNT,
        description="Exported from LangConfig"
    )


# ============================================================
# Main Entry Point
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    print(f"Starting WORKFLOW_NAME API server...")
    print(f"API docs: http://{host}:{port}/docs")
    print(f"Health check: http://{host}:{port}/health")

    uvicorn.run(app, host=host, port=port)
'''

        # Replace placeholders with actual values
        result = template.replace("WORKFLOW_NAME", workflow_name)
        result = result.replace("NODE_COUNT", str(node_count))
        result = result.replace("EDGE_COUNT", str(edge_count))

        return result
