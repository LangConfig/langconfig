# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""API endpoints for the local Codex CLI harness."""

import json
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.codex_harness import CodexHarnessError, codex_harness
from api.experimental_local import EXPERIMENTAL_API_RESPONSES, require_experimental_local_api


router = APIRouter(
    prefix="/api/codex",
    tags=["codex"],
    dependencies=[Depends(require_experimental_local_api)],
    responses=EXPERIMENTAL_API_RESPONSES,
)


class CodexRunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    mode: Literal["exec"] = Field(default="exec", description="Run a bounded Codex exec task.")
    sandbox_dir: Optional[str] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def get_codex_status():
    return codex_harness.status()


@router.post("/login/device")
def start_device_login():
    try:
        run = codex_harness.start_device_login()
        return codex_harness.serialize_run(run)
    except CodexHarnessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs")
def start_codex_run(request: CodexRunRequest):
    try:
        run = codex_harness.start_exec_run(
            request.prompt,
            sandbox_dir=request.sandbox_dir,
            model=request.model,
            metadata=request.metadata,
        )
        return codex_harness.serialize_run(run)
    except CodexHarnessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events")
async def get_codex_run_events(
    run_id: str,
    stream: bool = Query(True),
    start_index: int = Query(0, ge=0),
):
    if stream:
        async def event_stream():
            try:
                async for event in codex_harness.stream_events(run_id, start_index=start_index):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except CodexHarnessError as exc:
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        return {"events": codex_harness.list_events(run_id)}
    except CodexHarnessError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel")
def cancel_codex_run(run_id: str):
    try:
        return codex_harness.cancel_run(run_id)
    except CodexHarnessError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
