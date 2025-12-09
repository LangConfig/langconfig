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


class FileInfoWithContext(FileInfo):
    """File info with project/workflow/task context"""
    project_id: int | None = None
    workflow_id: int | None = None
    task_id: int | None = None
    full_path: str | None = None


class RenameFileRequest(BaseModel):
    """Request to rename a file"""
    new_name: str


class FileContentResponse(BaseModel):
    """Response with file content for preview"""
    filename: str
    content: str | None
    mime_type: str
    is_binary: bool
    truncated: bool
    size_bytes: int


class AllFilesResponse(BaseModel):
    """Response with list of all files across workspace"""
    files: List[FileInfoWithContext]
    total_files: int


class BulkDeleteRequest(BaseModel):
    """Request to delete multiple files"""
    files: List[dict]  # [{ "task_id": 1, "filename": "x.md" }]


class BulkDeleteResponse(BaseModel):
    """Response from bulk delete operation"""
    deleted: int
    failed: int
    errors: List[str]


class WorkspaceFilesResponse(BaseModel):
    """Response with list of files in a task's workspace"""
    task_id: int
    workflow_id: int | None  # Can be None for tasks created outside workflow context
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


# =============================================================================
# File Content & Preview
# =============================================================================

@router.get("/tasks/{task_id}/files/{filename}/content", response_model=FileContentResponse)
async def get_file_content(
    task_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Get file content for preview.

    Returns text content for text files, or binary indicator for non-text files.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    workspace_mgr = get_workspace_manager()

    content_data = workspace_mgr.get_file_content(
        project_id=task.project_id,
        workflow_id=task.workflow_id,
        task_id=task.id,
        filename=filename
    )

    if not content_data:
        raise HTTPException(status_code=404, detail="File not found")

    return FileContentResponse(
        filename=filename,
        content=content_data.get("content"),
        mime_type=content_data.get("mime_type", "text/plain"),
        is_binary=content_data.get("is_binary", False),
        truncated=content_data.get("truncated", False),
        size_bytes=content_data.get("size_bytes", 0)
    )


# =============================================================================
# Rename & Delete
# =============================================================================

@router.put("/tasks/{task_id}/files/{filename}")
async def rename_file(
    task_id: int,
    filename: str,
    request: RenameFileRequest,
    db: Session = Depends(get_db)
):
    """
    Rename a file in task workspace.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    workspace_mgr = get_workspace_manager()

    success = workspace_mgr.rename_file(
        project_id=task.project_id,
        workflow_id=task.workflow_id,
        task_id=task.id,
        old_name=filename,
        new_name=request.new_name
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not rename file. It may not exist, or target name already exists."
        )

    logger.info(f"Renamed file in task {task_id}: {filename} -> {request.new_name}")

    return {
        "status": "success",
        "old_name": filename,
        "new_name": request.new_name
    }


@router.delete("/tasks/{task_id}/files/{filename}")
async def delete_file(
    task_id: int,
    filename: str,
    db: Session = Depends(get_db)
):
    """
    Delete a file from task workspace.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    workspace_mgr = get_workspace_manager()

    success = workspace_mgr.delete_file(
        project_id=task.project_id,
        workflow_id=task.workflow_id,
        task_id=task.id,
        filename=filename
    )

    if not success:
        raise HTTPException(status_code=404, detail="File not found or could not be deleted")

    logger.info(f"Deleted file from task {task_id}: {filename}")

    return {"status": "success", "filename": filename}


# =============================================================================
# All Files (for Library)
# =============================================================================

@router.get("/files", response_model=AllFilesResponse)
async def list_all_files(
    project_id: int | None = None,
    workflow_id: int | None = None,
    search: str | None = None,
    file_type: str | None = None,
    db: Session = Depends(get_db)
):
    """
    List all files across workspace.

    Use for Library Files browser. Supports filtering by project, workflow,
    search term, and file type.
    """
    workspace_mgr = get_workspace_manager()

    files = workspace_mgr.list_all_files(
        project_id=project_id,
        workflow_id=workflow_id,
        search=search,
        file_type=file_type
    )

    return AllFilesResponse(
        files=files,
        total_files=len(files)
    )


@router.post("/files/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_files(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db)
):
    """
    Delete multiple files at once.

    Request body: { "files": [{ "task_id": 1, "filename": "x.md" }, ...] }
    """
    workspace_mgr = get_workspace_manager()
    deleted = 0
    failed = 0
    errors = []

    for file_info in request.files:
        task_id = file_info.get("task_id")
        filename = file_info.get("filename")

        if not task_id or not filename:
            failed += 1
            errors.append(f"Invalid file info: {file_info}")
            continue

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            failed += 1
            errors.append(f"Task {task_id} not found")
            continue

        success = workspace_mgr.delete_file(
            project_id=task.project_id,
            workflow_id=task.workflow_id,
            task_id=task.id,
            filename=filename
        )

        if success:
            deleted += 1
        else:
            failed += 1
            errors.append(f"Could not delete {filename} from task {task_id}")

    logger.info(f"Bulk delete: {deleted} deleted, {failed} failed")

    return BulkDeleteResponse(
        deleted=deleted,
        failed=failed,
        errors=errors
    )
