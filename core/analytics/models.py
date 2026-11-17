from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class MetricAvailability(StrEnum):
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    DELAYED = "delayed"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class ConnectionStatus(StrEnum):
    PENDING_AUTH = "PENDING_AUTH"
    CONNECTED = "CONNECTED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    REVOKED_OR_INVALID = "REVOKED_OR_INVALID"
    DISCONNECTED = "DISCONNECTED"


class QuotaPool(StrEnum):
    OWN_SYNC = "own_sync"
    PUBLIC_RESEARCH = "public_research"


class RetentionPolicy(StrEnum):
    KEEP_READONLY = "keep_readonly"
    PURGE_SYNCED_DATA = "purge_synced_data"


def canonical_dimensions_hash(dimensions: dict[str, str]) -> str:
    encoded = json.dumps(dimensions, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PlatformConnection:
    id: UUID
    workspace_id: UUID
    channel_id: UUID
    platform: str
    status: ConnectionStatus
    scopes: list[str]
    external_account_id: str | None = None
    external_channel_id: str | None = None
    token_expires_at: datetime | None = None
    last_validated_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    retention_policy: str = "keep_readonly"


@dataclass(frozen=True)
class OAuthTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at: datetime
    scopes: list[str]
    external_account_id: str | None = None


@dataclass(frozen=True)
class VideoRecord:
    id: UUID
    workspace_id: UUID
    channel_id: UUID
    external_video_id: str
    canonical_url: str
    title: str
    description: str
    format: str
    duration_seconds: int | None
    published_at: datetime | None
    thumbnail_url: str | None
    privacy_status: str
    source: str
    source_updated_at: datetime | None = None


@dataclass(frozen=True)
class MetricFactInput:
    metric_id: str
    visibility_scope: str
    source: str
    period_start: date
    period_end: date
    granularity: str
    dimensions_json: dict[str, str]
    availability: MetricAvailability
    value_num: float | None
    is_estimate: bool = False
    external_video_id: str | None = None

    def __post_init__(self) -> None:
        # Regra inegociavel AN-004: metrica ausente/atrasada/parcial/N/A nunca vira 0
        if self.availability != MetricAvailability.AVAILABLE and self.value_num is not None:
            raise ValueError(
                f"Metric {self.metric_id} with availability={self.availability.value} must have value_num=None, never {self.value_num}."
            )


@dataclass(frozen=True)
class MetricFactView:
    id: UUID
    metric_id: str
    display_name: str
    visibility_scope: str
    source: str
    source_revision: int
    period_start: date
    period_end: date
    granularity: str
    dimensions_json: dict[str, str]
    availability: MetricAvailability
    value_num: float | None
    is_estimate: bool
    fetched_at: datetime
    video_id: UUID | None = None


@dataclass(frozen=True)
class SyncCursorView:
    sync_scope: str
    freshness_status: str
    last_page_processed: int
    last_successful_sync_at: datetime | None
    source_updated_at: datetime | None
    cursor_token: str | None = None
    partial_errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class CatalogPageResult:
    external_channel_id: str
    videos: list[dict[str, Any]]
    next_page_token: str | None
    quota_cost: int


@dataclass(frozen=True)
class AnalyticsBatchResult:
    facts: list[MetricFactInput]
    partial_errors: list[dict[str, Any]]
    quota_cost: int
