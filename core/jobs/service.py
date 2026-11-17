from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from core.errors import AppError, ErrorCode
from core.jobs.models import JobEventRecord, JobRecord, JobStatus, canonical_payload_hash
from core.jobs.ports import JobRepositoryPort
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class CommandBus:
    """Single command entry point enforcing workspace auth, validation, and idempotency (ADR-003)."""

    def __init__(self, workspaces: WorkspaceService, jobs: JobRepositoryPort) -> None:
        self._workspaces = workspaces
        self._jobs = jobs

    def dispatch_job_command(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        job_type: str,
        idempotency_key: str,
        payload_json: dict[str, Any],
        channel_id: UUID | None = None,
        total_steps: int = 1,
        priority: int = 50,
        correlation_id: UUID | None = None,
    ) -> tuple[JobRecord, bool]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_type = job_type.strip()
        clean_key = idempotency_key.strip()
        if len(clean_type) < 2 or len(clean_type) > 80:
            raise AppError(ErrorCode.VALIDATION_ERROR, "job_type invalido.", http_status=422, details={"field": "job_type"})
        if len(clean_key) < 8 or len(clean_key) > 128:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Idempotency-Key deve ter entre 8 e 128 caracteres.",
                http_status=422,
                details={"field": "Idempotency-Key"},
            )
        if total_steps < 1:
            raise AppError(ErrorCode.VALIDATION_ERROR, "total_steps deve ser >= 1.", http_status=422)

        payload_hash = canonical_payload_hash(payload_json)
        return self._jobs.enqueue_job(
            actor=actor,
            workspace_id=workspace_id,
            channel_id=channel_id,
            job_type=clean_type,
            idempotency_key=clean_key,
            payload_hash=payload_hash,
            payload_json=payload_json,
            total_steps=total_steps,
            priority=priority,
            correlation_id=correlation_id or uuid4(),
        )

    def list_jobs(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._jobs.list_jobs(actor, workspace_id, status=status, job_type=job_type, limit=limit)

    def get_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        self._workspaces.require_membership(actor, workspace_id)
        job = self._jobs.get_job(actor, workspace_id, job_id)
        if job is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Job nao encontrado neste workspace.", http_status=404)
        return job

    def list_job_events(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        job_id: UUID,
        after_sequence: int = 0,
    ) -> list[JobEventRecord]:
        self.get_job(actor, workspace_id, job_id)
        return self._jobs.list_job_events(actor, workspace_id, job_id, after_sequence=after_sequence)

    def request_pause(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> tuple[JobRecord, str]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        job = self.get_job(actor, workspace_id, job_id)
        if job.status in (JobStatus.SUCCEEDED, JobStatus.CANCELLED):
            raise AppError(ErrorCode.VALIDATION_ERROR, f"Job ja finalizado ({job.status.value}); nao pode ser pausado.", http_status=422)
        updated = self._jobs.request_pause(actor, workspace_id, job_id)
        state_note = "pause_applied" if updated.status == JobStatus.PAUSED else "pause_requested_pending_checkpoint"
        return updated, state_note

    def resume_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        job = self.get_job(actor, workspace_id, job_id)
        if job.status not in (JobStatus.PAUSED, JobStatus.INTERRUPTED, JobStatus.RECOVERABLE, JobStatus.BLOCKED, JobStatus.FAILED):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"Job em estado {job.status.value} nao pode ser retomado.",
                http_status=422,
            )
        return self._jobs.resume_job(actor, workspace_id, job_id)

    def request_cancel(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> tuple[JobRecord, str]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        job = self.get_job(actor, workspace_id, job_id)
        if job.status in (JobStatus.SUCCEEDED, JobStatus.CANCELLED):
            return job, "already_terminal"
        updated = self._jobs.request_cancel(actor, workspace_id, job_id)
        state_note = "cancel_confirmed" if updated.status == JobStatus.CANCELLED else "cancel_requested_pending_boundary"
        return updated, state_note
