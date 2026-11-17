from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from adapters.supabase_db.client import SupabaseRestClient
from core.errors import AppError, ErrorCode
from core.jobs.models import (
    ClaimedJob,
    JobEventRecord,
    JobRecord,
    JobStatus,
    StorageObjectRecord,
    StorageObjectStatus,
)
from core.jobs.ports import JobRepositoryPort, StorageMetadataPort, WorkerQueuePort
from core.workspaces.models import AuthenticatedUser


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _row_to_job(r: dict[str, Any]) -> JobRecord:
    return JobRecord(
        id=UUID(str(r["id"])),
        workspace_id=UUID(str(r["workspace_id"])),
        channel_id=UUID(str(r["channel_id"])) if r.get("channel_id") else None,
        job_type=r["job_type"],
        status=JobStatus(r["status"]),
        priority=int(r["priority"]),
        idempotency_key=r["idempotency_key"],
        payload_hash=r["payload_hash"],
        payload_json=r.get("payload_json") or {},
        checkpoint_json=r.get("checkpoint_json") or {},
        current_step=r.get("current_step", "queued"),
        total_steps=int(r.get("total_steps", 1)),
        completed_steps=int(r.get("completed_steps", 0)),
        fencing_token=int(r.get("fencing_token", 0)),
        worker_id=r.get("worker_id"),
        attempt_count=int(r.get("attempt_count", 0)),
        max_attempts=int(r.get("max_attempts", 5)),
        pause_requested=bool(r.get("pause_requested", False)),
        cancel_requested=bool(r.get("cancel_requested", False)),
        error_code=r.get("error_code"),
        error_message=r.get("error_message"),
        retryable=bool(r.get("retryable", False)),
        correlation_id=UUID(str(r["correlation_id"])),
        created_by=UUID(str(r["created_by"])),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
        completed_at=_parse_dt(r.get("completed_at")),
    )


class SupabaseJobRepository(JobRepositoryPort):
    """PostgREST repository enforcing user JWT + RLS for API job endpoints."""

    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

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
        existing = self._client.request(
            "GET",
            "jobs",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "job_type": f"eq.{job_type}",
                "idempotency_key": f"eq.{idempotency_key}",
                "limit": "1",
            },
        )
        if existing:
            job = _row_to_job(existing[0])
            if job.payload_hash != payload_hash:
                raise AppError(
                    code=ErrorCode.IDEMPOTENCY_CONFLICT,
                    message="Idempotency-Key ja utilizada com payload diferente.",
                    http_status=409,
                )
            return job, True

        try:
            rows = self._client.request(
                "POST",
                "jobs",
                actor.access_token,
                prefer="return=representation",
                json_body={
                    "workspace_id": str(workspace_id),
                    "channel_id": str(channel_id) if channel_id else None,
                    "job_type": job_type,
                    "status": "QUEUED",
                    "priority": priority,
                    "idempotency_key": idempotency_key,
                    "payload_hash": payload_hash,
                    "payload_json": payload_json,
                    "total_steps": total_steps,
                    "correlation_id": str(correlation_id),
                    "created_by": str(actor.user_id),
                },
            )
            return _row_to_job(rows[0]), False
        except AppError as exc:
            if exc.code == ErrorCode.VERSION_CONFLICT:
                retry_rows = self._client.request(
                    "GET",
                    "jobs",
                    actor.access_token,
                    params={
                        "select": "*",
                        "workspace_id": f"eq.{workspace_id}",
                        "job_type": f"eq.{job_type}",
                        "idempotency_key": f"eq.{idempotency_key}",
                        "limit": "1",
                    },
                )
                if retry_rows:
                    job = _row_to_job(retry_rows[0])
                    if job.payload_hash != payload_hash:
                        raise AppError(
                            code=ErrorCode.IDEMPOTENCY_CONFLICT,
                            message="Idempotency-Key ja utilizada com payload diferente.",
                            http_status=409,
                        ) from exc
                    return job, True
            raise

    def list_jobs(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        params: dict[str, str] = {
            "select": "*",
            "workspace_id": f"eq.{workspace_id}",
            "order": "created_at.desc",
            "limit": str(max(1, min(limit, 200))),
        }
        if status:
            params["status"] = f"eq.{status}"
        if job_type:
            params["job_type"] = f"eq.{job_type}"
        rows = self._client.request("GET", "jobs", actor.access_token, params=params)
        return [_row_to_job(r) for r in rows or []]

    def get_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord | None:
        rows = self._client.request(
            "GET",
            "jobs",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "id": f"eq.{job_id}",
                "limit": "1",
            },
        )
        return _row_to_job(rows[0]) if rows else None

    def list_job_events(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        job_id: UUID,
        after_sequence: int = 0,
    ) -> list[JobEventRecord]:
        rows = self._client.request(
            "GET",
            "job_events",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "job_id": f"eq.{job_id}",
                "sequence_no": f"gt.{after_sequence}",
                "order": "sequence_no.asc",
            },
        )
        return [
            JobEventRecord(
                sequence_no=int(r["sequence_no"]),
                workspace_id=UUID(r["workspace_id"]),
                job_id=UUID(r["job_id"]),
                event_type=r["event_type"],
                step_name=r["step_name"],
                status=r["status"],
                message=r.get("message", ""),
                payload_json=r.get("payload_json") or {},
                created_at=_parse_dt(r.get("created_at")),
            )
            for r in rows or []
        ]

    def request_pause(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        current = self.get_job(actor, workspace_id, job_id)
        if current is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Job nao encontrado.", http_status=404)
        patch = (
            {"status": "PAUSED", "pause_requested": False}
            if current.status in (JobStatus.QUEUED, JobStatus.RECOVERABLE)
            else {"pause_requested": True}
        )
        rows = self._client.request(
            "PATCH",
            "jobs",
            actor.access_token,
            params={"id": f"eq.{job_id}", "workspace_id": f"eq.{workspace_id}"},
            prefer="return=representation",
            json_body=patch,
        )
        return _row_to_job(rows[0])

    def resume_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        rows = self._client.request(
            "PATCH",
            "jobs",
            actor.access_token,
            params={"id": f"eq.{job_id}", "workspace_id": f"eq.{workspace_id}"},
            prefer="return=representation",
            json_body={
                "status": "QUEUED",
                "pause_requested": False,
                "cancel_requested": False,
                "error_code": None,
                "error_message": None,
                "next_retry_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return _row_to_job(rows[0])

    def request_cancel(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        current = self.get_job(actor, workspace_id, job_id)
        if current is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Job nao encontrado.", http_status=404)
        if current.status in (JobStatus.QUEUED, JobStatus.PAUSED, JobStatus.RECOVERABLE, JobStatus.BLOCKED):
            patch: dict[str, Any] = {
                "status": "CANCELLED",
                "cancel_requested": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            patch = {"status": "CANCEL_REQUESTED", "cancel_requested": True}
        rows = self._client.request(
            "PATCH",
            "jobs",
            actor.access_token,
            params={"id": f"eq.{job_id}", "workspace_id": f"eq.{workspace_id}"},
            prefer="return=representation",
            json_body=patch,
        )
        return _row_to_job(rows[0])


class PostgresWorkerQueue(WorkerQueuePort):
    """Direct Postgres worker queue using FOR UPDATE SKIP LOCKED + fencing tokens."""

    def __init__(self, database_url: str, connect_timeout: float = 5.0) -> None:
        self._dsn = database_url
        self._connect_timeout = connect_timeout

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=int(self._connect_timeout), row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Banco Postgres do Supabase indisponivel para worker.",
                http_status=503,
                retryable=True,
            ) from exc

    def claim_next(
        self, worker_id: str, lease_seconds: int = 30, job_types: list[str] | None = None
    ) -> ClaimedJob | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM app.claim_next_job(%s, %s, %s)",
                        (worker_id, lease_seconds, job_types),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if not row:
                        return None
                    return ClaimedJob(
                        job_id=UUID(str(row["job_id"])),
                        workspace_id=UUID(str(row["workspace_id"])),
                        channel_id=UUID(str(row["channel_id"])) if row.get("channel_id") else None,
                        job_type=row["job_type"],
                        payload_json=row["payload_json"] or {},
                        checkpoint_json=row["checkpoint_json"] or {},
                        fencing_token=int(row["fencing_token"]),
                        attempt_count=int(row["attempt_count"]),
                        correlation_id=UUID(str(row["correlation_id"])),
                    )
        except psycopg.Error as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Falha de conexao ao reservar job.",
                http_status=503,
                retryable=True,
            ) from exc

    def heartbeat(self, job_id: UUID, worker_id: str, fencing_token: int, lease_seconds: int = 30) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT app.heartbeat_job(%s, %s, %s, %s) AS ok",
                        (str(job_id), worker_id, fencing_token, lease_seconds),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    return bool(row and row["ok"])
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha ao renovar heartbeat.", http_status=503, retryable=True) from exc

    def checkpoint(
        self,
        job_id: UUID,
        fencing_token: int,
        current_step: str,
        completed_steps: int,
        checkpoint_json: dict[str, Any],
        message: str = "",
    ) -> tuple[bool, bool, bool]:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM app.checkpoint_job(%s, %s, %s, %s, %s::jsonb, %s)",
                        (str(job_id), fencing_token, current_step, completed_steps, json.dumps(checkpoint_json), message),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if not row:
                        return False, False, False
                    return bool(row["accepted"]), bool(row["pause_requested"]), bool(row["cancel_requested"])
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha ao gravar checkpoint.", http_status=503, retryable=True) from exc

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
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT app.transition_job_with_fencing(%s, %s, %s, %s::jsonb, %s, %s, %s, %s) AS ok",
                        (
                            str(job_id),
                            fencing_token,
                            target_status,
                            json.dumps(checkpoint_json) if checkpoint_json is not None else None,
                            error_code,
                            error_message,
                            retryable,
                            next_retry_at,
                        ),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    return bool(row and row["ok"])
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha ao transicionar job.", http_status=503, retryable=True) from exc

    def reconcile_expired_leases(self) -> int:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT app.reconcile_expired_leases() AS cnt")
                    row = cur.fetchone()
                    conn.commit()
                    return int(row["cnt"]) if row else 0
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha na reconciliacao de leases.", http_status=503, retryable=True) from exc

    def get_or_record_effect(
        self,
        workspace_id: UUID,
        effect_scope: str,
        effect_key: str,
        result_json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT result_json FROM public.idempotent_effects
                        WHERE workspace_id = %s AND effect_scope = %s AND effect_key = %s
                        """,
                        (str(workspace_id), effect_scope, effect_key),
                    )
                    existing = cur.fetchone()
                    if existing is not None:
                        return existing["result_json"]
                    if result_json is None:
                        return None
                    cur.execute(
                        """
                        INSERT INTO public.idempotent_effects (workspace_id, effect_scope, effect_key, result_json)
                        VALUES (%s, %s, %s, %s::jsonb)
                        ON CONFLICT (workspace_id, effect_scope, effect_key) DO NOTHING
                        RETURNING result_json
                        """,
                        (str(workspace_id), effect_scope, effect_key, json.dumps(result_json)),
                    )
                    inserted = cur.fetchone()
                    conn.commit()
                    if inserted is not None:
                        return inserted["result_json"]
                    cur.execute(
                        """
                        SELECT result_json FROM public.idempotent_effects
                        WHERE workspace_id = %s AND effect_scope = %s AND effect_key = %s
                        """,
                        (str(workspace_id), effect_scope, effect_key),
                    )
                    row = cur.fetchone()
                    return row["result_json"] if row else None
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha no ledger de idempotencia.", http_status=503, retryable=True) from exc

    def dispatch_outbox_pending(self, consumer_name: str, limit: int = 50) -> list[dict[str, Any]]:
        """Transactional outbox -> inbox consumer helper (idempotent delivery)."""
        delivered: list[dict[str, Any]] = []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, workspace_id, event_type, aggregate_id, payload_json
                    FROM public.outbox_events
                    WHERE status = 'PENDING'
                    ORDER BY sequence_no ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO public.inbox_events (consumer_name, event_id, workspace_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (consumer_name, event_id) DO NOTHING
                        RETURNING event_id
                        """,
                        (consumer_name, str(row["id"]), str(row["workspace_id"])),
                    )
                    if cur.fetchone() is not None:
                        delivered.append(dict(row))
                    cur.execute(
                        """
                        UPDATE public.outbox_events
                        SET status = 'DISPATCHED', attempts = attempts + 1, dispatched_at = timezone('utc', now())
                        WHERE id = %s
                        """,
                        (str(row["id"]),),
                    )
                conn.commit()
        return delivered


class PostgresStorageMetadataRepository(StorageMetadataPort):
    def __init__(self, database_url: str) -> None:
        self._dsn = database_url

    def create_uploading_record(
        self,
        workspace_id: UUID,
        bucket: str,
        object_path: str,
        content_type: str,
        created_by: UUID,
        created_by_job: UUID | None = None,
    ) -> StorageObjectRecord:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.storage_objects
                        (workspace_id, bucket, object_path, content_type, status, created_by_job, created_by)
                    VALUES (%s, %s, %s, %s, 'UPLOADING', %s, %s)
                    ON CONFLICT (bucket, object_path) DO UPDATE
                    SET status = 'UPLOADING', updated_at = timezone('utc', now())
                    RETURNING *
                    """,
                    (
                        str(workspace_id),
                        bucket,
                        object_path,
                        content_type,
                        str(created_by_job) if created_by_job else None,
                        str(created_by),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
        return self._to_record(row)

    def update_status(
        self,
        workspace_id: UUID,
        object_id: UUID,
        status: StorageObjectStatus,
        sha256: str | None = None,
        size_bytes: int | None = None,
    ) -> StorageObjectRecord:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.storage_objects
                    SET status = %s,
                        sha256 = COALESCE(%s, sha256),
                        size_bytes = COALESCE(%s, size_bytes)
                    WHERE workspace_id = %s AND id = %s
                    RETURNING *
                    """,
                    (status.value, sha256, size_bytes, str(workspace_id), str(object_id)),
                )
                row = cur.fetchone()
                conn.commit()
        if not row:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "StorageObject nao encontrado.", http_status=404)
        return self._to_record(row)

    def list_objects(self, workspace_id: UUID, bucket: str | None = None) -> list[StorageObjectRecord]:
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                if bucket:
                    cur.execute(
                        "SELECT * FROM public.storage_objects WHERE workspace_id = %s AND bucket = %s ORDER BY created_at DESC",
                        (str(workspace_id), bucket),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM public.storage_objects WHERE workspace_id = %s ORDER BY created_at DESC",
                        (str(workspace_id),),
                    )
                rows = cur.fetchall()
        return [self._to_record(r) for r in rows]

    @staticmethod
    def _to_record(r: dict[str, Any]) -> StorageObjectRecord:
        return StorageObjectRecord(
            id=UUID(str(r["id"])),
            workspace_id=UUID(str(r["workspace_id"])),
            bucket=r["bucket"],
            object_path=r["object_path"],
            sha256=r.get("sha256"),
            size_bytes=r.get("size_bytes"),
            content_type=r["content_type"],
            status=StorageObjectStatus(r["status"]),
            created_by_job=UUID(str(r["created_by_job"])) if r.get("created_by_job") else None,
            created_by=UUID(str(r["created_by"])),
            created_at=_parse_dt(r.get("created_at")),
        )
