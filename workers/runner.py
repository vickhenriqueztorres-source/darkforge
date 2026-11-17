from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.jobs.models import ClaimedJob
from core.jobs.ports import WorkerQueuePort

logger = logging.getLogger("darkforge.worker")


@dataclass
class StepOutcome:
    step_name: str
    completed_steps: int
    checkpoint_json: dict
    message: str = ""


JobHandler = Callable[[ClaimedJob, "WorkerContext"], None]


class WorkerContext:
    """Passed to job handlers; enforces fencing token on every checkpoint & effect."""

    def __init__(self, queue: WorkerQueuePort, job: ClaimedJob, worker_id: str, lease_seconds: int) -> None:
        self._queue = queue
        self._job = job
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds

    def heartbeat(self) -> None:
        ok = self._queue.heartbeat(
            self._job.job_id, self._worker_id, self._job.fencing_token, self._lease_seconds
        )
        if not ok:
            raise AppError(
                code=ErrorCode.FENCING_TOKEN_STALE,
                message="Lease ou fencing token expirado; abortando worker antigo.",
                http_status=409,
            )

    def checkpoint(self, step_name: str, completed_steps: int, checkpoint_json: dict, message: str = "") -> str:
        """Records checkpoint and checks pause/cancel signals. Returns 'continue' | 'pause' | 'cancel'."""
        accepted, pause_req, cancel_req = self._queue.checkpoint(
            self._job.job_id,
            self._job.fencing_token,
            step_name,
            completed_steps,
            checkpoint_json,
            message,
        )
        if not accepted:
            raise AppError(
                code=ErrorCode.FENCING_TOKEN_STALE,
                message="Checkpoint rejeitado: fencing token obsoleto.",
                http_status=409,
            )
        if cancel_req:
            return "cancel"
        if pause_req:
            return "pause"
        return "continue"

    def run_idempotent_effect(self, scope: str, effect_key: str, fn: Callable[[], dict]) -> dict:
        """Executes external side effect at most once per (workspace_id, scope, effect_key)."""
        existing = self._queue.get_or_record_effect(self._job.workspace_id, scope, effect_key)
        if existing is not None:
            return existing
        result = fn()
        saved = self._queue.get_or_record_effect(self._job.workspace_id, scope, effect_key, result)
        return saved if saved is not None else result


def compute_backoff_seconds(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    raw = min(cap, base * (2 ** max(0, attempt - 1)))
    return raw + random.uniform(0.0, min(1.0, raw * 0.2))


class JobWorker:
    def __init__(
        self,
        queue: WorkerQueuePort,
        worker_id: str,
        handlers: dict[str, JobHandler] | None = None,
        lease_seconds: int = 30,
    ) -> None:
        self._queue = queue
        self._worker_id = worker_id
        self._handlers = handlers or {"diagnostic.multi_step": default_diagnostic_handler}
        self._lease_seconds = lease_seconds

    def reconcile_expired(self) -> int:
        return self._queue.reconcile_expired_leases()

    def run_once(self, job_types: list[str] | None = None) -> UUID | None:
        self.reconcile_expired()
        claimed = self._queue.claim_next(self._worker_id, self._lease_seconds, job_types)
        if claimed is None:
            return None

        handler = self._handlers.get(claimed.job_type)
        if handler is None:
            self._queue.transition(
                claimed.job_id,
                claimed.fencing_token,
                "FAILED",
                error_code="VALIDATION_ERROR",
                error_message=f"Handler nao registrado para job_type={claimed.job_type}",
                retryable=False,
            )
            return claimed.job_id

        ctx = WorkerContext(self._queue, claimed, self._worker_id, self._lease_seconds)
        try:
            handler(claimed, ctx)
        except _PausedAtBoundary as p:
            self._queue.transition(claimed.job_id, claimed.fencing_token, "PAUSED", checkpoint_json=p.checkpoint)
        except _CancelledAtBoundary as c:
            self._queue.transition(claimed.job_id, claimed.fencing_token, "CANCELLED", checkpoint_json=c.checkpoint)
        except AppError as err:
            if err.code == ErrorCode.FENCING_TOKEN_STALE:
                logger.warning("Fencing stale for job=%s worker=%s", claimed.job_id, self._worker_id)
                return claimed.job_id
            if err.code in (
                ErrorCode.SUPABASE_UNAVAILABLE,
                ErrorCode.YOUTUBE_QUOTA_EXCEEDED,
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                ErrorCode.DARKFORGE_UNAVAILABLE,
                ErrorCode.STUDIO_AUTH_REQUIRED,
                ErrorCode.STUDIO_RATE_LIMITED,
            ):
                self._queue.transition(
                    claimed.job_id,
                    claimed.fencing_token,
                    "BLOCKED",
                    error_code=err.code.value,
                    error_message=err.message,
                    retryable=True,
                )
            else:
                self._queue.transition(
                    claimed.job_id,
                    claimed.fencing_token,
                    "FAILED",
                    error_code=err.code.value,
                    error_message=err.message,
                    retryable=err.retryable,
                    next_retry_at=(
                        datetime.now(timezone.utc) + timedelta(seconds=compute_backoff_seconds(claimed.attempt_count))
                        if err.retryable
                        else None
                    ),
                )
        return claimed.job_id


class _PausedAtBoundary(Exception):
    def __init__(self, checkpoint: dict) -> None:
        self.checkpoint = checkpoint


class _CancelledAtBoundary(Exception):
    def __init__(self, checkpoint: dict) -> None:
        self.checkpoint = checkpoint


def default_diagnostic_handler(job: ClaimedJob, ctx: WorkerContext) -> None:
    """Multi-step resumable test/diagnostic job validating checkpoint + idempotency + pause/cancel."""
    steps = list(job.payload_json.get("steps") or ["prepare", "process", "verify"])
    done = list(job.checkpoint_json.get("completed_step_names") or [])

    for idx, step_name in enumerate(steps, start=1):
        if step_name in done:
            continue
        ctx.run_idempotent_effect(
            scope="diagnostic_step",
            effect_key=f"{job.job_id}:{step_name}",
            fn=lambda s=step_name: {"step": s, "executed_at": datetime.now(timezone.utc).isoformat()},
        )
        done.append(step_name)
        new_cp = {"completed_step_names": list(done)}
        signal = ctx.checkpoint(step_name, len(done), new_cp, message=f"Etapa {step_name} concluida")
        if signal == "cancel":
            raise _CancelledAtBoundary(new_cp)
        if signal == "pause":
            raise _PausedAtBoundary(new_cp)

    ctx._queue.transition(job.job_id, job.fencing_token, "SUCCEEDED", checkpoint_json={"completed_step_names": done})
