from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AudienceInterestLevel(StrEnum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

    @property
    def rank(self) -> int:
        return {
            AudienceInterestLevel.UNKNOWN: 0,
            AudienceInterestLevel.LOW: 1,
            AudienceInterestLevel.MEDIUM: 2,
            AudienceInterestLevel.HIGH: 3,
            AudienceInterestLevel.VERY_HIGH: 4,
        }[self]


def normalize_interest_level(raw: str | None) -> AudienceInterestLevel:
    txt = (raw or "").strip().lower()
    if any(k in txt for k in ("muito alto", "very high", "very_high")):
        return AudienceInterestLevel.VERY_HIGH
    if any(k in txt for k in ("alto", "high")):
        return AudienceInterestLevel.HIGH
    if any(k in txt for k in ("médio", "medio", "medium")):
        return AudienceInterestLevel.MEDIUM
    if any(k in txt for k in ("baixo", "low")):
        return AudienceInterestLevel.LOW
    return AudienceInterestLevel.UNKNOWN


@dataclass(frozen=True)
class StudioTrendsFilter:
    broad_topic: str
    min_interest: AudienceInterestLevel = AudienceInterestLevel.MEDIUM
    only_watched_by_my_viewers: bool = False
    upload_window_days: int | None = 28
    min_outlier_ratio: float = 3.0


@dataclass(frozen=True)
class StudioSearchTerm:
    term: str
    block_type: str  # 'top_search' | 'content_gap'
    audience_interest: AudienceInterestLevel
    is_hypothesis: bool = False
    gap_note: str = ""
    weekly_views_gt_1000: bool = True


@dataclass(frozen=True)
class StudioVideoCandidate:
    external_video_id: str
    canonical_url: str
    title: str
    external_channel_id: str | None
    channel_name: str
    public_views: int | None
    published_at_iso: str | None = None
    published_days_ago: int | None = None
    watched_by_my_viewers: bool = False
    format_name: str = "long"


@dataclass(frozen=True)
class StudioOutlierVideo:
    video: StudioVideoCandidate
    channel_baseline_views: float | None
    outlier_ratio: float | None
    outlier_tier: str  # '10x+' | '5x+' | '3x+' | '<3x' | 'insufficient_baseline'
    baseline_sample_size: int = 0


@dataclass(frozen=True)
class StudioExtractionResult:
    broad_topic: str
    terms: list[StudioSearchTerm] = field(default_factory=list)
    videos: list[StudioVideoCandidate] = field(default_factory=list)
    captured_via: str = "hybrid"
    limitations: list[str] = field(default_factory=list)
