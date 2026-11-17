from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from apps.api.config import get_settings
from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.workspaces.models import AuthenticatedUser
from scripts.diagnostics.export_diagnostics import export_safe_diagnostics

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


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
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _ser(getattr(obj, k)) for k in obj.__dataclass_fields__}
    return obj


def _collect_overview(
    *,
    user: AuthenticatedUser,
    workspace_id: UUID,
    channel_id: UUID | None,
    container: ServiceContainer,
) -> dict[str, Any]:
    container.workspaces.require_membership(user, workspace_id)

    channels = container.channels.list_channels(user, workspace_id)
    re_state = (
        container.reverse_engineering.list_state(user, workspace_id, channel_id=channel_id)
        if container.reverse_engineering is not None
        else {"audits": [], "viral_outliers": [], "autopsies": [], "mechanisms": [], "batches": []}
    )
    studio_runs = (
        container.studio_trends.list_runs(user, workspace_id, channel_id=channel_id)
        if container.studio_trends is not None
        else []
    )
    studio_items = (
        container.studio_trends.list_workspace_items(user, workspace_id, channel_id=channel_id)
        if container.studio_trends is not None
        else {"terms": [], "outliers": []}
    )
    google_trends = (
        container.google_trends.list_validations(user, workspace_id, channel_id=channel_id)
        if container.google_trends is not None
        else []
    )
    opportunities = (
        container.opportunities.list_opportunities(user, workspace_id, channel_id=channel_id)
        if container.opportunities is not None
        else []
    )
    briefs = (
        container.editorial.list_briefs(user, workspace_id)
        if container.editorial is not None
        else []
    )
    calendar_items = (
        container.editorial.list_calendar_items(user, workspace_id)
        if container.editorial is not None
        else []
    )
    portfolio_analytics: dict[str, Any] = {"channels": []}
    channel_videos: list[Any] = []
    if container.analytics is not None:
        today = date.today()
        p_start = today - timedelta(days=365)
        p_end = today + timedelta(days=365)
        portfolio_analytics = container.analytics.get_portfolio_analytics(user, workspace_id, p_start, p_end)
        if channel_id is not None:
            ch_an = container.analytics.get_channel_analytics(user, workspace_id, channel_id, p_start, p_end)
            channel_videos = ch_an.get("videos") or []
        elif channels:
            first_with_ext = next((c for c in channels if getattr(c, "external_channel_id", None)), channels[0])
            ch_an = container.analytics.get_channel_analytics(user, workspace_id, first_with_ext.id, p_start, p_end)
            channel_videos = ch_an.get("videos") or []

    cfg = get_settings()
    diagnostics: dict[str, Any] | None = None
    if cfg.database_url:
        diagnostics = export_safe_diagnostics(database_url=cfg.database_url, workspace_id=workspace_id)

    audits = re_state.get("audits") or []
    outliers = re_state.get("viral_outliers") or []
    autopsies = re_state.get("autopsies") or []
    mechanisms = re_state.get("mechanisms") or []
    batches = re_state.get("batches") or []

    selected_channels = sum(1 for a in audits if a.get("approved"))
    confirmed_outliers = [o for o in outliers if not o.get("is_false_positive")]
    sustainable_trends = sum(1 for g in google_trends if g.get("verdict") == "SUSTAINABLE_GO")
    approved_opps = sum(1 for o in opportunities if o.get("status") == "APPROVED")
    approved_briefs = sum(1 for b in briefs if b.get("status") == "APPROVED")

    return _ser(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": str(workspace_id),
            "channel_id_filter": str(channel_id) if channel_id else None,
            "summary": {
                "channels_count": len(channels),
                "phase1_audits_total": len(audits),
                "phase1_selected_count": selected_channels,
                "phase2_outliers_total": len(outliers),
                "phase2_valid_outliers": len(confirmed_outliers),
                "phase3_autopsies_count": len(autopsies),
                "phase4_mechanisms_count": len(mechanisms),
                "experiment_batches_count": len(batches),
                "studio_runs_count": len(studio_runs),
                "studio_terms_count": len(studio_items.get("terms") or []),
                "studio_outliers_count": len(studio_items.get("outliers") or []),
                "google_trends_count": len(google_trends),
                "google_trends_sustainable_count": sustainable_trends,
                "opportunities_count": len(opportunities),
                "opportunities_approved_count": approved_opps,
                "briefs_count": len(briefs),
                "briefs_approved_count": approved_briefs,
                "calendar_items_count": len(calendar_items),
            },
            "channels": channels,
            "portfolio_analytics": portfolio_analytics,
            "channel_videos": channel_videos,
            "reverse_engineering": re_state,
            "studio_trends": {
                "runs": studio_runs,
                "terms": studio_items.get("terms") or [],
                "outliers": studio_items.get("outliers") or [],
            },
            "google_trends": google_trends,
            "opportunities": opportunities,
            "briefs": briefs,
            "calendar": calendar_items,
            "diagnostics": diagnostics,
        }
    )


def _render_executive_markdown(overview: dict[str, Any]) -> str:
    s = overview["summary"]
    re_data = overview["reverse_engineering"]
    lines: list[str] = [
        f"# Relatorio Executivo — DarkForge Channel OS",
        f"- Gerado em: `{overview['generated_at']}`",
        f"- Workspace: `{overview['workspace_id']}`",
        "",
        "## 1. Resumo de Execucao",
        f"- Canais configurados: **{s['channels_count']}**",
        f"- Fase 1 (Canais de Referencia): **{s['phase1_selected_count']}/{s['phase1_audits_total']}** aprovados nos 6 criterios (meta: 5-10)",
        f"- Fase 2 (Outliers Virais): **{s['phase2_valid_outliers']}** validos de **{s['phase2_outliers_total']}** avaliados",
        f"- Fase 3 (Autopsias de Video): **{s['phase3_autopsies_count']}** concluidas",
        f"- Fase 4 (Mecanismos Transferiveis): **{s['phase4_mechanisms_count']}** sintetizados | Lotes de teste: **{s['experiment_batches_count']}**",
        f"- Studio Trends: **{s['studio_runs_count']}** coletas | **{s['studio_terms_count']}** buscas | **{s['studio_outliers_count']}** outliers",
        f"- Google Trends: **{s['google_trends_sustainable_count']}/{s['google_trends_count']}** sustentaveis (`SUSTAINABLE_GO`)",
        f"- Oportunidades: **{s['opportunities_count']}** ({s['opportunities_approved_count']} aprovadas) | Briefs: **{s['briefs_count']}** ({s['briefs_approved_count']} aprovados)",
        "",
        "## 2. Fase 1 & 2 — Canais de Referencia e Outliers",
    ]
    for a in re_data.get("audits", [])[:10]:
        badge = "APROVADO" if a.get("approved") else "DESCARTADO"
        lines.append(
            f"- **[{badge}]** {a.get('display_name')} — Score: {a.get('ranking_score')} | "
            f"Outliers: {a.get('outlier_hits_count')} (max {a.get('max_outlier_ratio')}x)"
        )
    if not re_data.get("audits"):
        lines.append("- Nenhuma auditoria de canal registrada ainda.")

    lines.append("")
    lines.append("### Outliers Priorizados (Media 20-30 & Views/Dia)")
    for o in re_data.get("viral_outliers", [])[:15]:
        status = "FALSO POSITIVO" if o.get("is_false_positive") else ("MULTI-CANAL" if o.get("confirmed_multi_channel") else "OUTLIER")
        lines.append(
            f"- **[{status}]** {o.get('title')} ({o.get('channel_name')}) — "
            f"{o.get('outlier_ratio')}x media | {o.get('views_per_day')} views/dia | Padrao `{o.get('pattern_key')}`"
        )
    if not re_data.get("viral_outliers"):
        lines.append("- Nenhum outlier Fase 2 registrado ainda.")

    lines.append("")
    lines.append("## 3. Fase 3 & 4 — Autopsias & Mecanismos Transferiveis")
    for m in re_data.get("mechanisms", [])[:10]:
        lines.append(
            f"- **{m.get('synthesized_title')}** — Formula: "
            f"`{m.get('formula_theme')} + {m.get('formula_angle')} + {m.get('formula_emotion')} + "
            f"{m.get('formula_structure')} + {m.get('formula_format')}`"
        )
    if not re_data.get("mechanisms"):
        lines.append("- Nenhum mecanismo transferivel sintetizado ainda.")

    lines.append("")
    lines.append("## 4. Confirmacao Google Trends (12m / 5 anos / Breakout)")
    for g in overview.get("google_trends", [])[:10]:
        bo = len(g.get("breakout_queries_json") or [])
        lines.append(
            f"- **{g.get('keyword')}** ({g.get('geo')}/{g.get('gprop')}) — Veredito: `{g.get('verdict')}` | "
            f"12m: `{g.get('direction_12m')}` | 5a: `{g.get('durability_5y')}` | Breakout: {bo}"
        )
    if not overview.get("google_trends"):
        lines.append("- Nenhuma validacao Google Trends executada ainda.")

    lines.append("")
    lines.append("## 5. Oportunidades Geradas (4 Analistas)")
    for opp in overview.get("opportunities", [])[:10]:
        lines.append(
            f"- **[{opp.get('status')}]** {opp.get('theme')} — Score `{opp.get('score')}` | Angulo: {opp.get('angle')}"
        )
    if not overview.get("opportunities"):
        lines.append("- Nenhuma oportunidade gerada ainda.")

    lines.append("")
    lines.append("_Relatorio gerado sem segredos, tokens OAuth ou credenciais privadas._")
    return "\n".join(lines)


@router.get("/reports/overview")
def get_reports_overview(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    return _collect_overview(user=user, workspace_id=workspace_id, channel_id=channel_id, container=container)


@router.get("/reports/executive.md", response_class=PlainTextResponse)
def export_executive_markdown(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> PlainTextResponse:
    overview = _collect_overview(user=user, workspace_id=workspace_id, channel_id=channel_id, container=container)
    md = _render_executive_markdown(overview)
    return PlainTextResponse(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="relatorio-executivo-darkforge.md"'},
    )
