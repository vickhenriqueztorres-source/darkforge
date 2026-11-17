from __future__ import annotations

from uuid import UUID

from core.analytics.service import AnalyticsService
from core.jobs.models import ClaimedJob
from workers.runner import WorkerContext


def build_youtube_sync_handler(analytics: AnalyticsService):
    def _handle(job: ClaimedJob, ctx: WorkerContext) -> None:
        payload = job.payload_json
        connection_id = UUID(str(payload["connection_id"]))
        channel_id = UUID(str(payload["channel_id"]))
        sync_scope = str(payload.get("sync_scope", "catalog_incremental"))

        signal = ctx.checkpoint("sync_start", 1, {"sync_scope": sync_scope}, "Iniciando sync oficial YouTube")
        if signal in ("pause", "cancel"):
            ctx._queue.transition(job.job_id, job.fencing_token, "PAUSED" if signal == "pause" else "CANCELLED")
            return

        result = analytics.execute_sync_unit(
            workspace_id=job.workspace_id,
            connection_id=connection_id,
            channel_id=channel_id,
            sync_scope=sync_scope,
        )
        ctx.checkpoint("sync_committed", 2, result, f"Videos={result['videos_upserted']}, Fatos={result['facts_recorded']}")
        ctx._queue.transition(job.job_id, job.fencing_token, "SUCCEEDED", checkpoint_json=result)

    return _handle
