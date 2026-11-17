from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.research.outlier_engine import rank_outlier_videos
from core.research.studio_models import (
    AudienceInterestLevel,
    StudioExtractionResult,
    StudioSearchTerm,
    StudioTrendsFilter,
    StudioVideoCandidate,
    normalize_interest_level,
)
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class StudioSessionPort(Protocol):
    def check_session_status(self, external_channel_id: str | None = None) -> dict[str, Any]: ...

    def open_manual_login_window(self, external_channel_id: str | None = None, wait_seconds: int = 180) -> dict[str, Any]: ...


class StudioExtractorPort(Protocol):
    def extract(self, *, external_channel_id: str | None, filters: StudioTrendsFilter) -> StudioExtractionResult: ...


class ChannelBaselinePort(Protocol):
    def fetch_public_channel_recent_view_counts(
        self,
        external_channel_id: str,
        *,
        api_key: str = "",
        access_token: str = "",
        max_videos: int = 20,
    ) -> tuple[list[int], int]: ...


class StudioTrendsService:
    """Orchestrates assisted browser Studio Trends runs, Outlier scoring and Opportunity integration (SP-10..SP-13)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        session_mgr: StudioSessionPort | None = None,
        extractor: StudioExtractorPort | None = None,
        baseline_fetcher: ChannelBaselinePort | None = None,
        command_bus: Any = None,
        youtube_api_key: str = "",
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._session = session_mgr
        self._extractor = extractor
        self._baseline = baseline_fetcher
        self._bus = command_bus
        self._api_key = youtube_api_key

    def session_status(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        if self._session is None:
            return {"authenticated": False, "reason": "session_manager_unconfigured"}
        ext_id = self._repo.get_channel_external_id(workspace_id, channel_id) if channel_id else None
        return self._session.check_session_status(external_channel_id=ext_id)

    def launch_manual_login(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if self._session is None:
            raise AppError(ErrorCode.STUDIO_AUTH_REQUIRED, "Gerenciador de sessao do navegador nao configurado.", http_status=503)
        ext_id = self._repo.get_channel_external_id(workspace_id, channel_id) if channel_id else None
        return self._session.open_manual_login_window(external_channel_id=ext_id)

    def create_studio_run(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        broad_topic: str,
        min_interest: str = "medium",
        only_watched_by_my_viewers: bool = False,
        upload_window_days: int | None = 28,
        min_outlier_ratio: float = 3.0,
        idempotency_key: str | None = None,
        execute_now: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_topic = broad_topic.strip()
        if len(clean_topic) < 2:
            raise AppError(ErrorCode.VALIDATION_ERROR, "broad_topic deve ter ao menos 2 caracteres.", http_status=422)

        filters_dict = {
            "min_interest": min_interest,
            "only_watched_by_my_viewers": only_watched_by_my_viewers,
            "upload_window_days": upload_window_days,
            "min_outlier_ratio": min_outlier_ratio,
        }
        job_id: UUID | None = None
        if self._bus is not None:
            job_rec, _ = self._bus.dispatch_job_command(
                actor=actor,
                workspace_id=workspace_id,
                job_type="studio_trends_scrape",
                idempotency_key=idempotency_key or f"studio-{workspace_id}-{clean_topic[:24]}",
                payload_json={"channel_id": str(channel_id), "broad_topic": clean_topic, "filters": filters_dict},
                channel_id=channel_id,
                total_steps=4,
            )
            job_id = job_rec.id

        run = self._repo.create_run(
            workspace_id=workspace_id,
            channel_id=channel_id,
            broad_topic=clean_topic,
            filters_json=filters_dict,
            job_id=job_id,
            created_by=actor.user_id,
        )
        if not execute_now:
            return {"run": run, "terms": [], "outliers": []}

        return self.execute_existing_run(
            actor=actor,
            workspace_id=workspace_id,
            run_id=UUID(str(run["id"])),
        )

    def execute_existing_run(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        run_id: UUID,
        *,
        channel_baselines_override: dict[str, list[int]] | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        run = self._repo.get_run(workspace_id, run_id)
        if run is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Studio trend run nao encontrada.", http_status=404)
        if self._extractor is None:
            raise AppError(ErrorCode.STUDIO_AUTH_REQUIRED, "Extrator de navegador nao configurado.", http_status=503)

        f = run.get("filters_json") or {}
        filters = StudioTrendsFilter(
            broad_topic=run["broad_topic"],
            min_interest=normalize_interest_level(f.get("min_interest", "medium")),
            only_watched_by_my_viewers=bool(f.get("only_watched_by_my_viewers", False)),
            upload_window_days=f.get("upload_window_days"),
            min_outlier_ratio=float(f.get("min_outlier_ratio", 3.0)),
        )
        ext_ch_id = self._repo.get_channel_external_id(workspace_id, UUID(str(run["channel_id"])))
        self._repo.mark_run_status(workspace_id=workspace_id, run_id=run_id, status="RUNNING")

        try:
            extracted = self._extractor.extract(external_channel_id=ext_ch_id, filters=filters)
        except AppError as exc:
            self._repo.mark_run_status(
                workspace_id=workspace_id,
                run_id=run_id,
                status="BLOCKED",
                error_code=exc.code.value,
                error_message=exc.message,
            )
            raise

        return self._score_and_persist(
            workspace_id=workspace_id,
            run_id=run_id,
            channel_id=UUID(str(run["channel_id"])),
            extracted=extracted,
            min_outlier_ratio=filters.min_outlier_ratio,
            channel_baselines_override=channel_baselines_override,
        )

    def ingest_captured_payload(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        run_id: UUID,
        *,
        terms: list[dict[str, Any]],
        videos: list[dict[str, Any]],
        channel_baselines: dict[str, list[int]] | None = None,
        min_outlier_ratio: float = 3.0,
    ) -> dict[str, Any]:
        """Persists captured/imported Studio Trends terms & scores outliers cleanly (for interactive/assisted/test runs)."""
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        run = self._repo.get_run(workspace_id, run_id)
        if run is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Studio trend run nao encontrada.", http_status=404)

        parsed_terms = [
            StudioSearchTerm(
                term=str(t["term"]),
                block_type=str(t.get("block_type", "top_search")),
                audience_interest=normalize_interest_level(t.get("audience_interest", "medium")),
                is_hypothesis=bool(t.get("block_type") == "content_gap" or t.get("is_hypothesis", False)),
                gap_note=str(t.get("gap_note", "")),
                weekly_views_gt_1000=bool(t.get("weekly_views_gt_1000", True)),
            )
            for t in terms
        ]
        parsed_videos = [
            StudioVideoCandidate(
                external_video_id=str(v["external_video_id"]),
                canonical_url=str(v.get("canonical_url") or f"https://www.youtube.com/watch?v={v['external_video_id']}"),
                title=str(v["title"]),
                external_channel_id=v.get("external_channel_id"),
                channel_name=str(v.get("channel_name", "Canal")),
                public_views=v.get("public_views"),
                published_at_iso=v.get("published_at_iso"),
                published_days_ago=v.get("published_days_ago"),
                watched_by_my_viewers=bool(v.get("watched_by_my_viewers", False)),
            )
            for v in videos
        ]
        extracted = StudioExtractionResult(
            broad_topic=run["broad_topic"],
            terms=parsed_terms,
            videos=parsed_videos,
            captured_via="assisted_capture",
            limitations=["Content gaps tratados como hipoteses editorialmente nao validadas."],
        )
        return self._score_and_persist(
            workspace_id=workspace_id,
            run_id=run_id,
            channel_id=UUID(str(run["channel_id"])),
            extracted=extracted,
            min_outlier_ratio=min_outlier_ratio,
            channel_baselines_override=channel_baselines,
        )

    def _score_and_persist(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        channel_id: UUID,
        extracted: StudioExtractionResult,
        min_outlier_ratio: float,
        channel_baselines_override: dict[str, list[int]] | None = None,
    ) -> dict[str, Any]:
        baselines: dict[str, list[int]] = dict(channel_baselines_override or {})
        if self._baseline is not None and self._api_key:
            for vid in extracted.videos:
                ch_ext = vid.external_channel_id
                if ch_ext and ch_ext not in baselines:
                    counts, _ = self._baseline.fetch_public_channel_recent_view_counts(
                        ch_ext,
                        api_key=self._api_key,
                        max_videos=20,
                    )
                    baselines[ch_ext] = counts

        outliers = rank_outlier_videos(
            extracted.videos,
            baselines,
            min_outlier_ratio=min_outlier_ratio,
            include_below_threshold=True,
        )

        term_rows = [
            {
                "term": t.term,
                "block_type": t.block_type,
                "audience_interest": t.audience_interest.value,
                "is_hypothesis": t.is_hypothesis,
                "gap_note": t.gap_note,
                "weekly_views_gt_1000": t.weekly_views_gt_1000,
            }
            for t in extracted.terms
        ]
        outlier_rows = [
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
        ]

        self._repo.save_run_results(
            workspace_id=workspace_id,
            run_id=run_id,
            channel_id=channel_id,
            terms=term_rows,
            outliers=outlier_rows,
            captured_via=extracted.captured_via,
            limitations=extracted.limitations,
        )
        detail = self._repo.get_run_detail(workspace_id, run_id)
        assert detail is not None
        return detail

    def list_runs(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_runs(workspace_id, channel_id=channel_id)

    def list_workspace_items(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_workspace_items(workspace_id, channel_id=channel_id)

    def get_run_detail(self, actor: AuthenticatedUser, workspace_id: UUID, run_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        detail = self._repo.get_run_detail(workspace_id, run_id)
        if detail is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Studio trend run nao encontrada.", http_status=404)
        return detail

    def curate_item(self, actor: AuthenticatedUser, workspace_id: UUID, kind: str, item_id: UUID, status: str) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if kind not in ("term", "outlier"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "kind deve ser term ou outlier.", http_status=422)
        if status not in ("pending", "approved", "rejected", "archived"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "curation_status invalido.", http_status=422)
        updated = self._repo.curate_item(workspace_id, kind, item_id, status)
        if updated is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Item Studio Trends nao encontrado.", http_status=404)
        return updated
