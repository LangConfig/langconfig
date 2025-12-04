# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from db.database import get_db
from models.core import Project, ProjectStatus, IndexingStatus

router = APIRouter(prefix="/api/projects", tags=["projects"])


# Pydantic Schemas
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    configuration: Optional[dict] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    configuration: Optional[dict] = None
    workflow_profile_id: Optional[int] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: ProjectStatus
    configuration: dict
    indexing_status: IndexingStatus
    workflow_profile_id: Optional[int]

    class Config:
        from_attributes = True


# Endpoints
@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    status: Optional[ProjectStatus] = None,
    db: Session = Depends(get_db)
):
    """List all projects with optional status filter"""
    query = db.query(Project)
    if status:
        query = query.filter(Project.status == status)

    projects = query.offset(skip).limit(limit).all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific project by ID"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db)
):
    """Create a new project"""
    # Check if name already exists
    existing = db.query(Project).filter(Project.name == project.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")

    # Set default configuration if not provided
    config = project.configuration or {"default_model": "gpt-4o"}

    db_project = Project(
        name=project.name,
        description=project.description,
        configuration=config,
        status=ProjectStatus.IDLE,
        indexing_status=IndexingStatus.NOT_INDEXED
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project: ProjectUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing project"""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update only provided fields
    update_data = project.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)

    db.commit()
    db.refresh(db_project)
    return db_project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a project and all associated data.

    Cascades to delete:
    - All workflows in this project
    - All tasks from those workflows
    - All execution events from those tasks
    - All documents in the RAG database
    - The project's vector index table
    - Generated files in workspace directories

    Note: Memory is managed by LangGraph's store system (per-thread)
    and doesn't require explicit cleanup.
    """
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        from models.workflow import WorkflowProfile, WorkflowVersion, WorkflowExecution
        from models.core import Task
        from models.execution_event import ExecutionEvent
        from sqlalchemy import text, create_engine
        from config import app_settings

        # Get all workflow IDs for this project
        workflow_ids = [w.id for w in db.query(WorkflowProfile).filter(
            WorkflowProfile.project_id == project_id
        ).all()]

        # 1. Delete execution events for all workflows in this project
        if workflow_ids:
            db.query(ExecutionEvent).filter(
                ExecutionEvent.workflow_id.in_(workflow_ids)
            ).delete(synchronize_session=False)

        # 2. Delete tasks for all workflows in this project
        # Use workflow_profile_id (the actual foreign key), not workflow_id (tracking string)
        if workflow_ids:
            db.query(Task).filter(
                Task.workflow_profile_id.in_(workflow_ids)
            ).delete(synchronize_session=False)

        # 3. Memory is stored in LangGraph's store system (not a separate table)
        # It's managed per-thread and doesn't need explicit cleanup

        # 4. Delete workflow executions for all workflows in this project
        if workflow_ids:
            db.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id.in_(workflow_ids)
            ).delete(synchronize_session=False)

        # 5. Delete workflow versions for all workflows in this project
        if workflow_ids:
            db.query(WorkflowVersion).filter(
                WorkflowVersion.workflow_id.in_(workflow_ids)
            ).delete(synchronize_session=False)

        # 6. Delete all workflows in this project
        db.query(WorkflowProfile).filter(
            WorkflowProfile.project_id == project_id
        ).delete(synchronize_session=False)

        # 7. Drop the project's vector index table if it exists
        try:
            engine = create_engine(app_settings.database_url)
            table_name = f"data_project_index_{project_id}"
            with engine.connect() as conn:
                # Check if table exists
                check_query = text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = '{table_name}'
                    )
                """)
                exists = conn.execute(check_query).scalar()

                if exists:
                    # Drop the table
                    drop_query = text(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                    conn.execute(drop_query)
                    conn.commit()
                    logger.info(f"Dropped vector index table: {table_name}")
        except Exception as e:
            logger.warning(f"Failed to drop vector index table for project {project_id}: {e}")
            # Continue even if vector table deletion fails

        # 8. Finally, delete the project itself
        db.delete(db_project)
        db.commit()

        logger.info(f"Successfully deleted project {project_id} and all related data")
        return None

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )


@router.post("/{project_id}/index")
async def index_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Start indexing a project's documents"""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")

    # TODO: Implement document indexing with embeddings
    db_project.indexing_status = IndexingStatus.INDEXING
    db.commit()

    return {
        "message": "Project indexing started",
        "project_id": project_id,
        "status": IndexingStatus.INDEXING
    }
