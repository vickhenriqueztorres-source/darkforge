from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from core.errors import AppError, ErrorCode


def _ser_val(v: Any) -> Any:
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "__float__") and type(v).__name__ == "Decimal":
        return float(v)
    if isinstance(v, list):
        return [_ser_val(i) for i in v]
    if isinstance(v, dict):
        return {k: _ser_val(val) for k, val in v.items()}
    return v


def _ser_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: _ser_val(v) for k, v in row.items()}


def _ser_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_ser_row(r) for r in rows if r is not None]  # type: ignore[misc]


def hash_ingest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PostgresExternalAgentsRepository:
    """Repositorio Postgres para telemetria dos 88 agentes externos."""

    def __init__(self, database_url: str) -> None:
        self._dsn = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=8, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Banco Postgres inacessivel para telemetria de agentes externos.",
                http_status=503,
                retryable=True,
            ) from exc

    def get_snapshot(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        pipeline_run_id: UUID | None = None,
        events_limit: int = 80,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM public.v_external_agent_latest_state
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY pipeline_order ASC, agent_key ASC
                """,
                (str(workspace_id), str(channel_id)),
            )
            agents = _ser_rows(cur.fetchall())

            # If a specific pipeline_run_id is requested, also return its executions
            run_executions: list[dict[str, Any]] = []
            if pipeline_run_id is not None:
                cur.execute(
                    """
                    SELECT
                        e.*,
                        cat.display_name, cat.group_key, cat.sub_group, cat.agent_kind,
                        cat.source_path, cat.runtime_lang, cat.studio_room_key, cat.studio_agent_key, cat.pipeline_order
                    FROM public.external_agent_executions AS e
                    JOIN public.external_agent_catalog AS cat ON cat.agent_key = e.agent_key
                    WHERE e.workspace_id = %s AND e.channel_id = %s AND e.pipeline_run_id = %s
                    ORDER BY cat.pipeline_order ASC, e.updated_at DESC
                    """,
                    (str(workspace_id), str(channel_id), str(pipeline_run_id)),
                )
                run_executions = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM public.v_external_pipeline_summary
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY updated_at DESC
                LIMIT 20
                """,
                (str(workspace_id), str(channel_id)),
            )
            pipeline_runs = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM public.v_external_room_rollup
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY room_key ASC
                """,
                (str(workspace_id), str(channel_id)),
            )
            room_rollups = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM public.external_agent_events
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (str(workspace_id), str(channel_id), events_limit),
            )
            recent_events = _ser_rows(list(reversed(cur.fetchall())))
            last_event_id = recent_events[-1]["id"] if recent_events else 0

        return {
            "agents": agents,
            "pipeline_runs": pipeline_runs,
            "run_executions": run_executions,
            "room_rollups": room_rollups,
            "recent_events": recent_events,
            "last_event_id": last_event_id,
        }

    def list_events(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        after_id: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM public.external_agent_events
                WHERE workspace_id = %s AND channel_id = %s AND id > %s
                ORDER BY id ASC
                LIMIT %s
                """,
                (str(workspace_id), str(channel_id), after_id, limit),
            )
            events = _ser_rows(cur.fetchall())
            last_id = events[-1]["id"] if events else after_id
        return {"events": events, "last_event_id": last_id}

    def get_agent_detail(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM public.v_external_agent_latest_state
                WHERE workspace_id = %s AND channel_id = %s AND agent_key = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            agent = _ser_row(cur.fetchone())
            if agent is None:
                return None

            cur.execute(
                """
                SELECT e.*, pr.external_run_id, pr.title AS pipeline_title, pr.pipeline_kind
                FROM public.external_agent_executions AS e
                LEFT JOIN public.external_pipeline_runs AS pr ON pr.id = e.pipeline_run_id
                WHERE e.workspace_id = %s AND e.channel_id = %s AND e.agent_key = %s
                ORDER BY e.updated_at DESC
                LIMIT 25
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            executions = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM public.external_agent_events
                WHERE workspace_id = %s AND channel_id = %s AND agent_key = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            events = _ser_rows(cur.fetchall())

        return {"agent": agent, "executions": executions, "events": events}

    def ingest_events(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        with self._connect() as conn, conn.cursor() as cur:
            for item in items:
                try:
                    cur.execute(
                        """
                        SELECT public.ingest_external_agent_event(
                            %s::uuid, %s::uuid, %s::text, %s::text,
                            %s::text, %s::text, %s::text, %s::text,
                            %s::text, %s::numeric, %s::text, %s::text,
                            %s::text, %s::text, %s::jsonb, %s::jsonb,
                            %s::jsonb, %s::jsonb, %s::text, %s::text,
                            %s::text, %s::text, %s::integer, %s::jsonb
                        ) AS res
                        """,
                        (
                            str(workspace_id),
                            str(channel_id),
                            item["agent_key"],
                            item["status"],
                            item.get("external_run_id"),
                            item.get("pipeline_kind") or "custom",
                            item.get("run_title"),
                            item.get("external_execution_id"),
                            item.get("stage_label"),
                            item.get("progress"),
                            item.get("model_name"),
                            item.get("event_type"),
                            item.get("level") or "info",
                            item.get("message"),
                            json.dumps(item.get("input_summary") or {}, ensure_ascii=False),
                            json.dumps(item.get("output_summary") or {}, ensure_ascii=False),
                            json.dumps(item.get("artifacts") or [], ensure_ascii=False),
                            json.dumps(item.get("metrics") or {}, ensure_ascii=False),
                            item.get("error_code"),
                            item.get("error_message"),
                            item.get("host_name"),
                            item.get("source_repo"),
                            item.get("attempt") or 1,
                            json.dumps(item.get("metadata") or {}, ensure_ascii=False),
                        ),
                    )
                    row = cur.fetchone()
                    if row and row.get("res") is not None:
                        results.append(_ser_val(row["res"]))
                except psycopg.Error as exc:
                    conn.rollback()
                    raise AppError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Falha ao registrar telemetria para '{item.get('agent_key')}': {exc.diag.message_primary or str(exc)}",
                        http_status=422,
                    ) from exc
            conn.commit()
        return results

    def create_ingest_token(
        self,
        workspace_id: UUID,
        channel_id: UUID | None,
        created_by: UUID,
        label: str,
    ) -> dict[str, Any]:
        raw_token = f"df_ext_{secrets.token_urlsafe(28)}"
        token_prefix = raw_token[:14]
        token_hash = hash_ingest_token(raw_token)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.external_ingest_tokens (
                    workspace_id, channel_id, label, token_prefix, token_hash, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, workspace_id, channel_id, label, token_prefix, created_by, revoked_at, last_used_at, created_at
                """,
                (
                    str(workspace_id),
                    str(channel_id) if channel_id else None,
                    label.strip(),
                    token_prefix,
                    token_hash,
                    str(created_by),
                ),
            )
            row = _ser_row(cur.fetchone())
            conn.commit()
        assert row is not None
        row["token"] = raw_token
        return row

    def list_ingest_tokens(
        self,
        workspace_id: UUID,
        channel_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if channel_id is not None:
                cur.execute(
                    """
                    SELECT id, workspace_id, channel_id, label, token_prefix, created_by, revoked_at, last_used_at, created_at
                    FROM public.external_ingest_tokens
                    WHERE workspace_id = %s AND (channel_id = %s OR channel_id IS NULL)
                    ORDER BY created_at DESC
                    """,
                    (str(workspace_id), str(channel_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT id, workspace_id, channel_id, label, token_prefix, created_by, revoked_at, last_used_at, created_at
                    FROM public.external_ingest_tokens
                    WHERE workspace_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(workspace_id),),
                )
            return _ser_rows(cur.fetchall())

    def revoke_ingest_token(self, workspace_id: UUID, token_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.external_ingest_tokens
                SET revoked_at = timezone('utc', now())
                WHERE workspace_id = %s AND id = %s AND revoked_at IS NULL
                RETURNING id, workspace_id, channel_id, label, token_prefix, revoked_at
                """,
                (str(workspace_id), str(token_id)),
            )
            row = _ser_row(cur.fetchone())
            conn.commit()
            return row

    def resolve_ingest_token(self, raw_token: str) -> dict[str, Any] | None:
        token_hash = hash_ingest_token(raw_token.strip())
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.external_ingest_tokens
                SET last_used_at = timezone('utc', now())
                WHERE token_hash = %s AND revoked_at IS NULL
                RETURNING id, workspace_id, channel_id, label
                """,
                (token_hash,),
            )
            row = _ser_row(cur.fetchone())
            conn.commit()
            return row
