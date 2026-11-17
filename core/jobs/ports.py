from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from core.jobs.models import (
    ClaimedJob,
    JobEventRecord,
    JobRecord,
    StorageObjectRecord,
    StorageObjectStatus,
)
from core.workspaces.models import AuthenticatedUser


class JobRepositoryPort(ABC):
    @abstractmethod
    def enqueue_job(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID | None,
        job_type: str,
        idempotency_key: str,
        payload_hash: str,
        payload_json: dict[str, Any],
        total_steps: int,
        priority: int,
        correlation_id: UUID,
    ) -> tuple[JobRecord, bool]:
        """Returns (job, deduplicated)."""
        raise NotImplementedError

    @abstractmethod
    def list_jobs(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_job_events(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        job_id: UUID,
        after_sequence: int = 0,
    ) -> list[JobEventRecord]:
        raise NotImplementedError

    @abstractmethod
    def request_pause(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        raise NotImplementedError

    @abstractmethod
    def resume_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        raise NotImplementedError

    @abstractmethod
    def request_cancel(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        raise NotImplementedError


class WorkerQueuePort(ABC):
    @abstractmethod
    def claim_next(self, worker_id: str, lease_seconds: int = 30, job_types: list[str] | None = None) -> ClaimedJob | None:
        raise NotImplementedError

    @abstractmethod
    def heartbeat(self, job_id: UUID, worker_id: str, fencing_token: int, lease_seconds: int = 30) -> bool:
        raise NotImplementedError

    @abstractmethod
    def checkpoint(
        self,
        job_id: UUID,
        fencing_token: int,
        current_step: str,
        completed_steps: int,
        checkpoint_json: dict[str, Any],
        message: str = "",
    ) -> tuple[bool, bool, bool]:
        """Returns (accepted, pause_requested, cancel_requested)."""
        raise NotImplementedError

    @abstractmethod
    def transition(
        self,
        job_id: UUID,
        fencing_token: int,
        target_status: str,
        checkpoint_json: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        retryable: bool = False,
        next_retry_at: datetime | None = None,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def reconcile_expired_leases(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_or_record_effect(
        self,
        workspace_id: UUID,
        effect_scope: str,
        effect_key: str,
        result_json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        raise NotImplementedError


class StorageMetadataPort(ABC):
    @abstractmethod
    def create_uploading_record(
        self,
        workspace_id: UUID,
        bucket: str,
        object_path: str,
        content_type: str,
        created_by: UUID,
        created_by_job: UUID | None = None,
    ) -> StorageObjectRecord:
        raise NotImplementedError

    @abstractmethod
    def update_status(
        self,
        workspace_id: UUID,
        object_id: UUID,
        status: StorageObjectStatus,
        sha256: str | None = None,
        size_bytes: int | None = None,
    ) -> StorageObjectRecord:
        raise NotImplementedError

    @abstractmethod
    def list_objects(self, workspace_id: UUID, bucket: str | None = None) -> list[StorageObjectRecord]:
        raise NotImplementedError
