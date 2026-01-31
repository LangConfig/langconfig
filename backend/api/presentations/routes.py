# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Presentation Generation API Endpoints

Create presentations from workflow artifacts in Google Slides, PDF, or Reveal.js formats.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import logging
import asyncio

from db.database import get_db
from sqlalchemy.orm import Session
from models.presentation_job import PresentationJob, PresentationJobStatus, PresentationFormat, PresentationTheme
from services.presentation_service import presentation_service
from services.oauth_service import google_oauth_service

router = APIRouter(prefix="/api/presentations", tags=["presentations"])
logger = logging.getLogger(__name__)


class SelectedItem(BaseModel):
    """A selected artifact or file."""
    type: str = Field(..., description="Type of item: 'artifact' or 'file'")
    id: str = Field(..., description="Unique identifier for the item")
    taskId: Optional[int] = Field(None, description="Task ID for artifacts")
    blockIndex: Optional[int] = Field(None, description="Block index for artifacts")
    block: Optional[Dict[str, Any]] = Field(None, description="Content block data for artifacts")
    filePath: Optional[str] = Field(None, description="File path for files")
    filename: Optional[str] = Field(None, description="Display name for files")


class GeneratePresentationRequest(BaseModel):
    """Request to generate a presentation."""
    title: str = Field(..., description="Presentation title", min_length=1, max_length=200)
    output_format: str = Field(..., description="Output format: google_slides, pdf, or revealjs")
    selected_items: List[SelectedItem] = Field(..., description="Selected artifacts and files", min_items=1)
    theme: str = Field("default", description="Visual theme: default, dark, or minimal")
    workflow_id: Optional[int] = Field(None, description="Workflow ID for context")
    task_id: Optional[int] = Field(None, description="Task ID for context")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Q4 Analysis Report",
                "output_format": "pdf",
                "selected_items": [
                    {
                        "type": "artifact",
                        "id": "artifact-1-0",
                        "taskId": 1,
                        "blockIndex": 0,
                        "block": {"type": "text", "text": "Key findings..."}
                    }
                ],
                "theme": "default"
            }
        }


class PresentationJobResponse(BaseModel):
    """Response containing job status."""
    id: int
    status: str
    output_format: str
    title: Optional[str]
    theme: Optional[str]
    result_url: Optional[str] = None
    result_file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


async def process_presentation_job(job_id: int):
    """Background task to process a presentation job."""
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        await presentation_service.process_job(db, job_id)
    finally:
        db.close()


@router.post("/generate", response_model=PresentationJobResponse)
async def generate_presentation(
    request: GeneratePresentationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start a presentation generation job.

    Creates an asynchronous job to generate a presentation from the selected
    artifacts and files. Poll the status endpoint for completion.

    **Output Formats:**
    - `google_slides` - Creates a Google Slides presentation (requires OAuth connection)
    - `pdf` - Generates a downloadable PowerPoint file
    - `revealjs` - Creates an HTML presentation package (ZIP)

    **Themes:**
    - `default` - Light theme with indigo accents
    - `dark` - Dark background with purple accents
    - `minimal` - Clean, minimal styling
    """
    # Validate output format
    valid_formats = [f.value for f in PresentationFormat]
    if request.output_format not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output format. Must be one of: {', '.join(valid_formats)}"
        )

    # Validate theme
    valid_themes = [t.value for t in PresentationTheme]
    if request.theme not in valid_themes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid theme. Must be one of: {', '.join(valid_themes)}"
        )

    # Check Google OAuth for Google Slides format
    if request.output_format == PresentationFormat.GOOGLE_SLIDES.value:
        status = await google_oauth_service.get_connection_status(db)
        if not status["connected"]:
            raise HTTPException(
                status_code=400,
                detail="Google account not connected. Please connect your Google account first."
            )

    try:
        # Convert Pydantic models to dicts
        selected_items = [item.model_dump() for item in request.selected_items]

        # Create job
        job = await presentation_service.create_job(
            db=db,
            title=request.title,
            output_format=request.output_format,
            selected_items=selected_items,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            theme=request.theme
        )

        # Start background processing
        background_tasks.add_task(process_presentation_job, job.id)

        logger.info(f"Started presentation job {job.id} for format {request.output_format}")

        return PresentationJobResponse(
            id=job.id,
            status=job.status,
            output_format=job.output_format,
            title=job.title,
            theme=job.theme,
            created_at=job.created_at.isoformat() if job.created_at else None
        )

    except Exception as e:
        logger.error(f"Failed to create presentation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/status", response_model=PresentationJobResponse)
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get the status of a presentation generation job.

    **Status Values:**
    - `pending` - Job is queued
    - `processing` - Job is being processed
    - `completed` - Job finished successfully
    - `failed` - Job failed (check error_message)

    When completed, the response includes:
    - `result_url` for Google Slides (direct link to presentation)
    - `result_file_path` for PDF/Reveal.js (use download endpoint)
    """
    job = await presentation_service.get_job(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Watchdog: auto-fail stale processing jobs (stuck > 5 minutes)
    STALE_JOB_THRESHOLD_SECONDS = 300
    if (
        job.status == PresentationJobStatus.PROCESSING.value
        and job.created_at
        and (datetime.now(timezone.utc) - job.created_at.replace(tzinfo=timezone.utc)).total_seconds() > STALE_JOB_THRESHOLD_SECONDS
    ):
        logger.warning(f"Job {job_id} detected as stale (processing > {STALE_JOB_THRESHOLD_SECONDS}s), marking as failed")
        job.mark_failed(f"Job timed out (stale after {STALE_JOB_THRESHOLD_SECONDS}s)")
        db.commit()

    return PresentationJobResponse(
        id=job.id,
        status=job.status,
        output_format=job.output_format,
        title=job.title,
        theme=job.theme,
        result_url=job.result_url,
        result_file_path=job.result_file_path,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None
    )


@router.get("/{job_id}/download")
async def download_presentation(job_id: int, db: Session = Depends(get_db)):
    """
    Download the generated presentation file.

    Only available for PDF and Reveal.js formats after job completion.
    Google Slides are accessed via the `result_url` in the status response.
    """
    job = await presentation_service.get_job(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != PresentationJobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    if job.output_format == PresentationFormat.GOOGLE_SLIDES.value:
        raise HTTPException(
            status_code=400,
            detail="Google Slides presentations cannot be downloaded. Use the result_url to access the presentation."
        )

    if not job.result_file_path:
        raise HTTPException(status_code=404, detail="Result file not found")

    file_path = Path(job.result_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Result file no longer exists")

    # Determine content type and filename
    if job.output_format == PresentationFormat.PDF.value:
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        filename = f"{job.title or 'presentation'}.pptx"
    else:  # revealjs
        media_type = "application/zip"
        filename = f"{job.title or 'presentation'}.zip"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/formats")
async def get_available_formats(db: Session = Depends(get_db)):
    """
    Get available presentation formats and their requirements.

    Returns information about each format including whether Google OAuth
    is connected for Google Slides export.
    """
    google_status = await google_oauth_service.get_connection_status(db)

    return {
        "formats": [
            {
                "id": "google_slides",
                "name": "Google Slides",
                "description": "Create a native Google Slides presentation",
                "file_extension": None,
                "requires_oauth": True,
                "oauth_connected": google_status["connected"],
                "oauth_email": google_status.get("email")
            },
            {
                "id": "pdf",
                "name": "PowerPoint",
                "description": "Download as PowerPoint file (.pptx)",
                "file_extension": "pptx",
                "requires_oauth": False,
                "oauth_connected": None
            },
            {
                "id": "revealjs",
                "name": "Reveal.js (HTML)",
                "description": "Web-based presentation package (ZIP)",
                "file_extension": "zip",
                "requires_oauth": False,
                "oauth_connected": None
            }
        ],
        "themes": [
            {"id": "default", "name": "Default", "description": "Light theme with indigo accents"},
            {"id": "dark", "name": "Dark", "description": "Dark background with purple accents"},
            {"id": "minimal", "name": "Minimal", "description": "Clean, minimal styling"}
        ]
    }


@router.get("/")
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List recent presentation generation jobs.

    Returns jobs in reverse chronological order (newest first).
    """
    jobs = (
        db.query(PresentationJob)
        .order_by(PresentationJob.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = db.query(PresentationJob).count()

    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.delete("/{job_id}")
async def delete_job(job_id: int, db: Session = Depends(get_db)):
    """
    Delete a presentation job and its generated file.
    """
    job = await presentation_service.get_job(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Delete the generated file if it exists
    if job.result_file_path:
        file_path = Path(job.result_file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted presentation file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete file {file_path}: {e}")

    # Delete the job record
    db.delete(job)
    db.commit()

    return {"message": f"Job {job_id} deleted successfully"}
