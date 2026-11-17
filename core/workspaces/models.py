from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    email: str | None = None
    access_token: str = ""


@dataclass(frozen=True)
class Workspace:
    id: UUID
    name: str
    slug: str
    created_by: UUID
    version: int = 1
    settings_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class WorkspaceMember:
    id: UUID
    workspace_id: UUID
    user_id: UUID
    role: WorkspaceRole
    created_at: datetime | None = None
