from __future__ import annotations

from typing import Any
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
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class CreateStudioRunRequest(BaseModel):
    channel_id: UUID
    broad_topic: str = Field(min_length=2, max_length=200)
    min_interest: str = Field(default="medium", pattern="^(low|medium|high|very_high)$")
    only_watched_by_my_viewers: bool = False
    upload_window_days: int | None = Field(default=28, ge=1, le=3650)
    min_outlier_ratio: float = Field(default=3.0, ge=1.0, le=100.0)
    execute_now: bool = True


class IngestStudioCaptureRequest(BaseModel):
    terms: list[dict[str, Any]] = Field(default_factory=list)
    videos: list[dict[str, Any]] = Field(default_factory=list)
    channel_baselines: dict[str, list[int]] = Field(default_factory=dict)
    min_outlier_ratio: float = Field(default=3.0, ge=1.0, le=100.0)


class CurateStudioItemRequest(BaseModel):
    status: str = Field(pattern="^(pending|approved|rejected|archived)$")


def _ser(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _require_studio(container: ServiceContainer):
    if container.studio_trends is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "StudioTrendsService nao configurado.", http_status=503, retryable=True)
    return container.studio_trends


@router.get("/research/studio-session/status")
def studio_session_status(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser(svc.session_status(user, workspace_id, channel_id=channel_id))


@router.post("/research/studio-session/login-window")
def open_studio_manual_login(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser(svc.launch_manual_login(user, workspace_id, channel_id=channel_id))


@router.get("/research/studio-runs")
def list_studio_runs(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser({"items": svc.list_runs(user, workspace_id, channel_id=channel_id)})


@router.post("/research/studio-runs", status_code=201)
def create_studio_run(
    body: CreateStudioRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser(
        svc.create_studio_run(
            user,
            workspace_id,
            body.channel_id,
            broad_topic=body.broad_topic,
            min_interest=body.min_interest,
            only_watched_by_my_viewers=body.only_watched_by_my_viewers,
            upload_window_days=body.upload_window_days,
            min_outlier_ratio=body.min_outlier_ratio,
            idempotency_key=idempotency_key,
            execute_now=body.execute_now,
        )
    )


@router.get("/research/studio-runs/{run_id}")
def get_studio_run_detail(
    run_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser(svc.get_run_detail(user, workspace_id, run_id))


@router.post("/research/studio-runs/{run_id}/ingest")
def ingest_studio_capture(
    run_id: UUID,
    body: IngestStudioCaptureRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser(
        svc.ingest_captured_payload(
            user,
            workspace_id,
            run_id,
            terms=body.terms,
            videos=body.videos,
            channel_baselines=body.channel_baselines,
            min_outlier_ratio=body.min_outlier_ratio,
        )
    )


@router.post("/research/studio-items/{kind}/{item_id}/curate")
def curate_studio_item(
    kind: str,
    item_id: UUID,
    body: CurateStudioItemRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return _ser({"item": svc.curate_item(user, workspace_id, kind, item_id, body.status)})
