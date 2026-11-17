from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from core.research.google_trends_models import GoogleTrendsReport


class PostgresGoogleTrendsRepository:
    """Postgres repository for Google Trends validations & 24h cache (SP-17)."""

    def __init__(self, database_url: str) -> None:
        self._db_url = database_url

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        return psycopg.connect(self._db_url, row_factory=dict_row, prepare_threshold=None)

    def get_channel_geo_lang(self, workspace_id: UUID, channel_id: UUID) -> tuple[str, str]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT country, language
                FROM public.channel_profile_versions
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY version_number DESC LIMIT 1
                """,
                (workspace_id, channel_id),
            )
            row = cur.fetchone()
        if not row:
            return "BR", "pt-BR"
        return str(row.get("country") or "BR").upper(), str(row.get("language") or "pt-BR")

    def find_cached_validation(
        self, workspace_id: UUID, keyword: str, geo: str, gprop: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM public.google_trends_validations
                WHERE workspace_id = %s
                  AND lower(keyword) = lower(%s)
                  AND upper(geo) = upper(%s)
                  AND lower(gprop) = lower(%s)
                  AND status = 'SUCCEEDED'
                  AND expires_at > timezone('utc', now())
                ORDER BY created_at DESC LIMIT 1
                """,
                (workspace_id, keyword.strip(), geo.strip(), gprop.strip()),
            )
            return cur.fetchone()

    def save_validation(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID | None,
        studio_term_id: UUID | None,
        report: GoogleTrendsReport,
        captured_via: str,
        created_by: UUID,
        job_id: UUID | None = None,
    ) -> dict[str, Any]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.google_trends_validations (
                    workspace_id, channel_id, studio_term_id, keyword, geo, gprop,
                    direction_12m, recent_avg_12m, baseline_avg_12m, slope_12m,
                    durability_5y, peak_decay_pct, seasonal_months_json, verdict,
                    confidence, summary, points_12m_json, points_5y_json,
                    top_queries_json, rising_queries_json, breakout_queries_json,
                    limitations_json, captured_via, status, job_id, created_by
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s,
                    %s, %s, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s, 'SUCCEEDED', %s, %s
                )
                RETURNING *
                """,
                (
                    workspace_id,
                    channel_id,
                    studio_term_id,
                    report.keyword,
                    report.geo,
                    report.gprop,
                    report.direction_12m.value,
                    report.recent_avg_12m,
                    report.baseline_avg_12m,
                    report.slope_12m,
                    report.durability_5y.value,
                    report.peak_decay_pct,
                    json.dumps(report.seasonal_months),
                    report.verdict.value,
                    report.confidence,
                    report.summary,
                    json.dumps([asdict(p) for p in report.points_12m]),
                    json.dumps([asdict(p) for p in report.points_5y]),
                    json.dumps([asdict(q) for q in report.top_queries]),
                    json.dumps([asdict(q) for q in report.rising_queries]),
                    json.dumps([asdict(q) for q in report.breakout_queries]),
                    json.dumps(report.limitations),
                    captured_via,
                    job_id,
                    created_by,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        assert row is not None
        return row

    def list_validations(self, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM public.google_trends_validations WHERE workspace_id = %s"
        params: list[Any] = [workspace_id]
        if channel_id:
            sql += " AND channel_id = %s"
            params.append(channel_id)
        sql += " ORDER BY created_at DESC LIMIT 40"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
