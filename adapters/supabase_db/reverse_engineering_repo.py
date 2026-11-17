from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class PostgresReverseEngineeringRepository:
    """Postgres repository for 4-Phase Reverse Engineering Engine & Experiment Batches (SP-19..SP-23)."""

    def __init__(self, database_url: str) -> None:
        self._db_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._db_url, row_factory=dict_row, prepare_threshold=None)

    def save_channel_audits(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        audits: list[dict[str, Any]],
        created_by: UUID,
    ) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        with self._connect() as conn, conn.cursor() as cur:
            for a in audits:
                cur.execute(
                    """
                    INSERT INTO public.reference_channel_audits (
                        workspace_id, channel_id, external_channel_id, display_name, approved,
                        passed_criteria_json, failed_criteria_json, channel_mean_views,
                        outlier_hits_count, max_outlier_ratio, ranking_score, warnings_json, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING *
                    """,
                    (
                        workspace_id,
                        channel_id,
                        a["external_channel_id"],
                        a["display_name"],
                        a["approved"],
                        json.dumps(a["passed_criteria"]),
                        json.dumps(a["failed_criteria"]),
                        a["channel_mean_views"],
                        a["outlier_hits_count"],
                        a["max_outlier_ratio"],
                        a["ranking_score"],
                        json.dumps(a["warnings"]),
                        created_by,
                    ),
                )
                row = cur.fetchone()
                if row:
                    saved.append(row)
            conn.commit()
        return saved

    def list_channel_audits(self, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM public.reference_channel_audits WHERE workspace_id = %s"
        params: list[Any] = [workspace_id]
        if channel_id:
            sql += " AND channel_id = %s"
            params.append(channel_id)
        sql += " ORDER BY ranking_score DESC, created_at DESC LIMIT 30"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def save_viral_outliers(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        outliers: list[dict[str, Any]],
        created_by: UUID,
    ) -> list[dict[str, Any]]:
        saved: list[dict[str, Any]] = []
        with self._connect() as conn, conn.cursor() as cur:
            for o in outliers:
                cur.execute(
                    """
                    INSERT INTO public.viral_outlier_snapshots (
                        workspace_id, channel_id, external_video_id, external_channel_id,
                        channel_name, title, views, days_since_upload, views_per_day,
                        channel_mean_views, outlier_ratio, pattern_key,
                        confirmed_multi_channel, is_false_positive, false_positive_reasons_json, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING *
                    """,
                    (
                        workspace_id,
                        channel_id,
                        o["external_video_id"],
                        o["external_channel_id"],
                        o["channel_name"],
                        o["title"],
                        o["views"],
                        o["days_since_upload"],
                        o["views_per_day"],
                        o["channel_mean_views"],
                        o["outlier_ratio"],
                        o["pattern_key"],
                        o["confirmed_multi_channel"],
                        o["is_false_positive"],
                        json.dumps(o["false_positive_reasons"]),
                        created_by,
                    ),
                )
                row = cur.fetchone()
                if row:
                    saved.append(row)
            conn.commit()
        return saved

    def list_viral_outliers(self, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM public.viral_outlier_snapshots WHERE workspace_id = %s"
        params: list[Any] = [workspace_id]
        if channel_id:
            sql += " AND channel_id = %s"
            params.append(channel_id)
        sql += " ORDER BY is_false_positive ASC, confirmed_multi_channel DESC, views_per_day DESC, outlier_ratio DESC LIMIT 50"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def save_autopsy(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        external_video_id: str,
        original_title: str,
        package_json: dict[str, Any],
        script_retention_json: dict[str, Any],
        comment_gaps_json: dict[str, Any],
        narrative_archetype: str,
        confidence: float,
        created_by: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.video_autopsies (
                    workspace_id, channel_id, external_video_id, original_title,
                    package_json, script_retention_json, comment_gaps_json,
                    narrative_archetype, confidence, created_by
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    channel_id,
                    external_video_id,
                    original_title,
                    json.dumps(package_json),
                    json.dumps(script_retention_json),
                    json.dumps(comment_gaps_json),
                    narrative_archetype,
                    confidence,
                    created_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def list_autopsies(self, workspace_id: UUID, autopsy_ids: list[UUID] | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            if autopsy_ids:
                cur.execute(
                    "SELECT * FROM public.video_autopsies WHERE workspace_id = %s AND id = ANY(%s) ORDER BY created_at DESC",
                    (workspace_id, autopsy_ids),
                )
            else:
                cur.execute(
                    "SELECT * FROM public.video_autopsies WHERE workspace_id = %s ORDER BY created_at DESC LIMIT 30",
                    (workspace_id,),
                )
            return cur.fetchall()

    def save_mechanism(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        formula_theme: str,
        formula_angle: str,
        formula_emotion: str,
        formula_structure: str,
        formula_format: str,
        synthesized_title: str,
        synthesized_thumb_concept: str,
        synthesized_outline_json: list[dict[str, Any]],
        filled_comment_gaps_json: list[str],
        originality_max_similarity: float,
        originality_blocked: bool,
        source_autopsy_ids_json: list[str],
        sample_warning: str | None,
        created_by: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.transferable_mechanisms (
                    workspace_id, channel_id, formula_theme, formula_angle, formula_emotion,
                    formula_structure, formula_format, synthesized_title, synthesized_thumb_concept,
                    synthesized_outline_json, filled_comment_gaps_json, originality_max_similarity,
                    originality_blocked, source_autopsy_ids_json, sample_warning, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb, %s, %s)
                RETURNING *
                """,
                (
                    workspace_id,
                    channel_id,
                    formula_theme,
                    formula_angle,
                    formula_emotion,
                    formula_structure,
                    formula_format,
                    synthesized_title,
                    synthesized_thumb_concept,
                    json.dumps(synthesized_outline_json),
                    json.dumps(filled_comment_gaps_json),
                    originality_max_similarity,
                    originality_blocked,
                    json.dumps(source_autopsy_ids_json),
                    sample_warning,
                    created_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def list_mechanisms(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.transferable_mechanisms WHERE workspace_id = %s ORDER BY created_at DESC LIMIT 30",
                (workspace_id,),
            )
            return cur.fetchall()

    def create_experiment_batch(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        mechanism_id: UUID | None,
        brief_id: UUID | None,
        title: str,
        created_by: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.experiment_batches (
                    workspace_id, channel_id, mechanism_id, brief_id, title, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (workspace_id, channel_id, mechanism_id, brief_id, title, created_by),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def record_experiment_metrics(
        self,
        *,
        workspace_id: UUID,
        batch_id: UUID,
        status: str,
        impressions: int | None,
        ctr_pct: float | None,
        retention_30s_pct: float | None,
        outcome_notes: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.experiment_batches
                SET status = %s,
                    impressions = COALESCE(%s, impressions),
                    ctr_pct = COALESCE(%s, ctr_pct),
                    retention_30s_pct = COALESCE(%s, retention_30s_pct),
                    outcome_notes = %s
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (status, impressions, ctr_pct, retention_30s_pct, outcome_notes, workspace_id, batch_id),
            )
            row = cur.fetchone()
            conn.commit()
        return row

    def list_experiment_batches(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.experiment_batches WHERE workspace_id = %s ORDER BY created_at DESC LIMIT 30",
                (workspace_id,),
            )
            return cur.fetchall()
