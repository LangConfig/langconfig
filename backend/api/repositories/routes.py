"""
Git Repository API — Read-only repository browser.

Repos are cloned locally so their files can be browsed in the UI and
selectively ingested into the project knowledge base (ContextDocument +
RAG indexing pipeline).
"""

import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.task_queue import task_queue
from db.database import get_db
from models.core import ContextDocument, DocumentType, IndexingStatus
from models.git_repository import GitRepository, RepoSyncStatus
from services.git_repository_service import (
    EXCLUDED_DIRS,
    MAX_INDEXABLE_FILE_SIZE,
    extract_repo_name,
    validate_clone_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repositories", tags=["repositories"])

# Cap on files per ingest request — keeps the synchronous request bounded.
# Larger folders should be ingested as smaller subdirectories.
MAX_INGEST_FILES = 500


# Maps file extensions to DocumentType for knowledge-base ingestion.
# Mirrors the doc_type_map used by api/knowledge/rag.py upload_document.
DOC_TYPE_MAP = {
    "txt": DocumentType.TEXT,
    "md": DocumentType.MARKDOWN,
    "pdf": DocumentType.PDF,
    "json": DocumentType.JSON,
    "py": DocumentType.CODE,
    "js": DocumentType.CODE,
    "ts": DocumentType.CODE,
    "tsx": DocumentType.CODE,
    "jsx": DocumentType.CODE,
    "java": DocumentType.CODE,
    "c": DocumentType.CODE,
    "cpp": DocumentType.CODE,
    "h": DocumentType.CODE,
    "hpp": DocumentType.CODE,
    "cs": DocumentType.CODE,
    "rb": DocumentType.CODE,
    "go": DocumentType.CODE,
    "rs": DocumentType.CODE,
    "php": DocumentType.CODE,
    "swift": DocumentType.CODE,
    "kt": DocumentType.CODE,
    "scala": DocumentType.CODE,
    "r": DocumentType.CODE,
    "sql": DocumentType.CODE,
    "sh": DocumentType.CODE,
    "bash": DocumentType.CODE,
    "toml": DocumentType.CODE,
    "ini": DocumentType.CODE,
    "cfg": DocumentType.CODE,
    "conf": DocumentType.CODE,
    "html": DocumentType.HTML,
    "htm": DocumentType.HTML,
    "xml": DocumentType.XML,
    "csv": DocumentType.CSV,
    "yaml": DocumentType.YAML,
    "yml": DocumentType.YAML,
}


# =============================================================================
# Pydantic Schemas
# =============================================================================

class RepoCreate(BaseModel):
    project_id: int
    clone_url: str
    branch: str = "main"


class RepoResponse(BaseModel):
    id: int
    project_id: int
    clone_url: str
    repo_name: str
    branch: str
    sync_status: str
    local_path: Optional[str] = None
    last_commit_hash: Optional[str] = None
    last_synced_at: Optional[str] = None
    last_error: Optional[str] = None
    indexed_files_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class IngestPathRequest(BaseModel):
    path: str  # relative to repo root; file or directory


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/", status_code=201)
async def create_repository(
    body: RepoCreate,
    db: Session = Depends(get_db),
):
    """Add a git repository and start cloning it in the background."""
    # Validate URL scheme
    try:
        validate_clone_url(body.clone_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for duplicates
    existing = db.query(GitRepository).filter(
        GitRepository.project_id == body.project_id,
        GitRepository.clone_url == body.clone_url,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Repository already linked to this project (id={existing.id})",
        )

    repo_name = extract_repo_name(body.clone_url)

    repo = GitRepository(
        project_id=body.project_id,
        clone_url=body.clone_url,
        repo_name=repo_name,
        branch=body.branch,
        sync_status=RepoSyncStatus.PENDING,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Enqueue background clone task
    task_id = await task_queue.enqueue(
        "clone_git_repo",
        {"repo_id": repo.id},
    )

    logger.info(f"Created repo {repo_name} (id={repo.id}), clone task={task_id}")
    return {**repo.to_dict(), "task_id": task_id}


@router.get("/")
async def list_repositories(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """List repositories, optionally filtered by project."""
    query = db.query(GitRepository)
    if project_id is not None:
        query = query.filter(GitRepository.project_id == project_id)

    repos = query.order_by(GitRepository.created_at.desc()).all()
    return [repo.to_dict() for repo in repos]


@router.get("/{repo_id}")
async def get_repository(
    repo_id: int,
    db: Session = Depends(get_db),
):
    """Get a single repository by ID."""
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo.to_dict()


@router.post("/{repo_id}/sync")
async def sync_repository(
    repo_id: int,
    db: Session = Depends(get_db),
):
    """Pull latest changes for the repository."""
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.sync_status in (
        RepoSyncStatus.PENDING,
        RepoSyncStatus.CLONING,
        RepoSyncStatus.SYNCING,
        RepoSyncStatus.INDEXING,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Repository is currently {repo.sync_status.value}",
        )

    # Mark the repo as pending BEFORE enqueueing: the in-progress guard above
    # then covers the enqueue->dequeue window (no duplicate sync tasks), and
    # the frontend's polling reliably sees an in-progress state immediately.
    repo.sync_status = RepoSyncStatus.PENDING
    repo.last_error = None
    db.commit()

    task_id = await task_queue.enqueue(
        "sync_git_repo",
        {"repo_id": repo.id},
    )

    logger.info(f"Enqueued sync for repo {repo.repo_name} (task={task_id})")
    return {"message": "Sync started", "task_id": task_id}


@router.delete("/{repo_id}", status_code=204)
async def delete_repository(repo_id: int, db: Session = Depends(get_db)):
    """Delete a repository (removes from disk and database)."""
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from services import git_repository_service as git_svc

    deleted = await git_svc.delete_repo(repo_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete repository")

    return None


@router.get("/{repo_id}/files")
async def list_repository_files(
    repo_id: int,
    db: Session = Depends(get_db),
):
    """List browsable files in the repository."""
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from services.git_repository_service import list_repo_files

    # The full-repo walk is blocking — run it off the event loop
    files = await asyncio.to_thread(list_repo_files, repo_id)
    return {"files": files, "total": len(files)}


@router.get("/{repo_id}/file")
async def get_repository_file(
    repo_id: int,
    path: str,
    db: Session = Depends(get_db),
):
    """Return the content of a single file from a cloned repo.

    Path-traversal safe: the resolved target must live under the repo root.
    Returns a structured payload for binary / too-large files so the client
    can render a placeholder instead of raising.
    """
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not repo.local_path:
        raise HTTPException(status_code=404, detail="Repository is not cloned yet")

    repo_root = Path(repo.local_path).resolve()
    if not repo_root.exists():
        raise HTTPException(status_code=404, detail="Repository directory missing")

    try:
        target = (repo_root / path).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if repo_root != target and repo_root not in target.parents:
        raise HTTPException(status_code=400, detail="Path escapes repository root")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    rel_parts = target.relative_to(repo_root).parts
    if any(part in EXCLUDED_DIRS for part in rel_parts):
        raise HTTPException(status_code=400, detail="File lives in an excluded directory")

    size = target.stat().st_size
    relative_path = str(target.relative_to(repo_root)).replace("\\", "/")

    if size > MAX_INDEXABLE_FILE_SIZE:
        return {"path": relative_path, "size": size, "too_large": True}

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"path": relative_path, "size": size, "binary": True}

    return {"path": relative_path, "size": size, "content": content}


# -----------------------------------------------------------------------------
# Knowledge-base ingestion
# -----------------------------------------------------------------------------

@router.post("/{repo_id}/ingest")
async def ingest_repository_path(
    repo_id: int,
    body: IngestPathRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Ingest a single file or a subdirectory of a cloned repo into the
    project knowledge base.

    Each file becomes a ContextDocument (saved via file_storage) and is
    queued for RAG indexing through the same background pipeline as
    manually uploaded documents. Applies the same extension / size /
    excluded-dir filters used by the repository browser.
    """
    repo = db.query(GitRepository).filter(GitRepository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not repo.local_path:
        raise HTTPException(status_code=404, detail="Repository is not cloned yet")

    repo_root = Path(repo.local_path).resolve()
    if not repo_root.exists():
        raise HTTPException(status_code=404, detail="Repository directory missing")

    try:
        target = (repo_root / body.path).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path")

    if repo_root != target and repo_root not in target.parents:
        raise HTTPException(status_code=400, detail="Path escapes repository root")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found in repo")

    # Import lazily so these imports only happen when someone actually ingests
    from api.knowledge.rag import index_document_background
    from services.file_storage import file_storage
    from services.git_repository_service import _should_index_file

    candidates: list = []
    if target.is_file():
        rel_parts = target.relative_to(repo_root).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            raise HTTPException(status_code=400, detail="File lives in an excluded directory")
        if not _should_index_file(target):
            raise HTTPException(status_code=400, detail="File type is not ingestable")
        candidates.append(target)
    else:
        def _collect_candidates() -> list:
            found = []
            for fp in target.rglob("*"):
                if not fp.is_file():
                    continue
                rel_parts = fp.relative_to(repo_root).parts
                if any(part in EXCLUDED_DIRS for part in rel_parts):
                    continue
                if not _should_index_file(fp):
                    continue
                found.append(fp)
            return found

        # The directory walk is blocking disk I/O — run it off the event loop
        candidates = await asyncio.to_thread(_collect_candidates)

    if not candidates:
        return {"ingested": 0, "skipped": 0, "errors": [], "message": "No ingestable files found"}

    if len(candidates) > MAX_INGEST_FILES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many files to ingest at once ({len(candidates)} found, "
                f"limit is {MAX_INGEST_FILES}). Ingest smaller subdirectories instead."
            ),
        )

    ingested = 0
    skipped = 0
    errors: list = []
    created_doc_ids: list = []

    def _read_candidate(fp: Path) -> Optional[str]:
        """Blocking stat+read for a candidate; None means skip."""
        if fp.stat().st_size > MAX_INDEXABLE_FILE_SIZE:
            return None
        try:
            return fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None

    for fp in candidates:
        relative_path = str(fp.relative_to(repo_root)).replace("\\", "/")
        saved_file_path: Optional[str] = None
        try:
            content = await asyncio.to_thread(_read_candidate, fp)
            if content is None or not content.strip():
                skipped += 1
                continue

            # Encode '/' as '__' (cannot appear inside a path segment created
            # by the single-'_' flattening) so distinct paths like 'a/b_c.md'
            # and 'a_b/c.md' don't collide on the same flattened filename.
            filename = f"{repo.repo_name}__{relative_path.replace('/', '__')}"

            # Skip duplicates (same project + filename already ingested)
            existing = db.query(ContextDocument).filter(
                ContextDocument.project_id == repo.project_id,
                ContextDocument.filename == filename,
            ).first()
            if existing:
                skipped += 1
                continue

            content_bytes = content.encode("utf-8")
            saved_file_path = await asyncio.to_thread(
                file_storage.save_file, repo.project_id, filename, content_bytes
            )

            file_ext = fp.suffix.lstrip(".").lower()
            document_type = DOC_TYPE_MAP.get(file_ext, DocumentType.TEXT)
            mime_type, _ = mimetypes.guess_type(fp.name)

            doc = ContextDocument(
                project_id=repo.project_id,
                filename=filename,
                original_filename=fp.name,
                file_path=saved_file_path,
                file_size=len(content_bytes),
                mime_type=mime_type,
                document_type=document_type,
                indexing_status=IndexingStatus.NOT_INDEXED,
                description=f"From {repo.clone_url}@{repo.branch}: {relative_path}",
                tags=["repository", repo.repo_name],
            )
            db.add(doc)
            db.flush()
            # Commit per file so a later failure's rollback only discards
            # that file's row, never previously ingested ones.
            db.commit()
            created_doc_ids.append(doc.id)
            ingested += 1

        except Exception as exc:
            logger.error("Failed to ingest %s: %s", fp, exc)
            errors.append({"file": relative_path, "error": str(exc)})
            # A failed flush/commit poisons the session — roll back so the
            # remaining files (and their commits) still work.
            try:
                db.rollback()
            except Exception as rollback_exc:
                logger.warning("Rollback after ingest failure failed: %s", rollback_exc)
            # Remove the orphaned storage file if its DB row never landed
            if saved_file_path:
                try:
                    await asyncio.to_thread(file_storage.delete_file, saved_file_path)
                except Exception as cleanup_exc:
                    logger.warning(
                        "Failed to clean up orphaned file %s: %s", saved_file_path, cleanup_exc
                    )

    # Queue RAG indexing through the same pipeline as uploaded documents
    for doc_id in created_doc_ids:
        background_tasks.add_task(index_document_background, doc_id)

    logger.info(
        f"Ingested {ingested} files from {repo.repo_name}:{body.path} "
        f"({skipped} skipped, {len(errors)} errors)"
    )
    return {"ingested": ingested, "skipped": skipped, "errors": errors}
