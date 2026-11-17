from __future__ import annotations

from uuid import UUID

from adapters.google_trends.collector import GoogleTrendsPlaywrightCollector
from adapters.supabase_db.google_trends_repo import PostgresGoogleTrendsRepository
from core.jobs.models import ClaimedJob
from core.research.google_trends_analyzer import evaluate_topic_sustainability
from workers.runner import WorkerContext


def handle_google_trends_validate(
    job: ClaimedJob,
    ctx: WorkerContext,
    *,
    repo: PostgresGoogleTrendsRepository,
    collector: GoogleTrendsPlaywrightCollector | None = None,
) -> None:
    p = job.payload_json
    keyword = str(p["keyword"])
    channel_id = UUID(str(p["channel_id"])) if p.get("channel_id") else None
    studio_term_id = UUID(str(p["studio_term_id"])) if p.get("studio_term_id") else None
    geo = str(p.get("geo") or "BR")
    gprop = str(p.get("gprop") or "youtube")
    hl = str(p.get("hl") or "pt-BR")

    col = collector or GoogleTrendsPlaywrightCollector()
    ctx.checkpoint("fetch_google_trends", 1, {"keyword": keyword, "geo": geo})
    raw = col.collect(keyword=keyword, geo=geo, gprop=gprop, hl=hl)

    ctx.checkpoint("analyze_sustainability", 2, {"points_12m": len(raw.get("points_12m", [])), "points_5y": len(raw.get("points_5y", []))})
    report = evaluate_topic_sustainability(
        keyword=keyword,
        geo=geo,
        gprop=gprop,
        points_12m=raw.get("points_12m", []),
        points_5y=raw.get("points_5y", []),
        related_queries=raw.get("related_queries", []),
    )
    saved = repo.save_validation(
        workspace_id=job.workspace_id,
        channel_id=channel_id,
        studio_term_id=studio_term_id,
        report=report,
        captured_via=str(raw.get("captured_via", "playwright_json")),
        created_by=job.created_by,
        job_id=job.job_id,
    )
    ctx._queue.transition(job.job_id, job.fencing_token, "SUCCEEDED", checkpoint_json={"validation_id": str(saved["id"]), "verdict": report.verdict.value})
