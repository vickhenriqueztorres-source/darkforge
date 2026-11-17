from __future__ import annotations

from statistics import median

from core.research.studio_models import StudioOutlierVideo, StudioVideoCandidate


def compute_channel_baseline(view_counts: list[int], min_samples: int = 3) -> float | None:
    """Computes robust median views baseline for a channel. Returns None if sample size < min_samples."""
    clean = [v for v in view_counts if isinstance(v, int) and v >= 0]
    if len(clean) < min_samples:
        return None
    val = float(median(clean))
    return val if val > 0 else None


def classify_outlier_tier(ratio: float | None) -> str:
    if ratio is None:
        return "insufficient_baseline"
    if ratio >= 10.0:
        return "10x+"
    if ratio >= 5.0:
        return "5x+"
    if ratio >= 3.0:
        return "3x+"
    return "<3x"


def rank_outlier_videos(
    candidates: list[StudioVideoCandidate],
    channel_baselines: dict[str, list[int]],
    *,
    min_outlier_ratio: float = 3.0,
    include_below_threshold: bool = False,
) -> list[StudioOutlierVideo]:
    """
    Calculates Outlier Score (video_views / channel_median_views) for each candidate.
    Preserves videos with insufficient_baseline when include_below_threshold=True.
    """
    seen_ids: set[str] = set()
    scored: list[StudioOutlierVideo] = []
    for cand in candidates:
        if cand.external_video_id in seen_ids:
            continue
        seen_ids.add(cand.external_video_id)
        samples = channel_baselines.get(cand.external_channel_id or "", [])
        baseline = compute_channel_baseline(samples)
        ratio: float | None = None
        if baseline is not None and cand.public_views is not None and baseline > 0:
            ratio = round(cand.public_views / baseline, 2)
        tier = classify_outlier_tier(ratio)
        if not include_below_threshold:
            if ratio is None or ratio < min_outlier_ratio:
                continue
        scored.append(
            StudioOutlierVideo(
                video=cand,
                channel_baseline_views=round(baseline, 2) if baseline is not None else None,
                outlier_ratio=ratio,
                outlier_tier=tier,
                baseline_sample_size=len(samples),
            )
        )

    scored.sort(key=lambda o: (o.outlier_ratio or -1.0, o.video.public_views or 0), reverse=True)
    return scored
