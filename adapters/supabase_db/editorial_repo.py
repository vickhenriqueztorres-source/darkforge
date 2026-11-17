from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class PostgresEditorialRepository:
    """Postgres repository for Opportunity Engine, EpisodeBriefs & Editorial Calendar (SP-07)."""

    def __init__(self, database_url: str) -> None:
        self._db_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._db_url, row_factory=dict_row, prepare_threshold=None)

    def load_generation_context(self, workspace_id: UUID, channel_id: UUID) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.channels WHERE workspace_id = %s AND id = %s",
                (workspace_id, channel_id),
            )
            channel = cur.fetchone()
            cur.execute(
                """
                SELECT * FROM public.channel_profile_versions
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY version_number DESC LIMIT 1
                """,
                (workspace_id, channel_id),
            )
            profile = cur.fetchone()
            cur.execute(
                """
                SELECT id, metric_id AS metric_key, value_num AS value, availability AS freshness_status, period_start, period_end
                FROM public.metric_snapshots
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY fetched_at DESC LIMIT 20
                """,
                (workspace_id, channel_id),
            )
            facts = cur.fetchall()
            cur.execute(
                """
                SELECT id, title, canonical_url, public_views_snapshot AS view_count, snapshot_observed_at AS observed_at
                FROM public.reference_videos
                WHERE workspace_id = %s AND curation_status = 'approved'
                ORDER BY snapshot_observed_at DESC LIMIT 10
                """,
                (workspace_id,),
            )
            refs = cur.fetchall()
            cur.execute(
                """
                SELECT id, term, block_type, audience_interest, is_hypothesis, gap_note
                FROM public.studio_search_terms
                WHERE workspace_id = %s AND channel_id = %s
                  AND curation_status IN ('pending', 'approved')
                  AND audience_interest IN ('medium', 'high', 'very_high')
                ORDER BY created_at DESC LIMIT 10
                """,
                (workspace_id, channel_id),
            )
            studio_terms = cur.fetchall()
            cur.execute(
                """
                SELECT id, external_video_id, title, canonical_url, outlier_ratio, outlier_tier, watched_by_my_viewers
                FROM public.studio_video_outliers
                WHERE workspace_id = %s AND channel_id = %s
                  AND curation_status IN ('pending', 'approved')
                  AND (outlier_ratio IS NULL OR outlier_ratio >= 3.0)
                ORDER BY outlier_ratio DESC NULLS LAST, created_at DESC LIMIT 10
                """,
                (workspace_id, channel_id),
            )
            studio_outliers = cur.fetchall()
            cur.execute(
                """
                SELECT id, keyword, geo, gprop, direction_12m, durability_5y, peak_decay_pct,
                       verdict, seasonal_months_json, breakout_queries_json, rising_queries_json, summary
                FROM public.google_trends_validations
                WHERE workspace_id = %s
                  AND (channel_id = %s OR channel_id IS NULL)
                  AND status = 'SUCCEEDED'
                ORDER BY created_at DESC LIMIT 8
                """,
                (workspace_id, channel_id),
            )
            google_trends = cur.fetchall()
        return {
            "channel": channel,
            "profile_version": profile,
            "analytics_facts": facts,
            "approved_references": refs,
            "studio_terms": studio_terms,
            "studio_outliers": studio_outliers,
            "google_trends": google_trends,
        }

    def insert_opportunity(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        profile_version_id: UUID | None,
        theme: str,
        angle: str,
        target_format: str,
        differentiation: str,
        score: float,
        score_version: str,
        score_breakdown_json: dict[str, Any],
        confidence: float,
        limitations_json: list[str],
        data_freshness: str,
        insufficient_data: bool,
        analyst_reports_json: list[dict[str, Any]],
        created_by: UUID,
        evidence_links: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.opportunities (
                    workspace_id, channel_id, profile_version_id, theme, angle, target_format,
                    differentiation, score, score_version, score_breakdown_json, confidence,
                    limitations_json, data_freshness, insufficient_data, analyst_reports_json, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    channel_id,
                    profile_version_id,
                    theme,
                    angle,
                    target_format,
                    differentiation,
                    score,
                    score_version,
                    json.dumps(score_breakdown_json),
                    confidence,
                    json.dumps(limitations_json),
                    data_freshness,
                    insufficient_data,
                    json.dumps(analyst_reports_json),
                    created_by,
                ),
            )
            opp = cur.fetchone()
            assert opp is not None
            for ev in evidence_links:
                cur.execute(
                    """
                    INSERT INTO public.evidence_links (
                        workspace_id, entity_type, entity_id, source_kind, source_id, snippet, source_url
                    )
                    VALUES (%s, 'opportunity', %s, %s, %s, %s, %s)
                    """,
                    (
                        workspace_id,
                        opp["id"],
                        ev["source_kind"],
                        str(ev["source_id"]),
                        ev.get("snippet", ""),
                        ev.get("source_url"),
                    ),
                )
            conn.commit()
        return opp

    def list_opportunities(
        self, workspace_id: UUID, *, channel_id: UUID | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["workspace_id = %s"]
        params: list[Any] = [workspace_id]
        if channel_id:
            clauses.append("channel_id = %s")
            params.append(channel_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        sql = f"SELECT * FROM public.opportunities WHERE {' AND '.join(clauses)} ORDER BY score DESC, created_at DESC"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def get_opportunity(self, workspace_id: UUID, opportunity_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.opportunities WHERE workspace_id = %s AND id = %s",
                (workspace_id, opportunity_id),
            )
            return cur.fetchone()

    def list_evidence(self, workspace_id: UUID, entity_type: str, entity_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.evidence_links
                WHERE workspace_id = %s AND entity_type = %s AND entity_id = %s
                ORDER BY created_at ASC
                """,
                (workspace_id, entity_type, entity_id),
            )
            return cur.fetchall()

    def list_opportunity_feedback(self, workspace_id: UUID, opportunity_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.opportunity_feedback
                WHERE workspace_id = %s AND opportunity_id = %s
                ORDER BY created_at ASC
                """,
                (workspace_id, opportunity_id),
            )
            return cur.fetchall()

    def update_opportunity_and_record_feedback(
        self,
        *,
        workspace_id: UUID,
        opportunity_id: UUID,
        previous_status: str,
        new_status: str,
        decision: str,
        reason_code: str | None,
        notes: str | None,
        edited_theme: str | None,
        edited_angle: str | None,
        edited_differentiation: str | None,
        actor_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.opportunities
                SET status = %s,
                    theme = COALESCE(%s, theme),
                    angle = COALESCE(%s, angle),
                    differentiation = COALESCE(%s, differentiation),
                    reviewed_by = %s,
                    reviewed_at = timezone('utc', now())
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (
                    new_status,
                    edited_theme,
                    edited_angle,
                    edited_differentiation,
                    actor_id,
                    workspace_id,
                    opportunity_id,
                ),
            )
            opp = cur.fetchone()
            cur.execute(
                """
                INSERT INTO public.opportunity_feedback (
                    workspace_id, opportunity_id, decision, reason_code, notes,
                    previous_status, new_status, actor_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (workspace_id, opportunity_id, decision, reason_code, notes, previous_status, new_status, actor_id),
            )
            fb = cur.fetchone()
            conn.commit()
        return {"opportunity": opp, "feedback": fb}

    def insert_brief(
        self,
        *,
        workspace_id: UUID,
        brief_group_id: UUID,
        version: int,
        parent_brief_id: UUID | None,
        opportunity_id: UUID,
        channel_id: UUID,
        profile_version_id: UUID,
        title: str,
        hook: str,
        angle: str,
        outline_json: list[dict[str, Any]],
        cta: str,
        target_format: str,
        source_refs_json: list[dict[str, Any]],
        generation_refs_json: list[str],
        content_sha256: str,
        actor_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.episode_briefs (
                    workspace_id, brief_group_id, version, parent_brief_id, opportunity_id,
                    channel_id, profile_version_id, title, hook, angle, outline_json,
                    cta, target_format, source_refs_json, generation_refs_json,
                    content_sha256, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    brief_group_id,
                    version,
                    parent_brief_id,
                    opportunity_id,
                    channel_id,
                    profile_version_id,
                    title,
                    hook,
                    angle,
                    json.dumps(outline_json),
                    cta,
                    target_format,
                    json.dumps(source_refs_json),
                    json.dumps(generation_refs_json),
                    content_sha256,
                    actor_id,
                ),
            )
            brief = cur.fetchone()
            assert brief is not None
            cur.execute(
                """
                INSERT INTO public.brief_decision_history (
                    workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                )
                VALUES (%s, %s, 'CREATE', NULL, 'DRAFT', 'Brief criado', %s)
                """,
                (workspace_id, brief["id"], actor_id),
            )
            conn.commit()
        return brief

    def list_briefs(self, workspace_id: UUID, *, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM public.episode_briefs WHERE workspace_id = %s"
        params: list[Any] = [workspace_id]
        if channel_id:
            sql += " AND channel_id = %s"
            params.append(channel_id)
        sql += " ORDER BY created_at DESC, version DESC"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def get_brief(self, workspace_id: UUID, brief_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.episode_briefs WHERE workspace_id = %s AND id = %s",
                (workspace_id, brief_id),
            )
            return cur.fetchone()

    def list_brief_versions(self, workspace_id: UUID, brief_group_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, version, status, title, content_sha256, frozen_at, approved_at, created_at
                FROM public.episode_briefs
                WHERE workspace_id = %s AND brief_group_id = %s
                ORDER BY version ASC
                """,
                (workspace_id, brief_group_id),
            )
            return cur.fetchall()

    def list_brief_history(self, workspace_id: UUID, brief_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.brief_decision_history
                WHERE workspace_id = %s AND brief_id = %s
                ORDER BY created_at ASC
                """,
                (workspace_id, brief_id),
            )
            return cur.fetchall()

    def update_brief_draft(
        self,
        *,
        workspace_id: UUID,
        brief_id: UUID,
        title: str,
        hook: str,
        angle: str,
        outline_json: list[dict[str, Any]],
        cta: str,
        content_sha256: str,
        actor_id: UUID,
        from_status: str,
        notes: str | None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.episode_briefs
                SET title = %s, hook = %s, angle = %s, outline_json = %s::jsonb, cta = %s, content_sha256 = %s
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (title, hook, angle, json.dumps(outline_json), cta, content_sha256, workspace_id, brief_id),
            )
            brief = cur.fetchone()
            cur.execute(
                """
                INSERT INTO public.brief_decision_history (
                    workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                )
                VALUES (%s, %s, 'UPDATE_DRAFT', %s, %s, %s, %s)
                """,
                (workspace_id, brief_id, from_status, from_status, notes or "Draft atualizado", actor_id),
            )
            conn.commit()
        assert brief is not None
        return brief

    def approve_brief(
        self,
        *,
        workspace_id: UUID,
        brief_id: UUID,
        from_status: str,
        actor_id: UUID,
        notes: str | None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.episode_briefs
                SET status = 'APPROVED',
                    frozen_at = timezone('utc', now()),
                    approved_by = %s,
                    approved_at = timezone('utc', now())
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (actor_id, workspace_id, brief_id),
            )
            brief = cur.fetchone()
            cur.execute(
                """
                INSERT INTO public.brief_decision_history (
                    workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                )
                VALUES (%s, %s, 'APPROVE', %s, 'APPROVED', %s, %s)
                """,
                (workspace_id, brief_id, from_status, notes or "Aprovacao humana congelou versao", actor_id),
            )
            conn.commit()
        assert brief is not None
        return brief

    def create_next_brief_version(
        self,
        *,
        workspace_id: UUID,
        parent_brief: dict[str, Any],
        title: str,
        hook: str,
        angle: str,
        outline_json: list[dict[str, Any]],
        cta: str,
        content_sha256: str,
        actor_id: UUID,
        notes: str | None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) AS max_ver FROM public.episode_briefs WHERE workspace_id = %s AND brief_group_id = %s",
                (workspace_id, parent_brief["brief_group_id"]),
            )
            max_ver = int(cur.fetchone()["max_ver"])  # type: ignore[index]
            next_ver = max_ver + 1

            if parent_brief["status"] == "APPROVED":
                cur.execute(
                    "UPDATE public.episode_briefs SET status = 'SUPERSEDED' WHERE workspace_id = %s AND id = %s",
                    (workspace_id, parent_brief["id"]),
                )
                cur.execute(
                    """
                    INSERT INTO public.brief_decision_history (
                        workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                    )
                    VALUES (%s, %s, 'CREATE_VERSION', 'APPROVED', 'SUPERSEDED', %s, %s)
                    """,
                    (workspace_id, parent_brief["id"], f"Substituido por v{next_ver}", actor_id),
                )

            cur.execute(
                """
                INSERT INTO public.episode_briefs (
                    workspace_id, brief_group_id, version, parent_brief_id, opportunity_id,
                    channel_id, profile_version_id, title, hook, angle, outline_json,
                    cta, target_format, source_refs_json, generation_refs_json,
                    content_sha256, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    parent_brief["brief_group_id"],
                    next_ver,
                    parent_brief["id"],
                    parent_brief["opportunity_id"],
                    parent_brief["channel_id"],
                    parent_brief["profile_version_id"],
                    title,
                    hook,
                    angle,
                    json.dumps(outline_json),
                    cta,
                    parent_brief["target_format"],
                    json.dumps(parent_brief["source_refs_json"]),
                    json.dumps(parent_brief["generation_refs_json"]),
                    content_sha256,
                    actor_id,
                ),
            )
            new_brief = cur.fetchone()
            assert new_brief is not None
            cur.execute(
                """
                INSERT INTO public.brief_decision_history (
                    workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                )
                VALUES (%s, %s, 'CREATE_VERSION', NULL, 'DRAFT', %s, %s)
                """,
                (workspace_id, new_brief["id"], notes or f"Nova versao v{next_ver} criada a partir de v{parent_brief['version']}", actor_id),
            )
            conn.commit()
        return new_brief

    def record_brief_action(
        self,
        *,
        workspace_id: UUID,
        brief_id: UUID,
        action: str,
        from_status: str | None,
        to_status: str,
        notes: str | None,
        actor_id: UUID,
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.brief_decision_history (
                    workspace_id, brief_id, action, from_status, to_status, notes, actor_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (workspace_id, brief_id, action, from_status, to_status, notes, actor_id),
            )
            conn.commit()

    def insert_calendar_item(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        brief_id: UUID | None,
        title: str,
        scheduled_for: str,
        notes: str | None,
        actor_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.editorial_calendar_items (
                    workspace_id, channel_id, brief_id, title, scheduled_for, auto_publish_enabled, notes, created_by
                )
                VALUES (%s, %s, %s, %s, %s::date, false, %s, %s)
                RETURNING *
                """,
                (workspace_id, channel_id, brief_id, title, scheduled_for, notes, actor_id),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def list_calendar_items(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.editorial_calendar_items WHERE workspace_id = %s ORDER BY scheduled_for ASC, created_at ASC",
                (workspace_id,),
            )
            return cur.fetchall()

    def update_calendar_status(self, workspace_id: UUID, item_id: UUID, status: str) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.editorial_calendar_items
                SET status = %s
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (status, workspace_id, item_id),
            )
            row = cur.fetchone()
            conn.commit()
        return row
