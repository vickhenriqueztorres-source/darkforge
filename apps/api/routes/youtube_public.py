from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from adapters.youtube.public_channel import PublicChannelCollector, parse_channel_ref
from apps.api.config import get_settings
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


@lru_cache(maxsize=1)
def get_public_collector() -> PublicChannelCollector:
    return PublicChannelCollector(api_key=get_settings().youtube_api_key)


class LinkYouTubeRequest(BaseModel):
    channel_ref: str = Field(min_length=2, max_length=300, description="@handle, URL do canal ou ID UC...")


def _channel_json(ch: Any) -> dict[str, Any]:
    data = asdict(ch)
    return {k: (str(v) if isinstance(v, UUID) else (v.isoformat() if hasattr(v, "isoformat") else v)) for k, v in data.items()}


@router.get("/channels/{channel_id}/youtube/overview")
def channel_youtube_overview(
    channel_id: UUID,
    refresh: bool = Query(default=False),
    max_videos: int = Query(default=30, ge=5, le=50),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
    collector: PublicChannelCollector = Depends(get_public_collector),
) -> dict[str, Any]:
    channel = container.channels.get_channel(actor, workspace_id, channel_id)
    raw_ref = channel.external_channel_id or channel.handle
    if not raw_ref:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Este canal ainda nao tem @handle do YouTube vinculado.",
            http_status=409,
            details={"next_action": "link_youtube_handle", "field": "channel_ref"},
        )
    overview = collector.fetch_overview(parse_channel_ref(raw_ref), force_refresh=refresh, max_videos=max_videos)
    return {
        "channel_link": {"handle": channel.handle, "external_channel_id": channel.external_channel_id},
        "has_api_key": collector.has_api_key,
        "overview": overview,
    }


@router.put("/channels/{channel_id}/youtube/link")
def link_channel_youtube(
    channel_id: UUID,
    body: LinkYouTubeRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
    collector: PublicChannelCollector = Depends(get_public_collector),
) -> dict[str, Any]:
    ref = parse_channel_ref(body.channel_ref)
    overview = collector.fetch_overview(ref, force_refresh=True)
    resolved = overview["channel"]
    handle = resolved.get("handle") or (f"@{ref.handle}" if ref.handle else None)
    channel = container.channels.link_youtube_channel(
        actor, workspace_id, channel_id, handle=handle, external_channel_id=resolved["channel_id"]
    )
    return {
        "channel": _channel_json(channel),
        "has_api_key": collector.has_api_key,
        "overview": overview,
    }
