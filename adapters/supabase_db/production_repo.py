from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class PostgresProductionRepository:
    """Postgres repository for ProductionIntents & Storage Artifact Validation (SP-08)."""

    def __init__(self, database_url: str) -> None:
        self._db_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._db_url, row_factory=dict_row, prepare_threshold=None)

    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.episode_briefs WHERE workspace_id = %s AND id = %s",
                (workspace_id, brief_id),
            )
            return cur.fetchone()

    def find_intent_by_idempotency(self, workspace_id: UUID, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.production_intents WHERE workspace_id = %s AND idempotency_key = %s",
                (workspace_id, idempotency_key),
            )
            return cur.fetchone()

    def insert_intent(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        brief_id: UUID,
        brief_version: int,
        brief_content_sha256: str,
        pipeline_version: str,
        idempotency_key: str,
        job_id: UUID | None,
        created_by: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.production_intents (
                    workspace_id, channel_id, brief_id, brief_version, brief_content_sha256,
                    pipeline_version, idempotency_key, job_id, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    channel_id,
                    brief_id,
                    brief_version,
                    brief_content_sha256,
                    pipeline_version,
                    idempotency_key,
                    job_id,
                    created_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def get_intent(self, workspace_id: UUID, intent_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.production_intents WHERE workspace_id = %s AND id = %s",
                (workspace_id, intent_id),
            )
            return cur.fetchone()

    def list_intents(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.production_intents WHERE workspace_id = %s ORDER BY created_at DESC",
                (workspace_id,),
            )
            return cur.fetchall()

    def mark_intent_status(
        self,
        *,
        workspace_id: UUID,
        intent_id: UUID,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
        external_darkforge_job_id: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.production_intents
                SET status = %s,
                    error_code = %s,
                    error_message = %s,
                    external_darkforge_job_id = COALESCE(%s, external_darkforge_job_id)
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (status, error_code, error_message, external_darkforge_job_id, workspace_id, intent_id),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def mark_job_blocked(self, *, workspace_id: UUID, job_id: UUID, error_code: str, error_message: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.jobs
                SET status = 'BLOCKED', error_code = %s, error_message = %s, retryable = true
                WHERE workspace_id = %s AND id = %s
                """,
                (error_code, error_message, workspace_id, job_id),
            )
            conn.commit()

    def get_storage_object(self, workspace_id: UUID, object_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.storage_objects WHERE workspace_id = %s AND id = %s",
                (workspace_id, object_id),
            )
            return cur.fetchone()

    def mark_intent_ready(
        self,
        *,
        workspace_id: UUID,
        intent_id: UUID,
        manifest_json: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.production_intents
                SET status = 'READY',
                    manifest_validated = true,
                    manifest_json = %s::jsonb,
                    error_code = NULL,
                    error_message = NULL
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (json.dumps(manifest_json), workspace_id, intent_id),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row
