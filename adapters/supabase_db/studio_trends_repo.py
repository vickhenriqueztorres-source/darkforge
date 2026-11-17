from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class PostgresStudioTrendsRepository:
    """Postgres repository for YouTube Studio Trends terms & Outlier videos (SP-13)."""

    def __init__(self, database_url: str) -> None:
        self._db_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._db_url, row_factory=dict_row, prepare_threshold=None)

    def create_run(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        broad_topic: str,
        filters_json: dict[str, Any],
        job_id: UUID | None,
        created_by: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.studio_trend_runs (
                    workspace_id, channel_id, broad_topic, filters_json, status, job_id, created_by
                )
                VALUES (%s, %s, %s, %s::jsonb, 'QUEUED', %s, %s)
                RETURNING *
                """,
                (workspace_id, channel_id, broad_topic, json.dumps(filters_json), job_id, created_by),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def get_run(self, workspace_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM public.studio_trend_runs WHERE workspace_id = %s AND id = %s",
                (workspace_id, run_id),
            )
            return cur.fetchone()

    def list_runs(self, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM public.studio_trend_runs WHERE workspace_id = %s"
        params: list[Any] = [workspace_id]
        if channel_id:
            sql += " AND channel_id = %s"
            params.append(channel_id)
        sql += " ORDER BY created_at DESC LIMIT 30"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    def mark_run_status(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        status: str,
        captured_via: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        limitations_json: list[str] | None = None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.studio_trend_runs
                SET status = %s,
                    captured_via = COALESCE(%s, captured_via),
                    error_code = %s,
                    error_message = %s,
                    limitations_json = COALESCE(%s::jsonb, limitations_json)
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (
                    status,
                    captured_via,
                    error_code,
                    error_message,
                    json.dumps(limitations_json) if limitations_json is not None else None,
                    workspace_id,
                    run_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        return row

    def save_run_results(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        channel_id: UUID,
        terms: list[dict[str, Any]],
        outliers: list[dict[str, Any]],
        captured_via: str,
        limitations: list[str],
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            for t in terms:
                cur.execute(
                    """
                    INSERT INTO public.studio_search_terms (
                        workspace_id, run_id, channel_id, term, block_type, audience_interest,
                        is_hypothesis, gap_note, weekly_views_gt_1000
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        workspace_id,
                        run_id,
                        channel_id,
                        t["term"],
                        t["block_type"],
                        t["audience_interest"],
                        t["is_hypothesis"],
                        t.get("gap_note", ""),
                        t.get("weekly_views_gt_1000", True),
                    ),
                )
            for o in outliers:
                cur.execute(
                    """
                    INSERT INTO public.studio_video_outliers (
                        workspace_id, run_id, channel_id, external_video_id, canonical_url, title,
                        external_channel_id, channel_name, public_views, channel_baseline_views,
                        outlier_ratio, outlier_tier, baseline_sample_size, watched_by_my_viewers,
                        published_days_ago
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workspace_id, run_id, external_video_id) DO UPDATE SET
                        outlier_ratio = EXCLUDED.outlier_ratio,
                        outlier_tier = EXCLUDED.outlier_tier,
                        channel_baseline_views = EXCLUDED.channel_baseline_views
                    """,
                    (
                        workspace_id,
                        run_id,
                        channel_id,
                        o["external_video_id"],
                        o["canonical_url"],
                        o["title"],
                        o.get("external_channel_id"),
                        o.get("channel_name", ""),
                        o.get("public_views"),
                        o.get("channel_baseline_views"),
                        o.get("outlier_ratio"),
                        o["outlier_tier"],
                        o.get("baseline_sample_size", 0),
                        o.get("watched_by_my_viewers", False),
                        o.get("published_days_ago"),
                    ),
                )
            cur.execute(
                """
                UPDATE public.studio_trend_runs
                SET status = 'SUCCEEDED',
                    captured_via = %s,
                    error_code = NULL,
                    error_message = NULL,
                    limitations_json = %s::jsonb
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (captured_via, json.dumps(limitations), workspace_id, run_id),
            )
            run = cur.fetchone()
            conn.commit()
        assert run is not None
        return run

    def get_run_detail(self, workspace_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM public.studio_trend_runs WHERE workspace_id = %s AND id = %s", (workspace_id, run_id))
            run = cur.fetchone()
            if run is None:
                return None
            cur.execute(
                "SELECT * FROM public.studio_search_terms WHERE workspace_id = %s AND run_id = %s ORDER BY audience_interest DESC, created_at ASC",
                (workspace_id, run_id),
            )
            terms = cur.fetchall()
            cur.execute(
                "SELECT * FROM public.studio_video_outliers WHERE workspace_id = %s AND run_id = %s ORDER BY outlier_ratio DESC NULLS LAST",
                (workspace_id, run_id),
            )
            outliers = cur.fetchall()
        return {"run": run, "terms": terms, "outliers": outliers}

    def curate_item(self, workspace_id: UUID, kind: str, item_id: UUID, status: str) -> dict[str, Any] | None:
        tbl = "studio_search_terms" if kind == "term" else "studio_video_outliers"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE public.{tbl} SET curation_status = %s WHERE workspace_id = %s AND id = %s RETURNING *",
                (status, workspace_id, item_id),
            )
            row = cur.fetchone()
            conn.commit()
        return row

    def get_channel_external_id(self, workspace_id: UUID, channel_id: UUID) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT external_channel_id FROM public.channels WHERE workspace_id = %s AND id = %s",
                (workspace_id, channel_id),
            )
            row = cur.fetchone()
        return row["external_channel_id"] if row else None

    def list_workspace_items(self, workspace_id: UUID, channel_id: UUID | None = None) -> dict[str, Any]:
        params: list[Any] = [workspace_id]
        ch_clause = ""
        if channel_id:
            ch_clause = " AND channel_id = %s"
            params.append(channel_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM public.studio_search_terms
                WHERE workspace_id = %s {ch_clause}
                ORDER BY created_at DESC LIMIT 40
                """,
                tuple(params),
            )
            terms = cur.fetchall()
            cur.execute(
                f"""
                SELECT * FROM public.studio_video_outliers
                WHERE workspace_id = %s {ch_clause}
                ORDER BY outlier_ratio DESC NULLS LAST, created_at DESC LIMIT 40
                """,
                tuple(params),
            )
            outliers = cur.fetchall()
        return {"terms": terms, "outliers": outliers}
