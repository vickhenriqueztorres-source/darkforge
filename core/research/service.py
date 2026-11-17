from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from core.analytics.models import QuotaPool
from core.analytics.ports import AnalyticsRepositoryPort
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


@dataclass(frozen=True)
class SimilarityBreakdown:
    score: float
    factors: dict[str, Any]


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower())}


def compute_channel_similarity(
    channel_niche: str,
    channel_pillars: list[str],
    channel_language: str,
    candidate_title_corpus: str,
    candidate_language: str | None,
) -> SimilarityBreakdown:
    """Computes explainable public similarity (RES-002). Never infers private audience overlap."""
    base_tokens = _tokenize(channel_niche + " " + " ".join(channel_pillars))
    cand_tokens = _tokenize(candidate_title_corpus)
    if base_tokens and cand_tokens:
        overlap = len(base_tokens & cand_tokens) / max(1, len(base_tokens))
    else:
        overlap = 0.0
    topic_score = min(100.0, round(overlap * 100.0, 2))
    lang_match = 100.0 if (candidate_language and candidate_language.lower().startswith(channel_language.split("-")[0].lower())) else 20.0
    total = round(0.7 * topic_score + 0.3 * lang_match, 2)
    return SimilarityBreakdown(
        score=total,
        factors={
            "topic_overlap_pct": topic_score,
            "language_match_pct": lang_match,
            "matched_terms": sorted(base_tokens & cand_tokens)[:12],
            "limitation": "Similaridade baseada apenas em metadados publicos observaveis; nao mede audiencia privada.",
        },
    )


def content_hash_for_video(external_video_id: str, title: str, description: str) -> str:
    raw = f"{external_video_id}|{title.strip()}|{description.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ResearchService:
    """Executes public research runs with quota priority, deduplication, and curation (SP-04)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        analytics_repo: AnalyticsRepositoryPort | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._analytics_repo = analytics_repo

    def create_and_populate_run(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        objective: str,
        query_terms: list[str],
        language: str,
        period_days: int,
        format_filter: str,
        quota_budget: int,
        idempotency_key: str,
        candidates: list[dict[str, Any]],
        channel_niche: str = "",
        channel_pillars: list[str] | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if not objective.strip():
            raise AppError(ErrorCode.VALIDATION_ERROR, "Objetivo da pesquisa e obrigatorio.", http_status=422)

        existing = self._repo.get_run_by_idempotency(workspace_id, idempotency_key)
        if existing is not None:
            return {"run": existing, "deduplicated": True}

        reservation_id: UUID | None = None
        if self._analytics_repo is not None:
            reservation_id = self._analytics_repo.reserve_quota(
                workspace_id,
                QuotaPool.PUBLIC_RESEARCH,
                "research.run",
                min(quota_budget, max(1, len(candidates) + 1)),
                uuid4(),
            )

        try:
            run = self._repo.create_run(
                workspace_id=workspace_id,
                channel_id=channel_id,
                objective=objective.strip(),
                query_terms=query_terms,
                language=language,
                period_days=period_days,
                format_filter=format_filter,
                quota_budget=quota_budget,
                idempotency_key=idempotency_key,
                user_id=actor.user_id,
            )

            saved_channels = 0
            saved_videos = 0
            for cand in candidates:
                sim = compute_channel_similarity(
                    channel_niche=channel_niche or " ".join(query_terms),
                    channel_pillars=channel_pillars or query_terms,
                    channel_language=language,
                    candidate_title_corpus=f"{cand.get('channel_name', '')} {cand.get('title', '')} {cand.get('description', '')}",
                    candidate_language=cand.get("language", language),
                )
                ref_ch_id = self._repo.upsert_reference_channel(
                    workspace_id=workspace_id,
                    run_id=run["id"],
                    external_channel_id=cand["external_channel_id"],
                    canonical_url=f"https://www.youtube.com/channel/{cand['external_channel_id']}",
                    display_name=cand.get("channel_name", cand["external_channel_id"]),
                    language=cand.get("language"),
                    similarity_score=sim.score,
                    similarity_factors=sim.factors,
                )
                saved_channels += 1
                if cand.get("external_video_id"):
                    self._repo.upsert_reference_video(
                        workspace_id=workspace_id,
                        ref_channel_id=ref_ch_id,
                        run_id=run["id"],
                        external_video_id=cand["external_video_id"],
                        canonical_url=f"https://www.youtube.com/watch?v={cand['external_video_id']}",
                        content_hash=content_hash_for_video(
                            cand["external_video_id"], cand.get("title", ""), cand.get("description", "")
                        ),
                        title=cand.get("title", ""),
                        description=cand.get("description", ""),
                        format_name=cand.get("format", "unknown"),
                        duration_seconds=cand.get("duration_seconds"),
                        thumbnail_url=cand.get("thumbnail_url"),
                        public_views_snapshot=cand.get("public_views"),
                        public_likes_snapshot=cand.get("public_likes"),
                        public_comments_snapshot=cand.get("public_comments"),
                    )
                    saved_videos += 1

            used = max(1, min(quota_budget, len(candidates) + 1))
            if self._analytics_repo is not None and reservation_id is not None:
                self._analytics_repo.commit_quota(reservation_id, used)

            updated_run = self._repo.complete_run(workspace_id, run["id"], quota_consumed=used)
            return {
                "run": updated_run,
                "deduplicated": False,
                "saved_channels": saved_channels,
                "saved_videos": saved_videos,
            }
        except Exception:
            if self._analytics_repo is not None and reservation_id is not None:
                self._analytics_repo.release_quota(reservation_id)
            raise

    def get_run_detail(self, actor: AuthenticatedUser, workspace_id: UUID, run_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        detail = self._repo.get_run_detail(workspace_id, run_id)
        if detail is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Research run nao encontrada.", http_status=404)
        return detail

    def curate_reference(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        entity_type: str,
        ref_id: UUID,
        status: str,
        notes: str = "",
        collection_name: str = "default",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if entity_type not in ("channel", "video"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "entity_type deve ser channel ou video.", http_status=422)
        if status not in ("pending", "approved", "rejected", "archived"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "curation_status invalido.", http_status=422)
        updated = self._repo.update_curation(workspace_id, entity_type, ref_id, status, notes, collection_name)
        if updated is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Referencia nao encontrada neste workspace.", http_status=404)
        return updated
