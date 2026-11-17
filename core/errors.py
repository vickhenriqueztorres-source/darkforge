from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class ErrorCode(StrEnum):
    AUTH_UNAUTHENTICATED = "AUTH_UNAUTHENTICATED"
    WORKSPACE_FORBIDDEN = "WORKSPACE_FORBIDDEN"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    SUPABASE_UNAVAILABLE = "SUPABASE_UNAVAILABLE"
    OAUTH_REQUIRED_OR_REVOKED = "OAUTH_REQUIRED_OR_REVOKED"
    YOUTUBE_QUOTA_EXCEEDED = "YOUTUBE_QUOTA_EXCEEDED"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    AI_EXTERNAL_CONSENT_REQUIRED = "AI_EXTERNAL_CONSENT_REQUIRED"
    AI_BUDGET_EXCEEDED = "AI_BUDGET_EXCEEDED"
    ORIGINALITY_SIMILARITY_BLOCKED = "ORIGINALITY_SIMILARITY_BLOCKED"
    STORAGE_CHECKSUM_MISMATCH = "STORAGE_CHECKSUM_MISMATCH"
    FENCING_TOKEN_STALE = "FENCING_TOKEN_STALE"
    DARKFORGE_UNAVAILABLE = "DARKFORGE_UNAVAILABLE"
    STUDIO_AUTH_REQUIRED = "STUDIO_AUTH_REQUIRED"
    STUDIO_RATE_LIMITED = "STUDIO_RATE_LIMITED"


@dataclass
class AppError(Exception):
    code: ErrorCode
    message: str
    http_status: int = 400
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    correlation_id: UUID = field(default_factory=uuid4)
    job_id: UUID | None = None

    def to_envelope(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "details": self.details,
            "correlation_id": str(self.correlation_id),
            "job_id": str(self.job_id) if self.job_id else None,
        }
