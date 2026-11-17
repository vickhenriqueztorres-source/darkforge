from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.generation.title_thumbnail import check_originality, generate_original_title_alternatives
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class ResearchCandidateInput(BaseModel):
    external_channel_id: str
    channel_name: str
    language: str | None = None
    external_video_id: str | None = None
    title: str = ""
    description: str = ""
    format: str = "unknown"
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    public_views: int | None = None
    public_likes: int | None = None
    public_comments: int | None = None


class CreateResearchRunRequest(BaseModel):
    channel_id: UUID
    objective: str = Field(min_length=2)
    query_terms: list[str] = Field(default_factory=list)
    language: str = "pt-BR"
    period_days: int = Field(default=90, ge=1, le=3650)
    format_filter: str = Field(default="all", pattern="^(all|long|short|live)$")
    quota_budget: int = Field(default=20, ge=1, le=500)
    channel_niche: str = ""
    channel_pillars: list[str] = Field(default_factory=list)
    candidates: list[ResearchCandidateInput] = Field(default_factory=list)


class CurateReferenceRequest(BaseModel):
    entity_type: str = Field(pattern="^(channel|video)$")
    status: str = Field(pattern="^(pending|approved|rejected|archived)$")
    notes: str = ""
    collection_name: str = "default"


class AnalyzeTitleRequest(BaseModel):
    title: str = Field(min_length=1)
    channel_id: UUID | None = None
    reference_video_id: UUID | None = None


class GenerateTitlesRequest(BaseModel):
    channel_name: str
    niche: str
    topic: str
    reference_titles: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)


class OriginalityCheckRequest(BaseModel):
    candidate_title: str
    reference_titles: list[str] = Field(default_factory=list)


class AnalyzeThumbnailRequest(BaseModel):
    source_url: str
    reference_video_id: UUID | None = None
    reference_notes: str = ""


def _serialize_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_serialize_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize_dict(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


@router.post("/research/runs", status_code=201)
def create_research_run(
    body: CreateResearchRunRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    if container.research is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ResearchService nao configurado.", http_status=503, retryable=True)
    res = container.research.create_and_populate_run(
        actor=actor,
        workspace_id=workspace_id,
        channel_id=body.channel_id,
        objective=body.objective,
        query_terms=body.query_terms,
        language=body.language,
        period_days=body.period_days,
        format_filter=body.format_filter,
        quota_budget=body.quota_budget,
        idempotency_key=idempotency_key or str(uuid4()),
        candidates=[c.model_dump() for c in body.candidates],
        channel_niche=body.channel_niche,
        channel_pillars=body.channel_pillars,
    )
    return _serialize_dict(res)


@router.get("/research/runs/{run_id}")
def get_research_run(
    run_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    if container.research is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ResearchService nao configurado.", http_status=503, retryable=True)
    return _serialize_dict(container.research.get_run_detail(actor, workspace_id, run_id))


@router.get("/research/references")
def list_references(
    curation_status: str | None = Query(default=None),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(actor, workspace_id)
    if container.research_repo is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ResearchRepo nao configurado.", http_status=503, retryable=True)
    return _serialize_dict(container.research_repo.list_references(workspace_id, curation_status))


@router.post("/research/references/{ref_id}/curate")
def curate_reference(
    ref_id: UUID,
    body: CurateReferenceRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    if container.research is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ResearchService nao configurado.", http_status=503, retryable=True)
    return _serialize_dict(
        container.research.curate_reference(
            actor, workspace_id, body.entity_type, ref_id, body.status, body.notes, body.collection_name
        )
    )


@router.post("/intel/titles/analyze")
def analyze_title(
    body: AnalyzeTitleRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    if container.title_thumb is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "TitleThumbnailService nao configurado.", http_status=503, retryable=True)
    return _serialize_dict(
        container.title_thumb.analyze_title(actor, workspace_id, body.title, body.channel_id, body.reference_video_id)
    )


@router.post("/intel/titles/generate")
def generate_titles(
    body: GenerateTitlesRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(actor, workspace_id)
    items = generate_original_title_alternatives(
        body.channel_name, body.niche, body.topic, body.reference_titles, body.forbidden_topics
    )
    return {"items": items}


@router.post("/intel/titles/originality-check")
def check_title_originality(
    body: OriginalityCheckRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(actor, workspace_id)
    return check_originality(body.candidate_title, body.reference_titles)


@router.post("/intel/thumbnails/analyze")
def analyze_thumbnail(
    body: AnalyzeThumbnailRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    if container.title_thumb is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "TitleThumbnailService nao configurado.", http_status=503, retryable=True)
    return _serialize_dict(
        container.title_thumb.analyze_thumbnail(
            actor, workspace_id, body.source_url, image_bytes=None, reference_video_id=body.reference_video_id, reference_notes=body.reference_notes
        )
    )
