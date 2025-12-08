# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Simple Orchestration API for LangConfig

Executes user-created workflows from the frontend.
No complex blueprints - just run the workflow the user is looking at.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import logging
import json
from pathlib import Path
import os

from db.database import get_db
from models.core import Task, TaskStatus
from models.workflow import WorkflowProfile
from core.workflows.executor import get_executor
from services.event_bus import get_event_bus

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])
logger = logging.getLogger(__name__)


def make_json_serializable(obj):
    """
    Recursively convert non-JSON-serializable objects (datetime, LangChain messages) to JSON-safe types.
    """
    from langchain_core.messages import BaseMessage

    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, BaseMessage):
        # Convert LangChain message to dict
        # Recursively serialize additional_kwargs in case they contain non-serializable objects
        return {
            "type": obj.__class__.__name__,
            "content": obj.content,
            "additional_kwargs": make_json_serializable(obj.additional_kwargs if hasattr(obj, 'additional_kwargs') else {})
        }
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return [make_json_serializable(item) for item in obj]
    else:
        # For any other non-serializable type, try str() as fallback
        try:
            import json
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)


# Pydantic Schemas
class TaskExecutionRequest(BaseModel):
    """Request to execute a simple task"""
    project_id: int
    description: str
    assigned_model: Optional[str] = "claude-sonnet-4"
    workflow_profile_id: Optional[int] = None


class WorkflowExecuteRequest(BaseModel):
    workflow_id: int
    project_id: Optional[int] = None  # Optional - for standalone workflow execution
    input_data: Dict[str, Any]
    context_documents: Optional[list[int]] = None


class WorkflowExecuteResponse(BaseModel):
    task_id: int
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    id: int
    project_id: Optional[int]  # Optional for standalone workflows
    status: TaskStatus
    result: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# Endpoints
@router.post("/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Execute a workflow with given input data"""

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == request.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create task record (project_id is optional for standalone workflows)
    # Extract user's actual input from the run workflow modal
    user_input = request.input_data.get("query") or request.input_data.get("task") or request.input_data.get("input") or f"Workflow: {workflow.name}"

    task = Task(
        project_id=request.project_id if request.project_id else None,
        description=user_input,  # Store the FULL user prompt (truncation happens in frontend)
        status=TaskStatus.QUEUED,
        assigned_model="default",
        workflow_profile_id=request.workflow_id
        # Note: input_data and context_documents passed directly to executor
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Execute workflow in background
    background_tasks.add_task(
        execute_workflow_background,
        task_id=task.id,
        project_id=request.project_id,
        workflow_id=request.workflow_id,
        input_data=request.input_data,
        context_documents=request.context_documents
    )

    return WorkflowExecuteResponse(
        task_id=task.id,
        status=task.status,
        message=f"Workflow '{workflow.name}' queued for execution"
    )


async def execute_workflow_background(
    task_id: int,
    project_id: int,
    workflow_id: int,
    input_data: Dict[str, Any],
    context_documents: Optional[list[int]] = None
):
    """
    Background task to execute a user-created workflow.
    Updates task status in database as it progresses.
    """
    from db.database import SessionLocal
    from core.workflows.checkpointing.cancellation import get_cancellation_registry

    db = SessionLocal()
    registry = get_cancellation_registry()

    # Register task for cancellation tracking
    cancellation_event = await registry.register_task(task_id)

    try:
        # Get task and workflow
        task = db.query(Task).filter(Task.id == task_id).first()
        workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()

        if not task or not workflow:
            logger.error(f"Task {task_id} or Workflow {workflow_id} not found")
            return

        # Update task status to IN_PROGRESS
        task.status = TaskStatus.IN_PROGRESS
        task.updated_at = datetime.utcnow()
        db.commit()

        # Get simple executor
        executor = get_executor()

        # Get RAG context if documents provided
        if context_documents and project_id:
            try:
                from services.context_retrieval import context_retriever
                from models.core import ContextDocument

                logger.info(f"Retrieving RAG context for {len(context_documents)} documents")

                # Combine all selected documents into a search query
                doc_names = []
                for doc_id in context_documents:
                    doc = db.query(ContextDocument).filter(ContextDocument.id == doc_id).first()
                    if doc:
                        doc_names.append(doc.name)

                # Use user's input as the query for semantic retrieval
                user_query = input_data.get("query", input_data.get("task", "Retrieve relevant context"))

                # Retrieve context using DNA-augmented HyDE
                context_package = await context_retriever.retrieve_context(
                    project_id=project_id,
                    task_description=user_query,
                    similarity_top_k=10,
                    include_dna_in_context=True,
                    use_hyde=None  # Auto-detect based on query
                )

                # Add context to input data for agents to use
                input_data["rag_context"] = {
                    "context": context_package.get("context", ""),
                    "metadata": context_package.get("metadata", {}),
                    "selected_documents": doc_names
                }

                logger.info(f"Retrieved {context_package['metadata'].get('chunks_included', 0)} context chunks")
            except Exception as e:
                logger.error(f"Failed to retrieve RAG context: {e}")
                # Continue execution without RAG context
                input_data["rag_context"] = {"error": str(e)}

        # Execute the workflow
        logger.info(f"Executing workflow '{workflow.name}' (id={workflow_id}) for task {task_id}")
        result = await executor.execute_workflow(
            workflow=workflow,
            input_data=input_data,
            project_id=project_id,
            task_id=task_id
        )

        # Sum tokens from all execution events
        from models.execution_event import ExecutionEvent
        total_tokens = 0
        token_events = db.query(ExecutionEvent).filter(
            ExecutionEvent.task_id == task_id,
            ExecutionEvent.event_type == "LLM_END"  # Matches callback handler emission
        ).all()

        for event in token_events:
            if event.event_data and "tokens_used" in event.event_data:
                total_tokens += event.event_data.get("tokens_used", 0)

        logger.info(f"Task {task_id} used {total_tokens} total tokens")

        # Update task with formatted output, step history, AND workflow summary
        task.status = TaskStatus.COMPLETED
        task.tokens_used = total_tokens
        if result and "formatted_output" in result:
            formatted_out = result["formatted_output"]

            # Extract clean message data (content + tool_calls + metadata)
            clean_messages = []
            for msg in result.get("messages", []):
                if hasattr(msg, 'content'):
                    msg_data = {
                        "role": msg.__class__.__name__.replace("Message", "").lower(),
                        "content": msg.content
                    }
                    # Preserve tool_calls if present (for AIMessage)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        msg_data["tool_calls"] = msg.tool_calls
                    # Preserve name if present
                    if hasattr(msg, 'name') and msg.name:
                        msg_data["name"] = msg.name
                    # Preserve additional_kwargs if present (may contain tool info)
                    if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                        msg_data["additional_kwargs"] = make_json_serializable(msg.additional_kwargs)
                    clean_messages.append(msg_data)
                elif isinstance(msg, dict) and "content" in msg:
                    clean_messages.append({
                        "role": msg.get("type", "unknown"),
                        "content": msg["content"],
                        "tool_calls": msg.get("tool_calls"),
                        "name": msg.get("name")
                    })

            task.result = {
                "formatted_content": formatted_out.get("formatted_content", "No output generated"),
                "output_type": formatted_out.get("output_type", "plain_text"),
                # Save clean message history for viewing agent progression
                "agent_messages": clean_messages,
                # NEW: Save workflow execution summary (tool calls, tokens, costs by agent)
                "workflow_summary": result.get("workflow_summary", {})
            }
        else:
            task.result = {"formatted_content": "Workflow completed with no output"}
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Workflow '{workflow.name}' completed for task {task_id}")

    except Exception as e:
        logger.error(f"Workflow execution failed for task {task_id}: {e}", exc_info=True)

        # Emit error event to SSE stream so frontend doesn't hang
        # This catches errors that happen outside the executor (e.g., during initialization)
        try:
            event_bus = get_event_bus()
            channel = f"workflow:{workflow_id}"

            # Emit error event
            await event_bus.publish(channel, {
                "type": "error",
                "data": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "workflow_id": workflow_id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })

            # Emit complete event so SSE stream closes properly
            await event_bus.publish(channel, {
                "type": "complete",
                "data": {
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "workflow_id": workflow_id,
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
        except Exception as emit_error:
            logger.error(f"Failed to emit error event: {emit_error}")

        # Update task with error
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.updated_at = datetime.utcnow()
            db.commit()

    finally:
        # Unregister task from cancellation tracking
        await registry.unregister_task(task_id)
        db.close()


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Get the status and result of a task"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a running task"""
    from core.workflows.checkpointing.cancellation import get_cancellation_registry

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled")

    # Request cancellation via the global registry
    registry = get_cancellation_registry()
    cancelled = await registry.request_cancellation(task_id)

    if cancelled:
        logger.info(f"Cancellation requested for task {task_id}")
        return {"message": f"Task {task_id} cancellation requested", "status": "pending"}
    else:
        # Task not in registry - might have already completed
        logger.warning(f"Task {task_id} not found in cancellation registry")
        task.status = TaskStatus.FAILED
        task.error_message = "Task cancelled by user (not actively running)"
        task.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "Task marked as cancelled", "status": "cancelled"}


@router.get("/health")
async def health_check():
    """Health check endpoint for orchestration service"""
    return {
        "status": "healthy",
        "service": "orchestration",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/workflows/{workflow_id}/history")
async def get_workflow_history(
    workflow_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get execution history for a workflow.

    Returns list of past task executions with results, status, and timing.
    """
    # Get all tasks for this workflow, ordered by most recent first
    tasks = db.query(Task).filter(
        Task.workflow_profile_id == workflow_id
    ).order_by(
        Task.created_at.desc()
    ).limit(limit).offset(offset).all()

    # Get total count
    total_count = db.query(Task).filter(
        Task.workflow_profile_id == workflow_id
    ).count()

    # Format task history with user input visible
    task_history = []
    for task in tasks:
        task_data = {
            "id": task.id,
            "user_input": task.description,  # The prompt/directive from the user - NOW VISIBLE!
            "status": task.status.value,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message,
            "result": task.result,  # Contains formatted_output
        }

        # Calculate duration if completed
        if task.created_at and task.completed_at:
            duration = (task.completed_at - task.created_at).total_seconds()
            task_data["duration_seconds"] = duration

        task_history.append(task_data)

    return {
        "workflow_id": workflow_id,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "tasks": task_history
    }


@router.get("/workflows/{workflow_id}/stream")
async def stream_workflow_execution(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    Stream workflow execution events via Server-Sent Events (SSE).

    This endpoint ONLY listens to events published by workflow executions.
    To execute a workflow, use POST /api/orchestration/execute first.

    Frontend connects with:
        new EventSource('/api/orchestration/workflows/123/stream')

    Events emitted (published by simple_executor.execute_workflow):
        - connected: Initial connection confirmation (from this endpoint)
        - on_chain_start: Node execution started
        - on_chain_end: Node execution completed
        - on_tool_start: Tool invocation started
        - on_tool_end: Tool invocation completed
        - on_chat_model_stream: LLM token streaming
        - status: Workflow status change
        - complete: Workflow finished (includes formatted_output)
        - error: Error occurred
        - ping: Keepalive (every 30s)

    Event channel: workflow:{workflow_id}
    Events are published by execute_workflow_background() -> simple_executor.execute_workflow()
    No Redis or WebSocket required - perfect for desktop applications.
    """

    event_bus = get_event_bus()
    channel = f"workflow:{workflow_id}"
    queue = await event_bus.subscribe(channel, maxsize=200)

    async def event_generator():
        try:
            # Send initial connection confirmation
            connection_event = {
                "workflow_id": workflow_id,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "SSE connection established"
            }
            yield f"event: connected\n"
            yield f"data: {json.dumps(connection_event)}\n\n"

            logger.info(f"SSE client connected to workflow {workflow_id}")
            logger.info(f"Listening for events on channel: workflow:{workflow_id}")

            # Stream events from queue to SSE client
            # Events are published by execute_workflow_background() -> simple_executor.execute_workflow()
            while True:
                try:
                    # Wait for event with timeout (for keepalive)
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    event_type = event.get("type", "message")
                    event_data = event.get("data", {})
                    event_id = event.get("event_id", 0)

                    # Include all metadata in the data payload for frontend
                    # This includes sequence_number for gap detection and ordering
                    full_event_data = {
                        **event_data,
                        "sequence_number": event.get("sequence_number"),
                        "timestamp": event.get("timestamp"),
                        "channel": event.get("channel"),
                        "event_id": event_id
                    }

                    # Format as SSE and flush immediately
                    sse_message = f"event: {event_type}\nid: {event_id}\ndata: {json.dumps(full_event_data, default=make_json_serializable)}\n\n"
                    yield sse_message

                    # Stop streaming if workflow complete or error
                    if event_type in ["complete", "error"]:
                        logger.info(f"Workflow {workflow_id} finished with status: {event_type}")
                        break

                except asyncio.TimeoutError:
                    # Send keepalive ping every 30s to prevent connection timeout
                    yield f"event: ping\n"
                    yield f"data: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"

        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected from workflow {workflow_id}")
        except Exception as e:
            logger.error(f"SSE stream error for workflow {workflow_id}: {e}", exc_info=True)
            # Send error event
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Clean up subscription
            await event_bus.unsubscribe(channel, queue)
            logger.info(f"Cleaned up SSE subscription for workflow {workflow_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/tasks/{task_id}/files")
async def list_task_files(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    List files generated by a specific task in its workspace.

    Uses workspace manager for organized file storage.
    """
    from services.workspace_manager import get_workspace_manager

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get workflow ID from task
    workflow_id = task.workflow_profile_id
    if not workflow_id:
        raise HTTPException(status_code=400, detail="Task has no associated workflow")

    # Use workspace manager to list files
    workspace_mgr = get_workspace_manager()
    files_info = workspace_mgr.list_task_files(
        project_id=task.project_id,
        workflow_id=workflow_id,
        task_id=task_id
    )

    return {
        "task_id": task_id,
        "workflow_id": workflow_id,
        "project_id": task.project_id,
        "files": files_info,
        "total_count": len(files_info)
    }


def _format_file_size(size_bytes: int) -> str:
    """Format bytes as human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@router.get("/tasks/{task_id}/files/{filename}")
async def download_task_file(
    task_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Download a specific file generated by a task.

    Uses workspace manager for secure, organized file access.
    """
    from services.workspace_manager import get_workspace_manager

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get workflow ID from task
    workflow_id = task.workflow_profile_id
    if not workflow_id:
        raise HTTPException(status_code=400, detail="Task has no associated workflow")

    # Use workspace manager to get file (includes security checks)
    workspace_mgr = get_workspace_manager()
    file_path = workspace_mgr.get_file_path(
        project_id=task.project_id,
        workflow_id=workflow_id,
        task_id=task_id,
        filename=filename
    )

    if not file_path:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    # Determine content type
    media_type = "application/octet-stream"
    if file_path.suffix == '.md':
        media_type = "text/markdown"
    elif file_path.suffix == '.txt':
        media_type = "text/plain"
    elif file_path.suffix == '.json':
        media_type = "application/json"
    elif file_path.suffix == '.csv':
        media_type = "text/csv"
    elif file_path.suffix == '.html':
        media_type = "text/html"
    elif file_path.suffix == '.pdf':
        media_type = "application/pdf"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name
    )


@router.get("/tasks/{task_id}/events")
async def get_task_execution_events(
    task_id: int,
    limit: Optional[int] = 1000,
    offset: Optional[int] = 0,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical execution events for a task.

    This endpoint provides access to all persisted events from a workflow execution,
    enabling:
    - Historical replay of past executions
    - Debugging and troubleshooting completed workflows
    - Viewing execution details after SSE connection closed

    Query Parameters:
        - limit: Maximum number of events to return (default: 1000)
        - offset: Number of events to skip for pagination (default: 0)
        - event_type: Filter by specific event type (e.g., "on_tool_start", "on_chain_end")

    Returns:
        List of execution events ordered by timestamp (oldest first)
    """
    from models.execution_event import ExecutionEvent
    from sqlalchemy import desc

    # Verify task exists
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build query
    query = db.query(ExecutionEvent).filter(ExecutionEvent.task_id == task_id)

    # Apply event type filter if specified
    if event_type:
        query = query.filter(ExecutionEvent.event_type == event_type)

    # Order by timestamp (oldest first for replay)
    query = query.order_by(ExecutionEvent.timestamp)

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    events = query.all()

    # Format response
    return {
        "task_id": task_id,
        "total_events": len(events),
        "offset": offset,
        "limit": limit,
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "event_data": event.event_data,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "run_id": event.run_id,
                "parent_run_id": event.parent_run_id
            }
            for event in events
        ]
    }


@router.get("/workflows/{workflow_id}/events")
async def get_workflow_execution_events(
    workflow_id: int,
    limit: Optional[int] = 1000,
    offset: Optional[int] = 0,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve historical execution events for all tasks in a workflow.

    This endpoint aggregates events from all task executions for a specific workflow,
    useful for:
    - Analyzing workflow performance across multiple executions
    - Debugging recurring issues
    - Viewing execution patterns

    Query Parameters:
        - limit: Maximum number of events to return (default: 1000)
        - offset: Number of events to skip for pagination (default: 0)
        - event_type: Filter by specific event type (e.g., "on_tool_start", "on_chain_end")

    Returns:
        List of execution events ordered by timestamp (newest first)
    """
    from models.execution_event import ExecutionEvent

    # Verify workflow exists
    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Build query
    query = db.query(ExecutionEvent).filter(ExecutionEvent.workflow_id == workflow_id)

    # Apply event type filter if specified
    if event_type:
        query = query.filter(ExecutionEvent.event_type == event_type)

    # Order by timestamp (newest first)
    query = query.order_by(ExecutionEvent.timestamp.desc())

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    events = query.all()

    # Format response
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow.name,
        "total_events": len(events),
        "offset": offset,
        "limit": limit,
        "events": [
            {
                "id": event.id,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "event_data": event.event_data,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "run_id": event.run_id,
                "parent_run_id": event.parent_run_id
            }
            for event in events
        ]
    }
