# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Hermes APIs for approval-gated LangConfig artifact drafts."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from db.database import get_db
from api.experimental_local import EXPERIMENTAL_API_RESPONSES, require_experimental_local_api
from models.hermes import HermesDraft
from services import hermes_service
from services.hermes_service import HermesApplyError, HermesValidationError


router = APIRouter(
    prefix="/api/hermes",
    tags=["hermes"],
    dependencies=[Depends(require_experimental_local_api)],
    responses=EXPERIMENTAL_API_RESPONSES,
)


class HermesDraftCreate(BaseModel):
    artifact_type: str
    title: str
    payload_json: Dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[int] = None
    source_session_id: Optional[str] = None
    codex_run_id: Optional[str] = None
    validate_on_create: bool = True


class HermesDraftApplyRequest(BaseModel):
    target_id: Optional[int] = None
    lock_version: Optional[int] = None
    approval_note: Optional[str] = None


class HermesDraftRejectRequest(BaseModel):
    reason: Optional[str] = None


class WorkflowValidationRequest(BaseModel):
    payload_json: Dict[str, Any]


@router.get("/drafts")
def list_drafts(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    artifact_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(HermesDraft)
    if project_id is not None:
        query = query.filter(HermesDraft.project_id == project_id)
    if status:
        query = query.filter(HermesDraft.status == status)
    if artifact_type:
        try:
            normalized_artifact_type = hermes_service.normalize_artifact_type(artifact_type)
        except HermesValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        query = query.filter(HermesDraft.artifact_type == normalized_artifact_type)
    drafts = query.order_by(desc(HermesDraft.updated_at)).limit(limit).all()
    return [hermes_service.serialize_draft(draft) for draft in drafts]


@router.post("/drafts")
def create_draft(request: HermesDraftCreate, db: Session = Depends(get_db)):
    try:
        draft = hermes_service.create_draft(
            db,
            artifact_type=request.artifact_type,
            title=request.title,
            payload_json=request.payload_json,
            project_id=request.project_id,
            source_session_id=request.source_session_id,
            codex_run_id=request.codex_run_id,
            validate_on_create=request.validate_on_create,
        )
        return hermes_service.serialize_draft(draft)
    except HermesValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = _get_draft_or_404(db, draft_id)
    return hermes_service.serialize_draft(draft)


@router.post("/drafts/{draft_id}/validate")
def validate_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = _get_draft_or_404(db, draft_id)
    try:
        validation = hermes_service.validate_existing_draft(db, draft)
        return {"draft": hermes_service.serialize_draft(draft), "validation_result": validation}
    except HermesApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/apply")
def apply_draft(
    draft_id: int,
    request: HermesDraftApplyRequest,
    db: Session = Depends(get_db),
):
    draft = _get_draft_or_404(db, draft_id)
    try:
        result = hermes_service.apply_draft(
            db,
            draft,
            target_id=request.target_id,
            lock_version=request.lock_version,
            approval_note=request.approval_note,
        )
        return {"draft": hermes_service.serialize_draft(draft), "apply_result": result}
    except HermesApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/{draft_id}/reject")
def reject_draft(
    draft_id: int,
    request: HermesDraftRejectRequest,
    db: Session = Depends(get_db),
):
    draft = _get_draft_or_404(db, draft_id)
    try:
        draft = hermes_service.reject_draft(db, draft, request.reason)
        return hermes_service.serialize_draft(draft)
    except HermesApplyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/validate/workflow")
def validate_workflow_payload(request: WorkflowValidationRequest, db: Session = Depends(get_db)):
    return hermes_service.validate_draft_payload("workflow", request.payload_json, db)


@router.get("/tools")
def list_hermes_tools() -> Dict[str, List[str]]:
    return {
        "tools": [
            "langconfig_search",
            "langconfig_validate_workflow",
            "langconfig_create_draft",
            "langconfig_apply_draft",
            "langconfig_export_workflow",
            "codex_run_task",
            "codex_get_status",
        ]
    }


def _get_draft_or_404(db: Session, draft_id: int) -> HermesDraft:
    draft = db.query(HermesDraft).filter(HermesDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Hermes draft not found")
    return draft
