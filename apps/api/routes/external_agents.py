from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.studio.external_agents_service import ExternalAgentsService
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1/external-agents", dependencies=[Depends(enforce_origin)])


def _require_ext(container: ServiceContainer) -> ExternalAgentsService:
    if container.external_agents is None:
        raise AppError(
            ErrorCode.SUPABASE_UNAVAILABLE,
            "ExternalAgentsService nao configurado neste servidor.",
            http_status=503,
            retryable=True,
        )
    return container.external_agents


class ExternalAgentReportItem(BaseModel):
    agent_key: str = Field(min_length=2, max_length=120)
    status: Literal[
        "idle",
        "queued",
        "working",
        "waiting_input",
        "waiting_approval",
        "blocked",
        "done",
        "gate_passed",
        "gate_failed",
        "failed",
        "skipped",
        "cancelled",
    ]
    external_run_id: str | None = Field(default=None, max_length=160)
    pipeline_kind: Literal[
        "hsl_episode",
        "shorts_cutter",
        "standalone_bot",
        "firefly_batch",
        "audio_factory",
        "custom",
    ] = "custom"
    run_title: str | None = Field(default=None, max_length=240)
    external_execution_id: str | None = Field(default=None, max_length=200)
    stage_label: str | None = Field(default=None, max_length=240)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    model_name: str | None = Field(default=None, max_length=120)
    event_type: Literal[
        "queued",
        "started",
        "progress",
        "stage_changed",
        "heartbeat",
        "artifact_created",
        "gate_passed",
        "gate_failed",
        "waiting_human",
        "completed",
        "failed",
        "cancelled",
        "log",
    ] | None = None
    level: Literal["debug", "info", "warn", "error"] = "info"
    message: str | None = Field(default=None, max_length=1000)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=120)
    error_message: str | None = Field(default=None, max_length=2000)
    host_name: str | None = Field(default=None, max_length=120)
    source_repo: str | None = Field(default=None, max_length=120)
    attempt: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportSingleRequest(ExternalAgentReportItem):
    channel_id: UUID | None = None


class ReportBatchRequest(BaseModel):
    channel_id: UUID | None = None
    events: list[ExternalAgentReportItem] = Field(min_length=1, max_length=100)


class CreateIngestTokenRequest(BaseModel):
    label: str = Field(min_length=2, max_length=120)


@router.get("/channels/{channel_id}/snapshot")
def get_external_agents_snapshot(
    channel_id: UUID,
    pipeline_run_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return svc.get_snapshot(user, workspace_id, channel_id, pipeline_run_id=pipeline_run_id)


@router.post("/channels/{channel_id}/sync")
def sync_external_agents_from_disk(
    channel_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return svc.sync_from_connected_repo(user, workspace_id, channel_id)


@router.get("/channels/{channel_id}/events")
def list_external_agent_events(
    channel_id: UUID,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return svc.list_events(user, workspace_id, channel_id, after_id=after_id, limit=limit)


@router.get("/channels/{channel_id}/agents/{agent_key}")
def get_external_agent_detail(
    channel_id: UUID,
    agent_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return svc.get_agent_detail(user, workspace_id, channel_id, agent_key)


@router.get("/channels/{channel_id}/tokens")
def list_ingest_tokens(
    channel_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return {"tokens": svc.list_ingest_tokens(user, workspace_id, channel_id)}


@router.post("/channels/{channel_id}/tokens", status_code=201)
def create_ingest_token(
    channel_id: UUID,
    body: CreateIngestTokenRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return {"token": svc.create_ingest_token(user, workspace_id, channel_id, body.label)}


@router.delete("/tokens/{token_id}")
def revoke_ingest_token(
    token_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    return {"revoked": svc.revoke_ingest_token(user, workspace_id, token_id)}


@router.post("/report", status_code=202)
def report_single_external_agent_event(
    body: ReportSingleRequest,
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    authorization: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    payload = body.model_dump(exclude={"channel_id"})
    if x_ingest_token:
        res = svc.report_with_ingest_token(x_ingest_token, body.channel_id, [payload])
        return {"recorded": res}
    if not authorization or not authorization.lower().startswith("bearer ") or not x_workspace_id:
        raise AppError(
            ErrorCode.AUTH_UNAUTHENTICATED,
            "Informe X-Ingest-Token ou Authorization Bearer + X-Workspace-Id.",
            http_status=401,
        )
    if body.channel_id is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "channel_id obrigatorio no corpo da requisicao.",
            http_status=422,
        )
    user = container.jwt_verifier.verify_token(authorization.split(" ", 1)[1])
    ws_id = UUID(x_workspace_id)
    res = svc.report_with_user(user, ws_id, body.channel_id, [payload])
    return {"recorded": res}


@router.post("/batch", status_code=202)
def report_batch_external_agent_events(
    body: ReportBatchRequest,
    x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
    authorization: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_ext(container)
    items = [e.model_dump() for e in body.events]
    if x_ingest_token:
        res = svc.report_with_ingest_token(x_ingest_token, body.channel_id, items)
        return {"recorded": res, "count": len(res)}
    if not authorization or not authorization.lower().startswith("bearer ") or not x_workspace_id:
        raise AppError(
            ErrorCode.AUTH_UNAUTHENTICATED,
            "Informe X-Ingest-Token ou Authorization Bearer + X-Workspace-Id.",
            http_status=401,
        )
    if body.channel_id is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "channel_id obrigatorio no corpo da requisicao.",
            http_status=422,
        )
    user = container.jwt_verifier.verify_token(authorization.split(" ", 1)[1])
    ws_id = UUID(x_workspace_id)
    res = svc.report_with_user(user, ws_id, body.channel_id, items)
    return {"recorded": res, "count": len(res)}
