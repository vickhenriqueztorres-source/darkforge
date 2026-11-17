from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

ALLOWED_TELEMETRY_EVENTS = frozenset(
    {
        "workspace_switched",
        "channel_profile_saved",
        "youtube_connect_started",
        "youtube_connect_completed",
        "youtube_sync_completed",
        "research_run_started",
        "research_reference_curated",
        "title_analyzed",
        "thumbnail_analyzed",
        "knowledge_imported",
        "knowledge_curated",
        "opportunity_generated",
        "opportunity_feedback_recorded",
        "brief_approved",
        "brief_exported",
        "production_intent_dispatched",
        "backup_restore_verified",
    }
)

_SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"sb_secret_[A-Za-z0-9_\-]+"), "sb_secret_[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "[JWT_REDACTED]"),
    (re.compile(r"postgres(?:ql)?://[^:@\s]+:[^@\s]+@"), "postgres://[REDACTED]:[REDACTED]@"),
]
_FORBIDDEN_META_KEYS = {
    "access_token",
    "refresh_token",
    "client_secret",
    "service_role_key",
    "supabase_service_role_key",
    "token_encryption_key",
    "database_url",
    "password",
    "secret",
    "content_text",
}


def redact_text(value: str) -> str:
    out = value
    for pat, repl in _SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


def sanitize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    cleaned: dict[str, Any] = {}
    for k, v in meta.items():
        if k.lower() in _FORBIDDEN_META_KEYS:
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, str):
            cleaned[k] = redact_text(v[:300])
        elif isinstance(v, dict):
            cleaned[k] = sanitize_metadata(v)
        elif isinstance(v, UUID):
            cleaned[k] = str(v)
        else:
            cleaned[k] = v
    return cleaned


@dataclass(frozen=True)
class TelemetryEvent:
    event_name: str
    workspace_id: str
    actor_id: str
    occurred_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TelemetryRecorder:
    """PRD 14.1 allowlisted telemetry recorder with secret & copy redaction."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def record(
        self,
        event_name: str,
        *,
        workspace_id: UUID | str,
        actor_id: UUID | str,
        metadata: dict[str, Any] | None = None,
    ) -> TelemetryEvent:
        if event_name not in ALLOWED_TELEMETRY_EVENTS:
            raise ValueError(f"Telemetry event not allowlisted: {event_name}")
        ev = TelemetryEvent(
            event_name=event_name,
            workspace_id=str(workspace_id),
            actor_id=str(actor_id),
            occurred_at=datetime.now(timezone.utc).isoformat(),
            metadata=sanitize_metadata(metadata),
        )
        self._events.append(ev)
        return ev

    def list_events(self, workspace_id: UUID | str | None = None) -> list[TelemetryEvent]:
        if workspace_id is None:
            return list(self._events)
        ws = str(workspace_id)
        return [e for e in self._events if e.workspace_id == ws]
