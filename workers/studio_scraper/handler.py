from __future__ import annotations

from uuid import UUID

from adapters.studio_browser.trends_extractor import StudioTrendsExtractor
from adapters.supabase_db.studio_trends_repo import PostgresStudioTrendsRepository
from adapters.youtube.client import OfficialYouTubeAdapter
from core.errors import AppError, ErrorCode
from core.jobs.models import ClaimedJob
from core.research.outlier_engine import rank_outlier_videos
from core.research.studio_models import StudioTrendsFilter, normalize_interest_level
from workers.runner import WorkerContext


def handle_studio_trends_scrape(
    job: ClaimedJob,
    ctx: WorkerContext,
    *,
    repo: PostgresStudioTrendsRepository,
    extractor: StudioTrendsExtractor | None = None,
    youtube_adapter: OfficialYouTubeAdapter | None = None,
    youtube_api_key: str = "",
) -> None:
    """Resumable worker handler for Playwright Studio Trends scraping & Outlier scoring (SP-13)."""
    p = job.payload_json
    channel_id = UUID(str(p["channel_id"]))
    broad_topic = str(p["broad_topic"])
    f = p.get("filters") or {}

    ext = extractor or StudioTrendsExtractor()
    ext_ch_id = repo.get_channel_external_id(job.workspace_id, channel_id)
    filters = StudioTrendsFilter(
        broad_topic=broad_topic,
        min_interest=normalize_interest_level(f.get("min_interest", "medium")),
        only_watched_by_my_viewers=bool(f.get("only_watched_by_my_viewers", False)),
        upload_window_days=f.get("upload_window_days"),
        min_outlier_ratio=float(f.get("min_outlier_ratio", 3.0)),
    )

    sig = ctx.checkpoint("prepare_studio_session", 1, {"topic": broad_topic}, "Preparando sessao Studio Trends")
    if sig != "continue":
        raise AppError(ErrorCode.FENCING_TOKEN_STALE, "Job interrompido por controle.", http_status=409)

    extracted = ext.extract(external_channel_id=ext_ch_id, filters=filters)
    ctx.checkpoint("extract_studio_trends", 2, {"terms": len(extracted.terms), "videos": len(extracted.videos)})

    baselines: dict[str, list[int]] = {}
    if youtube_adapter and youtube_api_key:
        for v in extracted.videos:
            if v.external_channel_id and v.external_channel_id not in baselines:
                counts, _ = youtube_adapter.fetch_public_channel_recent_view_counts(v.external_channel_id, api_key=youtube_api_key)
                baselines[v.external_channel_id] = counts

    outliers = rank_outlier_videos(extracted.videos, baselines, min_outlier_ratio=filters.min_outlier_ratio, include_below_threshold=True)
    ctx.checkpoint("score_outliers", 3, {"outliers_count": len(outliers)})

    run_id = UUID(str(p["run_id"])) if p.get("run_id") else None
    if run_id is not None:
        repo.save_run_results(
            workspace_id=job.workspace_id,
            run_id=run_id,
            channel_id=channel_id,
            terms=[
                {
                    "term": t.term,
                    "block_type": t.block_type,
                    "audience_interest": t.audience_interest.value,
                    "is_hypothesis": t.is_hypothesis,
                    "gap_note": t.gap_note,
                    "weekly_views_gt_1000": t.weekly_views_gt_1000,
                }
                for t in extracted.terms
            ],
            outliers=[
                {
                    "external_video_id": o.video.external_video_id,
                    "canonical_url": o.video.canonical_url,
                    "title": o.video.title,
                    "external_channel_id": o.video.external_channel_id,
                    "channel_name": o.video.channel_name,
                    "public_views": o.video.public_views,
                    "channel_baseline_views": o.channel_baseline_views,
                    "outlier_ratio": o.outlier_ratio,
                    "outlier_tier": o.outlier_tier,
                    "baseline_sample_size": o.baseline_sample_size,
                    "watched_by_my_viewers": o.video.watched_by_my_viewers,
                    "published_days_ago": o.video.published_days_ago,
                }
                for o in outliers
            ],
            captured_via=extracted.captured_via,
            limitations=extracted.limitations,
        )

    ctx._queue.transition(job.job_id, job.fencing_token, "SUCCEEDED", checkpoint_json={"completed": True, "terms": len(extracted.terms), "outliers": len(outliers)})
