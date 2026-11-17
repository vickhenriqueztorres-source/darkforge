from __future__ import annotations

import json
from typing import Any
from uuid import UUID

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
from core.studio.service import StudioService
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1/studio", dependencies=[Depends(enforce_origin)])


def _require_studio(container: ServiceContainer) -> StudioService:
    if container.studio is None:
        raise AppError(
            ErrorCode.SUPABASE_UNAVAILABLE,
            "StudioService nao configurado neste servidor.",
            http_status=503,
            retryable=True,
        )
    return container.studio


class CreateContentItemRequest(BaseModel):
    working_title: str = Field(min_length=2, max_length=240)
    trigger_initial_agents: bool = True


class EnqueueAgentRunRequest(BaseModel):
    content_item_id: UUID | None = None
    reason: str = Field(default="manual", min_length=1, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=4, max_length=160)
    topic: str | None = Field(default=None, max_length=200)


class UpdateChannelAgentRequest(BaseModel):
    enabled: bool | None = None
    display_name: str | None = Field(default=None, max_length=120)
    avatar_key: str | None = Field(default=None, max_length=80)
    model_policy: dict[str, Any] | None = None
    monthly_budget_cents: int | None = Field(default=None, ge=0)
    clear_budget: bool = False


class SubmitApprovalRequest(BaseModel):
    target_kind: str = Field(pattern="^(agent_output|opportunity|brief|publication_plan)$")
    target_id: UUID
    target_version: int = Field(ge=1)
    decision: str = Field(pattern="^(approved|rejected|changes_requested)$")
    reason: str | None = Field(default=None, max_length=1000)
    confirm_needs_review: bool = False
    content_item_id: UUID | None = None


class ReviseOutputRequest(BaseModel):
    action: str = Field(pattern="^(save_version|discard)$")
    edited_content: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=500)


class ManualPublishRequest(BaseModel):
    published_video_url: str = Field(min_length=10, max_length=500)


@router.get("/overview")
def get_studio_overview(
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.get_overview(user, workspace_id)


@router.get("/channels/{channel_id}/snapshot")
def get_studio_snapshot(
    channel_id: UUID,
    content_item_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.get_snapshot(user, workspace_id, channel_id, content_item_id=content_item_id)


@router.get("/channels/{channel_id}/events")
def get_studio_events(
    channel_id: UUID,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.get_events(user, workspace_id, channel_id, after_id=after_id, limit=limit)


@router.get("/channels/{channel_id}/events/stream")
def stream_studio_events(
    channel_id: UUID,
    after_id: int | None = Query(default=None, ge=0),
    last_event_id_h: str | None = Header(default=None, alias="Last-Event-ID"),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    svc = _require_studio(container)
    cursor = 0
    if after_id is not None:
        cursor = after_id
    elif last_event_id_h and last_event_id_h.isdigit():
        cursor = int(last_event_id_h)

    res = svc.get_events(user, workspace_id, channel_id, after_id=cursor, limit=200)

    def event_stream():
        for evt in res["events"]:
            payload = json.dumps(evt, ensure_ascii=False)
            yield f"id: {evt['id']}\nevent: {evt['event_type']}\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/channels/{channel_id}/rooms/{room_key}")
def get_room_detail(
    channel_id: UUID,
    room_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.get_room_detail(user, workspace_id, channel_id, room_key)


@router.get("/channels/{channel_id}/agents/{agent_key}")
def get_agent_detail(
    channel_id: UUID,
    agent_key: str,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.get_agent_detail(user, workspace_id, channel_id, agent_key)


@router.patch("/channels/{channel_id}/agents/{agent_key}")
def update_channel_agent(
    channel_id: UUID,
    agent_key: str,
    body: UpdateChannelAgentRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    updated = svc.update_channel_agent(
        user,
        workspace_id,
        channel_id,
        agent_key,
        enabled=body.enabled,
        display_name=body.display_name,
        avatar_key=body.avatar_key,
        model_policy=body.model_policy,
        monthly_budget_cents=body.monthly_budget_cents,
        clear_budget=body.clear_budget,
    )
    return {"agent": updated}


@router.post("/channels/{channel_id}/content-items", status_code=201)
def create_content_item(
    channel_id: UUID,
    body: CreateContentItemRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.create_content_item(
        user,
        workspace_id,
        channel_id,
        working_title=body.working_title,
        trigger_initial_agents=body.trigger_initial_agents,
    )


@router.post("/channels/{channel_id}/agents/{agent_key}/run", status_code=202)
def enqueue_agent_run(
    channel_id: UUID,
    agent_key: str,
    body: EnqueueAgentRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    run, deduplicated = svc.enqueue_agent_run(
        user,
        workspace_id,
        channel_id,
        agent_key=agent_key,
        content_item_id=body.content_item_id,
        reason=body.reason,
        idempotency_key=body.idempotency_key or idempotency_key,
        topic=body.topic,
    )
    return {"run": run, "deduplicated": deduplicated}


@router.post("/runs/{run_id}/cancel")
def cancel_agent_run(
    run_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return {"run": svc.cancel_agent_run(user, workspace_id, run_id)}


@router.post("/runs/{run_id}/retry", status_code=202)
def retry_agent_run(
    run_id: UUID,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return {"run": svc.retry_agent_run(user, workspace_id, run_id)}


@router.post("/channels/{channel_id}/approvals")
def submit_approval(
    channel_id: UUID,
    body: SubmitApprovalRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.submit_approval(
        user,
        workspace_id,
        channel_id,
        target_kind=body.target_kind,
        target_id=body.target_id,
        target_version=body.target_version,
        decision=body.decision,
        reason=body.reason,
        confirm_needs_review=body.confirm_needs_review,
        content_item_id=body.content_item_id,
    )


@router.post("/outputs/{output_id}/revise")
def revise_output(
    output_id: UUID,
    body: ReviseOutputRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return svc.revise_output(
        user,
        workspace_id,
        output_id,
        action=body.action,
        edited_content=body.edited_content,
        reason=body.reason,
    )


@router.post("/content-items/{content_item_id}/publish-manual")
def mark_manual_published(
    content_item_id: UUID,
    body: ManualPublishRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_studio(container)
    return {"content_item": svc.mark_manual_published(user, workspace_id, content_item_id, published_video_url=body.published_video_url)}
