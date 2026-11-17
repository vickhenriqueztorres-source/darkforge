from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from core.errors import AppError, ErrorCode
from core.studio.registry import AGENT_REGISTRY, assert_stage_transition


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


def _canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PostgresStudioRepository:
    """Repositorio transacional e de leitura para o Estúdio de Conteúdo (UI-01..UI-06)."""

    def __init__(self, database_url: str) -> None:
        self._dsn = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=8, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Banco Postgres inacessivel para operacao do Studio.",
                http_status=503,
                retryable=True,
            ) from exc

    # ------------------------------------------------------------------
    # Leitura: Snapshot, Eventos, Salas, Agentes, Content Items
    # ------------------------------------------------------------------
    def get_channel(self, workspace_id: UUID, channel_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.*, pv.version_number AS profile_version_number, pv.niche, pv.positioning,
                       pv.editorial_theme, pv.language, pv.country, pv.pillars_json,
                       pv.restrictions_json, pv.audience_json, pv.voice_json
                FROM public.channels AS c
                LEFT JOIN public.channel_profile_versions AS pv
                  ON pv.id = c.active_profile_version_id AND pv.workspace_id = c.workspace_id
                WHERE c.workspace_id = %s AND c.id = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id)),
            )
            return _ser_row(cur.fetchone())

    def ensure_channel_agents(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        darkforge_available: bool = False,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.channel_agents (workspace_id, channel_id, agent_key, enabled, avatar_key, config)
                SELECT
                    %s,
                    %s,
                    ad.key,
                    CASE WHEN ad.key = 'edicao' AND NOT %s THEN false ELSE true END,
                    ad.key,
                    CASE
                        WHEN ad.key = 'edicao' AND NOT %s THEN jsonb_build_object('unavailable_reason', 'DARKFORGE_UNAVAILABLE')
                        ELSE '{}'::jsonb
                    END
                FROM public.agent_definitions AS ad
                WHERE ad.active = true
                ON CONFLICT (channel_id, agent_key) DO NOTHING
                """,
                (str(workspace_id), str(channel_id), darkforge_available, darkforge_available),
            )
            conn.commit()
            cur.execute(
                "SELECT * FROM public.channel_agents WHERE workspace_id = %s AND channel_id = %s ORDER BY agent_key ASC",
                (str(workspace_id), str(channel_id)),
            )
            return _ser_rows(cur.fetchall())

    def get_snapshot(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        content_item_id: UUID | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.workspace_id, c.display_name, c.handle, c.status,
                       c.external_channel_id, c.active_profile_version_id,
                       pv.version_number AS profile_version_number,
                       pv.niche, pv.language, pv.editorial_theme
                FROM public.channels AS c
                LEFT JOIN public.channel_profile_versions AS pv
                  ON pv.id = c.active_profile_version_id AND pv.workspace_id = c.workspace_id
                WHERE c.workspace_id = %s AND c.id = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id)),
            )
            channel = _ser_row(cur.fetchone())
            if channel is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado neste workspace.", http_status=404)

            cur.execute(
                """
                SELECT
                    s.workspace_id, s.channel_id, s.channel_agent_id, s.agent_key, s.enabled,
                    s.config, s.model_policy, s.monthly_budget_cents, s.room_key, s.description,
                    s.requires_approval, s.contract_version, s.display_name, s.avatar_key,
                    s.run_id, s.job_id, s.content_item_id, s.status, s.stage_label,
                    s.progress, s.attempt, s.heartbeat_at, s.started_at, s.finished_at,
                    s.error_code, s.error_message, s.cost_estimate_cents, s.run_created_at
                FROM public.v_studio_agent_state AS s
                WHERE s.workspace_id = %s AND s.channel_id = %s
                """,
                (str(workspace_id), str(channel_id)),
            )
            agents = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT r.workspace_id, r.channel_id, r.room_key, r.room_label, r.sort_order,
                       r.working, r.awaiting_human, r.blocked, r.failed, r.agents, r.disabled_agents
                FROM public.v_studio_room_state AS r
                WHERE r.workspace_id = %s AND r.channel_id = %s
                ORDER BY r.sort_order ASC
                """,
                (str(workspace_id), str(channel_id)),
            )
            rooms = _ser_rows(cur.fetchall())

            # Content items do canal
            cur.execute(
                """
                SELECT * FROM public.v_content_pipeline
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY updated_at DESC
                LIMIT 25
                """,
                (str(workspace_id), str(channel_id)),
            )
            content_items = _ser_rows(cur.fetchall())

            active_item: dict[str, Any] | None = None
            if content_item_id is not None:
                active_item = next(
                    (ci for ci in content_items if ci["content_item_id"] == str(content_item_id)),
                    None,
                )
                if active_item is None:
                    cur.execute(
                        """
                        SELECT * FROM public.v_content_pipeline
                        WHERE workspace_id = %s AND channel_id = %s AND content_item_id = %s
                        LIMIT 1
                        """,
                        (str(workspace_id), str(channel_id), str(content_item_id)),
                    )
                    active_item = _ser_row(cur.fetchone())
            elif content_items:
                active_item = next(
                    (ci for ci in content_items if ci["stage"] not in ("arquivado",)),
                    content_items[0],
                )

            active_item_id = active_item["content_item_id"] if active_item else None

            # Ultimo output opportunity (do content_item ativo ou do canal)
            if active_item_id:
                cur.execute(
                    """
                    SELECT ao.*,
                           (SELECT jsonb_agg(jsonb_build_object(
                                'source_kind', s.source_kind, 'source_id', s.source_id,
                                'locator', s.locator, 'note', s.note
                           ))
                           FROM public.agent_output_sources AS s
                           WHERE s.output_id = ao.id) AS sources
                    FROM public.agent_outputs AS ao
                    WHERE ao.workspace_id = %s AND ao.channel_id = %s
                      AND ao.content_item_id = %s AND ao.output_type = 'opportunity'
                    ORDER BY ao.version DESC
                    LIMIT 1
                    """,
                    (str(workspace_id), str(channel_id), active_item_id),
                )
            else:
                cur.execute(
                    """
                    SELECT ao.*,
                           (SELECT jsonb_agg(jsonb_build_object(
                                'source_kind', s.source_kind, 'source_id', s.source_id,
                                'locator', s.locator, 'note', s.note
                           ))
                           FROM public.agent_output_sources AS s
                           WHERE s.output_id = ao.id) AS sources
                    FROM public.agent_outputs AS ao
                    WHERE ao.workspace_id = %s AND ao.channel_id = %s AND ao.output_type = 'opportunity'
                    ORDER BY ao.created_at DESC
                    LIMIT 1
                    """,
                    (str(workspace_id), str(channel_id)),
                )
            latest_opportunity = _ser_row(cur.fetchone())

            # Ultimo channel_insight (agente dados) + metric_snapshots reais
            cur.execute(
                """
                SELECT * FROM public.agent_outputs
                WHERE workspace_id = %s AND channel_id = %s AND output_type = 'channel_insight'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id)),
            )
            latest_insight = _ser_row(cur.fetchone())

            cur.execute(
                """
                SELECT DISTINCT ON (ms.metric_id)
                    ms.metric_id, md.display_name, ms.availability, ms.value_num,
                    ms.period_start, ms.period_end, ms.fetched_at, ms.source
                FROM public.metric_snapshots AS ms
                JOIN public.metric_definitions AS md ON md.metric_id = ms.metric_id
                WHERE ms.workspace_id = %s AND ms.channel_id = %s AND ms.video_id IS NULL
                  AND ms.metric_id IN ('yt.analytics.views', 'yt.analytics.impressions_ctr', 'yt.analytics.avg_view_duration_sec')
                ORDER BY ms.metric_id, ms.period_end DESC, ms.source_revision DESC, ms.fetched_at DESC
                """,
                (str(workspace_id), str(channel_id)),
            )
            raw_metrics = _ser_rows(cur.fetchall())

            # Serie diaria de views (se houver) para mini sparkline real
            cur.execute(
                """
                SELECT period_end AS day, value_num
                FROM public.metric_snapshots
                WHERE workspace_id = %s AND channel_id = %s AND video_id IS NULL
                  AND metric_id = 'yt.analytics.views' AND granularity = 'day' AND availability = 'available'
                ORDER BY period_end ASC
                LIMIT 30
                """,
                (str(workspace_id), str(channel_id)),
            )
            views_series = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT sync_scope, freshness_status, last_successful_sync_at
                FROM public.sync_cursors
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY updated_at DESC
                LIMIT 3
                """,
                (str(workspace_id), str(channel_id)),
            )
            sync_cursors = _ser_rows(cur.fetchall())

            # Eventos recentes + cursor
            cur.execute(
                """
                SELECT * FROM public.agent_events
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY id DESC
                LIMIT 60
                """,
                (str(workspace_id), str(channel_id)),
            )
            recent_events_desc = _ser_rows(cur.fetchall())
            recent_events = list(reversed(recent_events_desc))
            last_event_id = recent_events_desc[0]["id"] if recent_events_desc else 0

            # Ultimo evento por agente para o content item ativo (ou canal)
            if active_item_id:
                cur.execute(
                    """
                    SELECT DISTINCT ON (agent_key) *
                    FROM public.agent_events
                    WHERE workspace_id = %s AND channel_id = %s
                      AND (content_item_id = %s OR content_item_id IS NULL)
                    ORDER BY agent_key, id DESC
                    """,
                    (str(workspace_id), str(channel_id), active_item_id),
                )
            else:
                cur.execute(
                    """
                    SELECT DISTINCT ON (agent_key) *
                    FROM public.agent_events
                    WHERE workspace_id = %s AND channel_id = %s
                    ORDER BY agent_key, id DESC
                    """,
                    (str(workspace_id), str(channel_id)),
                )
            latest_event_by_agent = {r["agent_key"]: r for r in _ser_rows(cur.fetchall())}

            # Aprovacoes recentes e outputs do item ativo
            item_outputs: list[dict[str, Any]] = []
            pending_handoffs: list[dict[str, Any]] = []
            approvals: list[dict[str, Any]] = []
            if active_item_id:
                cur.execute(
                    """
                    SELECT ao.*,
                           COALESCE(
                               (SELECT jsonb_agg(jsonb_build_object(
                                    'source_kind', s.source_kind, 'source_id', s.source_id,
                                    'locator', s.locator, 'note', s.note
                               ))
                               FROM public.agent_output_sources AS s
                               WHERE s.output_id = ao.id),
                               '[]'::jsonb
                           ) AS sources
                    FROM public.agent_outputs AS ao
                    WHERE ao.workspace_id = %s AND ao.content_item_id = %s
                    ORDER BY ao.created_at DESC
                    LIMIT 40
                    """,
                    (str(workspace_id), active_item_id),
                )
                item_outputs = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT * FROM public.agent_handoffs
                    WHERE workspace_id = %s AND content_item_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(workspace_id), active_item_id),
                )
                pending_handoffs = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT * FROM public.approvals
                    WHERE workspace_id = %s AND content_item_id = %s
                    ORDER BY decided_at DESC
                    LIMIT 30
                    """,
                    (str(workspace_id), active_item_id),
                )
                approvals = _ser_rows(cur.fetchall())

        return {
            "channel": channel,
            "rooms": rooms,
            "agents": agents,
            "content_items": content_items,
            "active_content_item": active_item,
            "latest_opportunity": latest_opportunity,
            "latest_insight": latest_insight,
            "raw_metrics": raw_metrics,
            "views_series": views_series,
            "sync_cursors": sync_cursors,
            "recent_events": recent_events,
            "latest_event_by_agent": latest_event_by_agent,
            "item_outputs": item_outputs,
            "handoffs": pending_handoffs,
            "approvals": approvals,
            "last_event_id": last_event_id,
        }

    def get_events_after(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        after_id: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.agent_events
                WHERE workspace_id = %s AND channel_id = %s AND id > %s
                ORDER BY id ASC
                LIMIT %s
                """,
                (str(workspace_id), str(channel_id), max(0, after_id), safe_limit),
            )
            return _ser_rows(cur.fetchall())

    def get_room_detail(self, workspace_id: UUID, channel_id: UUID, room_key: str) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.studio_rooms WHERE key = %s", (room_key,))
            room = _ser_row(cur.fetchone())
            if room is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Sala nao encontrada.", http_status=404)

            cur.execute(
                """
                SELECT * FROM public.v_studio_agent_state
                WHERE workspace_id = %s AND channel_id = %s AND room_key = %s
                ORDER BY agent_key ASC
                """,
                (str(workspace_id), str(channel_id), room_key),
            )
            agents = _ser_rows(cur.fetchall())
            agent_keys = [a["agent_key"] for a in agents]

            runs: list[dict[str, Any]] = []
            outputs: list[dict[str, Any]] = []
            if agent_keys:
                cur.execute(
                    """
                    SELECT * FROM public.agent_runs
                    WHERE workspace_id = %s AND channel_id = %s AND agent_key = ANY(%s)
                    ORDER BY created_at DESC
                    LIMIT 25
                    """,
                    (str(workspace_id), str(channel_id), agent_keys),
                )
                runs = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT ao.*,
                           COALESCE(
                               (SELECT jsonb_agg(jsonb_build_object(
                                    'source_kind', s.source_kind, 'source_id', s.source_id,
                                    'locator', s.locator, 'note', s.note
                               ))
                               FROM public.agent_output_sources AS s
                               WHERE s.output_id = ao.id),
                               '[]'::jsonb
                           ) AS sources
                    FROM public.agent_outputs AS ao
                    WHERE ao.workspace_id = %s AND ao.channel_id = %s AND ao.agent_key = ANY(%s)
                    ORDER BY ao.created_at DESC
                    LIMIT 20
                    """,
                    (str(workspace_id), str(channel_id), agent_keys),
                )
                outputs = _ser_rows(cur.fetchall())

        return {"room": room, "agents": agents, "recent_runs": runs, "recent_outputs": outputs}

    def get_agent_detail(self, workspace_id: UUID, channel_id: UUID, agent_key: str) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.v_studio_agent_state
                WHERE workspace_id = %s AND channel_id = %s AND agent_key = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            agent = _ser_row(cur.fetchone())
            if agent is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agente nao encontrado neste canal.", http_status=404)

            cur.execute(
                """
                SELECT * FROM public.agent_runs
                WHERE workspace_id = %s AND channel_id = %s AND agent_key = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            runs = _ser_rows(cur.fetchall())

            cur.execute(
                """
                SELECT ao.*,
                       COALESCE(
                           (SELECT jsonb_agg(jsonb_build_object(
                                'source_kind', s.source_kind, 'source_id', s.source_id,
                                'locator', s.locator, 'note', s.note
                           ))
                           FROM public.agent_output_sources AS s
                           WHERE s.output_id = ao.id),
                           '[]'::jsonb
                       ) AS sources
                FROM public.agent_outputs AS ao
                WHERE ao.workspace_id = %s AND ao.channel_id = %s AND ao.agent_key = %s
                ORDER BY ao.created_at DESC
                LIMIT 15
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            outputs = _ser_rows(cur.fetchall())

        return {"agent": agent, "runs": runs, "outputs": outputs}

    # ------------------------------------------------------------------
    # Content Items & Configuracao da Equipe
    # ------------------------------------------------------------------
    def create_content_item(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        working_title: str,
        actor_id: UUID,
        initial_stage: str = "pesquisa",
    ) -> tuple[dict[str, Any], bool]:
        clean_title = working_title.strip()
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.content_items
                WHERE workspace_id = %s AND channel_id = %s AND lower(working_title) = lower(%s)
                  AND stage <> 'arquivado'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id), clean_title),
            )
            existing = _ser_row(cur.fetchone())
            if existing is not None:
                return existing, True

            cur.execute(
                """
                INSERT INTO public.content_items (workspace_id, channel_id, working_title, stage, status, created_by)
                VALUES (%s, %s, %s, %s, 'ativo', %s)
                RETURNING *
                """,
                (str(workspace_id), str(channel_id), clean_title, initial_stage, str(actor_id)),
            )
            row = _ser_row(cur.fetchone())
            conn.commit()
            assert row is not None
            return row, False

    def get_content_item(self, workspace_id: UUID, content_item_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.content_items WHERE workspace_id = %s AND id = %s LIMIT 1",
                (str(workspace_id), str(content_item_id)),
            )
            return _ser_row(cur.fetchone())

    def transition_content_item_stage(
        self,
        workspace_id: UUID,
        content_item_id: UUID,
        target_stage: str,
        target_status: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.content_items WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(content_item_id)),
            )
            current = cur.fetchone()
            if current is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Content item nao encontrado.", http_status=404)
            assert_stage_transition(current["stage"], target_stage)
            cur.execute(
                """
                UPDATE public.content_items
                SET stage = %s,
                    status = COALESCE(%s, status)
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (target_stage, target_status, str(workspace_id), str(content_item_id)),
            )
            updated = _ser_row(cur.fetchone())
            conn.commit()
            assert updated is not None
            return updated

    def update_channel_agent(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
        enabled: bool | None = None,
        display_name: str | None = None,
        avatar_key: str | None = None,
        model_policy: dict[str, Any] | None = None,
        monthly_budget_cents: int | None = None,
        clear_budget: bool = False,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.channel_agents
                WHERE workspace_id = %s AND channel_id = %s AND agent_key = %s
                FOR UPDATE
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            row = cur.fetchone()
            if row is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agente do canal nao encontrado.", http_status=404)

            new_enabled = row["enabled"] if enabled is None else enabled
            new_display = row["display_name"] if display_name is None else (display_name.strip() or None)
            new_avatar = row["avatar_key"] if avatar_key is None else (avatar_key.strip() or agent_key)
            new_policy = row["model_policy"] if model_policy is None else model_policy
            new_budget = None if clear_budget else (row["monthly_budget_cents"] if monthly_budget_cents is None else monthly_budget_cents)
            new_config = dict(row.get("config") or {})
            if new_enabled and "unavailable_reason" in new_config:
                new_config.pop("unavailable_reason", None)

            cur.execute(
                """
                UPDATE public.channel_agents
                SET enabled = %s,
                    display_name = %s,
                    avatar_key = %s,
                    model_policy = %s::jsonb,
                    monthly_budget_cents = %s,
                    config = %s::jsonb
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_enabled,
                    new_display,
                    new_avatar,
                    json.dumps(new_policy),
                    new_budget,
                    json.dumps(new_config),
                    str(row["id"]),
                ),
            )
            updated = _ser_row(cur.fetchone())
            conn.commit()
            assert updated is not None
            return updated

    # ------------------------------------------------------------------
    # Enfileiramento e Controle de Runs (UI-02-T03, UI-06-T02)
    # ------------------------------------------------------------------
    def enqueue_agent_run(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
        actor_id: UUID,
        idempotency_key: str,
        content_item_id: UUID | None = None,
        reason: str = "manual",
        parent_run_id: UUID | None = None,
        attempt: int = 1,
        priority: int = 60,
        allow_disabled: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_runs WHERE workspace_id = %s AND idempotency_key = %s LIMIT 1",
                (str(workspace_id), idempotency_key),
            )
            existing = _ser_row(cur.fetchone())
            if existing is not None:
                return existing, True

            cur.execute(
                """
                SELECT ca.*, ad.display_name AS default_name
                FROM public.channel_agents AS ca
                JOIN public.agent_definitions AS ad ON ad.key = ca.agent_key
                WHERE ca.workspace_id = %s AND ca.channel_id = %s AND ca.agent_key = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            ca = cur.fetchone()
            if ca is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, f"Agente '{agent_key}' nao encontrado no canal.", http_status=404)
            if not ca["enabled"] and not allow_disabled:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Agente '{agent_key}' esta desativado neste canal.",
                    http_status=409,
                    details={"agent_key": agent_key, "config": ca.get("config") or {}},
                )

            run_id = uuid4()
            job_id = uuid4()
            job_idem = f"agent-{agent_key}-{idempotency_key}"[:120]
            payload_json = {
                "run_id": str(run_id),
                "channel_id": str(channel_id),
                "channel_agent_id": str(ca["id"]),
                "agent_key": agent_key,
                "content_item_id": str(content_item_id) if content_item_id else None,
                "reason": reason,
            }
            payload_hash = _canonical_hash(payload_json)
            correlation_id = uuid4()

            cur.execute(
                """
                INSERT INTO public.jobs (
                    id, workspace_id, channel_id, job_type, status, priority,
                    idempotency_key, payload_hash, payload_json, total_steps,
                    correlation_id, created_by
                )
                VALUES (%s, %s, %s, 'agent.execute', 'QUEUED', %s, %s, %s, %s::jsonb, 4, %s, %s)
                ON CONFLICT (workspace_id, job_type, idempotency_key) DO NOTHING
                RETURNING id
                """,
                (
                    str(job_id),
                    str(workspace_id),
                    str(channel_id),
                    priority,
                    job_idem,
                    payload_hash,
                    json.dumps(payload_json),
                    str(correlation_id),
                    str(actor_id),
                ),
            )
            job_row = cur.fetchone()
            if job_row is None:
                cur.execute(
                    "SELECT * FROM public.agent_runs WHERE workspace_id = %s AND idempotency_key = %s LIMIT 1",
                    (str(workspace_id), idempotency_key),
                )
                dedup = _ser_row(cur.fetchone())
                if dedup is not None:
                    return dedup, True
                raise AppError(ErrorCode.IDEMPOTENCY_CONFLICT, "Conflito de idempotencia ao enfileirar agente.", http_status=409)

            cur.execute(
                """
                INSERT INTO public.agent_runs (
                    id, workspace_id, channel_id, channel_agent_id, agent_key,
                    content_item_id, job_id, parent_run_id, status, stage_label,
                    progress, attempt, idempotency_key, prompt_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued', 'na fila', NULL, %s, %s, 'v1')
                RETURNING *
                """,
                (
                    str(run_id),
                    str(workspace_id),
                    str(channel_id),
                    str(ca["id"]),
                    agent_key,
                    str(content_item_id) if content_item_id else None,
                    str(job_id),
                    str(parent_run_id) if parent_run_id else None,
                    attempt,
                    idempotency_key,
                ),
            )
            run_row = _ser_row(cur.fetchone())
            assert run_row is not None

            label = ca.get("display_name") or ca["default_name"]
            cur.execute(
                """
                INSERT INTO public.agent_events (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    seq, event_type, summary, payload
                )
                VALUES (%s, %s, %s, %s, %s, 1, 'run_queued', %s, %s::jsonb)
                """,
                (
                    str(workspace_id),
                    str(channel_id),
                    str(run_id),
                    str(content_item_id) if content_item_id else None,
                    agent_key,
                    f"{label}: na fila ({reason})",
                    json.dumps({"reason": reason, "job_id": str(job_id)}),
                ),
            )
            conn.commit()
            return run_row, False

    def cancel_agent_run(self, workspace_id: UUID, run_id: UUID) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_runs WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(run_id)),
            )
            run = cur.fetchone()
            if run is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Execucao de agente nao encontrada.", http_status=404)
            if run["status"] in ("done", "cancelled"):
                return _ser_row(run)  # type: ignore[return-value]

            if run["job_id"]:
                cur.execute(
                    "SELECT status FROM public.jobs WHERE id = %s FOR UPDATE",
                    (str(run["job_id"]),),
                )
                job = cur.fetchone()
                if job and job["status"] in ("QUEUED", "PAUSED", "RECOVERABLE", "BLOCKED"):
                    cur.execute(
                        """
                        UPDATE public.jobs
                        SET status = 'CANCELLED', cancel_requested = true, completed_at = timezone('utc', now())
                        WHERE id = %s
                        """,
                        (str(run["job_id"]),),
                    )
                elif job and job["status"] == "RUNNING":
                    cur.execute(
                        "UPDATE public.jobs SET status = 'CANCEL_REQUESTED', cancel_requested = true WHERE id = %s",
                        (str(run["job_id"]),),
                    )

            cur.execute(
                """
                UPDATE public.agent_runs
                SET status = 'cancelled', stage_label = 'cancelado', finished_at = timezone('utc', now())
                WHERE id = %s
                RETURNING *
                """,
                (str(run_id),),
            )
            updated = _ser_row(cur.fetchone())
            cur.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM public.agent_events WHERE run_id = %s", (str(run_id),))
            next_seq = cur.fetchone()["next_seq"]
            cur.execute(
                """
                INSERT INTO public.agent_events (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    seq, event_type, summary, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'cancelled', 'Execucao cancelada pelo operador', '{}'::jsonb)
                """,
                (
                    str(workspace_id),
                    str(run["channel_id"]),
                    str(run_id),
                    str(run["content_item_id"]) if run["content_item_id"] else None,
                    run["agent_key"],
                    next_seq,
                ),
            )
            conn.commit()
            assert updated is not None
            return updated

    def get_run(self, workspace_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_runs WHERE workspace_id = %s AND id = %s LIMIT 1",
                (str(workspace_id), str(run_id)),
            )
            return _ser_row(cur.fetchone())

    # ------------------------------------------------------------------
    # Worker Runtime & Persistencia Atomica com Fencing (UI-02-T04..T08)
    # ------------------------------------------------------------------
    def mark_run_started(self, run_id: UUID, fencing_token: int) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_runs WHERE id = %s FOR UPDATE",
                (str(run_id),),
            )
            run = cur.fetchone()
            if run is None:
                return None

            if run["job_id"]:
                cur.execute(
                    "SELECT status, fencing_token, attempt_count FROM public.jobs WHERE id = %s FOR UPDATE",
                    (str(run["job_id"]),),
                )
                job = cur.fetchone()
                if not job or int(job["fencing_token"]) != fencing_token or job["status"] not in ("RUNNING", "CANCEL_REQUESTED"):
                    raise AppError(ErrorCode.FENCING_TOKEN_STALE, "Lease/fencing expirado ao iniciar run.", http_status=409)
                attempt_num = max(int(run["attempt"]), int(job["attempt_count"]))
            else:
                attempt_num = int(run["attempt"])

            cur.execute(
                """
                UPDATE public.agent_runs
                SET status = 'working',
                    stage_label = 'carregando contexto autorizado',
                    attempt = %s,
                    started_at = COALESCE(started_at, timezone('utc', now())),
                    heartbeat_at = timezone('utc', now()),
                    error_code = NULL,
                    error_message = NULL
                WHERE id = %s
                RETURNING *
                """,
                (attempt_num, str(run_id)),
            )
            updated = _ser_row(cur.fetchone())
            cur.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM public.agent_events WHERE run_id = %s", (str(run_id),))
            next_seq = cur.fetchone()["next_seq"]
            cur.execute(
                """
                INSERT INTO public.agent_events (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    seq, event_type, summary, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'run_started', 'Iniciando execucao na sala', %s::jsonb)
                """,
                (
                    str(run["workspace_id"]),
                    str(run["channel_id"]),
                    str(run_id),
                    str(run["content_item_id"]) if run["content_item_id"] else None,
                    run["agent_key"],
                    next_seq,
                    json.dumps({"attempt": attempt_num, "fencing_token": fencing_token}),
                ),
            )
            conn.commit()
            return updated

    def update_run_progress(
        self,
        run_id: UUID,
        fencing_token: int,
        *,
        stage_label: str,
        progress: float | None,
        summary: str,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.agent_runs WHERE id = %s FOR UPDATE", (str(run_id),))
            run = cur.fetchone()
            if run is None:
                return
            if run["job_id"]:
                cur.execute(
                    "SELECT status, fencing_token FROM public.jobs WHERE id = %s FOR UPDATE",
                    (str(run["job_id"]),),
                )
                job = cur.fetchone()
                if not job or int(job["fencing_token"]) != fencing_token or job["status"] not in ("RUNNING", "CANCEL_REQUESTED"):
                    raise AppError(ErrorCode.FENCING_TOKEN_STALE, "Fencing token obsoleto ao atualizar progresso.", http_status=409)

            cur.execute(
                """
                UPDATE public.agent_runs
                SET stage_label = %s,
                    progress = %s,
                    heartbeat_at = timezone('utc', now())
                WHERE id = %s
                """,
                (stage_label, progress, str(run_id)),
            )
            cur.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM public.agent_events WHERE run_id = %s", (str(run_id),))
            next_seq = cur.fetchone()["next_seq"]
            cur.execute(
                """
                INSERT INTO public.agent_events (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    seq, event_type, summary, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'stage_changed', %s, %s::jsonb)
                """,
                (
                    str(run["workspace_id"]),
                    str(run["channel_id"]),
                    str(run_id),
                    str(run["content_item_id"]) if run["content_item_id"] else None,
                    run["agent_key"],
                    next_seq,
                    summary[:200],
                    json.dumps({"stage_label": stage_label, "progress": progress}),
                ),
            )
            conn.commit()

    def load_authorized_context(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
        content_item_id: UUID | None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.*, pv.id AS profile_version_id, pv.version_number, pv.niche,
                       pv.positioning, pv.editorial_theme, pv.language, pv.country,
                       pv.pillars_json, pv.audience_json, pv.voice_json, pv.restrictions_json
                FROM public.channels AS c
                LEFT JOIN public.channel_profile_versions AS pv
                  ON pv.id = c.active_profile_version_id AND pv.workspace_id = c.workspace_id
                WHERE c.workspace_id = %s AND c.id = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id)),
            )
            channel = _ser_row(cur.fetchone())
            if channel is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado.", http_status=404)

            cur.execute(
                """
                SELECT ca.*, ad.display_name AS default_display_name, ad.room_key, ad.requires_approval
                FROM public.channel_agents AS ca
                JOIN public.agent_definitions AS ad ON ad.key = ca.agent_key
                WHERE ca.workspace_id = %s AND ca.channel_id = %s AND ca.agent_key = %s
                LIMIT 1
                """,
                (str(workspace_id), str(channel_id), agent_key),
            )
            channel_agent = _ser_row(cur.fetchone())

            content_item: dict[str, Any] | None = None
            handoffs: list[dict[str, Any]] = []
            prior_outputs: list[dict[str, Any]] = []
            if content_item_id is not None:
                cur.execute(
                    "SELECT * FROM public.content_items WHERE workspace_id = %s AND id = %s LIMIT 1",
                    (str(workspace_id), str(content_item_id)),
                )
                content_item = _ser_row(cur.fetchone())
                cur.execute(
                    """
                    SELECT h.*, ao.output_type, ao.content, ao.version AS output_version, ao.status AS output_status
                    FROM public.agent_handoffs AS h
                    JOIN public.agent_outputs AS ao ON ao.id = h.output_id
                    WHERE h.workspace_id = %s AND h.content_item_id = %s
                      AND h.to_agent_key = %s AND h.status IN ('pending', 'accepted')
                    ORDER BY h.created_at ASC
                    """,
                    (str(workspace_id), str(content_item_id), agent_key),
                )
                handoffs = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT DISTINCT ON (output_type) *
                    FROM public.agent_outputs
                    WHERE workspace_id = %s AND content_item_id = %s
                      AND status IN ('validated', 'approved')
                    ORDER BY output_type, version DESC
                    """,
                    (str(workspace_id), str(content_item_id)),
                )
                prior_outputs = _ser_rows(cur.fetchall())

            # Entradas especificas autorizadas por agente
            metrics: list[dict[str, Any]] = []
            references: list[dict[str, Any]] = []
            studio_outliers: list[dict[str, Any]] = []
            google_trends: list[dict[str, Any]] = []
            knowledge_chunks: list[dict[str, Any]] = []
            production_intents: list[dict[str, Any]] = []
            calendar_items: list[dict[str, Any]] = []

            if agent_key in ("dados", "estrategia"):
                cur.execute(
                    """
                    SELECT id, metric_id, availability, value_num, period_start, period_end, fetched_at
                    FROM public.metric_snapshots
                    WHERE workspace_id = %s AND channel_id = %s AND video_id IS NULL
                    ORDER BY period_end DESC, fetched_at DESC
                    LIMIT 24
                    """,
                    (str(workspace_id), str(channel_id)),
                )
                metrics = _ser_rows(cur.fetchall())

            if agent_key in ("pesquisa", "estrategia", "titulos", "thumbnail"):
                cur.execute(
                    """
                    SELECT id, external_video_id, canonical_url, title, public_views_snapshot, snapshot_observed_at
                    FROM public.reference_videos
                    WHERE workspace_id = %s AND curation_status = 'approved'
                    ORDER BY snapshot_observed_at DESC
                    LIMIT 12
                    """,
                    (str(workspace_id),),
                )
                references = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT id, external_video_id, canonical_url, title, outlier_ratio, outlier_tier, created_at
                    FROM public.studio_video_outliers
                    WHERE workspace_id = %s AND channel_id = %s
                    ORDER BY outlier_ratio DESC NULLS LAST, created_at DESC
                    LIMIT 8
                    """,
                    (str(workspace_id), str(channel_id)),
                )
                studio_outliers = _ser_rows(cur.fetchall())

                cur.execute(
                    """
                    SELECT id, keyword, verdict, direction_12m, durability_5y, created_at
                    FROM public.google_trends_validations
                    WHERE workspace_id = %s AND (channel_id = %s OR channel_id IS NULL)
                    ORDER BY created_at DESC
                    LIMIT 6
                    """,
                    (str(workspace_id), str(channel_id)),
                )
                google_trends = _ser_rows(cur.fetchall())

            if agent_key in ("estrategia", "roteiro"):
                cur.execute(
                    """
                    SELECT kc.id AS chunk_id, kc.source_id, ks.title AS source_title,
                           ks.curation_level, kc.chunk_text
                    FROM public.knowledge_chunks AS kc
                    JOIN public.knowledge_sources AS ks ON ks.id = kc.source_id
                    WHERE kc.workspace_id = %s
                      AND ks.status = 'APPROVED'
                      AND ks.curation_level IN ('L2', 'L3')
                      AND ks.allowed_in_generation = true
                    ORDER BY kc.created_at DESC
                    LIMIT 8
                    """,
                    (str(workspace_id),),
                )
                knowledge_chunks = _ser_rows(cur.fetchall())

            if agent_key == "edicao":
                cur.execute(
                    """
                    SELECT id, brief_id, brief_version, status, manifest_validated, manifest_json, job_id
                    FROM public.production_intents
                    WHERE workspace_id = %s AND channel_id = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    (str(workspace_id), str(channel_id)),
                )
                production_intents = _ser_rows(cur.fetchall())

            if agent_key == "publicacao":
                cur.execute(
                    """
                    SELECT id, title, scheduled_for, status
                    FROM public.editorial_calendar_items
                    WHERE workspace_id = %s AND channel_id = %s
                    ORDER BY scheduled_for ASC
                    LIMIT 10
                    """,
                    (str(workspace_id), str(channel_id)),
                )
                calendar_items = _ser_rows(cur.fetchall())

        return {
            "channel": channel,
            "channel_agent": channel_agent,
            "content_item": content_item,
            "handoffs": handoffs,
            "prior_outputs": prior_outputs,
            "metrics": metrics,
            "references": references,
            "studio_outliers": studio_outliers,
            "google_trends": google_trends,
            "knowledge_chunks": knowledge_chunks,
            "production_intents": production_intents,
            "calendar_items": calendar_items,
        }

    def verify_sources_in_scope(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        sources: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Retorna (fontes_validas, fontes_invalidas) garantindo isolamento por workspace/canal."""
        valid: list[dict[str, Any]] = []
        invalid: list[dict[str, Any]] = []
        with self._connect() as conn, conn.cursor() as cur:
            for src in sources:
                kind = src.get("kind")
                sid = str(src.get("id") or "")
                ok = False
                try:
                    uid = UUID(sid)
                except ValueError:
                    uid = None

                if kind == "profile_version" and uid is not None:
                    cur.execute(
                        "SELECT 1 FROM public.channel_profile_versions WHERE id = %s AND workspace_id = %s AND channel_id = %s",
                        (str(uid), str(workspace_id), str(channel_id)),
                    )
                    ok = cur.fetchone() is not None
                elif kind == "metric":
                    if uid is not None:
                        cur.execute(
                            "SELECT 1 FROM public.metric_snapshots WHERE id = %s AND workspace_id = %s AND channel_id = %s",
                            (str(uid), str(workspace_id), str(channel_id)),
                        )
                        ok = cur.fetchone() is not None
                    else:
                        cur.execute("SELECT 1 FROM public.metric_definitions WHERE metric_id = %s", (sid,))
                        ok = cur.fetchone() is not None
                elif kind == "research_reference" and uid is not None:
                    cur.execute(
                        """
                        SELECT 1 FROM public.reference_videos WHERE id = %s AND workspace_id = %s
                        UNION ALL
                        SELECT 1 FROM public.studio_video_outliers WHERE id = %s AND workspace_id = %s AND channel_id = %s
                        UNION ALL
                        SELECT 1 FROM public.google_trends_validations WHERE id = %s AND workspace_id = %s
                        LIMIT 1
                        """,
                        (str(uid), str(workspace_id), str(uid), str(workspace_id), str(channel_id), str(uid), str(workspace_id)),
                    )
                    ok = cur.fetchone() is not None
                elif kind == "knowledge_chunk" and uid is not None:
                    cur.execute(
                        "SELECT 1 FROM public.knowledge_chunks WHERE id = %s AND workspace_id = %s",
                        (str(uid), str(workspace_id)),
                    )
                    ok = cur.fetchone() is not None
                elif kind == "agent_output" and uid is not None:
                    cur.execute(
                        "SELECT 1 FROM public.agent_outputs WHERE id = %s AND workspace_id = %s AND channel_id = %s",
                        (str(uid), str(workspace_id), str(channel_id)),
                    )
                    ok = cur.fetchone() is not None
                elif kind == "artifact" and uid is not None:
                    cur.execute(
                        """
                        SELECT 1 FROM public.artifacts WHERE id = %s AND workspace_id = %s
                        UNION ALL
                        SELECT 1 FROM public.production_intents WHERE id = %s AND workspace_id = %s AND channel_id = %s
                        LIMIT 1
                        """,
                        (str(uid), str(workspace_id), str(uid), str(workspace_id), str(channel_id)),
                    )
                    ok = cur.fetchone() is not None

                if ok:
                    valid.append(src)
                else:
                    invalid.append(src)
        return valid, invalid

    def commit_agent_run_atomic(
        self,
        *,
        run_id: UUID,
        job_id: UUID,
        fencing_token: int,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
        content_item_id: UUID | None,
        output_type: str,
        schema_version: int,
        summary: str,
        content_json: dict[str, Any],
        valid_sources: list[dict[str, Any]],
        output_status: str,  # 'validated' | 'needs_review'
        validation_info: dict[str, Any],
        originality_score: float | None,
        input_hash: str,
        model_id: str,
        provider: str,
        cost_estimate_cents: int,
        actor_id: UUID,
    ) -> dict[str, Any]:
        """Persiste output, fontes, eventos, handoffs, proximo run e transicao de job em UMA transacao com fencing."""
        spec = AGENT_REGISTRY[agent_key]
        content_hash = _canonical_hash(content_json)

        with self._connect() as conn:
            with conn.cursor() as cur:
                # 1. Verifica fencing token do job com lock exclusivo
                cur.execute(
                    "SELECT status, fencing_token, current_step FROM public.jobs WHERE id = %s AND workspace_id = %s FOR UPDATE",
                    (str(job_id), str(workspace_id)),
                )
                job = cur.fetchone()
                if not job or int(job["fencing_token"]) != fencing_token or job["status"] not in ("RUNNING", "CANCEL_REQUESTED"):
                    raise AppError(
                        ErrorCode.FENCING_TOKEN_STALE,
                        "Fencing token obsoleto ao persistir resultado do agente; commit abortado.",
                        http_status=409,
                    )

                # Lock no run
                cur.execute(
                    "SELECT * FROM public.agent_runs WHERE id = %s AND workspace_id = %s FOR UPDATE",
                    (str(run_id), str(workspace_id)),
                )
                run = cur.fetchone()
                if run is None:
                    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "agent_run nao encontrado.", http_status=404)

                # 2. Calcula versao do output e marca anteriores como superseded
                if content_item_id is not None:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_ver
                        FROM public.agent_outputs
                        WHERE content_item_id = %s AND output_type = %s
                        """,
                        (str(content_item_id), output_type),
                    )
                    next_version = int(cur.fetchone()["next_ver"])
                    cur.execute(
                        """
                        UPDATE public.agent_outputs
                        SET status = 'superseded'
                        WHERE content_item_id = %s AND output_type = %s AND status IN ('draft', 'validated')
                        """,
                        (str(content_item_id), output_type),
                    )
                else:
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(version), 0) + 1 AS next_ver
                        FROM public.agent_outputs
                        WHERE channel_id = %s AND content_item_id IS NULL AND output_type = %s
                        """,
                        (str(channel_id), output_type),
                    )
                    next_version = int(cur.fetchone()["next_ver"])
                    cur.execute(
                        """
                        UPDATE public.agent_outputs
                        SET status = 'superseded'
                        WHERE channel_id = %s AND content_item_id IS NULL AND output_type = %s
                          AND status IN ('draft', 'validated')
                        """,
                        (str(channel_id), output_type),
                    )

                # 3. Insere agent_outputs
                cur.execute(
                    """
                    INSERT INTO public.agent_outputs (
                        workspace_id, channel_id, run_id, content_item_id, agent_key,
                        output_type, schema_version, version, content, content_hash,
                        status, validation, originality_score, author_kind
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, 'agent')
                    RETURNING *
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        str(run_id),
                        str(content_item_id) if content_item_id else None,
                        agent_key,
                        output_type,
                        schema_version,
                        next_version,
                        json.dumps(content_json),
                        content_hash,
                        output_status,
                        json.dumps(validation_info),
                        originality_score,
                    ),
                )
                output_row = _ser_row(cur.fetchone())
                assert output_row is not None

                # 4. Insere agent_output_sources
                for src in valid_sources:
                    cur.execute(
                        """
                        INSERT INTO public.agent_output_sources (workspace_id, output_id, source_kind, source_id, locator)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            str(workspace_id),
                            output_row["id"],
                            src["kind"],
                            str(src["id"]),
                            src.get("locator"),
                        ),
                    )

                # 5. Eventos do run (output_saved + output_validated|needs_review)
                cur.execute("SELECT COALESCE(MAX(seq), 0) AS max_seq FROM public.agent_events WHERE run_id = %s", (str(run_id),))
                seq = int(cur.fetchone()["max_seq"])

                seq += 1
                cur.execute(
                    """
                    INSERT INTO public.agent_events (
                        workspace_id, channel_id, run_id, content_item_id, agent_key,
                        seq, event_type, summary, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'output_saved', %s, %s::jsonb)
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        str(run_id),
                        str(content_item_id) if content_item_id else None,
                        agent_key,
                        seq,
                        f"Output v{next_version} salvo ({output_type})",
                        json.dumps({"output_id": output_row["id"], "version": next_version}),
                    ),
                )

                seq += 1
                ev_type = "needs_review" if output_status == "needs_review" else "output_validated"
                cur.execute(
                    """
                    INSERT INTO public.agent_events (
                        workspace_id, channel_id, run_id, content_item_id, agent_key,
                        seq, event_type, summary, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        str(run_id),
                        str(content_item_id) if content_item_id else None,
                        agent_key,
                        seq,
                        ev_type,
                        summary[:120],
                        json.dumps({"output_id": output_row["id"], "status": output_status, "validation": validation_info}),
                    ),
                )

                # 6. Consome handoffs de entrada desse agente no item
                if content_item_id is not None:
                    cur.execute(
                        """
                        UPDATE public.agent_handoffs
                        SET status = 'consumed', consumed_by_run_id = %s
                        WHERE workspace_id = %s AND content_item_id = %s
                          AND to_agent_key = %s AND status IN ('pending', 'accepted')
                        """,
                        (str(run_id), str(workspace_id), str(content_item_id), agent_key),
                    )

                # 7. Determina status final do run e handoffs de saida
                if output_status == "needs_review":
                    final_run_status = "needs_review"
                    stage_label = "revisao humana necessaria"
                elif spec.requires_approval:
                    final_run_status = "waiting_approval"
                    stage_label = "aguardando aprovacao humana"
                else:
                    final_run_status = "done"
                    stage_label = "concluido"

                created_handoffs: list[dict[str, Any]] = []
                enqueued_next_runs: list[dict[str, Any]] = []

                if content_item_id is not None and output_status == "validated":
                    for next_key in spec.next_agents:
                        cur.execute(
                            """
                            INSERT INTO public.agent_handoffs (
                                workspace_id, channel_id, content_item_id, from_run_id, output_id, to_agent_key, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                            ON CONFLICT (output_id, to_agent_key) DO NOTHING
                            RETURNING *
                            """,
                            (
                                str(workspace_id),
                                str(channel_id),
                                str(content_item_id),
                                str(run_id),
                                output_row["id"],
                                next_key,
                            ),
                        )
                        h_row = _ser_row(cur.fetchone())
                        if h_row is not None:
                            created_handoffs.append(h_row)
                            seq += 1
                            cur.execute(
                                """
                                INSERT INTO public.agent_events (
                                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                                    seq, event_type, summary, payload
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, 'handoff_created', %s, %s::jsonb)
                                """,
                                (
                                    str(workspace_id),
                                    str(channel_id),
                                    str(run_id),
                                    str(content_item_id),
                                    agent_key,
                                    seq,
                                    f"Handoff criado para {next_key}",
                                    json.dumps({"to_agent_key": next_key, "handoff_id": h_row["id"]}),
                                ),
                            )

                    # Atualiza estagio do content item e dispara proximos se NAO exigir aprovacao humana
                    if spec.requires_approval:
                        target_stage = "estrategia" if agent_key == "estrategia" else "publicacao"
                        cur.execute(
                            """
                            UPDATE public.content_items
                            SET stage = %s, status = 'aguardando_aprovacao'
                            WHERE id = %s AND workspace_id = %s
                            """,
                            (target_stage, str(content_item_id), str(workspace_id)),
                        )
                    else:
                        if agent_key in ("titulos", "roteiro"):
                            cur.execute(
                                "UPDATE public.content_items SET stage = 'design', status = 'ativo' WHERE id = %s AND stage IN ('estrategia', 'roteiro')",
                                (str(content_item_id),),
                            )
                        elif agent_key == "edicao":
                            cur.execute(
                                "UPDATE public.content_items SET stage = 'publicacao', status = 'ativo' WHERE id = %s",
                                (str(content_item_id),),
                            )

                        for next_key in spec.next_agents:
                            enq = self._maybe_enqueue_downstream_in_tx(
                                cur=cur,
                                workspace_id=workspace_id,
                                channel_id=channel_id,
                                content_item_id=content_item_id,
                                target_agent_key=next_key,
                                actor_id=actor_id,
                            )
                            if enq is not None:
                                enqueued_next_runs.append(enq)

                # Caso especial: `dados` rodou sem content_item_id -> verifica se existe content_item aguardando `dados` para disparar `estrategia`
                if content_item_id is None and agent_key == "dados" and output_status == "validated":
                    cur.execute(
                        """
                        SELECT ci.id FROM public.content_items AS ci
                        WHERE ci.workspace_id = %s AND ci.channel_id = %s
                          AND ci.stage IN ('ideia', 'pesquisa')
                          AND EXISTS (
                              SELECT 1 FROM public.agent_outputs AS ao
                              WHERE ao.content_item_id = ci.id AND ao.agent_key = 'pesquisa' AND ao.status IN ('validated', 'approved')
                          )
                        ORDER BY ci.updated_at DESC
                        LIMIT 5
                        """,
                        (str(workspace_id), str(channel_id)),
                    )
                    for item_r in cur.fetchall():
                        enq = self._maybe_enqueue_downstream_in_tx(
                            cur=cur,
                            workspace_id=workspace_id,
                            channel_id=channel_id,
                            content_item_id=UUID(str(item_r["id"])),
                            target_agent_key="estrategia",
                            actor_id=actor_id,
                        )
                        if enq is not None:
                            enqueued_next_runs.append(enq)

                # 8. Atualiza agent_runs + evento completed (se nao needs_review)
                if final_run_status == "done":
                    seq += 1
                    cur.execute(
                        """
                        INSERT INTO public.agent_events (
                            workspace_id, channel_id, run_id, content_item_id, agent_key,
                            seq, event_type, summary, payload
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'completed', %s, %s::jsonb)
                        """,
                        (
                            str(workspace_id),
                            str(channel_id),
                            str(run_id),
                            str(content_item_id) if content_item_id else None,
                            agent_key,
                            seq,
                            summary[:120],
                            json.dumps({"output_id": output_row["id"], "version": next_version}),
                        ),
                    )

                cur.execute(
                    """
                    UPDATE public.agent_runs
                    SET status = %s,
                        stage_label = %s,
                        progress = 1.0,
                        input_hash = %s,
                        model_id = %s,
                        provider = %s,
                        cost_estimate_cents = %s,
                        heartbeat_at = timezone('utc', now()),
                        finished_at = timezone('utc', now())
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        final_run_status,
                        stage_label,
                        input_hash,
                        model_id,
                        provider,
                        cost_estimate_cents,
                        str(run_id),
                    ),
                )
                updated_run = _ser_row(cur.fetchone())

                # 9. Fecha o job da fila unica usando app.transition_job_with_fencing na MESMA transacao
                cur.execute(
                    "SELECT app.transition_job_with_fencing(%s, %s, 'SUCCEEDED', %s::jsonb, NULL, NULL, false, NULL) AS ok",
                    (
                        str(job_id),
                        fencing_token,
                        json.dumps({"run_id": str(run_id), "output_id": output_row["id"], "status": final_run_status}),
                    ),
                )
                ok_row = cur.fetchone()
                if not ok_row or not ok_row["ok"]:
                    raise AppError(
                        ErrorCode.FENCING_TOKEN_STALE,
                        "Job transition com fencing falhou; rollback atomico executado.",
                        http_status=409,
                    )

            conn.commit()
        return {
            "run": updated_run,
            "output": output_row,
            "handoffs": created_handoffs,
            "enqueued_next_runs": enqueued_next_runs,
        }

    def _maybe_enqueue_downstream_in_tx(
        self,
        *,
        cur: psycopg.Cursor[Any],
        workspace_id: UUID,
        channel_id: UUID,
        content_item_id: UUID,
        target_agent_key: str,
        actor_id: UUID,
    ) -> dict[str, Any] | None:
        spec = AGENT_REGISTRY[target_agent_key]

        # Agente deve estar habilitado no canal
        cur.execute(
            """
            SELECT ca.*, ad.display_name AS default_name
            FROM public.channel_agents AS ca
            JOIN public.agent_definitions AS ad ON ad.key = ca.agent_key
            WHERE ca.workspace_id = %s AND ca.channel_id = %s AND ca.agent_key = %s
            LIMIT 1
            """,
            (str(workspace_id), str(channel_id), target_agent_key),
        )
        ca = cur.fetchone()
        if not ca or not ca["enabled"]:
            return None

        # Verifica se ja existe run ativo ou concluido recente para este item/agente
        cur.execute(
            """
            SELECT id FROM public.agent_runs
            WHERE workspace_id = %s AND content_item_id = %s AND agent_key = %s
              AND status IN ('queued', 'working', 'waiting_approval', 'done')
            LIMIT 1
            """,
            (str(workspace_id), str(content_item_id), target_agent_key),
        )
        if cur.fetchone() is not None:
            return None

        # Verifica se TODAS as dependencias obrigatorias estao prontas
        for dep_key in spec.depends_on_agents:
            dep_spec = AGENT_REGISTRY[dep_key]
            allowed_statuses = ("approved",) if dep_spec.requires_approval else ("validated", "approved")
            if dep_key == "dados":
                # 'dados' pode ter output no item ou output valido recente do canal
                cur.execute(
                    """
                    SELECT 1 FROM public.agent_outputs
                    WHERE workspace_id = %s AND channel_id = %s AND agent_key = 'dados'
                      AND status = ANY(%s)
                      AND (content_item_id = %s OR content_item_id IS NULL)
                    LIMIT 1
                    """,
                    (str(workspace_id), str(channel_id), list(allowed_statuses), str(content_item_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT 1 FROM public.agent_outputs
                    WHERE workspace_id = %s AND content_item_id = %s AND agent_key = %s
                      AND status = ANY(%s)
                    LIMIT 1
                    """,
                    (str(workspace_id), str(content_item_id), dep_key, list(allowed_statuses)),
                )
            if cur.fetchone() is None:
                return None

        # Enfileira job + run dentro da mesma transacao
        idem_key = f"handoff-{content_item_id}-{target_agent_key}"[:120]
        run_id = uuid4()
        job_id = uuid4()
        job_idem = f"agent-{target_agent_key}-{idem_key}"[:120]
        payload_json = {
            "run_id": str(run_id),
            "channel_id": str(channel_id),
            "channel_agent_id": str(ca["id"]),
            "agent_key": target_agent_key,
            "content_item_id": str(content_item_id),
            "reason": "handoff",
        }
        cur.execute(
            """
            INSERT INTO public.jobs (
                id, workspace_id, channel_id, job_type, status, priority,
                idempotency_key, payload_hash, payload_json, total_steps,
                correlation_id, created_by
            )
            VALUES (%s, %s, %s, 'agent.execute', 'QUEUED', 65, %s, %s, %s::jsonb, 4, %s, %s)
            ON CONFLICT (workspace_id, job_type, idempotency_key) DO NOTHING
            RETURNING id
            """,
            (
                str(job_id),
                str(workspace_id),
                str(channel_id),
                job_idem,
                _canonical_hash(payload_json),
                json.dumps(payload_json),
                str(uuid4()),
                str(actor_id),
            ),
        )
        if cur.fetchone() is None:
            return None

        cur.execute(
            """
            INSERT INTO public.agent_runs (
                id, workspace_id, channel_id, channel_agent_id, agent_key,
                content_item_id, job_id, status, stage_label, progress,
                attempt, idempotency_key, prompt_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'queued', 'handoff recebido', NULL, 1, %s, 'v1')
            RETURNING *
            """,
            (
                str(run_id),
                str(workspace_id),
                str(channel_id),
                str(ca["id"]),
                target_agent_key,
                str(content_item_id),
                str(job_id),
                idem_key,
            ),
        )
        new_run = _ser_row(cur.fetchone())
        label = ca.get("display_name") or ca["default_name"]
        cur.execute(
            """
            INSERT INTO public.agent_events (
                workspace_id, channel_id, run_id, content_item_id, agent_key,
                seq, event_type, summary, payload
            )
            VALUES (%s, %s, %s, %s, %s, 1, 'run_queued', %s, %s::jsonb)
            """,
            (
                str(workspace_id),
                str(channel_id),
                str(run_id),
                str(content_item_id),
                target_agent_key,
                f"{label}: enfileirado por handoff",
                json.dumps({"reason": "handoff", "job_id": str(job_id)}),
            ),
        )
        return new_run

    def fail_or_block_run_atomic(
        self,
        *,
        run_id: UUID,
        job_id: UUID,
        fencing_token: int,
        workspace_id: UUID,
        target_status: str,  # 'failed' | 'blocked'
        error_code: str,
        error_message: str,
        retryable: bool = False,
    ) -> None:
        job_target = "BLOCKED" if target_status == "blocked" else "FAILED"
        event_type = "blocked" if target_status == "blocked" else "failed"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.agent_runs WHERE id = %s FOR UPDATE", (str(run_id),))
            run = cur.fetchone()
            if run is None:
                return
            cur.execute("SELECT fencing_token, status FROM public.jobs WHERE id = %s FOR UPDATE", (str(job_id),))
            job = cur.fetchone()
            if not job or int(job["fencing_token"]) != fencing_token:
                return

            cur.execute(
                """
                UPDATE public.agent_runs
                SET status = %s,
                    stage_label = %s,
                    error_code = %s,
                    error_message = %s,
                    finished_at = timezone('utc', now())
                WHERE id = %s
                """,
                (target_status, error_code, error_code, error_message[:500], str(run_id)),
            )
            cur.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM public.agent_events WHERE run_id = %s", (str(run_id),))
            next_seq = cur.fetchone()["next_seq"]
            cur.execute(
                """
                INSERT INTO public.agent_events (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    seq, event_type, summary, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(workspace_id),
                    str(run["channel_id"]),
                    str(run_id),
                    str(run["content_item_id"]) if run["content_item_id"] else None,
                    run["agent_key"],
                    next_seq,
                    event_type,
                    error_message[:120],
                    json.dumps({"error_code": error_code}),
                ),
            )
            cur.execute(
                "SELECT app.transition_job_with_fencing(%s, %s, %s, NULL, %s, %s, %s, NULL)",
                (str(job_id), fencing_token, job_target, error_code, error_message[:500], retryable),
            )
            conn.commit()

    def reconcile_expired_agent_runs(self) -> int:
        """Sincroniza agent_runs em 'working' cujo job teve lease expirado no SP-02."""
        reconciled = 0
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT app.reconcile_expired_leases()")
            cur.execute(
                """
                SELECT ar.*, j.status AS job_status, j.attempt_count, j.max_attempts
                FROM public.agent_runs AS ar
                JOIN public.jobs AS j ON j.id = ar.job_id
                WHERE ar.status = 'working'
                  AND j.status IN ('RECOVERABLE', 'FAILED', 'INTERRUPTED')
                FOR UPDATE OF ar SKIP LOCKED
                """
            )
            rows = cur.fetchall()
            for r in rows:
                if r["job_status"] == "RECOVERABLE" and int(r["attempt_count"]) < int(r["max_attempts"]):
                    new_status = "queued"
                    ev_type = "stage_changed"
                    summary = "Worker interrompido; run devolvido para fila (recovery)"
                    cur.execute(
                        """
                        UPDATE public.agent_runs
                        SET status = 'queued', stage_label = 'recuperando execucao',
                            heartbeat_at = NULL, error_code = 'LEASE_EXPIRED'
                        WHERE id = %s
                        """,
                        (str(r["id"]),),
                    )
                else:
                    new_status = "failed"
                    ev_type = "failed"
                    summary = "Execucao interrompida apos exceder tentativas de recovery"
                    cur.execute(
                        """
                        UPDATE public.agent_runs
                        SET status = 'failed', stage_label = 'falha por timeout de lease',
                            error_code = 'LEASE_EXPIRED',
                            error_message = 'Worker expirou lease e atingiu limite de tentativas.',
                            finished_at = timezone('utc', now())
                        WHERE id = %s
                        """,
                        (str(r["id"]),),
                    )

                cur.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM public.agent_events WHERE run_id = %s",
                    (str(r["id"]),),
                )
                next_seq = cur.fetchone()["next_seq"]
                cur.execute(
                    """
                    INSERT INTO public.agent_events (
                        workspace_id, channel_id, run_id, content_item_id, agent_key,
                        seq, event_type, summary, payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(r["workspace_id"]),
                        str(r["channel_id"]),
                        str(r["id"]),
                        str(r["content_item_id"]) if r["content_item_id"] else None,
                        r["agent_key"],
                        next_seq,
                        ev_type,
                        summary,
                        json.dumps({"recovered_to": new_status}),
                    ),
                )
                reconciled += 1
            conn.commit()
        return reconciled

    # ------------------------------------------------------------------
    # Aprovacoes, Revisoes Humanas e Publicacao Manual (UI-06-T03..T06)
    # ------------------------------------------------------------------
    def submit_approval(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        target_kind: str,
        target_id: UUID,
        target_version: int,
        decision: str,  # 'approved' | 'rejected' | 'changes_requested'
        reason: str | None,
        decided_by: UUID,
        confirm_needs_review: bool = False,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_outputs WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(target_id)),
            )
            output = cur.fetchone()
            if output is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Alvo de aprovacao nao encontrado.", http_status=404)
            if int(output["version"]) != target_version:
                raise AppError(
                    ErrorCode.VERSION_CONFLICT,
                    f"Versao divergente: solicitado v{target_version}, atual v{output['version']}.",
                    http_status=409,
                )
            if output["status"] == "needs_review" and decision == "approved" and not confirm_needs_review:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "Output marcado como needs_review exige confirmacao explicita para aprovacao.",
                    http_status=409,
                    details={"requires_confirm_needs_review": True},
                )

            content_item_id = UUID(str(output["content_item_id"])) if output.get("content_item_id") else None

            cur.execute(
                """
                INSERT INTO public.approvals (
                    workspace_id, channel_id, content_item_id, target_kind, target_id,
                    target_version, decision, reason, decided_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id),
                    str(content_item_id) if content_item_id else None,
                    target_kind,
                    str(target_id),
                    target_version,
                    decision,
                    reason,
                    str(decided_by),
                ),
            )
            approval = _ser_row(cur.fetchone())

            new_out_status = "approved" if decision == "approved" else "rejected"
            cur.execute(
                "UPDATE public.agent_outputs SET status = %s WHERE id = %s RETURNING *",
                (new_out_status, str(target_id)),
            )
            updated_output = _ser_row(cur.fetchone())

            # Atualiza run ligado
            if output.get("run_id"):
                run_status = "done" if decision == "approved" else ("waiting_input" if decision == "changes_requested" else "cancelled")
                cur.execute(
                    "UPDATE public.agent_runs SET status = %s, stage_label = %s WHERE id = %s",
                    (run_status, f"decisao humana: {decision}", str(output["run_id"])),
                )

            enqueued: list[dict[str, Any]] = []
            if content_item_id is not None:
                if decision == "approved":
                    spec = AGENT_REGISTRY.get(output["agent_key"])
                    if output["agent_key"] == "estrategia":
                        cur.execute(
                            "UPDATE public.content_items SET stage = 'roteiro', status = 'ativo' WHERE id = %s",
                            (str(content_item_id),),
                        )
                    elif output["agent_key"] == "publicacao":
                        cur.execute(
                            "UPDATE public.content_items SET stage = 'publicacao', status = 'concluido' WHERE id = %s",
                            (str(content_item_id),),
                        )

                    if spec:
                        for next_key in spec.next_agents:
                            enq = self._maybe_enqueue_downstream_in_tx(
                                cur=cur,
                                workspace_id=workspace_id,
                                channel_id=channel_id,
                                content_item_id=content_item_id,
                                target_agent_key=next_key,
                                actor_id=decided_by,
                            )
                            if enq is not None:
                                enqueued.append(enq)
                else:
                    cur.execute(
                        """
                        UPDATE public.agent_handoffs
                        SET status = 'cancelled'
                        WHERE output_id = %s AND status = 'pending'
                        """,
                        (str(target_id),),
                    )
                    cur.execute(
                        "UPDATE public.content_items SET status = 'bloqueado' WHERE id = %s",
                        (str(content_item_id),),
                    )

            conn.commit()
            return {"approval": approval, "output": updated_output, "enqueued_next_runs": enqueued}

    def approve_brief_stage_and_release_production(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        content_item_id: UUID,
        brief_version: int,
        decision: str,
        reason: str | None,
        decided_by: UUID,
    ) -> dict[str, Any]:
        """Aprova o brief consolidado (titulos+roteiro+thumbnail) e libera `edicao`."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.content_items WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(content_item_id)),
            )
            item = cur.fetchone()
            if item is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Content item nao encontrado.", http_status=404)

            cur.execute(
                """
                INSERT INTO public.approvals (
                    workspace_id, channel_id, content_item_id, target_kind, target_id,
                    target_version, decision, reason, decided_by
                )
                VALUES (%s, %s, %s, 'brief', %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id),
                    str(content_item_id),
                    str(item.get("brief_id") or content_item_id),
                    brief_version,
                    decision,
                    reason,
                    str(decided_by),
                ),
            )
            approval = _ser_row(cur.fetchone())

            enqueued: list[dict[str, Any]] = []
            if decision == "approved":
                cur.execute(
                    """
                    UPDATE public.content_items
                    SET stage = 'producao', status = 'ativo', brief_version = %s
                    WHERE id = %s
                    """,
                    (brief_version, str(content_item_id)),
                )
                enq = self._maybe_enqueue_downstream_in_tx(
                    cur=cur,
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    content_item_id=content_item_id,
                    target_agent_key="edicao",
                    actor_id=decided_by,
                )
                if enq is not None:
                    enqueued.append(enq)
            else:
                cur.execute(
                    """
                    UPDATE public.agent_handoffs
                    SET status = 'cancelled'
                    WHERE content_item_id = %s AND to_agent_key = 'edicao' AND status = 'pending'
                    """,
                    (str(content_item_id),),
                )
                cur.execute(
                    "UPDATE public.content_items SET status = 'bloqueado' WHERE id = %s",
                    (str(content_item_id),),
                )

            conn.commit()
            return {"approval": approval, "enqueued_next_runs": enqueued}

    def revise_output(
        self,
        *,
        workspace_id: UUID,
        output_id: UUID,
        actor_id: UUID,
        action: str,  # 'save_version' | 'discard'
        edited_content: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.agent_outputs WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(output_id)),
            )
            existing = cur.fetchone()
            if existing is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Output nao encontrado.", http_status=404)

            if action == "discard":
                cur.execute(
                    "UPDATE public.agent_outputs SET status = 'rejected' WHERE id = %s RETURNING *",
                    (str(output_id),),
                )
                rejected = _ser_row(cur.fetchone())
                conn.commit()
                return {"output": rejected, "action": "discarded"}

            if edited_content is None:
                raise AppError(ErrorCode.VALIDATION_ERROR, "edited_content e obrigatorio para save_version.", http_status=422)

            if existing["content_item_id"]:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1 AS next_ver
                    FROM public.agent_outputs
                    WHERE content_item_id = %s AND output_type = %s
                    """,
                    (str(existing["content_item_id"]), existing["output_type"]),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1 AS next_ver
                    FROM public.agent_outputs
                    WHERE channel_id = %s AND content_item_id IS NULL AND output_type = %s
                    """,
                    (str(existing["channel_id"]), existing["output_type"]),
                )
            next_version = int(cur.fetchone()["next_ver"])

            cur.execute(
                "UPDATE public.agent_outputs SET status = 'superseded' WHERE id = %s",
                (str(output_id),),
            )
            cur.execute(
                """
                INSERT INTO public.agent_outputs (
                    workspace_id, channel_id, run_id, content_item_id, agent_key,
                    output_type, schema_version, version, content, content_hash,
                    status, validation, author_kind, author_user_id, parent_output_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'validated', %s::jsonb, 'human', %s, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(existing["channel_id"]),
                    str(existing["run_id"]) if existing.get("run_id") else None,
                    str(existing["content_item_id"]) if existing.get("content_item_id") else None,
                    existing["agent_key"],
                    existing["output_type"],
                    existing["schema_version"],
                    next_version,
                    json.dumps(edited_content),
                    _canonical_hash(edited_content),
                    json.dumps({"human_revised": True, "reason": reason or "Revisao humana"}),
                    str(actor_id),
                    str(output_id),
                ),
            )
            new_out = _ser_row(cur.fetchone())
            if existing.get("run_id"):
                cur.execute(
                    "UPDATE public.agent_runs SET status = 'done', stage_label = 'revisado por humano' WHERE id = %s",
                    (str(existing["run_id"]),),
                )
            conn.commit()
            return {"output": new_out, "action": "saved_new_version"}

    def mark_manual_published(
        self,
        *,
        workspace_id: UUID,
        content_item_id: UUID,
        published_video_url: str,
        actor_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.content_items WHERE workspace_id = %s AND id = %s FOR UPDATE",
                (str(workspace_id), str(content_item_id)),
            )
            item = cur.fetchone()
            if item is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Content item nao encontrado.", http_status=404)

            cur.execute(
                """
                UPDATE public.content_items
                SET stage = 'publicado_manual',
                    status = 'concluido',
                    published_video_url = %s,
                    published_at = timezone('utc', now())
                WHERE id = %s
                RETURNING *
                """,
                (published_video_url, str(content_item_id)),
            )
            updated = _ser_row(cur.fetchone())

            # Registra em audit_events (append-only)
            cur.execute(
                """
                INSERT INTO public.audit_events (
                    workspace_id, actor_user_id, action, entity_type, entity_id, correlation_id, metadata_json
                )
                VALUES (%s, %s, 'content_item.published_manual', 'content_item', %s, %s, %s::jsonb)
                """,
                (
                    str(workspace_id),
                    str(actor_id),
                    str(content_item_id),
                    str(uuid4()),
                    json.dumps({"published_video_url": published_video_url}),
                ),
            )
            conn.commit()
            assert updated is not None
            return updated
