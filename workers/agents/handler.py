from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID

from adapters.ai_providers.omniroute import OmniRouteClient
from adapters.ai_providers.router import AIProviderRouter, redact_sensitive_text
from adapters.supabase_db.studio_repo import PostgresStudioRepository
from adapters.youtube.public_channel import PublicChannelCollector, parse_channel_ref
from core.errors import AppError, ErrorCode
from core.jobs.models import ClaimedJob
from core.studio.contracts import build_agent_prompt, validate_agent_output_envelope
from core.studio.registry import AGENT_REGISTRY
from workers.runner import WorkerContext

ModelCaller = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]

TITLE_SIMILARITY_REVIEW_THRESHOLD = 0.70


def _json_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


_GENERIC_PILLARS = {"outliers", "retencao", "retenção", "crescimento", "youtube", "shorts", "longos"}


def _norm_text(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).lower().strip()


def _extract_forbidden_topics(profile: dict[str, Any]) -> list[str]:
    restrictions = profile.get("restrictions_json") or {}
    if isinstance(restrictions, dict):
        topics = restrictions.get("forbidden_topics") or []
    elif isinstance(restrictions, list):
        topics = restrictions
    else:
        topics = []
    return [_norm_text(str(t)) for t in topics if str(t).strip()]


def _is_forbidden_text(text: str, forbidden_topics: list[str]) -> bool:
    if not forbidden_topics:
        return False
    norm = _norm_text(text)
    return any(tok in norm for tok in forbidden_topics)


def resolve_research_queries(context: dict[str, Any], explicit_topic: str | None = None) -> list[str]:
    """Gera 1-2 queries objetivas e aderentes ao canal (topico explicito -> video -> pilares/nicho)."""
    if explicit_topic and explicit_topic.strip():
        return [explicit_topic.strip()[:200]]
    content_item = context.get("content_item") or {}
    if isinstance(content_item, dict) and str(content_item.get("working_title") or "").strip():
        return [str(content_item["working_title"]).strip()[:200]]

    channel = context.get("channel") or {}
    display_name = str(channel.get("display_name") or "").strip()
    niche = str(channel.get("niche") or "").strip()
    pillars_raw = channel.get("pillars_json") or []
    pillars = [
        str(p).strip()
        for p in (pillars_raw if isinstance(pillars_raw, list) else [])
        if str(p).strip()
        and _norm_text(str(p)) != _norm_text(display_name)
        and _norm_text(str(p)) not in _GENERIC_PILLARS
    ]

    queries: list[str] = []
    for p in pillars[:2]:
        clean = re.sub(r"[^\w\sáàâãéêíóôõúç-]", " ", p, flags=re.I)
        clean = " ".join(clean.split())
        if clean:
            queries.append(clean[:120])

    if not queries and niche:
        queries.append(niche[:120])
    if not queries:
        editorial = str(channel.get("editorial_theme") or "").strip()
        if editorial and _norm_text(editorial) != _norm_text(display_name):
            queries.append(editorial[:120])
    return queries or [display_name or "engenharia infraestrutura"]


def resolve_research_topic(context: dict[str, Any], explicit_topic: str | None = None) -> str:
    """Resolve o tema real de pesquisa (topico explicito -> video ativo -> nicho/pilares -> canal)."""
    if explicit_topic and explicit_topic.strip():
        return explicit_topic.strip()[:200]
    content_item = context.get("content_item") or {}
    if isinstance(content_item, dict) and str(content_item.get("working_title") or "").strip():
        return str(content_item["working_title"]).strip()[:200]

    channel = context.get("channel") or {}
    display_name = str(channel.get("display_name") or "").strip()
    niche = str(channel.get("niche") or "").strip()
    pillars_raw = channel.get("pillars_json") or []
    pillars = [str(p).strip() for p in pillars_raw if str(p).strip()] if isinstance(pillars_raw, list) else []

    if niche:
        return niche[:200]

    editorial = str(channel.get("editorial_theme") or "").strip()
    if editorial and editorial.lower() != display_name.lower():
        return editorial[:200]
    if pillars:
        first_non_name = next((p for p in pillars if p.lower() != display_name.lower()), pillars[0])
        return first_non_name[:200]
    return (display_name or "Tema do canal")[:200]


_NOISE_YT_TOKENS = ("podcast", "cortes", "mesacast", "entrevista completa", "live completa", "react")


def _is_noise_video(title: str, channel_name: str, explicit_topic: str | None) -> bool:
    if explicit_topic and any(tok in _norm_text(explicit_topic) for tok in _NOISE_YT_TOKENS):
        return False
    norm = _norm_text(f"{title} {channel_name}")
    return any(tok in norm for tok in _NOISE_YT_TOKENS)


def _build_local_episode_suggestions(
    *,
    research_topic: str,
    candidates: list[dict[str, Any]],
    refs: list[dict[str, Any]],
    channel: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fallback deterministico para sugestoes de episodios quando em modo local_only."""
    if not candidates:
        return []
    suggestions: list[dict[str, Any]] = []
    ref_by_id = {str(r.get("id")): r for r in refs}
    for c in candidates[:3]:
        rid = str(c.get("reference_id") or "")
        ref = ref_by_id.get(rid) or {}
        ref_title = str(ref.get("title") or c.get("why_similar") or research_topic).strip()
        short_subject = ref_title.split("|")[0].split("—")[-1].strip()[:90] or research_topic[:90]
        suggestions.append(
            {
                "title": f"Como Funciona Por Dentro {short_subject}?"[:155],
                "alternative_title": f"O Gargalo Oculto Que Move {short_subject}"[:155],
                "theme": short_subject[:200],
                "angle": "Engenharia reversa do processo fisico, gargalo tecnico e impacto em escala real.",
                "thumbnail_structure": {
                    "hero_object": f"Corte tecnico ou objeto central de {short_subject[:80]} em 4K",
                    "shock_text": "COMO FUNCIONA?",
                    "visual_composition": "Fundo #060709, destaque #FF5500 na restricao fisica e telemetria #00F0FF.",
                },
                "opening_hook": "0-15s: localize no mapa, apresente a unidade concreta e o erro de previsao antes de explicar a solucao.",
                "why_now": f"Ancorado em referencia publica real ({str(c.get('why_similar') or '')[:160]}).",
                "reference_ids": [rid] if rid else [],
            }
        )
    return suggestions


def _format_views_pt(views: Any) -> str:
    if not isinstance(views, (int, float)) or views < 0:
        return ""
    n = int(views)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M views"
    if n >= 1_000:
        return f"{round(n / 1_000)}K views"
    return f"{n} views"


def default_local_agent_model_caller(
    prompt: str,
    context: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    """Gerador local deterministico que respeita estritamente dados reais do banco (zero numero inventado)."""
    agent_key: str = meta["agent_key"]
    channel = context["channel"]
    channel_id = str(channel["id"])
    content_item = context.get("content_item")
    content_item_id = str(content_item["id"]) if content_item else None
    working_title = (content_item or {}).get("working_title") or channel.get("editorial_theme") or channel.get("display_name") or "Tema do canal"
    now_iso = datetime.now(timezone.utc).isoformat()
    profile_id = channel.get("profile_version_id")

    sources: list[dict[str, Any]] = []
    if profile_id:
        sources.append({"kind": "profile_version", "id": str(profile_id), "locator": f"v{channel.get('version_number', 1)}"})

    limitations: list[str] = []

    if agent_key == "dados":
        metrics_rows = context.get("metrics") or []
        by_id = {m["metric_id"]: m for m in metrics_rows}
        period_end = date.today()
        period_start = period_end - timedelta(days=28)

        def metric_entry(mid: str, key: str) -> dict[str, Any]:
            row = by_id.get(mid)
            if row and row.get("availability") == "available" and row.get("value_num") is not None:
                sources.append({"kind": "metric", "id": str(row["id"]), "locator": mid})
                return {
                    "key": key,
                    "value": float(row["value_num"]),
                    "delta_pct": None,
                    "availability": "available",
                    "fetched_at": str(row.get("fetched_at") or now_iso),
                }
            limitations.append(f"Metrica {mid} indisponivel no banco (mantida como null).")
            return {
                "key": key,
                "value": None,
                "delta_pct": None,
                "availability": "unknown",
                "fetched_at": None,
            }

        metrics_out = [
            metric_entry("yt.analytics.views", "views"),
            metric_entry("yt.analytics.impressions_ctr", "ctr"),
            metric_entry("yt.analytics.avg_view_duration_sec", "avg_view_duration_sec"),
        ]
        available_cnt = sum(1 for m in metrics_out if m["availability"] == "available")
        confidence = "alta" if available_cnt == 3 else ("media" if available_cnt >= 1 else "baixa")
        findings = (
            [{"text": f"{available_cnt} metricas sincronizadas lidas do historico real.", "evidence": [s["id"] for s in sources]}]
            if available_cnt > 0
            else [{"text": "Sem metricas sincronizadas; aguardando OAuth/sync do canal.", "evidence": [s["id"] for s in sources]}]
        )
        return {
            "agent_key": "dados",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": (
                f"{available_cnt}/3 metricas reais analisadas"
                if available_cnt > 0
                else "Analytics indisponivel (dados marcados como unknown)"
            )[:120],
            "confidence": confidence,
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "period": {"from": period_start.isoformat(), "to": period_end.isoformat()},
                "metrics": metrics_out,
                "findings": findings,
            },
        }

    if agent_key == "pesquisa":
        research_topic = resolve_research_topic(context, context.get("research_topic"))
        forbidden = _extract_forbidden_topics(channel)
        refs = [
            r for r in (context.get("references") or [])
            if not _is_forbidden_text(f"{r.get('title', '')} {r.get('channel_name', '')}", forbidden)
        ]
        outliers = [
            o for o in (context.get("studio_outliers") or [])
            if not _is_forbidden_text(str(o.get("title", "")), forbidden)
        ]
        gt = context.get("google_trends") or []
        for warn in context.get("research_warnings") or []:
            limitations.append(str(warn))
        candidates: list[dict[str, Any]] = []
        for r in refs[:6]:
            sources.append({"kind": "research_reference", "id": str(r["id"]), "locator": "reference_videos"})
            meta_parts: list[str] = []
            views_lbl = _format_views_pt(r.get("public_views_snapshot"))
            if views_lbl:
                meta_parts.append(views_lbl)
            if r.get("outlier_ratio"):
                meta_parts.append(f"outlier {r['outlier_ratio']}x")
            if r.get("channel_name"):
                meta_parts.append(str(r["channel_name"]))
            elif r.get("notes"):
                meta_parts.append(str(r["notes"]))
            prefix = f"{' • '.join(meta_parts)} — " if meta_parts else "Referencia: "
            candidates.append(
                {
                    "reference_id": str(r["id"]),
                    "url": str(r.get("canonical_url") or ""),
                    "why_similar": f"{prefix}{r.get('title', '')}"[:240],
                    "observed_at": str(r.get("snapshot_observed_at") or now_iso),
                }
            )
        for o in outliers[:3]:
            sources.append({"kind": "research_reference", "id": str(o["id"]), "locator": "studio_video_outliers"})
            candidates.append(
                {
                    "reference_id": str(o["id"]),
                    "url": str(o.get("canonical_url") or ""),
                    "why_similar": f"Outlier {o.get('outlier_ratio') or '?'}x: {o.get('title', '')[:100]}",
                    "observed_at": str(o.get("created_at") or now_iso),
                }
            )
        for g in gt[:2]:
            sources.append({"kind": "research_reference", "id": str(g["id"]), "locator": "google_trends"})

        if len(candidates) >= 2 or (len(candidates) >= 1 and len(gt) >= 1):
            val_status = "validado"
            reason = f"{len(candidates)} referencias publicas e {len(gt)} validacoes Trends sustentam '{research_topic}'."
            conf = "alta" if len(candidates) >= 3 else "media"
        elif len(candidates) == 1 or len(gt) >= 1:
            val_status = "fraco"
            reason = f"Apenas {len(candidates)} referencia publica e {len(gt)} validacoes Trends encontradas para '{research_topic}'."
            conf = "media"
        else:
            val_status = "sem_evidencia"
            reason = f"Nenhuma referencia publica encontrada para '{research_topic}'."
            limitations.append("Pesquisa publica sem referencias aprovadas no workspace.")
            conf = "baixa"

        episode_suggestions = _build_local_episode_suggestions(
            research_topic=research_topic,
            candidates=candidates,
            refs=refs,
            channel=channel,
        )

        return {
            "agent_key": "pesquisa",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": f"Tema {val_status} ({len(candidates)} referencias): {research_topic}"[:120],
            "confidence": conf,
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "question": f"O tema '{research_topic}' tem demanda validada para {channel.get('display_name')}?",
                "candidates": candidates,
                "topic_validation": {
                    "topic": research_topic,
                    "status": val_status,
                    "reason": reason[:600],
                },
                "episode_suggestions": episode_suggestions,
            },
        }

    if agent_key == "estrategia":
        prior = context.get("prior_outputs") or []
        for p in prior:
            sources.append({"kind": "agent_output", "id": str(p["id"]), "locator": p["output_type"]})
        chunks = context.get("knowledge_chunks") or []
        for ch in chunks[:3]:
            sources.append({"kind": "knowledge_chunk", "id": str(ch["chunk_id"]), "locator": ch.get("source_title")})

        has_refs = bool(context.get("references") or context.get("studio_outliers") or context.get("google_trends"))
        has_metrics = any(m.get("availability") == "available" for m in (context.get("metrics") or []))
        has_rag = bool(chunks)
        pot = round(0.45 + (0.25 if has_refs else 0.0) + (0.15 if has_rag else 0.0) + (0.10 if has_metrics else 0.0), 2)
        conc = 0.50 if has_refs else 0.35
        score_val = int(round(pot * 100))
        if not has_refs:
            limitations.append("Sem referencias publicas aprovadas; score reflete incerteza.")
        if not has_metrics:
            limitations.append("Sem metricas privadas sincronizadas.")
        evidence = [
            {"text": f"Baseado em {len(prior)} outputs anteriores e {len(chunks)} chunks RAG", "source_id": s["id"]}
            for s in sources[:3]
        ]
        return {
            "agent_key": "estrategia",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": f"Oportunidade '{working_title[:60]}' (score {score_val}/100)"[:120],
            "confidence": "alta" if (has_refs and has_metrics) else ("media" if (has_refs or has_rag) else "baixa"),
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "topic": working_title,
                "angle": f"Abordagem diferenciada de '{working_title}' ancorada nos pilares do canal.",
                "differentiation": f"Evita repeticao de titulos existentes e aplica estrutura verificada.",
                "score": {
                    "value": score_val,
                    "max": 100,
                    "version": "score-v1",
                    "components": [
                        {"key": "potencial", "value": pot},
                        {"key": "concorrencia", "value": conc},
                    ],
                },
                "labels": {
                    "potencial": "alto" if pot >= 0.70 else ("medio" if pot >= 0.45 else "baixo"),
                    "concorrencia": "media" if conc >= 0.45 else "baixa",
                },
                "evidence": evidence,
            },
        }

    if agent_key == "titulos":
        prior = context.get("prior_outputs") or []
        for p in prior:
            sources.append({"kind": "agent_output", "id": str(p["id"]), "locator": p["output_type"]})
        refs = context.get("references") or []
        closest_id = str(refs[0]["id"]) if refs else None
        options = [
            {
                "text": f"O que ninguém explica sobre {working_title[:70]}",
                "pattern": "lacuna_curiosidade",
                "differentiation": "Foca no mecanismo oculto sem prometer resultado impossivel.",
                "closest_reference_id": closest_id,
                "similarity": 0.24,
            },
            {
                "text": f"Por que {working_title[:65]} muda tudo em 2026",
                "pattern": "contraste_temporal",
                "differentiation": "Ancoragem factual e angulo proprio do canal.",
                "closest_reference_id": closest_id,
                "similarity": 0.21,
            },
            {
                "text": f"Os 3 erros invisíveis por trás de {working_title[:55]}",
                "pattern": "diagnostico_estruturado",
                "differentiation": "Estrutura de diagnostico pratico baseada nos pilares do canal.",
                "closest_reference_id": closest_id,
                "similarity": 0.19,
            },
        ]
        return {
            "agent_key": "titulos",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": f"{len(options)} opcoes originais de titulo geradas"[:120],
            "confidence": "media" if refs else "baixa",
            "limitations": [] if refs else ["Sem titulos de referencia aprovados para comparar similaridade."],
            "sources": sources,
            "payload": {"options": options},
        }

    if agent_key == "roteiro":
        prior = context.get("prior_outputs") or []
        for p in prior:
            sources.append({"kind": "agent_output", "id": str(p["id"]), "locator": p["output_type"]})
        chunks = context.get("knowledge_chunks") or []
        for ch in chunks[:3]:
            sources.append({"kind": "knowledge_chunk", "id": str(ch["chunk_id"]), "locator": ch.get("source_title")})
        if not chunks:
            limitations.append("Sem chunks RAG L2/L3 aprovados; roteiro estruturado apenas com perfil e oportunidade.")

        return {
            "agent_key": "roteiro",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": "Rascunho v1 de roteiro (hook, outline e CTA)"[:120],
            "confidence": "alta" if chunks else "media",
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "hook": f"Nos primeiros 25 segundos, abrimos o conflito central de '{working_title}' com evidencia concreta.",
                "outline": [
                    {"section": "Abertura / Hook", "goal": "Estabelecer tensao e promessa realista", "duration_sec": 35},
                    {"section": "Desenvolvimento", "goal": "Apresentar provas e contexto do canal", "duration_sec": 360},
                    {"section": "Fechamento / CTA", "goal": "Consolidar aprendizado e proximo passo", "duration_sec": 45},
                ],
                "body": [
                    {"section": "Abertura / Hook", "text": f"Contexto direto sobre {working_title} alinhado a voz do canal."},
                    {"section": "Desenvolvimento", "text": "Analise passo a passo com fontes verificadas."},
                    {"section": "Fechamento / CTA", "text": "Resumo pratico e convite para o proximo episodio."},
                ],
                "cta": "Inscreva-se e acompanhe o proximo estudo completo do canal.",
            },
        }

    if agent_key == "thumbnail":
        prior = context.get("prior_outputs") or []
        for p in prior:
            sources.append({"kind": "agent_output", "id": str(p["id"]), "locator": p["output_type"]})
        limitations.append("Provedor de visao OCR nao configurado; conceitos gerados sem analise visual automatica.")
        concepts = [
            {
                "idea": f"Contraste de escala sobre '{working_title[:60]}' com foco no elemento central",
                "text_overlay": "O PONTO CEGO",
                "composition": "Regra dos tercos: objeto principal a direita, texto curto em alto contraste a esquerda",
                "palette": "ardosia escuro, ambar quente e branco nitido",
                "similar_reference_ids": [],
                "similarity_flag": False,
            },
            {
                "idea": f"Diagrama antes/depois mostrando ruptura em '{working_title[:50]}'",
                "text_overlay": "POR QUE FALHA",
                "composition": "Divisao diagonal limpa com destaque em latão",
                "palette": "madeira escura, ambar e cinza neutro",
                "similar_reference_ids": [],
                "similarity_flag": False,
            },
            {
                "idea": f"Close dramatico em evidencia documental de '{working_title[:50]}'",
                "text_overlay": "PROVA REAL",
                "composition": "Primeiro plano nitido com fundo em desfoque leve",
                "palette": "preto carvao, dourado suave e marfim",
                "similar_reference_ids": [],
                "similarity_flag": False,
            },
        ]
        return {
            "agent_key": "thumbnail",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": f"{len(concepts)} conceitos de thumbnail propostos"[:120],
            "confidence": "media",
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "concepts": concepts,
                "vision_available": False,
            },
        }

    if agent_key == "edicao":
        intents = context.get("production_intents") or []
        if intents:
            intent = intents[0]
            sources.append({"kind": "artifact", "id": str(intent["id"]), "locator": "production_intent"})
            manifest_ready = bool(intent.get("manifest_validated"))
            prod_id = str(intent["id"])
            stage = str(intent.get("status") or "INTENT_CREATED")
            progress = 1.0 if stage == "READY" else None
            checks = [{"check": "manifest_validated", "result": "pass" if manifest_ready else "unknown"}]
        else:
            prod_id = str(content_item_id or channel_id)
            manifest_ready = False
            stage = "aguardando_dispatch_darkforge"
            progress = None
            checks = [{"check": "darkforge_manifest", "result": "unknown"}]
            limitations.append("Nenhuma ProductionIntent despachada no DarkForge; progresso real indefinido (null).")

        return {
            "agent_key": "edicao",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": f"Producao em '{stage}'"[:120],
            "confidence": "alta" if manifest_ready else "baixa",
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "production_job_id": prod_id,
                "stage": stage,
                "progress": progress,
                "artifact": {"id": None, "manifest_ready": manifest_ready, "checksum": None},
                "quality_checks": checks,
            },
        }

    # publicacao
    prior = context.get("prior_outputs") or []
    for p in prior:
        sources.append({"kind": "agent_output", "id": str(p["id"]), "locator": p["output_type"]})
    scheduled_dt = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=17, minute=0, second=0, microsecond=0)
    return {
        "agent_key": "publicacao",
        "contract_version": 1,
        "channel_id": channel_id,
        "content_item_id": content_item_id,
        "summary": f"Plano de publicacao sugerido para {scheduled_dt.strftime('%d/%m %H:%M')}"[:120],
        "confidence": "media",
        "limitations": ["Publicacao automatica bloqueada; requer revisao e envio manual no YouTube."],
        "sources": sources,
        "payload": {
            "scheduled_for": scheduled_dt.isoformat(),
            "title_option_index": 0,
            "description": f"Estudo completo sobre {working_title}. Fontes verificadas no painel editorial.",
            "tags": [str(channel.get("niche") or "youtube"), working_title[:40]],
            "requires_human_publish": True,
        },
    }


class AgentJobHandler:
    """Handler do JobWorker unico (SP-02) para executar runs de agentes (UI-02-T04..T08)."""

    def __init__(
        self,
        repo: PostgresStudioRepository,
        *,
        ai_router: AIProviderRouter | None = None,
        model_caller: ModelCaller | None = None,
        public_collector: PublicChannelCollector | None = None,
        omniroute_client: OmniRouteClient | None = None,
        step_delay_seconds: float = 0.0,
    ) -> None:
        self._repo = repo
        self._ai_router = ai_router or AIProviderRouter()
        self._model_caller = model_caller or default_local_agent_model_caller
        self._public_collector = public_collector or PublicChannelCollector(
            api_key=os.getenv("YOUTUBE_API_KEY", ""),
            timeout_seconds=10.0,
        )
        self._omniroute = omniroute_client or OmniRouteClient()
        self._step_delay = max(0.0, float(step_delay_seconds))

    def _plan_queries_with_omniroute(
        self,
        auth_ctx: dict[str, Any],
        topic: str,
        fallback_queries: list[str],
        explicit_topic: str | None,
    ) -> list[str]:
        channel = auth_ctx.get("channel") or {}
        chunks = [
            redact_sensitive_text(str(c.get("chunk_text") or ""))[:400]
            for c in (auth_ctx.get("knowledge_chunks") or [])[:4]
        ]
        sys_p = (
            "Voce e um estrategista de pesquisa do YouTube. Retorne APENAS JSON valido "
            'no formato {"queries": ["query 1", "query 2"]}. '
            "Cada query deve ter 3 a 7 palavras para buscar documentarios/obras/engenharia/infraestrutura no YouTube, "
            "evitando podcasts, cortes ou temas proibidos."
        )
        usr_p = json.dumps(
            {
                "channel_name": channel.get("display_name"),
                "niche": channel.get("niche"),
                "positioning": channel.get("positioning"),
                "pillars": channel.get("pillars_json") or [],
                "forbidden_topics": _extract_forbidden_topics(channel),
                "explicit_topic": explicit_topic,
                "resolved_topic": topic,
                "knowledge_excerpts": chunks,
            },
            ensure_ascii=False,
        )
        try:
            data, _ = self._omniroute.chat_json(sys_p, usr_p, temperature=0.25, max_tokens=220)
            raw_q = data.get("queries")
            if isinstance(raw_q, list):
                cleaned = [str(q).strip()[:120] for q in raw_q if str(q).strip()]
                if cleaned:
                    return cleaned[:2]
        except Exception as exc:
            warns = list(auth_ctx.get("research_warnings") or [])
            warns.append(f"Planejamento de busca OmniRoute degradado para busca local ({redact_sensitive_text(str(exc))[:100]}).")
            auth_ctx["research_warnings"] = warns
        return fallback_queries

    def _synthesize_pesquisa_with_omniroute(
        self,
        auth_ctx: dict[str, Any],
        repair_error: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        channel = auth_ctx["channel"]
        channel_id = str(channel["id"])
        content_item = auth_ctx.get("content_item")
        content_item_id = str(content_item["id"]) if content_item else None
        research_topic = resolve_research_topic(auth_ctx, auth_ctx.get("research_topic"))
        refs = auth_ctx.get("references") or []
        chunks = auth_ctx.get("knowledge_chunks") or []
        profile_id = channel.get("profile_version_id")
        now_iso = datetime.now(timezone.utc).isoformat()

        ref_map = {str(r["id"]): r for r in refs}
        chunk_map = {str(c["chunk_id"]): c for c in chunks}

        refs_payload = [
            {
                "reference_id": str(r["id"]),
                "title": r.get("title"),
                "channel_name": r.get("channel_name"),
                "views": r.get("public_views_snapshot"),
                "outlier_ratio": r.get("outlier_ratio"),
                "url": r.get("canonical_url"),
            }
            for r in refs[:8]
        ]
        chunks_payload = [
            {
                "chunk_id": str(c["chunk_id"]),
                "source_title": c.get("source_title"),
                "excerpt": redact_sensitive_text(str(c.get("chunk_text") or ""))[:450],
            }
            for c in chunks[:4]
        ]

        sys_prompt = (
            "Voce e o Pesquisador + Engenheiro Reverso de YouTube do canal. "
            "Com base APENAS nos <dados> fornecidos (identidade, Engenharia Reversa, pautas e videos reais coletados), "
            "avalie a demanda do tema e crie 3 a 5 sugestoes completas de NOVOS EPISODIOS.\n"
            "Regras obrigatorias:\n"
            "1. Retorne APENAS um JSON valido (sem markdown).\n"
            "2. Titulos: <= 14 palavras, pergunta fisica concreta ou Formula Matriz (unidade pequena + consequencia/escala), "
            "SEM ':' e SEM o nome do canal.\n"
            "3. Thumbnail (leitura 0.2s): hero_object (objeto/corte/mapa em 4K), shock_text (2-3 palavras maiusculas), "
            "visual_composition (Carbon Black #060709, Sodium Orange #FF5500, Laser Cyan #00F0FF, medidor #00FF66/#FF2A2A; sem cyberpunk/hologramas).\n"
            "4. opening_hook (0-30s): Auto-Relevancia + Erro de Previsao + Consequencia + Microprova + Lacuna de Informacao.\n"
            "5. Use SOMENTE reference_id existentes em references_collected; NUNCA invente URL ou ID."
        )
        schema_hint = {
            "summary": "string <= 120 chars",
            "confidence": "alta | media | baixa",
            "limitations": ["string"],
            "question": "string",
            "topic_validation": {"topic": research_topic, "status": "validado | fraco | sem_evidencia", "reason": "string"},
            "candidate_notes": [{"reference_id": "id_real", "why_similar": "por que esse video valida o tema e embalagem"}],
            "episode_suggestions": [
                {
                    "title": "string <= 14 palavras",
                    "alternative_title": "string",
                    "theme": "string",
                    "angle": "solucao de engenharia contraintuitiva / escala / disputa + mecanismo",
                    "thumbnail_structure": {
                        "hero_object": "string",
                        "shock_text": "2-3 PALAVRAS",
                        "visual_composition": "string",
                    },
                    "opening_hook": "string 0-30s",
                    "why_now": "string ancorada nos comparaveis/janela",
                    "reference_ids": ["id_real"],
                }
            ],
        }
        user_prompt = (
            "<dados>\n"
            + redact_sensitive_text(
                json.dumps(
                    {
                        "channel": {
                            "display_name": channel.get("display_name"),
                            "niche": channel.get("niche"),
                            "positioning": channel.get("positioning"),
                            "pillars": channel.get("pillars_json") or [],
                            "voice": channel.get("voice_json") or {},
                            "forbidden_topics": _extract_forbidden_topics(channel),
                        },
                        "research_topic": research_topic,
                        "knowledge_chunks": chunks_payload,
                        "references_collected": refs_payload,
                        "output_schema": schema_hint,
                    },
                    ensure_ascii=False,
                )
            ).replace("</dados>", "")
            + "\n</dados>"
        )
        if repair_error:
            user_prompt += f"\n\nCORRECAO OBRIGATORIA DE SCHEMA: {repair_error}"

        ai_json, used_model = self._omniroute.chat_json(sys_prompt, user_prompt, temperature=0.35, max_tokens=1600)

        # Monta sources e candidates estritamente com IDs reais verificados no banco
        sources: list[dict[str, Any]] = []
        if profile_id:
            sources.append({"kind": "profile_version", "id": str(profile_id), "locator": f"v{channel.get('version_number', 1)}"})
        for cid in list(chunk_map.keys())[:3]:
            sources.append({"kind": "knowledge_chunk", "id": cid, "locator": chunk_map[cid].get("source_title")})

        notes_by_ref = {
            str(n.get("reference_id")): str(n.get("why_similar") or "").strip()
            for n in (ai_json.get("candidate_notes") or [])
            if isinstance(n, dict) and str(n.get("reference_id") or "") in ref_map
        }
        candidates: list[dict[str, Any]] = []
        for r in refs[:6]:
            rid = str(r["id"])
            sources.append({"kind": "research_reference", "id": rid, "locator": "reference_videos"})
            views_lbl = _format_views_pt(r.get("public_views_snapshot"))
            prefix_bits = [b for b in (views_lbl, f"outlier {r['outlier_ratio']}x" if r.get("outlier_ratio") else "", str(r.get("channel_name") or "")) if b]
            default_why = f"{' • '.join(prefix_bits)} — {r.get('title', '')}" if prefix_bits else str(r.get("title") or "")
            note = notes_by_ref.get(rid)
            why_txt = f"{' • '.join(prefix_bits)} — {r.get('title', '')} ({note})" if (note and prefix_bits) else (note or default_why)
            candidates.append(
                {
                    "reference_id": rid,
                    "url": str(r.get("canonical_url") or ""),
                    "why_similar": why_txt[:480],
                    "observed_at": str(r.get("snapshot_observed_at") or now_iso),
                }
            )

        raw_eps = ai_json.get("episode_suggestions") or []
        episode_suggestions: list[dict[str, Any]] = []
        for ep in raw_eps[:5]:
            if not isinstance(ep, dict):
                continue
            title = str(ep.get("title") or "").strip()[:160]
            if not title:
                continue
            thumb = ep.get("thumbnail_structure") if isinstance(ep.get("thumbnail_structure"), dict) else {}
            valid_ref_ids = [str(x) for x in (ep.get("reference_ids") or []) if str(x) in ref_map][:6]
            if not valid_ref_ids and candidates:
                valid_ref_ids = [candidates[0]["reference_id"]]
            episode_suggestions.append(
                {
                    "title": title,
                    "alternative_title": (str(ep.get("alternative_title") or "").strip()[:160] or None),
                    "theme": str(ep.get("theme") or research_topic).strip()[:240],
                    "angle": str(ep.get("angle") or "Engenharia reversa do sistema oculto e gargalo fisico.").strip()[:400],
                    "thumbnail_structure": {
                        "hero_object": str(thumb.get("hero_object") or "Objeto central ou corte tecnico em 4K").strip()[:240],
                        "shock_text": str(thumb.get("shock_text") or "COMO FUNCIONA?").strip()[:80],
                        "visual_composition": str(thumb.get("visual_composition") or "Carbon Black #060709, Sodium Orange #FF5500, Laser Cyan #00F0FF").strip()[:400],
                    },
                    "opening_hook": str(ep.get("opening_hook") or "0-15s: auto-relevancia, erro de previsao, microprova e lacuna.").strip()[:500],
                    "why_now": str(ep.get("why_now") or "Demanda validada pelas referencias publicas analisadas.").strip()[:400],
                    "reference_ids": valid_ref_ids,
                }
            )

        if not episode_suggestions:
            episode_suggestions = _build_local_episode_suggestions(
                research_topic=research_topic,
                candidates=candidates,
                refs=refs,
                channel=channel,
            )

        tv = ai_json.get("topic_validation") if isinstance(ai_json.get("topic_validation"), dict) else {}
        val_status = str(tv.get("status") or ("validado" if len(candidates) >= 2 else ("fraco" if candidates else "sem_evidencia")))
        if val_status not in ("validado", "fraco", "sem_evidencia"):
            val_status = "validado" if len(candidates) >= 2 else "fraco"
        conf = str(ai_json.get("confidence") or ("alta" if len(candidates) >= 2 else "baixa"))
        if conf not in ("alta", "media", "baixa"):
            conf = "media"
        limitations = [str(x)[:300] for x in (ai_json.get("limitations") or []) if str(x).strip()][:6]
        for w in auth_ctx.get("research_warnings") or []:
            limitations.append(str(w)[:300])

        summary = str(ai_json.get("summary") or f"Tema {val_status} ({len(candidates)} refs, {len(episode_suggestions)} eps): {research_topic}")[:120]
        envelope = {
            "agent_key": "pesquisa",
            "contract_version": 1,
            "channel_id": channel_id,
            "content_item_id": content_item_id,
            "summary": summary,
            "confidence": conf,
            "limitations": limitations,
            "sources": sources,
            "payload": {
                "question": str(ai_json.get("question") or f"O tema '{research_topic}' tem demanda validada para {channel.get('display_name')}?")[:400],
                "candidates": candidates,
                "topic_validation": {
                    "topic": str(tv.get("topic") or research_topic)[:240],
                    "status": val_status,
                    "reason": str(tv.get("reason") or f"{len(candidates)} referencias e {len(episode_suggestions)} sugestoes de episodios.")[:600],
                },
                "episode_suggestions": episode_suggestions,
            },
        }
        return envelope, used_model

    def _run_live_public_research(
        self,
        *,
        workspace_id: UUID,
        channel_id: UUID,
        run_id: UUID,
        fencing_token: int,
        auth_ctx: dict[str, Any],
        explicit_topic: str | None,
        use_omniroute: bool = False,
        heartbeat_fn: Callable[[], None] | None = None,
    ) -> None:
        topic = resolve_research_topic(auth_ctx, explicit_topic)
        queries = resolve_research_queries(auth_ctx, explicit_topic)
        if use_omniroute:
            if heartbeat_fn:
                heartbeat_fn()
            queries = self._plan_queries_with_omniroute(auth_ctx, topic, queries, explicit_topic)
            if heartbeat_fn:
                heartbeat_fn()
        auth_ctx["research_topic"] = topic
        channel = auth_ctx.get("channel") or {}
        language = str(channel.get("language") or "pt-BR")
        country = str(channel.get("country") or "BR")
        forbidden = _extract_forbidden_topics(channel)

        # Tokens editoriais (nicho + pilares + positioning + chunks) para ranquear aderencia real
        profile_blob = " ".join(
            [
                topic,
                str(channel.get("niche") or ""),
                str(channel.get("positioning") or ""),
                " ".join(str(p) for p in (channel.get("pillars_json") or [])),
                " ".join(str(c.get("chunk_text") or "")[:300] for c in (auth_ctx.get("knowledge_chunks") or [])[:4]),
            ]
        )
        topic_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", _norm_text(profile_blob))}

        self._repo.update_run_progress(
            run_id,
            fencing_token,
            stage_label="pesquisando referencias no YouTube",
            progress=0.25,
            summary=f"Pesquisando referencias publicas sobre '{topic[:60]}'",
        )

        discovered_by_id: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for q in queries[:2]:
            try:
                search_hits = self._public_collector.search_public_videos(
                    q,
                    max_results=8,
                    language=language,
                    country=country,
                )
                for hit in search_hits:
                    blob = f"{hit.get('title', '')} {hit.get('channel_name', '')}"
                    if _is_forbidden_text(blob, forbidden):
                        continue
                    if _is_noise_video(str(hit.get("title") or ""), str(hit.get("channel_name") or ""), explicit_topic):
                        continue
                    vid = str(hit.get("video_id") or "")
                    if vid and vid not in discovered_by_id:
                        discovered_by_id[vid] = hit
            except Exception as exc:
                warnings.append(f"Busca publica ('{q[:40]}') falhou ({redact_sensitive_text(str(exc))[:120]}).")

        def _score_hit(v: dict[str, Any]) -> tuple[int, float]:
            is_long = 1 if v.get("format") != "short" else 0
            tokens = set(re.findall(r"[a-z0-9]{4,}", _norm_text(f"{v.get('title', '')} {v.get('channel_name', '')}")))
            overlap = len(tokens & topic_tokens)
            views = max(0, int(v.get("views") or 0))
            return (is_long, overlap * 1.5 + math.log10(views + 1))

        ranked_search = sorted(discovered_by_id.values(), key=_score_hit, reverse=True)
        discovered: list[dict[str, Any]] = ranked_search[:5]

        ext_ref = str(channel.get("external_channel_id") or channel.get("handle") or "").strip()
        if ext_ref:
            try:
                ov = self._public_collector.fetch_overview(parse_channel_ref(ext_ref), max_videos=15)
                ch_info = ov.get("channel") or {}
                ch_vids = sorted(
                    ov.get("videos") or [],
                    key=lambda v: (1 if v.get("format") != "short" else 0, v.get("outlier_ratio") or 0.0, v.get("views") or 0),
                    reverse=True,
                )
                seen_vids = {str(d.get("video_id")) for d in discovered}
                for v in ch_vids[:2]:
                    if v["video_id"] in seen_vids:
                        continue
                    discovered.append(
                        {
                            "video_id": v["video_id"],
                            "url": v.get("url"),
                            "title": v.get("title") or "",
                            "channel_id": ch_info.get("channel_id") or ext_ref,
                            "channel_name": ch_info.get("title") or channel.get("display_name") or "Canal",
                            "views": v.get("views"),
                            "duration_seconds": v.get("duration_seconds"),
                            "format": v.get("format") or "unknown",
                            "thumbnail_url": v.get("thumbnail_url"),
                            "outlier_ratio": v.get("outlier_ratio"),
                            "source": "linked_channel_public",
                        }
                    )
            except Exception as exc:
                warnings.append(f"Coleta de outliers do canal vinculado falhou ({redact_sensitive_text(str(exc))[:120]}).")

        if warnings:
            auth_ctx["research_warnings"] = warnings
        if heartbeat_fn:
            heartbeat_fn()

        if discovered and hasattr(self._repo, "save_discovered_research_references"):
            actor_raw = channel.get("created_by")
            try:
                actor_id = UUID(str(actor_raw))
            except Exception:
                return
            saved = self._repo.save_discovered_research_references(
                workspace_id=workspace_id,
                channel_id=channel_id,
                actor_id=actor_id,
                run_id=run_id,
                topic=topic,
                language=language,
                candidates=discovered,
            )
            if saved:
                auth_ctx["references"] = saved

    def __call__(self, job: ClaimedJob, ctx: WorkerContext) -> None:
        payload = job.payload_json or {}
        run_id_raw = payload.get("run_id")
        if not run_id_raw:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Payload de agent.execute sem run_id.", http_status=422)

        run_id = UUID(str(run_id_raw))
        agent_key = str(payload.get("agent_key") or "")
        spec = AGENT_REGISTRY.get(agent_key)
        if spec is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"Agente desconhecido: {agent_key}.", http_status=422)

        content_item_id = UUID(str(payload["content_item_id"])) if payload.get("content_item_id") else None
        channel_id = UUID(str(payload.get("channel_id") or job.channel_id))
        workspace_id = job.workspace_id

        try:
            # 1. Marca working + evento run_started
            run_row = self._repo.mark_run_started(run_id, job.fencing_token)
            if run_row is None:
                raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "agent_run ausente.", http_status=404)

            ctx.heartbeat()
            sig = ctx.checkpoint("context", 1, {"stage": "loading_context"}, "Contexto autorizado carregado")
            if sig == "cancel":
                self._repo.cancel_agent_run(workspace_id, run_id)
                return
            if sig == "pause":
                ctx._queue.transition(job.job_id, job.fencing_token, "PAUSED", checkpoint_json={"stage": "loading_context"})
                return

            # 2. Carrega contexto autorizado e verifica politica do canal
            auth_ctx = self._repo.load_authorized_context(workspace_id, channel_id, agent_key, content_item_id)
            channel_agent = auth_ctx.get("channel_agent") or {}
            policy = channel_agent.get("model_policy") or {"mode": "local_only", "external_consent": False}
            policy_mode = str(policy.get("mode", "local_only"))

            if policy_mode in ("external", "external_consented") and not bool(policy.get("external_consent")):
                raise AppError(
                    ErrorCode.AI_EXTERNAL_CONSENT_REQUIRED,
                    "Politica externa sem consentimento explicito; execucao bloqueada.",
                    http_status=412,
                )

            if policy_mode == "local_only" and not self._ai_router.policy.local_available:
                raise AppError(
                    ErrorCode.AI_PROVIDER_UNAVAILABLE,
                    "Provedor local indisponivel; fallback externo silencioso bloqueado (ADR-007).",
                    http_status=503,
                    retryable=True,
                )

            use_omniroute = (
                agent_key == "pesquisa"
                and self._model_caller is default_local_agent_model_caller
                and policy_mode in ("external", "external_consented")
                and bool(policy.get("external_consent"))
                and self._omniroute.is_configured
            )
            explicit_topic = str(payload.get("topic") or "") or None
            if agent_key == "pesquisa":
                self._run_live_public_research(
                    workspace_id=workspace_id,
                    channel_id=channel_id,
                    run_id=run_id,
                    fencing_token=job.fencing_token,
                    auth_ctx=auth_ctx,
                    explicit_topic=explicit_topic,
                    use_omniroute=use_omniroute,
                    heartbeat_fn=ctx.heartbeat,
                )

            self._repo.update_run_progress(
                run_id,
                job.fencing_token,
                stage_label="executando modelo",
                progress=0.45,
                summary=f"Executando {spec.display_name}",
            )
            if self._step_delay > 0:
                time.sleep(self._step_delay)
            sig = ctx.checkpoint("inference", 2, {"stage": "calling_model"}, "Chamando modelo")
            if sig == "cancel":
                self._repo.cancel_agent_run(workspace_id, run_id)
                return
            if sig == "pause":
                ctx._queue.transition(job.job_id, job.fencing_token, "PAUSED", checkpoint_json={"stage": "calling_model"})
                return

            # 3. Monta prompt conforme template §4 (sem credenciais, com <dados>)
            channel = auth_ctx["channel"]
            display_name = channel_agent.get("display_name") or spec.display_name
            authorized_inputs = {
                "handoffs": auth_ctx["handoffs"],
                "prior_outputs": auth_ctx["prior_outputs"],
                "metrics": auth_ctx["metrics"],
                "references": auth_ctx["references"],
                "studio_outliers": auth_ctx["studio_outliers"],
                "google_trends": auth_ctx["google_trends"],
                "knowledge_chunks": auth_ctx["knowledge_chunks"],
                "production_intents": auth_ctx["production_intents"],
                "calendar_items": auth_ctx["calendar_items"],
            }
            prompt = build_agent_prompt(
                agent_display_name=display_name,
                agent_key=agent_key,
                channel_name=channel["display_name"],
                agent_responsibility=spec.responsibility,
                profile=channel,
                content_item_working_title=(auth_ctx.get("content_item") or {}).get("working_title"),
                authorized_inputs=authorized_inputs,
                output_type=spec.output_type,
                contract_version=spec.contract_version,
                output_json_schema=spec.payload_model.model_json_schema(),
            )
            input_hash = _json_hash(authorized_inputs)

            # 4. Chama modelo + valida contra contrato v1 com 1 tentativa de reparo
            caller_meta = {
                "agent_key": agent_key,
                "output_type": spec.output_type,
                "contract_version": spec.contract_version,
                "attempt": 1,
                "repair_error": None,
            }
            used_provider = "local"
            used_model_id = self._ai_router.policy.local_model_id

            def _invoke_model(prompt_txt: str, meta_obj: dict[str, Any]) -> dict[str, Any]:
                nonlocal used_provider, used_model_id
                ctx.heartbeat()
                if use_omniroute:
                    try:
                        out_ai, mdl = self._synthesize_pesquisa_with_omniroute(
                            auth_ctx,
                            repair_error=meta_obj.get("repair_error"),
                        )
                        ctx.heartbeat()
                        used_provider = "external"
                        used_model_id = mdl
                        return out_ai
                    except Exception as exc:
                        ctx.heartbeat()
                        warns = list(auth_ctx.get("research_warnings") or [])
                        warns.append(f"OmniRoute indisponivel; sintese feita localmente ({redact_sensitive_text(str(exc))[:110]}).")
                        auth_ctx["research_warnings"] = warns
                used_provider = "local" if policy_mode == "local_only" else "external"
                used_model_id = (
                    self._ai_router.policy.local_model_id
                    if policy_mode == "local_only"
                    else self._ai_router.policy.external_model_id
                )
                return self._model_caller(prompt_txt, auth_ctx, meta_obj)

            raw_output = _invoke_model(prompt, caller_meta)
            validation_err: str | None = None
            envelope = None
            validated_payload = None
            for attempt_idx in (1, 2):
                try:
                    envelope, validated_payload = validate_agent_output_envelope(
                        raw_output,
                        expected_agent_key=agent_key,
                        expected_output_type=spec.output_type,
                        expected_channel_id=channel_id,
                        expected_content_item_id=content_item_id,
                        expected_contract_version=spec.contract_version,
                    )
                    validation_err = None
                    break
                except Exception as exc:
                    validation_err = redact_sensitive_text(str(exc))
                    if attempt_idx == 1:
                        repair_meta = {**caller_meta, "attempt": 2, "repair_error": validation_err}
                        repair_prompt = f"{prompt}\n\nCORRECAO OBRIGATORIA DE SCHEMA: {validation_err}"
                        raw_output = _invoke_model(repair_prompt, repair_meta)

            if validation_err is not None or envelope is None or validated_payload is None:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    f"Output do agente invalido apos tentativa de reparo: {validation_err}",
                    http_status=422,
                    retryable=False,
                )

            self._repo.update_run_progress(
                run_id,
                job.fencing_token,
                stage_label="validando fontes e regras",
                progress=0.80,
                summary="Validando fontes, originalidade e politicas",
            )
            if self._step_delay > 0:
                time.sleep(self._step_delay)
            sig = ctx.checkpoint("validate", 3, {"stage": "validating_rules"}, "Validando regras de negocio")
            if sig == "cancel":
                self._repo.cancel_agent_run(workspace_id, run_id)
                return
            if sig == "pause":
                ctx._queue.transition(job.job_id, job.fencing_token, "PAUSED", checkpoint_json={"stage": "validating_rules"})
                return

            # 5. Regras de negocio §3 (escopo de fontes, similaridade, temas proibidos)
            raw_sources = [s.model_dump() for s in envelope.sources]
            valid_sources, invalid_sources = self._repo.verify_sources_in_scope(workspace_id, channel_id, raw_sources)
            review_reasons: list[str] = []
            if invalid_sources:
                review_reasons.append(f"fontes_fora_de_escopo:{len(invalid_sources)}")

            if not valid_sources and not spec.source_optional:
                review_reasons.append("sem_fontes_minimas")

            # Similaridade em titulos e capas
            originality_score: float | None = None
            payload_dict = validated_payload.model_dump(by_alias=True)
            if agent_key == "titulos":
                sims = [float(opt.get("similarity", 0.0)) for opt in payload_dict.get("options", [])]
                max_sim = max(sims) if sims else 0.0
                originality_score = round(max(0.0, 1.0 - max_sim), 4)
                if max_sim >= TITLE_SIMILARITY_REVIEW_THRESHOLD:
                    review_reasons.append(f"similaridade_alta:{max_sim:.2f}")
            elif agent_key == "thumbnail":
                flagged = any(bool(c.get("similarity_flag")) for c in payload_dict.get("concepts", []))
                originality_score = 0.35 if flagged else 0.90
                if flagged:
                    review_reasons.append("similaridade_capa_sinalizada")

            # Temas proibidos
            forbidden = _extract_forbidden_topics(channel)
            if forbidden:
                text_blob = json.dumps(payload_dict, ensure_ascii=False).lower()
                matched_forbidden = [t for t in forbidden if t in text_blob]
                if matched_forbidden:
                    review_reasons.append(f"tema_proibido:{','.join(matched_forbidden)}")

            output_status = "needs_review" if review_reasons else "validated"
            validation_info = {
                "valid": len(review_reasons) == 0,
                "review_reasons": review_reasons,
                "invalid_sources_removed": len(invalid_sources),
                "warnings": envelope.limitations,
            }

            content_to_store = {
                "summary": redact_sensitive_text(envelope.summary),
                "confidence": envelope.confidence,
                "limitations": [redact_sensitive_text(l) for l in envelope.limitations],
                **payload_dict,
            }

            # 6. Persistencia atomica com fencing token
            self._repo.commit_agent_run_atomic(
                run_id=run_id,
                job_id=job.job_id,
                fencing_token=job.fencing_token,
                workspace_id=workspace_id,
                channel_id=channel_id,
                agent_key=agent_key,
                content_item_id=content_item_id,
                output_type=spec.output_type,
                schema_version=spec.contract_version,
                summary=redact_sensitive_text(envelope.summary),
                content_json=content_to_store,
                valid_sources=valid_sources,
                output_status=output_status,
                validation_info=validation_info,
                originality_score=originality_score,
                input_hash=input_hash,
                model_id=used_model_id,
                provider=used_provider,
                cost_estimate_cents=0,
                actor_id=UUID(str(channel.get("created_by"))),
            )
        except AppError as err:
            if err.code == ErrorCode.FENCING_TOKEN_STALE:
                raise
            is_blocked = err.code in (
                ErrorCode.SUPABASE_UNAVAILABLE,
                ErrorCode.YOUTUBE_QUOTA_EXCEEDED,
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                ErrorCode.AI_EXTERNAL_CONSENT_REQUIRED,
                ErrorCode.DARKFORGE_UNAVAILABLE,
                ErrorCode.STUDIO_AUTH_REQUIRED,
                ErrorCode.STUDIO_RATE_LIMITED,
            )
            self._repo.fail_or_block_run_atomic(
                run_id=run_id,
                job_id=job.job_id,
                fencing_token=job.fencing_token,
                workspace_id=workspace_id,
                target_status="blocked" if is_blocked else "failed",
                error_code=err.code.value,
                error_message=redact_sensitive_text(err.message),
                retryable=err.retryable,
            )
            # Evita dupla transicao no JobWorker pois ja transitamos atomicamente
            return
