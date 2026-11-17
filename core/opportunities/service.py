from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService

SCORE_VERSION = "v1.0.0"


class EditorialAIRouterPort(Protocol):
    def generate_with_context(
        self,
        goal: str,
        context_chunks: list[dict[str, Any]],
        use_external: bool = False,
        external_consent_granted: bool = False,
        budget_limit_chars: int = 8000,
    ) -> Any: ...


@dataclass(frozen=True)
class AnalystReport:
    analyst: str
    findings: list[str]
    evidence: list[dict[str, Any]]
    recommendations: list[str]
    confidence: float
    limitations: list[str]
    data_freshness: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyst": self.analyst,
            "findings": self.findings,
            "evidence": self.evidence,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "limitations": self.limitations,
            "data_freshness": self.data_freshness,
        }


def compute_opportunity_score(
    *,
    relevance: float,
    demand: float,
    baseline_lift: float,
    format_fit: float,
    timing: float,
    viability: float,
    knowledge_support: float,
    penalty: float,
) -> tuple[float, dict[str, float]]:
    """
    Score = 0.25R + 0.20D + 0.15L + 0.15F + 0.10T + 0.10V + 0.05C - P
    Clamped to [0.0, 1.0]. Version: v1.0.0.
    """
    raw = (
        0.25 * relevance
        + 0.20 * demand
        + 0.15 * baseline_lift
        + 0.15 * format_fit
        + 0.10 * timing
        + 0.10 * viability
        + 0.05 * knowledge_support
        - penalty
    )
    score = round(max(0.0, min(1.0, raw)), 4)
    breakdown = {
        "R": round(relevance, 4),
        "D": round(demand, 4),
        "L": round(baseline_lift, 4),
        "F": round(format_fit, 4),
        "T": round(timing, 4),
        "V": round(viability, 4),
        "C": round(knowledge_support, 4),
        "P": round(penalty, 4),
        "score": score,
    }
    return score, breakdown


class OpportunityService:
    """Opportunity Engine (OPP-001..006): specialized analysts + versioned scoring."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        knowledge_service: Any = None,
        ai_router: EditorialAIRouterPort | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._knowledge = knowledge_service
        self._ai = ai_router

    def generate_opportunities(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        *,
        topic_hint: str,
        target_format: str = "long",
        use_external: bool = False,
        external_consent_granted: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        hint = topic_hint.strip()
        if len(hint) < 2:
            raise AppError(ErrorCode.VALIDATION_ERROR, "topic_hint deve ter ao menos 2 caracteres.", http_status=422)
        if target_format not in ("long", "short", "live"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "target_format invalido.", http_status=422)

        context = self._repo.load_generation_context(workspace_id, channel_id)
        channel = context.get("channel")
        profile = context.get("profile_version")
        if channel is None or profile is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal ou ChannelProfileVersion nao encontrado.", http_status=404)

        analytics_facts: list[dict[str, Any]] = context.get("analytics_facts", [])
        ref_videos: list[dict[str, Any]] = context.get("approved_references", [])
        studio_terms: list[dict[str, Any]] = context.get("studio_terms", [])
        studio_outliers: list[dict[str, Any]] = context.get("studio_outliers", [])
        google_trends: list[dict[str, Any]] = context.get("google_trends", [])

        # Retrieve only approved L2/L3 RAG chunks with allowed_in_generation=true (OPP-001 / KNOW-005)
        rag_hits: list[dict[str, Any]] = []
        if self._knowledge is not None:
            rag_res = self._knowledge.retrieve(
                actor=actor,
                workspace_id=workspace_id,
                query=hint,
                channel_id=channel_id,
                allowed_levels=("L2", "L3"),
                top_k=5,
            )
            rag_hits = rag_res.get("chunks", [])

        # Respect ADR-007 external provider gate before any external generation call
        ai_meta: dict[str, Any] = {"provider": "local_template", "external_used": False}
        if use_external:
            if self._ai is None:
                raise AppError(
                    ErrorCode.AI_PROVIDER_UNAVAILABLE,
                    "Provedor externo solicitado, mas AIProviderRouter nao esta configurado.",
                    http_status=503,
                )
            gen = self._ai.generate_with_context(
                goal=f"Gerar angulo editorial para: {hint}",
                context_chunks=rag_hits,
                use_external=True,
                external_consent_granted=external_consent_granted,
            )
            ai_meta = {"provider": getattr(gen, "provider_name", "external"), "external_used": True}

        # Build the 4 specialized analyst contracts
        profile_payload = profile.get("payload_json") or {}
        pillars = profile.get("pillars_json") or profile_payload.get("pillars") or []
        raw_restrictions = profile.get("restrictions_json") or profile_payload.get("restrictions") or {}
        if isinstance(raw_restrictions, dict):
            restrictions = raw_restrictions.get("forbidden_topics") or list(raw_restrictions.keys())
        else:
            restrictions = list(raw_restrictions)
        voice_obj = profile.get("voice_json") or {}
        voice_tone = voice_obj.get("tone") if isinstance(voice_obj, dict) else profile_payload.get("voice_tone", "direta")
        voice_tone = voice_tone or profile_payload.get("voice_tone", "direta")

        limitations: list[str] = []
        if not analytics_facts:
            limitations.append("Sem metricas privadas recentes sincronizadas (analytics_facts ausentes).")
        if not ref_videos:
            limitations.append("Sem referencias publicas aprovadas neste canal (reference_videos vazio).")
        if not rag_hits:
            limitations.append("Sem chunks RAG aprovados L2/L3 com allowed_in_generation=true para este tema.")

        insufficient_data = (
            len(analytics_facts) == 0
            and len(ref_videos) == 0
            and len(rag_hits) == 0
            and len(studio_terms) == 0
            and len(studio_outliers) == 0
            and len(google_trends) == 0
        )

        profile_evidence = [
            {
                "source_kind": "channel_profile",
                "source_id": str(profile["id"]),
                "snippet": f"Pilares: {', '.join(pillars[:4]) or 'nao definidos'}; Restricoes: {', '.join(restrictions[:3]) or 'nenhuma'}",
            }
        ]
        profile_report = AnalystReport(
            analyst="channel_profile_analyst",
            findings=[f"Canal '{channel['display_name']}' alinhado ao tema '{hint}'."],
            evidence=profile_evidence,
            recommendations=[f"Priorizar formato '{target_format}' respeitando voz: {voice_tone}"],
            confidence=0.82 if pillars else 0.55,
            limitations=[] if pillars else ["Pilares editoriais pouco especificados no perfil."],
            data_freshness="fresh",
        )

        analytics_evidence = [
            {
                "source_kind": "analytics_fact",
                "source_id": str(f["id"]),
                "snippet": f"{f['metric_key']}={f['value']} ({f.get('freshness_status', 'unknown')})",
            }
            for f in analytics_facts[:5]
        ]
        analytics_report = AnalystReport(
            analyst="analytics_performance_analyst",
            findings=(
                [f"{len(analytics_facts)} fatos de performance propria considerados para baseline."]
                if analytics_facts
                else ["Nenhum fato de analytics proprio disponivel; baseline em incerteza."]
            ),
            evidence=analytics_evidence,
            recommendations=["Validar retencao nos primeiros 30s na primeira execucao."] if analytics_facts else ["Conectar/sincronizar canal para baseline proprio (AN-004)."],
            confidence=0.78 if analytics_facts else 0.25,
            limitations=[] if analytics_facts else ["Dados privados de analytics ausentes (NAO convertidos em zero)."],
            data_freshness="fresh" if analytics_facts else "insufficient",
        )

        research_evidence = [
            {
                "source_kind": "reference_video",
                "source_id": str(r["id"]),
                "snippet": f"[PUBLICO] {r['title']} ({r.get('canonical_url', '')})",
                "source_url": r.get("canonical_url"),
            }
            for r in ref_videos[:5]
        ] + [
            {
                "source_kind": "studio_trend_term",
                "source_id": str(st["id"]),
                "snippet": (
                    f"[STUDIO {'GAP HIPOTESE' if st.get('is_hypothesis') else 'TREND'} | {st.get('audience_interest')}] "
                    f"{st['term']}"
                ),
            }
            for st in studio_terms[:5]
        ] + [
            {
                "source_kind": "studio_outlier_video",
                "source_id": str(so["id"]),
                "snippet": (
                    f"[OUTLIER {so.get('outlier_ratio') or '?'}x"
                    f"{' | ASSISTIDO PELO PUBLICO' if so.get('watched_by_my_viewers') else ''}] {so['title']}"
                ),
                "source_url": so.get("canonical_url"),
            }
            for so in studio_outliers[:5]
        ] + [
            {
                "source_kind": "google_trends_validation",
                "source_id": str(gt["id"]),
                "snippet": (
                    f"[GOOGLE TRENDS {gt.get('verdict')} | {gt.get('geo')}/{gt.get('gprop')} | "
                    f"12m={gt.get('direction_12m')} 5y={gt.get('durability_5y')}] {gt['keyword']}"
                ),
            }
            for gt in google_trends[:4]
        ]
        matched_gt = [gt for gt in google_trends if hint.lower() in str(gt.get("keyword", "")).lower() or str(gt.get("keyword", "")).lower() in hint.lower()]
        active_gt = matched_gt[0] if matched_gt else (google_trends[0] if google_trends else None)
        has_research_signals = bool(ref_videos or studio_terms or studio_outliers or google_trends)
        research_findings: list[str] = []
        if ref_videos:
            research_findings.append(f"{len(ref_videos)} referencias publicas curadas sustentam demanda no topico.")
        if studio_terms:
            gaps_cnt = sum(1 for t in studio_terms if t.get("is_hypothesis"))
            research_findings.append(f"{len(studio_terms)} termos Studio Trends (Medio+) capturados ({gaps_cnt} content gaps como hipoteses).")
        if studio_outliers:
            research_findings.append(f"{len(studio_outliers)} videos outliers (>=3x baseline do canal) encontrados.")
        if active_gt is not None:
            bo_cnt = len(active_gt.get("breakout_queries_json") or [])
            research_findings.append(
                f"Google Trends ({active_gt.get('geo')}): veredito {active_gt.get('verdict')} "
                f"(12m={active_gt.get('direction_12m')}, 5a={active_gt.get('durability_5y')}, Breakout={bo_cnt})."
            )
            if active_gt.get("verdict") == "AVOID_DEAD_PEAK":
                limitations.append(f"Google Trends sinalizou PICO MORTO ({active_gt.get('peak_decay_pct', 0):.0f}% abaixo do topo em 5 anos).")
        if not research_findings:
            research_findings.append("Nenhuma referencia publica ou sinal Studio Trends encontrado para validar demanda externa.")

        research_recs = ["Diferenciar angulo frente aos titulos publicos sem clonar estrutura (ORIG-001) e validar content gaps."]
        if active_gt and active_gt.get("breakout_queries_json"):
            bo_terms = ", ".join(str(q.get("term", "")) for q in (active_gt.get("breakout_queries_json") or [])[:3])
            research_recs.append(f"Explorar consultas Breakout (>5000%) em titulos/ganchos: {bo_terms}")
        if active_gt and active_gt.get("verdict") == "AVOID_DEAD_PEAK":
            research_recs.append("ALERTA GOOGLE TRENDS: tema com pico morto em 5a — nao priorizar como demanda continua.")

        research_report = AnalystReport(
            analyst="public_research_analyst",
            findings=research_findings,
            evidence=research_evidence,
            recommendations=research_recs,
            confidence=0.84 if (active_gt and active_gt.get("verdict") == "SUSTAINABLE_GO") else (0.80 if (studio_outliers or (ref_videos and studio_terms)) else (0.72 if has_research_signals else 0.30)),
            limitations=[] if has_research_signals else ["Pesquisa publica ausente para o tema."],
            data_freshness="fresh" if has_research_signals else "insufficient",
        )

        rag_evidence = [
            {
                "source_kind": "knowledge_chunk",
                "source_id": str(h["chunk_id"]),
                "snippet": f"[{h['curation_level']}] {h['source_title']}: {h['chunk_text'][:120]}",
            }
            for h in rag_hits[:5]
        ]
        rag_report = AnalystReport(
            analyst="copy_rag_analyst",
            findings=(
                [f"{len(rag_hits)} chunks L2/L3 autorizados fornecem ganchos e provas."]
                if rag_hits
                else ["Nenhum chunk L2/L3 curado disponivel para fundamentar o roteiro."]
            ),
            evidence=rag_evidence,
            recommendations=["Usar somente fontes L2/L3 com citacoes rastreaveis no EpisodeBrief."],
            confidence=0.80 if rag_hits else 0.30,
            limitations=[] if rag_hits else ["Base Knowledge RAG vazia ou sem curadoria L2/L3."],
            data_freshness="fresh" if rag_hits else "insufficient",
        )

        # Compute deterministic, versioned score (OPP-002 / OPP-006)
        relevance = 0.85 if any(hint.lower() in p.lower() for p in pillars) else 0.65
        demand_count = len(ref_videos) + len(studio_terms) + len(studio_outliers)
        demand = min(0.95, 0.35 + 0.12 * demand_count) if demand_count else (0.60 if active_gt and active_gt.get("verdict") == "SUSTAINABLE_GO" else 0.15)
        baseline_lift = min(0.90, 0.45 + 0.08 * len(analytics_facts)) if analytics_facts else (0.55 if studio_outliers else 0.15)
        format_fit = 0.85 if target_format == "long" else 0.78
        timing = 0.82 if (demand_count or analytics_facts) else 0.30
        if active_gt is not None:
            if active_gt.get("verdict") == "SUSTAINABLE_GO":
                timing = min(1.0, timing + 0.12 + (0.06 if active_gt.get("breakout_queries_json") else 0.0))
                demand = min(1.0, demand + 0.10)
            elif active_gt.get("verdict") == "AVOID_DEAD_PEAK":
                timing = 0.10
        viability = 0.85
        knowledge_support = min(1.0, 0.25 * len(rag_hits)) if rag_hits else 0.05
        penalty = 0.25 if insufficient_data else 0.03
        if active_gt is not None and active_gt.get("verdict") == "AVOID_DEAD_PEAK":
            penalty = min(0.60, penalty + 0.30)
        elif active_gt is not None and active_gt.get("verdict") == "CAUTION_DECLINING":
            penalty = min(0.60, penalty + 0.12)

        score, breakdown = compute_opportunity_score(
            relevance=relevance,
            demand=demand,
            baseline_lift=baseline_lift,
            format_fit=format_fit,
            timing=timing,
            viability=viability,
            knowledge_support=knowledge_support,
            penalty=penalty,
        )
        confidence = round(0.28 if insufficient_data else min(0.92, (profile_report.confidence + analytics_report.confidence + research_report.confidence + rag_report.confidence) / 4.0), 4)
        freshness = "insufficient" if insufficient_data else ("fresh" if analytics_facts and ref_videos else "partial")

        reports = [profile_report.to_dict(), analytics_report.to_dict(), research_report.to_dict(), rag_report.to_dict()]
        all_evidence = profile_evidence + analytics_evidence + research_evidence + rag_evidence

        angle = (
            f"Abordagem investigativa e pratica sobre '{hint}' aplicando evidencias publicas e regras proprias do canal '{channel['display_name']}'."
            if not insufficient_data
            else f"Hipotese inicial sobre '{hint}' (INCERTEZA ELEVADA: faltam evidencias de analytics, pesquisa publica e RAG L2/L3)."
        )
        differentiation = (
            f"Foge de tutoriais genericos ao combinar pilares ({', '.join(pillars[:2]) or 'canal'}) com citacoes verificadas e evitacao de repeticao."
        )

        opportunity = self._repo.insert_opportunity(
            workspace_id=workspace_id,
            channel_id=channel_id,
            profile_version_id=profile["id"],
            theme=hint,
            angle=angle,
            target_format=target_format,
            differentiation=differentiation,
            score=score,
            score_version=SCORE_VERSION,
            score_breakdown_json=breakdown,
            confidence=confidence,
            limitations_json=limitations,
            data_freshness=freshness,
            insufficient_data=insufficient_data,
            analyst_reports_json=reports,
            created_by=actor.user_id,
            evidence_links=all_evidence,
        )
        return {
            "opportunity": opportunity,
            "evidence": all_evidence,
            "ai_execution": ai_meta,
        }

    def list_opportunities(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_opportunities(workspace_id, channel_id=channel_id, status=status)

    def get_opportunity(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        opportunity_id: UUID,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        opp = self._repo.get_opportunity(workspace_id, opportunity_id)
        if opp is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Oportunidade nao encontrada.", http_status=404)
        evidence = self._repo.list_evidence(workspace_id, "opportunity", opportunity_id)
        feedback = self._repo.list_opportunity_feedback(workspace_id, opportunity_id)
        return {"opportunity": opp, "evidence": evidence, "feedback": feedback}

    def review_opportunity(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        opportunity_id: UUID,
        *,
        decision: str,
        reason_code: str | None = None,
        notes: str | None = None,
        edited_theme: str | None = None,
        edited_angle: str | None = None,
        edited_differentiation: str | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        status_map = {
            "APPROVE": "APPROVED",
            "REJECT": "REJECTED",
            "EDIT": "UNDER_REVIEW",
            "ARCHIVE": "ARCHIVED",
            "NOTE": None,
        }
        if decision not in status_map:
            raise AppError(ErrorCode.VALIDATION_ERROR, "decision invalida.", http_status=422)
        existing = self._repo.get_opportunity(workspace_id, opportunity_id)
        if existing is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Oportunidade nao encontrada.", http_status=404)

        new_status = status_map[decision] or existing["status"]
        updated = self._repo.update_opportunity_and_record_feedback(
            workspace_id=workspace_id,
            opportunity_id=opportunity_id,
            previous_status=existing["status"],
            new_status=new_status,
            decision=decision,
            reason_code=reason_code,
            notes=notes,
            edited_theme=edited_theme,
            edited_angle=edited_angle,
            edited_differentiation=edited_differentiation,
            actor_id=actor.user_id,
        )
        return {
            "opportunity": updated["opportunity"],
            "feedback": updated["feedback"],
            "feedback_mode": "editorial_audit_only",
            "fine_tuning_claimed": False,
        }
