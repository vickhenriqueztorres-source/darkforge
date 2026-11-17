from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Channel:
    id: UUID
    workspace_id: UUID
    platform: str
    display_name: str
    status: str
    created_by: UUID
    external_channel_id: str | None = None
    handle: str | None = None
    active_profile_version_id: UUID | None = None
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ChannelProfileInput:
    name: str
    language: str
    country: str
    timezone: str
    niche: str
    positioning: str = ""
    editorial_theme: str = ""
    audience_json: dict[str, Any] = field(default_factory=dict)
    pillars_json: list[str] = field(default_factory=list)
    voice_json: dict[str, Any] = field(default_factory=dict)
    formats_json: list[str] = field(default_factory=list)
    objectives_json: list[str] = field(default_factory=list)
    restrictions_json: dict[str, Any] = field(default_factory=dict)
    change_summary: str = "Atualizacao editorial"
    theme_change_reason: str = ""


@dataclass(frozen=True)
class ChannelProfileVersion:
    id: UUID
    workspace_id: UUID
    channel_id: UUID
    version_number: int
    name: str
    platform: str
    language: str
    country: str
    timezone: str
    niche: str
    positioning: str
    editorial_theme: str
    audience_json: dict[str, Any]
    pillars_json: list[str]
    voice_json: dict[str, Any]
    formats_json: list[str]
    objectives_json: list[str]
    restrictions_json: dict[str, Any]
    effective_from: datetime
    change_summary: str
    created_by: UUID
    created_at: datetime | None = None


@dataclass(frozen=True)
class EditorialThemeChange:
    id: UUID
    workspace_id: UUID
    channel_id: UUID
    previous_version_id: UUID | None
    new_version_id: UUID
    previous_theme: str
    new_theme: str
    reason: str
    effective_at: datetime
    changed_by: UUID
