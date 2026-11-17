from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from adapters.supabase_db.studio_repo import PostgresStudioRepository
from core.errors import AppError, ErrorCode
from core.studio.contracts import validate_agent_output_envelope
from core.studio.registry import AGENT_REGISTRY, get_agent_spec
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService

STALE_METRIC_HOURS = 6
_YT_HOST_RE = re.compile(r"^(www\.|m\.)?(youtube\.com|youtu\.be)$", re.IGNORECASE)


def _parse_iso_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def compute_channel_metrics_summary(
    *,
    raw_metrics: list[dict[str, Any]],
    latest_insight: dict[str, Any] | None,
    sync_cursors: list[dict[str, Any]],
    views_series: list[dict[str, Any]],
    now: datetime | None = None,
    stale_after_hours: int = STALE_METRIC_HOURS,
) -> dict[str, Any]:
    """Deriva métricas do painel Canal sem nunca inventar números (unknown -> null)."""
    ref_now = now or datetime.now(timezone.utc)
    by_id = {m["metric_id"]: m for m in raw_metrics}

    insight_metrics: dict[str, dict[str, Any]] = {}
    if latest_insight and isinstance(latest_insight.get("content"), dict):
        for m in latest_insight["content"].get("metrics") or []:
            if isinstance(m, dict) and m.get("key"):
                insight_metrics[str(m["key"])] = m

    def build_card(metric_id: str, insight_key: str, label: str, unit: str) -> dict[str, Any]:
        snap = by_id.get(metric_id)
        ins = insight_metrics.get(insight_key)
        if snap is not None:
            fetched_at = snap.get("fetched_at")
            dt = _parse_iso_dt(fetched_at)
            is_stale = bool(dt and (ref_now - dt) > timedelta(hours=stale_after_hours))
            availability = snap.get("availability") or "unknown"
            value = snap.get("value_num") if availability == "available" else None
            delta_pct = ins.get("delta_pct") if ins else None
            return {
                "key": insight_key,
                "metric_id": metric_id,
                "label": label,
                "unit": unit,
                "value": value,
                "delta_pct": delta_pct,
                "availability": availability,
                "stale": is_stale,
                "fetched_at": fetched_at,
                "source": snap.get("source"),
            }
        if ins is not None:
            fetched_at = ins.get("fetched_at") or latest_insight.get("created_at") if latest_insight else None
            dt = _parse_iso_dt(fetched_at)
            is_stale = bool(dt and (ref_now - dt) > timedelta(hours=stale_after_hours))
            availability = ins.get("availability") or "unknown"
            value = ins.get("value") if availability == "available" else None
            return {
                "key": insight_key,
                "metric_id": metric_id,
                "label": label,
                "unit": unit,
                "value": value,
                "delta_pct": ins.get("delta_pct"),
                "availability": availability,
                "stale": is_stale,
                "fetched_at": fetched_at,
                "source": "channel_insight",
            }
        return {
            "key": insight_key,
            "metric_id": metric_id,
            "label": label,
            "unit": unit,
            "value": None,
            "delta_pct": None,
            "availability": "unknown",
            "stale": False,
            "fetched_at": None,
            "source": None,
        }

    cards = [
        build_card("yt.analytics.views", "views", "Visualizações", "count"),
        build_card("yt.analytics.impressions_ctr", "ctr", "CTR", "percent"),
        build_card("yt.analytics.avg_view_duration_sec", "avg_view_duration_sec", "Tempo médio", "seconds"),
    ]

    latest_sync_at: str | None = None
    for cur in sync_cursors:
        if cur.get("last_successful_sync_at"):
            latest_sync_at = cur["last_successful_sync_at"]
            break
    if latest_sync_at is None:
        fetched_dates = [c["fetched_at"] for c in cards if c.get("fetched_at")]
        latest_sync_at = max(fetched_dates) if fetched_dates else None

    overall_stale = any(c["stale"] for c in cards)
    if not any(c["availability"] == "available" for c in cards):
        overall_availability = "unknown"
    elif overall_stale:
        overall_availability = "stale"
    else:
        overall_availability = "available"

    return {
        "cards": cards,
        "series": [
            {"day": str(p["day"]), "value": float(p["value_num"])}
            for p in views_series
            if p.get("value_num") is not None
        ],
        "fetched_at": latest_sync_at,
        "availability": overall_availability,
        "stale": overall_stale,
    }


class StudioService:
    """Servico de dominio do Estúdio de Conteúdo (UI-02, UI-03, UI-05, UI-06)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: PostgresStudioRepository,
        *,
        darkforge_available: bool = False,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._darkforge_available = darkforge_available

    def get_snapshot(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        content_item_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        raw = self._repo.get_snapshot(workspace_id, channel_id, content_item_id=content_item_id)
        if len(raw.get("agents") or []) == 0:
            self._repo.ensure_channel_agents(workspace_id, channel_id, darkforge_available=self._darkforge_available)
            raw = self._repo.get_snapshot(workspace_id, channel_id, content_item_id=content_item_id)

        metrics_panel = compute_channel_metrics_summary(
            raw_metrics=raw.pop("raw_metrics", []),
            latest_insight=raw.pop("latest_insight", None),
            sync_cursors=raw.pop("sync_cursors", []),
            views_series=raw.pop("views_series", []),
        )
        raw["metrics_panel"] = metrics_panel
        raw["darkforge_available"] = self._darkforge_available
        raw["snapshot_at"] = datetime.now(timezone.utc).isoformat()
        return raw

    def get_events(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        after_id: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        ch = self._repo.get_channel(workspace_id, channel_id)
        if ch is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado neste workspace.", http_status=404)
        events = self._repo.get_events_after(workspace_id, channel_id, after_id=after_id, limit=limit)
        next_cursor = events[-1]["id"] if events else after_id
        return {"events": events, "last_event_id": next_cursor}

    def get_room_detail(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        room_key: str,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.get_room_detail(workspace_id, channel_id, room_key)

    def get_agent_detail(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        get_agent_spec(agent_key)
        return self._repo.get_agent_detail(workspace_id, channel_id, agent_key)

    def create_content_item(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        working_title: str,
        trigger_initial_agents: bool = True,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean = working_title.strip()
        if len(clean) < 2 or len(clean) > 240:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "working_title deve ter entre 2 e 240 caracteres.",
                http_status=422,
                details={"field": "working_title"},
            )
        ch = self._repo.get_channel(workspace_id, channel_id)
        if ch is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado neste workspace.", http_status=404)

        item, deduplicated = self._repo.create_content_item(
            workspace_id=workspace_id,
            channel_id=channel_id,
            working_title=clean,
            actor_id=actor.user_id,
            initial_stage="pesquisa",
        )
        enqueued_runs: list[dict[str, Any]] = []
        if trigger_initial_agents:
            item_id = UUID(str(item["id"]))
            for agent_key in ("dados", "pesquisa"):
                try:
                    run, _ = self._repo.enqueue_agent_run(
                        workspace_id=workspace_id,
                        channel_id=channel_id,
                        agent_key=agent_key,
                        actor_id=actor.user_id,
                        idempotency_key=f"init-{item_id}-{agent_key}",
                        content_item_id=item_id,
                        reason="novo_video",
                    )
                    enqueued_runs.append(run)
                except AppError as err:
                    if err.http_status != 409:
                        raise
        return {"content_item": item, "deduplicated": deduplicated, "enqueued_runs": enqueued_runs}

    def enqueue_agent_run(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        agent_key: str,
        content_item_id: UUID | None = None,
        reason: str = "manual",
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        get_agent_spec(agent_key)
        self._repo.ensure_channel_agents(workspace_id, channel_id, darkforge_available=self._darkforge_available)
        idem = (idempotency_key or f"manual-{channel_id}-{agent_key}-{content_item_id or 'channel'}-{uuid4().hex[:8]}")[:160]
        return self._repo.enqueue_agent_run(
            workspace_id=workspace_id,
            channel_id=channel_id,
            agent_key=agent_key,
            actor_id=actor.user_id,
            idempotency_key=idem,
            content_item_id=content_item_id,
            reason=reason,
        )

    def cancel_agent_run(self, actor: AuthenticatedUser, workspace_id: UUID, run_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        return self._repo.cancel_agent_run(workspace_id, run_id)

    def retry_agent_run(self, actor: AuthenticatedUser, workspace_id: UUID, run_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        prev = self._repo.get_run(workspace_id, run_id)
        if prev is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Execucao anterior nao encontrada.", http_status=404)
        new_attempt = int(prev["attempt"]) + 1
        new_run, _ = self._repo.enqueue_agent_run(
            workspace_id=workspace_id,
            channel_id=UUID(str(prev["channel_id"])),
            agent_key=prev["agent_key"],
            actor_id=actor.user_id,
            idempotency_key=f"retry-{run_id}-att-{new_attempt}"[:160],
            content_item_id=UUID(str(prev["content_item_id"])) if prev.get("content_item_id") else None,
            reason=f"retry_attempt_{new_attempt}",
            parent_run_id=run_id,
            attempt=new_attempt,
        )
        return new_run

    def submit_approval(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        target_kind: str,
        target_id: UUID,
        target_version: int,
        decision: str,
        reason: str | None = None,
        confirm_needs_review: bool = False,
        content_item_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if target_kind not in ("agent_output", "opportunity", "brief", "publication_plan"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "target_kind invalido.", http_status=422)
        if decision not in ("approved", "rejected", "changes_requested"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "decision invalida.", http_status=422)

        if target_kind == "brief" and content_item_id is not None:
            return self._repo.approve_brief_stage_and_release_production(
                workspace_id=workspace_id,
                channel_id=channel_id,
                content_item_id=content_item_id,
                brief_version=target_version,
                decision=decision,
                reason=reason,
                decided_by=actor.user_id,
            )

        return self._repo.submit_approval(
            workspace_id=workspace_id,
            channel_id=channel_id,
            target_kind=target_kind,
            target_id=target_id,
            target_version=target_version,
            decision=decision,
            reason=reason,
            decided_by=actor.user_id,
            confirm_needs_review=confirm_needs_review,
        )

    def revise_output(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        output_id: UUID,
        *,
        action: str,
        edited_content: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if action not in ("save_version", "discard"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "action invalida (save_version|discard).", http_status=422)
        if action == "save_version":
            if edited_content is None:
                raise AppError(ErrorCode.VALIDATION_ERROR, "edited_content obrigatorio.", http_status=422)
            # Valida contra contrato do output se envelope completo for passado
            if {"agent_key", "payload", "channel_id"}.issubset(edited_content.keys()):
                spec = AGENT_REGISTRY.get(str(edited_content["agent_key"]))
                if spec is None:
                    raise AppError(ErrorCode.VALIDATION_ERROR, "agent_key invalido no output editado.", http_status=422)
                validate_agent_output_envelope(
                    edited_content,
                    expected_agent_key=spec.key,
                    expected_output_type=spec.output_type,
                    expected_channel_id=UUID(str(edited_content["channel_id"])),
                    expected_content_item_id=UUID(str(edited_content["content_item_id"])) if edited_content.get("content_item_id") else None,
                )
        return self._repo.revise_output(
            workspace_id=workspace_id,
            output_id=output_id,
            actor_id=actor.user_id,
            action=action,
            edited_content=edited_content,
            reason=reason,
        )

    def update_channel_agent(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        agent_key: str,
        *,
        enabled: bool | None = None,
        display_name: str | None = None,
        avatar_key: str | None = None,
        model_policy: dict[str, Any] | None = None,
        monthly_budget_cents: int | None = None,
        clear_budget: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        get_agent_spec(agent_key)
        self._repo.ensure_channel_agents(workspace_id, channel_id, darkforge_available=self._darkforge_available)

        if model_policy is not None:
            mode = str(model_policy.get("mode", "local_only"))
            if mode not in ("local_only", "external_consented"):
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "model_policy.mode deve ser 'local_only' ou 'external_consented'.",
                    http_status=422,
                )
            if mode == "external_consented" and not bool(model_policy.get("external_consent")):
                raise AppError(
                    ErrorCode.AI_EXTERNAL_CONSENT_REQUIRED,
                    "Politica externa exige consentimento explicito (external_consent=true).",
                    http_status=412,
                )

        if monthly_budget_cents is not None and monthly_budget_cents < 0:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Orcamento mensal nao pode ser negativo.", http_status=422)

        return self._repo.update_channel_agent(
            workspace_id=workspace_id,
            channel_id=channel_id,
            agent_key=agent_key,
            enabled=enabled,
            display_name=display_name,
            avatar_key=avatar_key,
            model_policy=model_policy,
            monthly_budget_cents=monthly_budget_cents,
            clear_budget=clear_budget,
        )

    def mark_manual_published(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        content_item_id: UUID,
        *,
        published_video_url: str,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_url = published_video_url.strip()
        parsed = urlparse(clean_url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc or not _YT_HOST_RE.match(parsed.netloc):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Informe uma URL valida do YouTube (https://www.youtube.com/watch?v=... ou https://youtu.be/...).",
                http_status=422,
                details={"field": "published_video_url"},
            )
        return self._repo.mark_manual_published(
            workspace_id=workspace_id,
            content_item_id=content_item_id,
            published_video_url=clean_url,
            actor_id=actor.user_id,
        )
