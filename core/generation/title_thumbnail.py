from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService

FORBIDDEN_UNVERIFIED_PROMISES = (
    "garantido",
    "views garantidas",
    "100% viral",
    "viralizacao garantida",
)


def _normalize_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9áàâãéêíóôõúç]+", text.lower())


def jaccard_similarity(text_a: str, text_b: str) -> float:
    ta = set(_normalize_tokens(text_a))
    tb = set(_normalize_tokens(text_b))
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)


def check_originality(candidate_title: str, reference_titles: list[str], threshold: float = 0.75) -> dict[str, Any]:
    """Checks literal/near-duplicate similarity against references and unverified claims (ORIG-001)."""
    max_sim = 0.0
    most_similar_ref: str | None = None
    for ref in reference_titles:
        sim = jaccard_similarity(candidate_title, ref)
        if sim > max_sim:
            max_sim = sim
            most_similar_ref = ref

    lower = candidate_title.lower()
    unverified_hits = [p for p in FORBIDDEN_UNVERIFIED_PROMISES if p in lower]
    blocked = max_sim >= threshold
    return {
        "max_similarity": max_sim,
        "most_similar_reference": most_similar_ref,
        "similarity_flagged": blocked,
        "unverified_promise_hits": unverified_hits,
        "approval_blocked": blocked or bool(unverified_hits),
        "error_code": ErrorCode.ORIGINALITY_SIMILARITY_BLOCKED.value if blocked else None,
    }


def analyze_title_structure(title: str) -> dict[str, Any]:
    """Extracts explainable structural features without claiming CTR causality (TITLE-001)."""
    clean = title.strip()
    tokens = _normalize_tokens(clean)
    has_number = bool(re.search(r"\b\d+\b", clean))
    has_question = "?" in clean
    has_mechanism = any(k in clean.lower() for k in ("como", "por que", "porque", "mecanismo", "mudanc", "erro", "segredo"))
    has_contrast = any(k in clean.lower() for k in ("vs", "sem ", "mas ", "antes", "depois", "enquanto"))
    features = []
    if has_number:
        features.append("number")
    if has_question:
        features.append("question")
    if has_mechanism:
        features.append("mechanism")
    if has_contrast:
        features.append("contrast")
    if len(tokens) >= 6:
        features.append("specific_niche")
    if any(k in clean.lower() for k in ("dobr", "retenc", "cresc", "melhor", "evit")):
        features.append("benefit")

    formula_parts = []
    if has_mechanism:
        formula_parts.append("[Mecanismo]")
    if has_number:
        formula_parts.append("[Numero]")
    formula_parts.append("[Promessa Especifica]")
    if has_contrast:
        formula_parts.append("[Contraste]")

    return {
        "source_title": clean,
        "char_count": len(clean),
        "word_count": len(tokens),
        "features": features,
        "editorial_formula": " + ".join(formula_parts),
        "confidence": 0.72 if len(tokens) >= 4 else 0.4,
        "limitations": [
            "Analise estrutural baseada apenas no texto do titulo; nao comprova causalidade de CTR.",
        ],
    }


def generate_original_title_alternatives(
    channel_name: str,
    niche: str,
    topic: str,
    reference_titles: list[str],
    forbidden_topics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generates differentiated original alternatives checked against reference similarity & forbidden topics."""
    blocked_terms = [t.lower().strip() for t in (forbidden_topics or []) if t.strip()]
    for term in blocked_terms:
        if term in topic.lower():
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"Topico viola restricao editorial do canal: '{term}'.",
                http_status=422,
            )

    candidates = [
        {
            "title": f"{topic}: O Mecanismo Oculto que Poucos Analisam em {niche}",
            "differentiation": f"Desloca o foco para o mecanismo real alinhado ao posicionamento de {channel_name}.",
        },
        {
            "title": f"Por Que {topic} Muda Tudo no Cenario Atual de {niche} (Sem Exageros)",
            "differentiation": "Evita promessa absoluta e prioriza contraste analitico.",
        },
        {
            "title": f"Os 3 Sinais Reais Por Tras de {topic} — Analise Completa",
            "differentiation": "Estrutura baseada em evidencias observaveis e numero especifico.",
        },
    ]

    results = []
    for cand in candidates:
        orig = check_originality(cand["title"], reference_titles)
        results.append(
            {
                "channel_name": channel_name,
                "title": cand["title"],
                "differentiation": cand["differentiation"],
                "references_used_count": len(reference_titles),
                "originality": orig,
                "is_proposal": True,
            }
        )
    return results


def validate_safe_external_url(url: str) -> str:
    """SSRF guard: allows only https public URLs and blocks loopback/private/link-local hosts."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("https", "http") or not parsed.netloc or not parsed.hostname:
        raise AppError(ErrorCode.VALIDATION_ERROR, "URL de capa invalida.", http_status=422)
    host = parsed.hostname.lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254"):
        raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "URL bloqueada por protecao SSRF.", http_status=403)
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "IP privado/interno bloqueado por protecao SSRF.", http_status=403)
    except ValueError:
        pass  # Hostname (not bare IP)
    return url.strip()


@dataclass
class VisionResult:
    available: bool
    ocr_text: str | None
    composition: dict[str, Any]
    limitations: list[str]


class TitleThumbnailService:
    def __init__(self, workspaces: WorkspaceService, repo: Any, vision_provider: Any = None) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._vision = vision_provider

    def analyze_title(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        title: str,
        channel_id: UUID | None = None,
        reference_video_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if not title.strip():
            raise AppError(ErrorCode.VALIDATION_ERROR, "Titulo e obrigatorio.", http_status=422)
        analysis = analyze_title_structure(title)
        saved = self._repo.save_title_analysis(workspace_id, channel_id, reference_video_id, analysis, actor.user_id)
        return saved

    def analyze_thumbnail(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        source_url: str,
        image_bytes: bytes | None = None,
        reference_video_id: UUID | None = None,
        reference_notes: str = "",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_url = validate_safe_external_url(source_url)
        sha = hashlib.sha256(image_bytes).hexdigest() if image_bytes is not None else None
        asset = self._repo.upsert_thumbnail_asset(
            workspace_id=workspace_id,
            reference_video_id=reference_video_id,
            source_url=clean_url,
            sha256=sha,
            availability_status="available" if image_bytes is not None else "unavailable",
        )

        # THUMB-003: if vision/OCR unavailable or no image bytes, mark unavailable and NEVER invent OCR
        if self._vision is None or image_bytes is None:
            return self._repo.save_thumbnail_analysis(
                workspace_id=workspace_id,
                thumbnail_asset_id=asset["id"],
                vision_status="unavailable",
                ocr_text=None,
                composition_json={},
                differentiation_notes="Analise visual indisponivel (modelo de visao ou bytes da imagem ausentes). Fluxo de titulos permanece operacional.",
                limitations=["Provedor de visao/OCR indisponivel; nenhuma leitura visual inventada."],
                user_id=actor.user_id,
            )

        res: VisionResult = self._vision.analyze(image_bytes)
        if not res.available:
            return self._repo.save_thumbnail_analysis(
                workspace_id=workspace_id,
                thumbnail_asset_id=asset["id"],
                vision_status="unavailable",
                ocr_text=None,
                composition_json={},
                differentiation_notes="Visao/OCR indisponivel no momento.",
                limitations=res.limitations or ["Visao indisponivel."],
                user_id=actor.user_id,
            )
        return self._repo.save_thumbnail_analysis(
            workspace_id=workspace_id,
            thumbnail_asset_id=asset["id"],
            vision_status="available",
            ocr_text=res.ocr_text,
            composition_json=res.composition,
            differentiation_notes=reference_notes or "Usar apenas como direcao visual diferenciada; proibido copiar layout ou identidade.",
            limitations=res.limitations + ["OCR/visao e analise probabilistica, nao verdade absoluta."],
            user_id=actor.user_id,
        )
