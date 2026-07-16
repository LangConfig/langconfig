# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Platform Brain indexing and retrieval endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from api.experimental_local import EXPERIMENTAL_API_RESPONSES, require_experimental_local_api
from services.platform_brain_service import platform_brain_service


router = APIRouter(
    prefix="/api/platform-brain",
    tags=["platform-brain"],
    dependencies=[Depends(require_experimental_local_api)],
    responses=EXPERIMENTAL_API_RESPONSES,
)


class PlatformBrainQuery(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=25)
    source_types: Optional[List[str]] = None
    project_id: Optional[int] = None


@router.get("/status")
def get_platform_brain_status():
    return platform_brain_service.status()


@router.post("/reindex")
def reindex_platform_brain(db: Session = Depends(get_db)):
    return platform_brain_service.reindex(db)


@router.post("/query")
def query_platform_brain(request: PlatformBrainQuery, db: Session = Depends(get_db)):
    return platform_brain_service.query(
        request.query,
        db,
        top_k=request.top_k,
        source_types=request.source_types,
        project_id=request.project_id,
    )


@router.get("/query")
def query_platform_brain_get(
    q: str = Query(..., min_length=1),
    top_k: int = Query(8, ge=1, le=25),
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return platform_brain_service.query(q, db, top_k=top_k, project_id=project_id)
