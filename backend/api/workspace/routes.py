# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
API endpoints for workspace file management.

Provides access to files created by agents during workflow execution.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from db.database import get_db
from services.workspace_manager import get_workspace_manager
from models.core import Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class FileInfo(BaseModel):
    """Information about a file in the workspace"""
    filename: str
    path: str
    size_bytes: int
    size_human: str
    modified_at: str
    extension: str


class WorkspaceFilesResponse(BaseModel):
    """Response with list of files in a task's workspace"""
    task_id: int
    workflow_id: int
    project_id: int | None
    files: List[FileInfo]
    total_files: int
    workspace_path: str


@router.get("/tasks/{task_id}/files", response_model=WorkspaceFilesResponse)
async def list_task_files(
    task_id: int,
    db: Session = Depends(get_db)
):
    """
    List all files created by a task.

    Files are organized in: outputs/project_X/workflow_Y/task_Z/
    """
    # Get task to find workflow_id and project_id
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    workspace_mgr = get_workspace_manager()

    try:
        files = workspace_mgr.list_task_files(
            project_id=task.project_id,
            workflow_id=task.workflow_id,
            task_id=task.id
        )

        workspace_path = str(workspace_mgr.get_task_workspace(
            project_id=task.project_id,
            workflow_id=task.workflow_id,
            task_id=task.id
        ))

        return WorkspaceFilesResponse(
            task_id=task.id,
            workflow_id=task.workflow_id,
            project_id=task.project_id,
            files=files,
            total_files=len(files),
            workspace_path=workspace_path
        )
    except Exception as e:
        logger.error(f"Error listing task files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/files/{filename}")
async def download_task_file(
    task_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Download a specific file from a task's workspace.

    Security: Path traversal attempts are blocked.
    """
    # Get task to find workflow_id and project_id
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    workspace_mgr = get_workspace_manager()

    file_path = workspace_mgr.get_file_path(
        project_id=task.project_id,
        workflow_id=task.workflow_id,
        task_id=task.id,
        filename=filename
    )

    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="File not found or invalid path"
        )

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.get("/workflows/{workflow_id}/files")
async def list_workflow_files(
    workflow_id: int,
    db: Session = Depends(get_db)
):
    """
    List all files from all tasks in a workflow.

    Returns aggregated view of all files created during workflow execution.
    """
    from models.workflow import WorkflowProfile

    workflow = db.query(WorkflowProfile).filter(WorkflowProfile.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get all tasks for this workflow
    tasks = db.query(Task).filter(Task.workflow_id == workflow_id).all()

    workspace_mgr = get_workspace_manager()
    all_files = []

    for task in tasks:
        try:
            files = workspace_mgr.list_task_files(
                project_id=task.project_id,
                workflow_id=task.workflow_id,
                task_id=task.id
            )

            # Add task_id to each file for context
            for file_info in files:
                file_info['task_id'] = task.id

            all_files.extend(files)
        except Exception as e:
            logger.warning(f"Could not list files for task {task.id}: {e}")
            continue

    # Sort by modification time
    all_files.sort(key=lambda x: x['modified_at'], reverse=True)

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow.name,
        "files": all_files,
        "total_files": len(all_files),
        "total_tasks": len(tasks)
    }
