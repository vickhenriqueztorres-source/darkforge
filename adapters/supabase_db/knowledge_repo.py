from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from core.errors import AppError, ErrorCode
from core.knowledge.chunker import ChunkDraft


class PostgresKnowledgeRepository:
    """Postgres + pgvector + FTS repository for Knowledge/RAG Studio (SP-06)."""

    def __init__(self, database_url: str) -> None:
        self._dsn = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=6, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Postgres indisponivel.", http_status=503, retryable=True) from exc

    def find_source_by_hash(self, workspace_id: UUID, content_sha256: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM public.knowledge_sources
                WHERE workspace_id = %s AND content_sha256 = %s AND status <> 'DELETED'
                ORDER BY source_version DESC LIMIT 1
                """,
                (str(workspace_id), content_sha256),
            ).fetchone()
        return dict(row) if row else None

    def insert_source(
        self,
        workspace_id: UUID,
        channel_id: UUID | None,
        title: str,
        source_type: str,
        language: str,
        origin_type: str,
        rights_status: str,
        allowed_in_generation: bool,
        collection_name: str,
        content_text: str,
        content_sha256: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.knowledge_sources (
                    workspace_id, channel_id, title, source_type, language, origin_type,
                    rights_status, allowed_in_generation, curation_level, status,
                    collection_name, content_text, content_sha256, source_version, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'L0', 'IMPORTED', %s, %s, %s, 1, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id) if channel_id else None,
                    title,
                    source_type,
                    language,
                    origin_type,
                    rights_status,
                    allowed_in_generation,
                    collection_name,
                    content_text,
                    content_sha256,
                    str(user_id),
                ),
            ).fetchone()
            conn.commit()
        return dict(row)

    def list_sources(self, workspace_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, workspace_id, channel_id, title, source_type, language, origin_type,
                       rights_status, allowed_in_generation, curation_level, status,
                       collection_name, source_version, created_at, updated_at
                FROM public.knowledge_sources
                WHERE workspace_id = %s AND status <> 'DELETED'
                ORDER BY created_at DESC
                """,
                (str(workspace_id),),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_source_review(
        self,
        workspace_id: UUID,
        source_id: UUID,
        curation_level: str,
        status: str,
        allowed_in_generation: bool | None,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                UPDATE public.knowledge_sources
                SET curation_level = %s,
                    status = %s,
                    allowed_in_generation = COALESCE(%s, allowed_in_generation)
                WHERE workspace_id = %s AND id = %s
                RETURNING *
                """,
                (curation_level, status, allowed_in_generation, str(workspace_id), str(source_id)),
            ).fetchone()
            conn.commit()
        return dict(row) if row else None

    def get_active_revision(self, workspace_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM public.embedding_revisions WHERE workspace_id = %s AND status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1",
                (str(workspace_id),),
            ).fetchone()
        return dict(row) if row else None

    def get_or_create_active_revision(
        self, workspace_id: UUID, model: str, version: str, dimensions: int, force_new: bool = False
    ) -> dict[str, Any]:
        with self._connect() as conn:
            if not force_new:
                existing = conn.execute(
                    """
                    SELECT * FROM public.embedding_revisions
                    WHERE workspace_id = %s AND embedding_model = %s AND embedding_version = %s AND dimensions = %s
                    LIMIT 1
                    """,
                    (str(workspace_id), model, version, dimensions),
                ).fetchone()
                if existing:
                    return dict(existing)

            # Force new revision (for model upgrade / rebuild) uses distinct version suffix if needed
            ver_label = version if not force_new else f"{version}-rebuild"
            existing_reb = conn.execute(
                """
                SELECT * FROM public.embedding_revisions
                WHERE workspace_id = %s AND embedding_model = %s AND embedding_version = %s AND dimensions = %s
                LIMIT 1
                """,
                (str(workspace_id), model, ver_label, dimensions),
            ).fetchone()
            if existing_reb:
                return dict(existing_reb)

            row = conn.execute(
                """
                INSERT INTO public.embedding_revisions (workspace_id, embedding_model, embedding_version, dimensions, status)
                VALUES (%s, %s, %s, %s, 'BUILDING')
                RETURNING *
                """,
                (str(workspace_id), model, ver_label, dimensions),
            ).fetchone()
            conn.commit()
        return dict(row)

    def promote_revision_active(self, workspace_id: UUID, revision_id: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "UPDATE public.embedding_revisions SET status = 'DEPRECATED' WHERE workspace_id = %s AND status = 'ACTIVE' AND id <> %s",
                (str(workspace_id), str(revision_id)),
            )
            row = conn.execute(
                "UPDATE public.embedding_revisions SET status = 'ACTIVE' WHERE workspace_id = %s AND id = %s RETURNING *",
                (str(workspace_id), str(revision_id)),
            ).fetchone()
            conn.commit()
        return dict(row)

    def list_indexable_sources(self, workspace_id: UUID, source_ids: list[UUID] | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if source_ids:
                rows = conn.execute(
                    """
                    SELECT * FROM public.knowledge_sources
                    WHERE workspace_id = %s AND id = ANY(%s)
                      AND status IN ('APPROVED', 'INDEXED', 'REVIEWED')
                    """,
                    (str(workspace_id), [str(s) for s in source_ids]),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM public.knowledge_sources
                    WHERE workspace_id = %s AND status IN ('APPROVED', 'INDEXED')
                    """,
                    (str(workspace_id),),
                ).fetchall()
        return [dict(r) for r in rows]

    def upsert_chunks_and_embeddings(
        self,
        workspace_id: UUID,
        source: dict[str, Any],
        revision_id: UUID,
        chunks: list[ChunkDraft],
        vectors: list[list[float]],
    ) -> None:
        with self._connect() as conn:
            for chunk, vec in zip(chunks, vectors):
                c_row = conn.execute(
                    """
                    INSERT INTO public.knowledge_chunks (
                        workspace_id, source_id, channel_id, source_version, chunk_index, section_label, chunk_text, chunk_hash, language
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, source_version, chunk_index) DO UPDATE
                    SET chunk_text = EXCLUDED.chunk_text,
                        chunk_hash = EXCLUDED.chunk_hash,
                        section_label = EXCLUDED.section_label
                    RETURNING id
                    """,
                    (
                        str(workspace_id),
                        str(source["id"]),
                        str(source["channel_id"]) if source.get("channel_id") else None,
                        source["source_version"],
                        chunk.chunk_index,
                        chunk.section_label,
                        chunk.chunk_text,
                        chunk.chunk_hash,
                        source["language"],
                    ),
                ).fetchone()
                vec_lit = "[" + ",".join(str(x) for x in vec) + "]"
                conn.execute(
                    """
                    INSERT INTO public.knowledge_embeddings (workspace_id, chunk_id, revision_id, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (chunk_id, revision_id) DO UPDATE
                    SET embedding = EXCLUDED.embedding
                    """,
                    (str(workspace_id), str(c_row["id"]), str(revision_id), vec_lit),
                )
            conn.execute(
                "UPDATE public.knowledge_sources SET status = 'INDEXED' WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(source["id"])),
            )
            conn.commit()

    def hybrid_search(
        self,
        workspace_id: UUID,
        revision_id: UUID,
        query_text: str,
        query_vector: list[float],
        allowed_levels: list[str],
        channel_id: UUID | None = None,
        language: str | None = None,
        collection_name: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        vec_lit = "[" + ",".join(str(x) for x in query_vector) + "]"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    kc.id AS chunk_id,
                    ks.id AS source_id,
                    ks.title AS source_title,
                    ks.curation_level,
                    ks.collection_name,
                    ks.rights_status,
                    kc.section_label,
                    kc.chunk_text,
                    (1.0 - (ke.embedding <=> %s::vector)) AS vec_score,
                    COALESCE(ts_rank_cd(kc.fts_tsv, plainto_tsquery('simple', %s)), 0.0) AS fts_score,
                    (
                        0.65 * (1.0 - (ke.embedding <=> %s::vector))
                        + 0.35 * LEAST(1.0, COALESCE(ts_rank_cd(kc.fts_tsv, plainto_tsquery('simple', %s)), 0.0))
                        + CASE WHEN ks.curation_level = 'L3' THEN 0.15 ELSE 0.0 END
                    ) AS hybrid_score
                FROM public.knowledge_embeddings AS ke
                JOIN public.knowledge_chunks AS kc ON kc.id = ke.chunk_id AND kc.workspace_id = ke.workspace_id
                JOIN public.knowledge_sources AS ks ON ks.id = kc.source_id AND ks.workspace_id = kc.workspace_id
                WHERE ke.workspace_id = %s
                  AND ke.revision_id = %s
                  AND ks.status = 'INDEXED'
                  AND ks.allowed_in_generation = true
                  AND ks.rights_status <> 'restricted'
                  AND ks.curation_level = ANY(%s)
                  AND (%s::uuid IS NULL OR ks.channel_id IS NULL OR ks.channel_id = %s::uuid)
                  AND (%s::text IS NULL OR ks.language = %s::text)
                  AND (%s::text IS NULL OR ks.collection_name = %s::text)
                ORDER BY hybrid_score DESC
                LIMIT %s
                """,
                (
                    vec_lit,
                    query_text,
                    vec_lit,
                    query_text,
                    str(workspace_id),
                    str(revision_id),
                    allowed_levels,
                    str(channel_id) if channel_id else None,
                    str(channel_id) if channel_id else None,
                    language,
                    language,
                    collection_name,
                    collection_name,
                    top_k,
                ),
            ).fetchall()
        return [dict(r) for r in rows]

    def revalidate_chunk_ids(self, workspace_id: UUID, chunk_ids: list[UUID]) -> list[UUID]:
        if not chunk_ids:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT kc.id
                FROM public.knowledge_chunks AS kc
                JOIN public.knowledge_sources AS ks ON ks.id = kc.source_id
                WHERE kc.workspace_id = %s
                  AND kc.id = ANY(%s)
                  AND ks.status = 'INDEXED'
                  AND ks.allowed_in_generation = true
                """,
                (str(workspace_id), [str(cid) for cid in chunk_ids]),
            ).fetchall()
        return [UUID(str(r["id"])) for r in rows]

    def record_retrieval_run(
        self,
        workspace_id: UUID,
        channel_id: UUID | None,
        revision_id: UUID,
        query_text: str,
        filters: dict[str, Any],
        chunk_ids: list[str],
        scores: list[float],
        user_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.retrieval_runs (workspace_id, channel_id, revision_id, query_text, filters_json, chunk_ids_json, scores_json, created_by)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id) if channel_id else None,
                    str(revision_id),
                    query_text,
                    json.dumps(filters),
                    json.dumps(chunk_ids),
                    json.dumps(scores),
                    str(user_id),
                ),
            ).fetchone()
            conn.commit()
        return dict(row)

    def record_generation(
        self,
        workspace_id: UUID,
        channel_id: UUID | None,
        profile_version_id: UUID | None,
        retrieval_run_id: UUID | None,
        prompt_name: str,
        prompt_version: str,
        provider_name: str,
        model_id: str,
        external_consent_granted: bool,
        data_categories_sent: list[str],
        context_chunk_ids: list[UUID],
        output_json: dict[str, Any],
        validations_json: dict[str, Any],
        user_id: UUID,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO public.generations (
                    workspace_id, channel_id, profile_version_id, retrieval_run_id,
                    prompt_name, prompt_version, provider_name, model_id,
                    external_consent_granted, data_categories_sent, context_chunk_ids,
                    output_json, validations_json, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[], %s::jsonb, %s::jsonb, %s)
                RETURNING *
                """,
                (
                    str(workspace_id),
                    str(channel_id) if channel_id else None,
                    str(profile_version_id) if profile_version_id else None,
                    str(retrieval_run_id) if retrieval_run_id else None,
                    prompt_name,
                    prompt_version,
                    provider_name,
                    model_id,
                    external_consent_granted,
                    data_categories_sent,
                    [str(c) for c in context_chunk_ids],
                    json.dumps(output_json),
                    json.dumps(validations_json),
                    str(user_id),
                ),
            ).fetchone()
            conn.commit()
        return dict(row)

    def get_generation_provenance(self, workspace_id: UUID, generation_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn:
            gen = conn.execute(
                "SELECT * FROM public.generations WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(generation_id)),
            ).fetchone()
            if not gen:
                return None
            chunk_ids = [str(c) for c in (gen.get("context_chunk_ids") or [])]
            chunks = []
            if chunk_ids:
                chunks = conn.execute(
                    """
                    SELECT kc.id AS chunk_id, kc.source_id, kc.section_label, kc.chunk_text, ks.title AS source_title, ks.curation_level, ks.status
                    FROM public.knowledge_chunks AS kc
                    JOIN public.knowledge_sources AS ks ON ks.id = kc.source_id
                    WHERE kc.workspace_id = %s AND kc.id = ANY(%s::uuid[])
                    """,
                    (str(workspace_id), chunk_ids),
                ).fetchall()
        return {"generation": dict(gen), "cited_chunks": [dict(c) for c in chunks]}

    def archive_or_delete_source(self, workspace_id: UUID, source_id: UUID, hard_delete: bool = False) -> dict[str, Any] | None:
        with self._connect() as conn:
            src = conn.execute(
                "SELECT id, status FROM public.knowledge_sources WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(source_id)),
            ).fetchone()
            if not src:
                return None
            emb_res = conn.execute(
                """
                DELETE FROM public.knowledge_embeddings
                WHERE workspace_id = %s AND chunk_id IN (
                    SELECT id FROM public.knowledge_chunks WHERE workspace_id = %s AND source_id = %s
                )
                """,
                (str(workspace_id), str(workspace_id), str(source_id)),
            )
            emb_del = emb_res.rowcount or 0
            chunk_del = 0
            if hard_delete:
                ch_res = conn.execute(
                    "DELETE FROM public.knowledge_chunks WHERE workspace_id = %s AND source_id = %s",
                    (str(workspace_id), str(source_id)),
                )
                chunk_del = ch_res.rowcount or 0
                conn.execute(
                    "UPDATE public.knowledge_sources SET status = 'DELETED', allowed_in_generation = false, content_text = '[DELETED]' WHERE workspace_id = %s AND id = %s",
                    (str(workspace_id), str(source_id)),
                )
            else:
                conn.execute(
                    "UPDATE public.knowledge_sources SET status = 'ARCHIVED', allowed_in_generation = false WHERE workspace_id = %s AND id = %s",
                    (str(workspace_id), str(source_id)),
                )
            conn.commit()
        return {
            "source_id": str(source_id),
            "action": "deleted" if hard_delete else "archived",
            "embeddings_removed": emb_del,
            "chunks_removed": chunk_del,
            "backup_retention_notice": "Backups anteriores podem manter snapshot ate expirar a janela de retencao.",
        }
