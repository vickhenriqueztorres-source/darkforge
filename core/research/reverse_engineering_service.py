from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.research.channel_selector import (
    ReferenceChannelCandidate,
    TargetChannelFit,
    select_reference_channels,
)
from core.research.transferable_mechanism import (
    extract_transferable_mechanism,
    synthesize_original_episode_concept,
)
from core.research.video_autopsy import (
    CommentGapMining,
    PackageAutopsy,
    ScriptRetentionAutopsy,
    VideoAutopsyReport,
    run_full_video_autopsy,
)
from core.research.viral_outlier_analyzer import (
    ChannelVideoRecord,
    detect_multi_channel_patterns,
    isolate_channel_outliers,
    normalize_pattern_key,
)
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class ReverseEngineeringService:
    """Orchestrates the 4-Phase Viral Reverse Engineering Pipeline (SP-19..SP-23)."""

    def __init__(self, workspaces: WorkspaceService, repo: Any) -> None:
        self._workspaces = workspaces
        self._repo = repo

    def phase1_evaluate_channels(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        target: TargetChannelFit,
        candidates: list[ReferenceChannelCandidate],
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        res = select_reference_channels(candidates, target)
        all_evals = list(res["selected"]) + list(res["rejected"])  # type: ignore[arg-type]
        saved = self._repo.save_channel_audits(
            workspace_id=workspace_id,
            channel_id=channel_id,
            audits=[asdict(e) for e in all_evals],
            created_by=actor.user_id,
        )
        return {
            "selected_count": res["selected_count"],
            "meets_5_to_10_target": res["meets_5_to_10_target"],
            "recommendation": res["recommendation"],
            "audits": saved,
        }

    def phase2_find_viral_outliers(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        videos_by_channel: dict[str, list[ChannelVideoRecord]],
        small_niche: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        isolated_all = []
        discarded_fp_all = []
        channel_summaries: list[dict[str, Any]] = []
        for ext_ch_id, vids in videos_by_channel.items():
            iso = isolate_channel_outliers(vids, small_niche=small_niche)
            isolated_all.extend(iso["outliers"])  # type: ignore[arg-type]
            discarded_fp_all.extend(iso["discarded_false_positives"])  # type: ignore[arg-type]
            channel_summaries.append(
                {
                    "external_channel_id": ext_ch_id,
                    "channel_mean_views": iso["channel_mean_views"],
                    "sample_size": iso["sample_size"],
                    "baseline_warning": iso["baseline_warning"],
                    "isolated_count": len(iso["outliers"]),  # type: ignore[arg-type]
                }
            )

        grouped = detect_multi_channel_patterns(isolated_all)
        confirmed_keys = {p.pattern_key for p in grouped["confirmed_patterns"]}  # type: ignore[attr-defined]

        rows_to_save = []
        for item in isolated_all + discarded_fp_all:
            pk = normalize_pattern_key(item.video.topic or item.video.title, item.video.format_name)
            rows_to_save.append(
                {
                    "external_video_id": item.video.external_video_id,
                    "external_channel_id": item.video.external_channel_id,
                    "channel_name": item.video.channel_name,
                    "title": item.video.title,
                    "views": item.video.views,
                    "days_since_upload": item.video.days_since_upload,
                    "views_per_day": item.views_per_day,
                    "channel_mean_views": item.channel_mean_views,
                    "outlier_ratio": item.outlier_ratio,
                    "pattern_key": pk,
                    "confirmed_multi_channel": (not item.is_false_positive) and (pk in confirmed_keys),
                    "is_false_positive": item.is_false_positive,
                    "false_positive_reasons": item.false_positive_reasons,
                }
            )
        saved = self._repo.save_viral_outliers(
            workspace_id=workspace_id,
            channel_id=channel_id,
            outliers=rows_to_save,
            created_by=actor.user_id,
        )
        return {
            "channel_summaries": channel_summaries,
            "confirmed_patterns_count": len(grouped["confirmed_patterns"]),  # type: ignore[arg-type]
            "discarded_coincidence_count": len(grouped["discarded_single_channel"]),  # type: ignore[arg-type]
            "saved_outliers": saved,
        }

    def phase3_run_autopsy(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        external_video_id: str,
        title: str,
        transcript_or_notes: str,
        comments: list[str],
        thumbnail_focus: str = "",
        thumbnail_visual_question: str = "",
        thumbnail_emotion: str = "curiosidade",
        thumbnail_text: str = "",
        first_visual_description: str = "",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if not title.strip():
            raise AppError(ErrorCode.VALIDATION_ERROR, "title obrigatorio para autopsia.", http_status=422)
        report = run_full_video_autopsy(
            external_video_id=external_video_id,
            title=title,
            transcript_or_notes=transcript_or_notes,
            comments=comments,
            thumbnail_focus=thumbnail_focus,
            thumbnail_visual_question=thumbnail_visual_question,
            thumbnail_emotion=thumbnail_emotion,
            thumbnail_text=thumbnail_text,
            first_visual_description=first_visual_description,
        )
        saved = self._repo.save_autopsy(
            workspace_id=workspace_id,
            channel_id=channel_id,
            external_video_id=report.external_video_id,
            original_title=report.package.original_title,
            package_json=asdict(report.package),
            script_retention_json=asdict(report.script_retention),
            comment_gaps_json=asdict(report.comments),
            narrative_archetype=report.detected_narrative_archetype,
            confidence=report.confidence,
            created_by=actor.user_id,
        )
        return saved

    def phase4_synthesize_mechanism(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        autopsy_ids: list[UUID] | None,
        own_validated_topic: str,
        new_angle: str,
        target_format: str = "long",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        rows = self._repo.list_autopsies(workspace_id, autopsy_ids=autopsy_ids)
        if not rows:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Nenhuma autopsia encontrada para sintetizar mecanismo.", http_status=404)

        reports: list[VideoAutopsyReport] = []
        for r in rows:
            p = r["package_json"]
            s = r["script_retention_json"]
            c = r["comment_gaps_json"]
            reports.append(
                VideoAutopsyReport(
                    external_video_id=r["external_video_id"],
                    package=PackageAutopsy(**p),
                    script_retention=ScriptRetentionAutopsy(**s),
                    comments=CommentGapMining(**c),
                    detected_narrative_archetype=r["narrative_archetype"],
                    confidence=float(r["confidence"]),
                )
            )
        formula = extract_transferable_mechanism(reports)
        concept = synthesize_original_episode_concept(
            formula,
            own_validated_topic=own_validated_topic,
            new_angle=new_angle,
            target_format=target_format,
        )
        saved = self._repo.save_mechanism(
            workspace_id=workspace_id,
            channel_id=channel_id,
            formula_theme=concept.formula_theme,
            formula_angle=concept.formula_angle,
            formula_emotion=concept.formula_emotion,
            formula_structure=concept.formula_structure,
            formula_format=concept.formula_format,
            synthesized_title=concept.synthesized_title,
            synthesized_thumb_concept=concept.synthesized_thumb_concept,
            synthesized_outline_json=concept.synthesized_outline,
            filled_comment_gaps_json=concept.filled_comment_gaps,
            originality_max_similarity=concept.originality_max_similarity,
            originality_blocked=concept.originality_blocked,
            source_autopsy_ids_json=[str(r["id"]) for r in rows],
            sample_warning=formula.sample_warning,
            created_by=actor.user_id,
        )
        return saved

    def create_experiment_batch(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        title: str,
        mechanism_id: UUID | None = None,
        brief_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        return self._repo.create_experiment_batch(
            workspace_id=workspace_id,
            channel_id=channel_id,
            mechanism_id=mechanism_id,
            brief_id=brief_id,
            title=title.strip(),
            created_by=actor.user_id,
        )

    def record_experiment_metrics(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        batch_id: UUID,
        *,
        status: str,
        impressions: int | None = None,
        ctr_pct: float | None = None,
        retention_30s_pct: float | None = None,
        outcome_notes: str = "",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        row = self._repo.record_experiment_metrics(
            workspace_id=workspace_id,
            batch_id=batch_id,
            status=status,
            impressions=impressions,
            ctr_pct=ctr_pct,
            retention_30s_pct=retention_30s_pct,
            outcome_notes=outcome_notes,
        )
        if row is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Lote de teste nao encontrado.", http_status=404)
        return row

    def list_state(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        return {
            "audits": self._repo.list_channel_audits(workspace_id, channel_id=channel_id),
            "viral_outliers": self._repo.list_viral_outliers(workspace_id, channel_id=channel_id),
            "autopsies": self._repo.list_autopsies(workspace_id),
            "mechanisms": self._repo.list_mechanisms(workspace_id),
            "batches": self._repo.list_experiment_batches(workspace_id),
        }
