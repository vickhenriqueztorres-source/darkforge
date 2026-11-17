from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.channels.models import ChannelProfileInput
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=3, max_length=64)


class ChannelProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=2, max_length=20)
    country: str = Field(min_length=2, max_length=10)
    timezone: str = Field(min_length=2, max_length=64)
    niche: str = Field(min_length=1, max_length=160)
    positioning: str = ""
    editorial_theme: str = ""
    audience_json: dict[str, Any] = Field(default_factory=dict)
    pillars_json: list[str] = Field(default_factory=list)
    voice_json: dict[str, Any] = Field(default_factory=dict)
    formats_json: list[str] = Field(default_factory=list)
    objectives_json: list[str] = Field(default_factory=list)
    restrictions_json: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = "Atualizacao editorial"
    theme_change_reason: str = ""

    def to_domain(self) -> ChannelProfileInput:
        return ChannelProfileInput(
            name=self.name,
            language=self.language,
            country=self.country,
            timezone=self.timezone,
            niche=self.niche,
            positioning=self.positioning,
            editorial_theme=self.editorial_theme,
            audience_json=self.audience_json,
            pillars_json=self.pillars_json,
            voice_json=self.voice_json,
            formats_json=self.formats_json,
            objectives_json=self.objectives_json,
            restrictions_json=self.restrictions_json,
            change_summary=self.change_summary,
            theme_change_reason=self.theme_change_reason,
        )


class CreateChannelRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    handle: str | None = None
    profile: ChannelProfilePayload


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


@router.get("/health")
def health(container: ServiceContainer = Depends(get_container)) -> dict[str, Any]:
    supabase_ok = container.supabase_client.check_health()
    return {
        "status": "ok" if supabase_ok else "degraded",
        "supabase_reachable": supabase_ok,
        "service": "darkforge-channel-os-api",
    }


@router.get("/workspaces")
def list_workspaces(
    actor: AuthenticatedUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    items = container.workspaces.list_workspaces(actor)
    return {
        "items": [
            {"workspace": _serialize(ws), "role": member.role.value}
            for ws, member in items
        ]
    }


@router.post("/workspaces", status_code=201)
def create_workspace(
    body: CreateWorkspaceRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    ws, member = container.workspaces.create_workspace(actor, body.name, body.slug)
    return {"workspace": _serialize(ws), "role": member.role.value}


@router.get("/channels")
def list_channels(
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    channels = container.channels.list_channels(actor, workspace_id)
    return {"items": [_serialize(ch) for ch in channels]}


@router.post("/channels", status_code=201)
def create_channel(
    body: CreateChannelRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    channel, version = container.channels.create_channel(
        actor=actor,
        workspace_id=workspace_id,
        display_name=body.display_name,
        handle=body.handle,
        profile=body.profile.to_domain(),
    )
    return {"channel": _serialize(channel), "profile_version": _serialize(version)}


@router.put("/channels/{channel_id}/profile")
def update_channel_profile(
    channel_id: UUID,
    body: ChannelProfilePayload,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    channel, version, theme_change = container.channels.update_profile(
        actor=actor,
        workspace_id=workspace_id,
        channel_id=channel_id,
        profile=body.to_domain(),
    )
    return {
        "channel": _serialize(channel),
        "profile_version": _serialize(version),
        "theme_change": _serialize(theme_change) if theme_change else None,
    }


@router.get("/channels/{channel_id}/profile/versions")
def list_profile_versions(
    channel_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    versions = container.channels.list_profile_versions(actor, workspace_id, channel_id)
    return {"items": [_serialize(v) for v in versions]}


@router.get("/channels/{channel_id}/theme-changes")
def list_theme_changes(
    channel_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    changes = container.channels.list_theme_changes(actor, workspace_id, channel_id)
    return {"items": [_serialize(c) for c in changes]}
