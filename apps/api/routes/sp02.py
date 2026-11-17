from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class CreateJobRequest(BaseModel):
    job_type: str = Field(min_length=2, max_length=80)
    channel_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    total_steps: int = Field(default=3, ge=1, le=500)
    priority: int = Field(default=50, ge=1, le=100)


class ReconcileStorageRequest(BaseModel):
    bucket: str = Field(pattern="^(knowledge|references|exports|production)$")


def _serialize(obj: Any) -> Any:
    raw = asdict(obj)
    for k, v in list(raw.items()):
        if isinstance(v, UUID):
            raw[k] = str(v)
        elif hasattr(v, "value"):
            raw[k] = v.value
        elif hasattr(v, "isoformat"):
            raw[k] = v.isoformat()
    return raw


@router.post("/jobs", status_code=202)
def enqueue_job(
    body: CreateJobRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    key = idempotency_key or str(uuid4())
    corr = UUID(x_correlation_id) if x_correlation_id else uuid4()
    job, deduplicated = container.command_bus.dispatch_job_command(
        actor=actor,
        workspace_id=workspace_id,
        channel_id=body.channel_id,
        job_type=body.job_type,
        idempotency_key=key,
        payload_json=body.payload,
        total_steps=body.total_steps,
        priority=body.priority,
        correlation_id=corr,
    )
    return {
        "job_id": str(job.id),
        "status": job.status.value,
        "idempotency_key": job.idempotency_key,
        "correlation_id": str(job.correlation_id),
        "deduplicated": deduplicated,
    }


@router.get("/jobs")
def list_jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    jobs = container.command_bus.list_jobs(actor, workspace_id, status=status, job_type=job_type, limit=limit)
    return {"items": [_serialize(j) for j in jobs]}


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    job = container.command_bus.get_job(actor, workspace_id, job_id)
    events = container.command_bus.list_job_events(actor, workspace_id, job_id, after_sequence=0)
    return {"job": _serialize(job), "events": [_serialize(e) for e in events]}


@router.post("/jobs/{job_id}/pause")
def pause_job(
    job_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    job, state_note = container.command_bus.request_pause(actor, workspace_id, job_id)
    return {"job": _serialize(job), "control_result": state_note}


@router.post("/jobs/{job_id}/resume")
def resume_job(
    job_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    job = container.command_bus.resume_job(actor, workspace_id, job_id)
    return {"job": _serialize(job), "control_result": "resumed_to_queue"}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    job, state_note = container.command_bus.request_cancel(actor, workspace_id, job_id)
    return {"job": _serialize(job), "control_result": state_note}


@router.get("/jobs/{job_id}/events")
def stream_job_events(
    job_id: UUID,
    last_event_id_q: int | None = Query(default=None, alias="last_event_id"),
    last_event_id_h: str | None = Header(default=None, alias="Last-Event-ID"),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    after_seq = 0
    if last_event_id_q is not None:
        after_seq = max(0, last_event_id_q)
    elif last_event_id_h and last_event_id_h.isdigit():
        after_seq = int(last_event_id_h)

    events = container.command_bus.list_job_events(actor, workspace_id, job_id, after_sequence=after_seq)

    def event_stream():
        for evt in events:
            data = json.dumps(_serialize(evt), ensure_ascii=True)
            yield f"id: {evt.sequence_no}\nevent: {evt.event_type}\ndata: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/storage/reconcile")
def reconcile_storage(
    body: ReconcileStorageRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
    if container.storage_service is None:
        raise AppError(
            code=ErrorCode.SUPABASE_UNAVAILABLE,
            message="StorageService nao configurado neste servidor.",
            http_status=503,
            retryable=True,
        )
    report = container.storage_service.reconcile_bucket(workspace_id, body.bucket)
    return {"report": _serialize(report)}
