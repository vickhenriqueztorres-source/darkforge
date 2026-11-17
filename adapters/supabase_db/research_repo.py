from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from core.errors import AppError, ErrorCode


class PostgresResearchAndIntelRepository:
    def __init__(self, database_url: str) -> None:
        self._dsn = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=6, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Postgres indisponivel.", http_status=503, retryable=True) from exc

    def get_run_by_idempotency(self, workspace_id: UUID, idempotency_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM public.research_runs WHERE workspace_id = %s AND idempotency_key = %s",
                (str(workspace_id), idempotency_key),
            ).fetchone()
        return dict(row) if row else None

    def create_run(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        objective: str,
        query_terms: list[str],
        language: str,
        period_days: int,
        format_filter: str,
        quota_budget: int,
        idempotency_key: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.research_runs
                    (workspace_id, channel_id, objective, query_terms, language, period_days, format_filter, quota_budget, idempotency_key, status, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'RUNNING', %s)
                RETURNING *
                """,
                (str(workspace_id), str(channel_id), objective, query_terms, language, period_days, format_filter, quota_budget, idempotency_key, str(user_id)),
            ).fetchone()
            conn.commit()
        return dict(row)

    def complete_run(self, workspace_id: UUID, run_id: UUID, quota_consumed: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                UPDATE public.research_runs
                SET status = 'SUCCEEDED', quota_consumed = %s
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (quota_consumed, str(workspace_id), str(run_id)),
            ).fetchone()
            conn.commit()
        return dict(row)

    def upsert_reference_channel(
        self,
        workspace_id: UUID,
        run_id: UUID,
        external_channel_id: str,
        canonical_url: str,
        display_name: str,
        language: str | None,
        similarity_score: float,
        similarity_factors: dict[str, Any],
    ) -> UUID:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.reference_channels
                    (workspace_id, research_run_id, external_channel_id, canonical_url, display_name, language, similarity_score, similarity_factors_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (workspace_id, platform, external_channel_id) DO UPDATE
                SET similarity_score = EXCLUDED.similarity_score,
                    similarity_factors_json = EXCLUDED.similarity_factors_json,
                    observed_at = timezone('utc', now())
                RETURNING id
                """,
                (str(workspace_id), str(run_id), external_channel_id, canonical_url, display_name, language, similarity_score, json.dumps(similarity_factors)),
            ).fetchone()
            conn.commit()
        return UUID(str(row["id"]))

    def upsert_reference_video(
        self,
        workspace_id: UUID,
        ref_channel_id: UUID,
        run_id: UUID,
        external_video_id: str,
        canonical_url: str,
        content_hash: str,
        title: str,
        description: str,
        format_name: str,
        duration_seconds: int | None,
        thumbnail_url: str | None,
        public_views_snapshot: int | None,
        public_likes_snapshot: int | None,
        public_comments_snapshot: int | None,
    ) -> UUID:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.reference_videos (
                    workspace_id, reference_channel_id, research_run_id, external_video_id, canonical_url,
                    content_hash, title, description, format, duration_seconds, thumbnail_url,
                    public_views_snapshot, public_likes_snapshot, public_comments_snapshot
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, platform, external_video_id) DO UPDATE
                SET content_hash = EXCLUDED.content_hash,
                    title = EXCLUDED.title,
                    public_views_snapshot = EXCLUDED.public_views_snapshot,
                    public_likes_snapshot = EXCLUDED.public_likes_snapshot,
                    public_comments_snapshot = EXCLUDED.public_comments_snapshot,
                    snapshot_observed_at = timezone('utc', now())
                RETURNING id
                """,
                (
                    str(workspace_id), str(ref_channel_id), str(run_id), external_video_id, canonical_url,
                    content_hash, title, description, format_name, duration_seconds, thumbnail_url,
                    public_views_snapshot, public_likes_snapshot, public_comments_snapshot,
                ),
            ).fetchone()
            conn.commit()
        return UUID(str(row["id"]))

    def get_run_detail(self, workspace_id: UUID, run_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn:
            run = conn.execute(
                "SELECT * FROM public.research_runs WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(run_id)),
            ).fetchone()
            if not run:
                return None
            channels = conn.execute(
                "SELECT * FROM public.reference_channels WHERE workspace_id = %s AND research_run_id = %s ORDER BY similarity_score DESC",
                (str(workspace_id), str(run_id)),
            ).fetchall()
            videos = conn.execute(
                "SELECT * FROM public.reference_videos WHERE workspace_id = %s AND research_run_id = %s ORDER BY snapshot_observed_at DESC",
                (str(workspace_id), str(run_id)),
            ).fetchall()
        return {
            "run": dict(run),
            "channels": [dict(c) for c in channels],
            "videos": [dict(v) for v in videos],
            "scope_notice": "Dados publicos observaveis; metricas privadas (CTR/retencao/receita) indisponiveis.",
        }

    def list_runs(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM public.research_runs WHERE workspace_id = %s ORDER BY created_at DESC LIMIT 50",
                (str(workspace_id),),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_references(self, workspace_id: UUID, curation_status: str | None = None) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as conn:
            if curation_status:
                chs = conn.execute(
                    "SELECT * FROM public.reference_channels WHERE workspace_id = %s AND curation_status = %s ORDER BY similarity_score DESC",
                    (str(workspace_id), curation_status),
                ).fetchall()
                vids = conn.execute(
                    "SELECT * FROM public.reference_videos WHERE workspace_id = %s AND curation_status = %s ORDER BY snapshot_observed_at DESC",
                    (str(workspace_id), curation_status),
                ).fetchall()
            else:
                chs = conn.execute(
                    "SELECT * FROM public.reference_channels WHERE workspace_id = %s ORDER BY similarity_score DESC",
                    (str(workspace_id),),
                ).fetchall()
                vids = conn.execute(
                    "SELECT * FROM public.reference_videos WHERE workspace_id = %s ORDER BY snapshot_observed_at DESC",
                    (str(workspace_id),),
                ).fetchall()
        return {"channels": [dict(c) for c in chs], "videos": [dict(v) for v in vids]}

    def update_curation(
        self, workspace_id: UUID, entity_type: str, ref_id: UUID, status: str, notes: str, collection_name: str
    ) -> dict[str, Any] | None:
        table = "public.reference_channels" if entity_type == "channel" else "public.reference_videos"
        with self._connect() as conn:
            row = conn.execute(
                f"""
                UPDATE {table}
                SET curation_status = %s, notes = %s, collection_name = %s
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (status, notes, collection_name, str(workspace_id), str(ref_id)),
            ).fetchone()
            conn.commit()
        return dict(row) if row else None

    def save_title_analysis(
        self, workspace_id: UUID, channel_id: UUID | None, ref_video_id: UUID | None, analysis: dict[str, Any], user_id: UUID
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.title_analyses
                    (workspace_id, channel_id, reference_video_id, source_title, features_json, editorial_formula, confidence, limitations_json, created_by)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id) if channel_id else None,
                    str(ref_video_id) if ref_video_id else None,
                    analysis["source_title"],
                    json.dumps({"features": analysis["features"], "word_count": analysis["word_count"], "char_count": analysis["char_count"]}),
                    analysis["editorial_formula"],
                    analysis["confidence"],
                    json.dumps(analysis["limitations"]),
                    str(user_id),
                ),
            ).fetchone()
            conn.commit()
        return dict(row)

    def upsert_thumbnail_asset(
        self, workspace_id: UUID, reference_video_id: UUID | None, source_url: str, sha256: str | None, availability_status: str
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.thumbnail_assets (workspace_id, reference_video_id, source_url, sha256, availability_status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (workspace_id, source_url) DO UPDATE
                SET sha256 = COALESCE(EXCLUDED.sha256, public.thumbnail_assets.sha256),
                    availability_status = EXCLUDED.availability_status,
                    collected_at = timezone('utc', now())
                RETURNING *
                """,
                (str(workspace_id), str(reference_video_id) if reference_video_id else None, source_url, sha256, availability_status),
            ).fetchone()
            conn.commit()
        return dict(row)

    def save_thumbnail_analysis(
        self,
        workspace_id: UUID,
        thumbnail_asset_id: UUID,
        vision_status: str,
        ocr_text: str | None,
        composition_json: dict[str, Any],
        differentiation_notes: str,
        limitations: list[str],
        user_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.thumbnail_analyses
                    (workspace_id, thumbnail_asset_id, vision_status, ocr_text, composition_json, differentiation_notes, limitations_json, created_by)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(thumbnail_asset_id),
                    vision_status,
                    ocr_text,
                    json.dumps(composition_json),
                    differentiation_notes,
                    json.dumps(limitations),
                    str(user_id),
                ),
            ).fetchone()
            conn.commit()
        return dict(row)
