from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header
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


class CreateProductionIntentRequest(BaseModel):
    pipeline_version: str = Field(default="media_vertical_v1", min_length=2, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class CompleteManifestRequest(BaseModel):
    pipeline_version: str = Field(min_length=2)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


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


def _require_production(container: ServiceContainer):
    if container.production is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ProductionIntentService nao configurado.", http_status=503, retryable=True)
    return container.production


@router.get("/production/health")
def production_gateway_health(
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_production(container)
    return _ser(svc.gateway_health(user, workspace_id))


@router.get("/production/intents")
def list_production_intents(
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_production(container)
    return _ser({"items": svc.list_intents(user, workspace_id)})


@router.post("/briefs/{brief_id}/production")
def create_production_intent(
    brief_id: UUID,
    body: CreateProductionIntentRequest | None = None,
    idempotency_key_header: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_production(container)
    idem_key = (idempotency_key_header or (body.idempotency_key if body else None) or f"prod-{brief_id}").strip()
    pipe = body.pipeline_version if body else "media_vertical_v1"
    return _ser(
        svc.create_production_intent(
            user,
            workspace_id,
            brief_id,
            idempotency_key=idem_key,
            pipeline_version=pipe,
        )
    )


@router.post("/production/intents/{intent_id}/dispatch")
def dispatch_production_intent(
    intent_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_production(container)
    return _ser(svc.dispatch_intent(user, workspace_id, intent_id))


@router.post("/production/intents/{intent_id}/complete")
def complete_production_intent(
    intent_id: UUID,
    body: CompleteManifestRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_production(container)
    return _ser(svc.complete_with_validated_manifest(user, workspace_id, intent_id, body.model_dump()))
