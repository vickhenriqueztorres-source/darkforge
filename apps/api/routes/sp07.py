from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
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


class GenerateOpportunitiesRequest(BaseModel):
    channel_id: UUID
    topic_hint: str = Field(min_length=2, max_length=200)
    target_format: str = Field(default="long", pattern="^(long|short|live)$")
    use_external: bool = False
    external_consent_granted: bool = False


class ReviewOpportunityRequest(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT|EDIT|ARCHIVE|NOTE)$")
    reason_code: str | None = None
    notes: str | None = None
    edited_theme: str | None = None
    edited_angle: str | None = None
    edited_differentiation: str | None = None


class CreateBriefRequest(BaseModel):
    opportunity_id: UUID
    title: str = Field(min_length=2, max_length=200)
    hook: str = Field(min_length=2)
    angle: str = Field(min_length=2)
    outline: list[dict[str, Any]] = Field(default_factory=list)
    cta: str = ""
    target_format: str = Field(default="long", pattern="^(long|short|live)$")
    generation_refs: list[str] = Field(default_factory=list)


class UpdateBriefRequest(BaseModel):
    title: str | None = None
    hook: str | None = None
    angle: str | None = None
    outline: list[dict[str, Any]] | None = None
    cta: str | None = None
    notes: str | None = None


class ApproveBriefRequest(BaseModel):
    notes: str | None = None


class CreateCalendarItemRequest(BaseModel):
    channel_id: UUID
    title: str = Field(min_length=2, max_length=200)
    scheduled_for: str
    brief_id: UUID | None = None
    notes: str | None = None
    auto_publish_enabled: bool = False


class UpdateCalendarStatusRequest(BaseModel):
    status: str = Field(pattern="^(PLANNED|IN_PRODUCTION|READY_FOR_MANUAL_PUBLISH|PUBLISHED_MANUALLY|CANCELED)$")


def _ser(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__float__") and type(obj).__name__ == "Decimal":
        return float(obj)
    return obj


def _require_opportunities(container: ServiceContainer):
    if container.opportunities is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "OpportunityService nao configurado.", http_status=503, retryable=True)
    return container.opportunities


def _require_editorial(container: ServiceContainer):
    if container.editorial is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "EditorialStudioService nao configurado.", http_status=503, retryable=True)
    return container.editorial


@router.get("/opportunities")
def list_opportunities(
    channel_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_opportunities(container)
    items = svc.list_opportunities(user, workspace_id, channel_id=channel_id, status=status)
    return _ser({"items": items})


@router.post("/opportunities/generate")
def generate_opportunities(
    body: GenerateOpportunitiesRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_opportunities(container)
    res = svc.generate_opportunities(
        user,
        workspace_id,
        body.channel_id,
        topic_hint=body.topic_hint,
        target_format=body.target_format,
        use_external=body.use_external,
        external_consent_granted=body.external_consent_granted,
    )
    return _ser(res)


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_opportunities(container)
    return _ser(svc.get_opportunity(user, workspace_id, opportunity_id))


@router.post("/opportunities/{opportunity_id}/feedback")
def review_opportunity(
    opportunity_id: UUID,
    body: ReviewOpportunityRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_opportunities(container)
    return _ser(
        svc.review_opportunity(
            user,
            workspace_id,
            opportunity_id,
            decision=body.decision,
            reason_code=body.reason_code,
            notes=body.notes,
            edited_theme=body.edited_theme,
            edited_angle=body.edited_angle,
            edited_differentiation=body.edited_differentiation,
        )
    )


@router.get("/briefs")
def list_briefs(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser({"items": svc.list_briefs(user, workspace_id, channel_id=channel_id)})


@router.post("/briefs")
def create_brief(
    body: CreateBriefRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(
        svc.create_brief(
            user,
            workspace_id,
            opportunity_id=body.opportunity_id,
            title=body.title,
            hook=body.hook,
            angle=body.angle,
            outline=body.outline,
            cta=body.cta,
            target_format=body.target_format,
            generation_refs=body.generation_refs,
        )
    )


@router.get("/briefs/{brief_id}")
def get_brief(
    brief_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(svc.get_brief(user, workspace_id, brief_id))


@router.put("/briefs/{brief_id}")
def update_brief(
    brief_id: UUID,
    body: UpdateBriefRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(
        svc.update_draft(
            user,
            workspace_id,
            brief_id,
            title=body.title,
            hook=body.hook,
            angle=body.angle,
            outline=body.outline,
            cta=body.cta,
            notes=body.notes,
        )
    )


@router.post("/briefs/{brief_id}/approve")
def approve_brief(
    brief_id: UUID,
    body: ApproveBriefRequest | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(svc.approve_brief(user, workspace_id, brief_id, notes=body.notes if body else None))


@router.post("/briefs/{brief_id}/versions")
def create_brief_version(
    brief_id: UUID,
    body: UpdateBriefRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(
        svc.create_new_version(
            user,
            workspace_id,
            brief_id,
            title=body.title,
            hook=body.hook,
            angle=body.angle,
            outline=body.outline,
            cta=body.cta,
            notes=body.notes,
        )
    )


@router.get("/briefs/{brief_id}/export")
def export_brief(
    brief_id: UUID,
    format: str = Query(default="markdown", pattern="^(markdown|json|csv)$"),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(svc.export_brief(user, workspace_id, brief_id, fmt=format))


@router.get("/calendar")
def list_calendar(
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser({"items": svc.list_calendar_items(user, workspace_id)})


@router.post("/calendar")
def create_calendar_item(
    body: CreateCalendarItemRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser(
        {
            "item": svc.create_calendar_item(
                user,
                workspace_id,
                channel_id=body.channel_id,
                title=body.title,
                scheduled_for=body.scheduled_for,
                brief_id=body.brief_id,
                notes=body.notes,
                auto_publish_enabled=body.auto_publish_enabled,
            )
        }
    )


@router.patch("/calendar/{item_id}")
def update_calendar_status(
    item_id: UUID,
    body: UpdateCalendarStatusRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_editorial(container)
    return _ser({"item": svc.update_calendar_status(user, workspace_id, item_id, body.status)})
