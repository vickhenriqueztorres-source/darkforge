from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    RECOVERABLE = "RECOVERABLE"
    INTERRUPTED = "INTERRUPTED"
    LOCAL_COMPLETED_PENDING_SYNC = "LOCAL_COMPLETED_PENDING_SYNC"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"


class StorageObjectStatus(StrEnum):
    UPLOADING = "UPLOADING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    FAILED = "FAILED"
    ORPHANED = "ORPHANED"


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    workspace_id: UUID
    channel_id: UUID | None
    job_type: str
    status: JobStatus
    priority: int
    idempotency_key: str
    payload_hash: str
    payload_json: dict[str, Any]
    checkpoint_json: dict[str, Any]
    current_step: str
    total_steps: int
    completed_steps: int
    fencing_token: int
    worker_id: str | None
    attempt_count: int
    max_attempts: int
    pause_requested: bool
    cancel_requested: bool
    error_code: str | None
    error_message: str | None
    retryable: bool
    correlation_id: UUID
    created_by: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class ClaimedJob:
    job_id: UUID
    workspace_id: UUID
    channel_id: UUID | None
    job_type: str
    payload_json: dict[str, Any]
    checkpoint_json: dict[str, Any]
    fencing_token: int
    attempt_count: int
    correlation_id: UUID


@dataclass(frozen=True)
class JobEventRecord:
    sequence_no: int
    workspace_id: UUID
    job_id: UUID
    event_type: str
    step_name: str
    status: str
    message: str
    payload_json: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class StorageObjectRecord:
    id: UUID
    workspace_id: UUID
    bucket: str
    object_path: str
    sha256: str | None
    size_bytes: int | None
    content_type: str
    status: StorageObjectStatus
    created_by_job: UUID | None
    created_by: UUID
    created_at: datetime | None = None


@dataclass(frozen=True)
class ReconcileReport:
    workspace_id: UUID
    bucket: str
    missing_in_storage: list[str]
    orphaned_in_storage: list[str]
    incomplete_uploads: list[str]
