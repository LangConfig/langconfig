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


class FileMetadataResponse(BaseModel):
    """Full file metadata including agent context"""
    id: int
    filename: str
    file_path: str
    # Agent context
    agent_label: str | None = None
    agent_type: str | None = None
    node_id: str | None = None
    # Workflow context
    workflow_id: int | None = None
    workflow_name: str | None = None
    task_id: int | None = None
    project_id: int | None = None
    execution_id: str | None = None
    # Content metadata
    original_query: str | None = None
    description: str | None = None
    content_type: str | None = None
    tags: List[str] = []
    # File info
    size_bytes: int | None = None
    mime_type: str | None = None
    extension: str | None = None
    # Timestamps
    created_at: str | None = None
    updated_at: str | None = None

    class Config:
        from_attributes = True


class FileMetadataUpdateRequest(BaseModel):
    """Request to update file metadata"""
    description: str | None = None
    content_type: str | None = None
    tags: List[str] | None = None


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
    For default files, task_id should be null/None.
    """
    workspace_mgr = get_workspace_manager()
    deleted = 0
    failed = 0
    errors = []

    for file_info in request.files:
        task_id = file_info.get("task_id")
        filename = file_info.get("filename")

        if not filename:
            failed += 1
            errors.append(f"Invalid file info: {file_info}")
            continue

        # Handle default files (no task_id)
        if task_id is None:
            success = workspace_mgr.delete_default_file(filename)
            if success:
                deleted += 1
            else:
                failed += 1
                errors.append(f"Could not delete default file {filename}")
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


# =============================================================================
# Knowledge Base Integration
# =============================================================================

class IndexFileRequest(BaseModel):
    """Request to index a file into the knowledge base"""
    project_id: int


class IndexFileResponse(BaseModel):
    """Response from indexing a file"""
    status: str
    message: str
    chunks_created: int | None = None


@router.post("/tasks/{task_id}/files/{filename}/index", response_model=IndexFileResponse)
async def index_file_to_knowledge_base(
    task_id: int,
    filename: str,
    request: IndexFileRequest,
    db: Session = Depends(get_db)
):
    """
    Index a workspace file into the project's knowledge base (vector store).

    This makes the file's content searchable via RAG queries.
    Also creates a ContextDocument record so the file appears in the Knowledge Base UI.
    """
    from pathlib import Path
    from models.core import ContextDocument, IndexingStatus, DocumentType
    import os
    import mimetypes

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
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return IndexFileResponse(
                status="error",
                message="File is empty - nothing to index"
            )

        # Index directly using the text content
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from llama_index.core.schema import TextNode
        from llama_index.core import Settings
        from datetime import datetime, timezone

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunks = text_splitter.split_text(content)

        if not chunks:
            return IndexFileResponse(
                status="error",
                message="Could not split file into chunks"
            )

        # Get vector store for the project
        from services.llama_config import get_vector_store
        vector_store = get_vector_store(request.project_id)

        # Create embeddings and store
        embed_model = Settings.embed_model
        nodes = []

        for i, chunk_text in enumerate(chunks):
            node_id = f"workspace_file_{task_id}_{filename}_{i}"
            metadata = {
                "source": "workspace_file",
                "task_id": task_id,
                "filename": filename,
                "project_id": request.project_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }

            text_node = TextNode(
                id_=node_id,
                text=chunk_text,
                metadata=metadata
            )

            # Generate embedding synchronously
            embedding = embed_model.get_text_embedding(chunk_text)
            text_node.embedding = embedding

            nodes.append(text_node)

        # Store in vector database
        vector_store.add(nodes)

        # Determine document type from extension
        ext = os.path.splitext(filename)[1].lower()
        doc_type_map = {
            '.md': DocumentType.MARKDOWN,
            '.txt': DocumentType.TEXT,
            '.pdf': DocumentType.PDF,
            '.py': DocumentType.CODE,
            '.js': DocumentType.CODE,
            '.ts': DocumentType.CODE,
            '.json': DocumentType.JSON,
            '.html': DocumentType.HTML,
            '.xml': DocumentType.XML,
            '.csv': DocumentType.CSV,
            '.yaml': DocumentType.YAML,
            '.yml': DocumentType.YAML,
        }
        doc_type = doc_type_map.get(ext, DocumentType.TEXT)

        # Get mime type
        mime_type, _ = mimetypes.guess_type(filename)

        # Create a ContextDocument record so it shows in the Knowledge Base UI
        context_doc = ContextDocument(
            filename=filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=os.path.getsize(file_path),
            mime_type=mime_type or 'text/plain',
            document_type=doc_type,
            indexing_status=IndexingStatus.READY,
            indexed_at=datetime.now(timezone.utc),
            indexed_chunks_count=len(nodes),
            description=f"Workspace file from task {task_id}",
            content_preview=content[:500] if len(content) > 500 else content,
            project_id=request.project_id,
        )
        db.add(context_doc)
        db.commit()

        logger.info(f"Indexed {len(nodes)} chunks from {filename} to project {request.project_id} knowledge base")

        return IndexFileResponse(
            status="success",
            message=f"Successfully indexed {len(nodes)} chunks into the knowledge base",
            chunks_created=len(nodes)
        )

    except Exception as e:
        logger.error(f"Error indexing file to knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/default/files/{filename}/index", response_model=IndexFileResponse)
async def index_default_file_to_knowledge_base(
    filename: str,
    request: IndexFileRequest,
    db: Session = Depends(get_db)
):
    """
    Index a default workspace file into the project's knowledge base.

    Also creates a ContextDocument record so the file appears in the Knowledge Base UI.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from llama_index.core.schema import TextNode
    from llama_index.core import Settings
    from datetime import datetime, timezone
    from models.core import ContextDocument, IndexingStatus, DocumentType
    import os
    import mimetypes

    workspace_mgr = get_workspace_manager()
    file_path = workspace_mgr.get_default_file_path(filename)

    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.strip():
            return IndexFileResponse(
                status="error",
                message="File is empty - nothing to index"
            )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1024,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunks = text_splitter.split_text(content)

        if not chunks:
            return IndexFileResponse(
                status="error",
                message="Could not split file into chunks"
            )

        # Get vector store for the project
        from services.llama_config import get_vector_store
        vector_store = get_vector_store(request.project_id)

        # Create embeddings and store
        embed_model = Settings.embed_model
        nodes = []

        for i, chunk_text in enumerate(chunks):
            node_id = f"workspace_file_default_{filename}_{i}"
            metadata = {
                "source": "workspace_file",
                "filename": filename,
                "project_id": request.project_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }

            text_node = TextNode(
                id_=node_id,
                text=chunk_text,
                metadata=metadata
            )

            embedding = embed_model.get_text_embedding(chunk_text)
            text_node.embedding = embedding

            nodes.append(text_node)

        vector_store.add(nodes)

        # Determine document type from extension
        ext = os.path.splitext(filename)[1].lower()
        doc_type_map = {
            '.md': DocumentType.MARKDOWN,
            '.txt': DocumentType.TEXT,
            '.pdf': DocumentType.PDF,
            '.py': DocumentType.CODE,
            '.js': DocumentType.CODE,
            '.ts': DocumentType.CODE,
            '.json': DocumentType.JSON,
            '.html': DocumentType.HTML,
            '.xml': DocumentType.XML,
            '.csv': DocumentType.CSV,
            '.yaml': DocumentType.YAML,
            '.yml': DocumentType.YAML,
        }
        doc_type = doc_type_map.get(ext, DocumentType.TEXT)

        # Get mime type
        mime_type, _ = mimetypes.guess_type(filename)

        # Create a ContextDocument record so it shows in the Knowledge Base UI
        context_doc = ContextDocument(
            filename=filename,
            original_filename=filename,
            file_path=str(file_path),
            file_size=os.path.getsize(file_path),
            mime_type=mime_type or 'text/plain',
            document_type=doc_type,
            indexing_status=IndexingStatus.READY,
            indexed_at=datetime.now(timezone.utc),
            indexed_chunks_count=len(nodes),
            description="Workspace file from default folder",
            content_preview=content[:500] if len(content) > 500 else content,
            project_id=request.project_id,
        )
        db.add(context_doc)
        db.commit()

        logger.info(f"Indexed {len(nodes)} chunks from default/{filename} to project {request.project_id} knowledge base")

        return IndexFileResponse(
            status="success",
            message=f"Successfully indexed {len(nodes)} chunks into the knowledge base",
            chunks_created=len(nodes)
        )

    except Exception as e:
        logger.error(f"Error indexing default file to knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# File Metadata (for tracking agent context, tags, etc.)
# =============================================================================

@router.get("/files/metadata/{file_id}", response_model=FileMetadataResponse)
async def get_file_metadata(
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    Get full metadata for a specific file.

    Returns agent context, workflow info, tags, and other metadata.
    """
    from models.workspace_file import WorkspaceFile

    file_record = db.query(WorkspaceFile).filter(WorkspaceFile.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File metadata not found")

    return FileMetadataResponse(
        id=file_record.id,
        filename=file_record.filename,
        file_path=file_record.file_path,
        agent_label=file_record.agent_label,
        agent_type=file_record.agent_type,
        node_id=file_record.node_id,
        workflow_id=file_record.workflow_id,
        workflow_name=file_record.workflow_name,
        task_id=file_record.task_id,
        project_id=file_record.project_id,
        execution_id=file_record.execution_id,
        original_query=file_record.original_query,
        description=file_record.description,
        content_type=file_record.content_type,
        tags=file_record.tags or [],
        size_bytes=file_record.size_bytes,
        mime_type=file_record.mime_type,
        extension=file_record.extension,
        created_at=file_record.created_at.isoformat() if file_record.created_at else None,
        updated_at=file_record.updated_at.isoformat() if file_record.updated_at else None,
    )


@router.patch("/files/metadata/{file_id}", response_model=FileMetadataResponse)
async def update_file_metadata(
    file_id: int,
    request: FileMetadataUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update file metadata (tags, description, content_type).

    Only user-editable fields can be updated. Agent context is read-only.
    """
    from models.workspace_file import WorkspaceFile

    file_record = db.query(WorkspaceFile).filter(WorkspaceFile.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File metadata not found")

    # Update editable fields
    if request.description is not None:
        file_record.description = request.description
    if request.content_type is not None:
        file_record.content_type = request.content_type
    if request.tags is not None:
        file_record.tags = request.tags

    db.commit()
    db.refresh(file_record)

    logger.info(f"Updated metadata for file {file_id}: {file_record.filename}")

    return FileMetadataResponse(
        id=file_record.id,
        filename=file_record.filename,
        file_path=file_record.file_path,
        agent_label=file_record.agent_label,
        agent_type=file_record.agent_type,
        node_id=file_record.node_id,
        workflow_id=file_record.workflow_id,
        workflow_name=file_record.workflow_name,
        task_id=file_record.task_id,
        project_id=file_record.project_id,
        execution_id=file_record.execution_id,
        original_query=file_record.original_query,
        description=file_record.description,
        content_type=file_record.content_type,
        tags=file_record.tags or [],
        size_bytes=file_record.size_bytes,
        mime_type=file_record.mime_type,
        extension=file_record.extension,
        created_at=file_record.created_at.isoformat() if file_record.created_at else None,
        updated_at=file_record.updated_at.isoformat() if file_record.updated_at else None,
    )


@router.get("/files/by-path")
async def get_file_metadata_by_path(
    file_path: str,
    db: Session = Depends(get_db)
):
    """
    Get file metadata by file path.

    Useful when you have the file path from the filesystem listing
    but need to look up the database metadata.
    """
    from models.workspace_file import WorkspaceFile

    file_record = db.query(WorkspaceFile).filter(WorkspaceFile.file_path == file_path).first()
    if not file_record:
        return {"metadata": None, "has_metadata": False}

    return {
        "metadata": FileMetadataResponse(
            id=file_record.id,
            filename=file_record.filename,
            file_path=file_record.file_path,
            agent_label=file_record.agent_label,
            agent_type=file_record.agent_type,
            node_id=file_record.node_id,
            workflow_id=file_record.workflow_id,
            workflow_name=file_record.workflow_name,
            task_id=file_record.task_id,
            project_id=file_record.project_id,
            execution_id=file_record.execution_id,
            original_query=file_record.original_query,
            description=file_record.description,
            content_type=file_record.content_type,
            tags=file_record.tags or [],
            size_bytes=file_record.size_bytes,
            mime_type=file_record.mime_type,
            extension=file_record.extension,
            created_at=file_record.created_at.isoformat() if file_record.created_at else None,
            updated_at=file_record.updated_at.isoformat() if file_record.updated_at else None,
        ),
        "has_metadata": True
    }


@router.get("/files/with-metadata")
async def list_files_with_metadata(
    project_id: int | None = None,
    workflow_id: int | None = None,
    agent_label: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db)
):
    """
    List all files with their metadata from the database.

    Supports filtering by project, workflow, agent, or search term.
    This returns richer metadata than the filesystem-based listing.
    """
    from models.workspace_file import WorkspaceFile

    query = db.query(WorkspaceFile)

    if project_id is not None:
        query = query.filter(WorkspaceFile.project_id == project_id)
    if workflow_id is not None:
        query = query.filter(WorkspaceFile.workflow_id == workflow_id)
    if agent_label is not None:
        query = query.filter(WorkspaceFile.agent_label.ilike(f"%{agent_label}%"))
    if search is not None:
        query = query.filter(
            WorkspaceFile.filename.ilike(f"%{search}%") |
            WorkspaceFile.description.ilike(f"%{search}%")
        )

    # Order by most recent first
    query = query.order_by(WorkspaceFile.created_at.desc())

    files = query.all()

    return {
        "files": [
            FileMetadataResponse(
                id=f.id,
                filename=f.filename,
                file_path=f.file_path,
                agent_label=f.agent_label,
                agent_type=f.agent_type,
                node_id=f.node_id,
                workflow_id=f.workflow_id,
                workflow_name=f.workflow_name,
                task_id=f.task_id,
                project_id=f.project_id,
                execution_id=f.execution_id,
                original_query=f.original_query,
                description=f.description,
                content_type=f.content_type,
                tags=f.tags or [],
                size_bytes=f.size_bytes,
                mime_type=f.mime_type,
                extension=f.extension,
                created_at=f.created_at.isoformat() if f.created_at else None,
                updated_at=f.updated_at.isoformat() if f.updated_at else None,
            )
            for f in files
        ],
        "total_files": len(files)
    }


# =============================================================================
# Default Folder Files (standalone/chat execution outputs)
# =============================================================================

@router.get("/default/files")
async def list_default_files():
    """
    List all files in the default workspace.

    These are files created during standalone/chat execution (no workflow context).
    """
    workspace_mgr = get_workspace_manager()
    files = workspace_mgr.list_default_files()

    return {
        "files": files,
        "total_files": len(files)
    }


@router.get("/default/files/{filename}")
async def download_default_file(filename: str):
    """Download a file from the default workspace."""
    from fastapi.responses import FileResponse

    workspace_mgr = get_workspace_manager()
    file_path = workspace_mgr.get_default_file_path(filename)

    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream"
    )


@router.get("/default/files/{filename}/content", response_model=FileContentResponse)
async def get_default_file_content(filename: str):
    """Get content of a file in the default workspace for preview."""
    workspace_mgr = get_workspace_manager()

    content_data = workspace_mgr.get_default_file_content(filename)

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


@router.put("/default/files/{filename}")
async def rename_default_file(filename: str, request: RenameFileRequest):
    """Rename a file in the default workspace."""
    workspace_mgr = get_workspace_manager()

    success = workspace_mgr.rename_default_file(filename, request.new_name)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not rename file. It may not exist, or target name already exists."
        )

    return {
        "status": "success",
        "old_name": filename,
        "new_name": request.new_name
    }


@router.delete("/default/files/{filename}")
async def delete_default_file(filename: str):
    """Delete a file from the default workspace."""
    workspace_mgr = get_workspace_manager()

    success = workspace_mgr.delete_default_file(filename)

    if not success:
        raise HTTPException(status_code=404, detail="File not found or could not be deleted")

    return {"status": "success", "filename": filename}
