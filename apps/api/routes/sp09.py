from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.config import get_settings
from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from scripts.diagnostics.export_diagnostics import export_safe_diagnostics

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class RecordTelemetryRequest(BaseModel):
    event_name: str = Field(min_length=2, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/diagnostics/export")
def get_redacted_diagnostics(
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(user, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
    cfg = get_settings()
    if not cfg.database_url:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "DATABASE_URL nao configurado.", http_status=503, retryable=True)
    return export_safe_diagnostics(database_url=cfg.database_url, workspace_id=workspace_id)


@router.post("/telemetry/events")
def record_telemetry_event(
    body: RecordTelemetryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(user, workspace_id)
    try:
        ev = container.telemetry.record(
            body.event_name,
            workspace_id=workspace_id,
            actor_id=user.user_id,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), http_status=422) from exc
    return {
        "event": {
            "event_name": ev.event_name,
            "workspace_id": ev.workspace_id,
            "actor_id": ev.actor_id,
            "occurred_at": ev.occurred_at,
            "metadata": ev.metadata,
        }
    }
