from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.research.channel_selector import ReferenceChannelCandidate, TargetChannelFit
from core.research.viral_outlier_analyzer import ChannelVideoRecord
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class ChannelCandidatePayload(BaseModel):
    external_channel_id: str
    display_name: str
    language: str = "pt-BR"
    market_country: str = "BR"
    recent_video_views_90d: list[int] = Field(default_factory=list)
    all_recent_20_30_views: list[int] = Field(default_factory=list)
    production_format: str = "faceless_essay"
    audience_profile_tags: list[str] = Field(default_factory=list)
    is_celebrity_or_mega_brand: bool = False
    subscriber_count: int | None = None


class Phase1EvaluateChannelsRequest(BaseModel):
    channel_id: UUID
    target_language: str = "pt-BR"
    target_country: str = "BR"
    feasible_formats: list[str] = Field(default_factory=lambda: ["faceless_essay", "documentary"])
    target_audience_tags: list[str] = Field(default_factory=list)
    min_outlier_ratio: float = 3.0
    candidates: list[ChannelCandidatePayload] = Field(default_factory=list)


class Phase2VideoPayload(BaseModel):
    external_video_id: str
    external_channel_id: str
    channel_name: str
    title: str
    views: int
    days_since_upload: int = Field(ge=1)
    duration_seconds: int | None = None
    topic: str = ""
    format_name: str = "long"
    is_breaking_news: bool = False
    has_celebrity_collab: bool = False
    channel_authority_only: bool = False
    in_suggested_feed: bool = False


class Phase2FindOutliersRequest(BaseModel):
    channel_id: UUID
    small_niche: bool = False
    videos: list[Phase2VideoPayload] = Field(default_factory=list)


class Phase3AutopsyRequest(BaseModel):
    channel_id: UUID
    external_video_id: str
    title: str
    transcript_or_notes: str = ""
    comments: list[str] = Field(default_factory=list)
    thumbnail_focus: str = ""
    thumbnail_visual_question: str = ""
    thumbnail_emotion: str = "curiosidade"
    thumbnail_text: str = ""
    first_visual_description: str = ""


class Phase4SynthesizeRequest(BaseModel):
    channel_id: UUID
    autopsy_ids: list[UUID] | None = None
    own_validated_topic: str = Field(min_length=2)
    new_angle: str = Field(min_length=2)
    target_format: str = Field(default="long", pattern="^(long|short|live)$")


class CreateBatchRequest(BaseModel):
    channel_id: UUID
    mechanism_id: UUID | None = None
    brief_id: UUID | None = None
    title: str = Field(min_length=2)


class UpdateBatchMetricsRequest(BaseModel):
    status: str = Field(pattern="^(PLANNED|PUBLISHED_MEASURING|VALIDATED|INCONCLUSIVE|REJECTED)$")
    impressions: int | None = None
    ctr_pct: float | None = None
    retention_30s_pct: float | None = None
    outcome_notes: str = ""


def _ser(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__float__") and type(obj).__name__ == "Decimal":
        return float(obj)
    return obj


def _require_re(container: ServiceContainer):
    if container.reverse_engineering is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "ReverseEngineeringService nao configurado.", http_status=503, retryable=True)
    return container.reverse_engineering


@router.get("/research/reverse-engineering/state")
def get_re_state(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    return _ser(svc.list_state(user, workspace_id, channel_id=channel_id))


@router.post("/research/reverse-engineering/phase1-channels")
def phase1_channels(
    body: Phase1EvaluateChannelsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    target = TargetChannelFit(
        language=body.target_language,
        market_country=body.target_country,
        feasible_formats=body.feasible_formats,
        target_audience_tags=body.target_audience_tags,
        min_outlier_ratio=body.min_outlier_ratio,
    )
    cands = [ReferenceChannelCandidate(**c.model_dump()) for c in body.candidates]
    return _ser(svc.phase1_evaluate_channels(user, workspace_id, body.channel_id, target=target, candidates=cands))


@router.post("/research/reverse-engineering/phase2-outliers")
def phase2_outliers(
    body: Phase2FindOutliersRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    by_ch: dict[str, list[ChannelVideoRecord]] = {}
    for v in body.videos:
        by_ch.setdefault(v.external_channel_id, []).append(ChannelVideoRecord(**v.model_dump()))
    return _ser(svc.phase2_find_viral_outliers(user, workspace_id, body.channel_id, videos_by_channel=by_ch, small_niche=body.small_niche))


@router.post("/research/reverse-engineering/phase3-autopsy")
def phase3_autopsy(
    body: Phase3AutopsyRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    return _ser(
        {
            "autopsy": svc.phase3_run_autopsy(
                user,
                workspace_id,
                body.channel_id,
                external_video_id=body.external_video_id,
                title=body.title,
                transcript_or_notes=body.transcript_or_notes,
                comments=body.comments,
                thumbnail_focus=body.thumbnail_focus,
                thumbnail_visual_question=body.thumbnail_visual_question,
                thumbnail_emotion=body.thumbnail_emotion,
                thumbnail_text=body.thumbnail_text,
                first_visual_description=body.first_visual_description,
            )
        }
    )


@router.post("/research/reverse-engineering/phase4-synthesize")
def phase4_synthesize(
    body: Phase4SynthesizeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    return _ser(
        {
            "mechanism": svc.phase4_synthesize_mechanism(
                user,
                workspace_id,
                body.channel_id,
                autopsy_ids=body.autopsy_ids,
                own_validated_topic=body.own_validated_topic,
                new_angle=body.new_angle,
                target_format=body.target_format,
            )
        }
    )


@router.post("/research/reverse-engineering/batches")
def create_experiment_batch(
    body: CreateBatchRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    return _ser(
        {
            "batch": svc.create_experiment_batch(
                user,
                workspace_id,
                body.channel_id,
                title=body.title,
                mechanism_id=body.mechanism_id,
                brief_id=body.brief_id,
            )
        }
    )


@router.patch("/research/reverse-engineering/batches/{batch_id}")
def update_experiment_batch(
    batch_id: UUID,
    body: UpdateBatchMetricsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_re(container)
    return _ser(
        {
            "batch": svc.record_experiment_metrics(
                user,
                workspace_id,
                batch_id,
                status=body.status,
                impressions=body.impressions,
                ctr_pct=body.ctr_pct,
                retention_30s_pct=body.retention_30s_pct,
                outcome_notes=body.outcome_notes,
            )
        }
    )
