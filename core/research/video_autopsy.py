from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ALLOWED_TO_MODEL = [
    "demanda_comprovada",
    "estrutura_narrativa",
    "mecanismo_de_clique_e_curiosidade",
    "ritmo_de_blocos_e_open_loops",
]

FORBIDDEN_TO_COPY = [
    "texto_exato_do_titulo",
    "composicao_identica_da_capa",
    "voz_identidade_visual_propria",
    "roteiro_ou_frases_literais",
]

_CURIOSITY_TRIGGERS = (
    "como",
    "por que",
    "porque",
    "segredo",
    "erro",
    "nunca",
    "ninguem",
    "farsa",
    "desapareceu",
    "verdade",
    "golpe",
    "hidden",
    "secret",
    "never",
    "why",
    "how",
    "mistake",
)
_OPEN_LOOP_RE = re.compile(r"\b(mas|porem|entretanto|so que|ate que|mal sabia|o problema|but|however|until|before)\b|\?", re.IGNORECASE)
_VISUAL_PROOF_RE = re.compile(r"\b(mapa|documento|foto|arquivo|grafico|print|camera|registro|prova|evidence|map|photo|chart)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PackageAutopsy:
    original_title: str
    syntactic_skeleton: str
    central_tension_or_risk: str
    curiosity_trigger_words: list[str]
    keywords_frontloaded: bool
    thumbnail_single_focus: str
    thumbnail_visual_question: str
    thumbnail_emotion: str
    thumbnail_text_complements_title: bool
    allowed_to_model: list[str] = field(default_factory=lambda: list(ALLOWED_TO_MODEL))
    forbidden_to_copy: list[str] = field(default_factory=lambda: list(FORBIDDEN_TO_COPY))


@dataclass(frozen=True)
class ScriptRetentionAutopsy:
    hook_0_15s_first_sentence: str
    hook_0_15s_first_visual: str
    hook_0_15s_confirms_promise_no_fluff: bool
    segment_15_30s_conflict_or_value: str
    segment_15_30s_planted_risk_before_context: bool
    middle_blocks: list[dict[str, Any]]
    open_loops_count: int
    tension_turns_count: int
    visual_proofs_count: int


@dataclass(frozen=True)
class CommentGapMining:
    unanswered_questions: list[str]
    missing_detail_complaints: list[str]
    sequel_requests: list[str]
    top_audience_gaps: list[str]


@dataclass(frozen=True)
class VideoAutopsyReport:
    external_video_id: str
    package: PackageAutopsy
    script_retention: ScriptRetentionAutopsy
    comments: CommentGapMining
    detected_narrative_archetype: str
    confidence: float


def _build_syntactic_skeleton(title: str) -> str:
    lower = title.strip()
    # Replace quoted/numeric specifics with structural placeholders so caller models the skeleton, never words
    skel = re.sub(r"\b\d+[.,]?\d*\b", "[NUMERO]", lower)
    if re.search(r"^(como|how)\b", skel, re.IGNORECASE):
        return "[Como/Metodo] + [Sujeito] + [Transformacao/Consequencia]"
    if re.search(r"^(por que|why|o golpe|a farsa)\b", skel, re.IGNORECASE):
        return "[Transgressao/Causa Oculta] + [Vitima/Sistema] + [Consequencia]"
    if "?" in skel:
        return "[Pergunta Aberta de Tensao] + [Risco/Implicacao]"
    return "[Objeto/Evento] + [Ruptura ou Virada Inesperada]"


def autopsy_package(
    *,
    title: str,
    thumbnail_focus: str = "",
    thumbnail_visual_question: str = "",
    thumbnail_emotion: str = "curiosidade",
    thumbnail_text: str = "",
) -> PackageAutopsy:
    clean = title.strip()
    words = [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]+", clean)]
    triggers = [t for t in _CURIOSITY_TRIGGERS if re.search(rf"\b{re.escape(t)}\b", clean.lower())]
    half = max(1, len(words) // 2)
    # Strong topic/noun words (>4 chars) appearing in first half count as frontloaded keywords
    first_half_content = [w for w in words[:half] if len(w) >= 4]
    keywords_frontloaded = len(first_half_content) >= 1

    if any(k in clean.lower() for k in ("desapareceu", "sumiu", "morto", "erro", "destruiu", "golpe", "enganou")):
        tension = "perda_ameaca_ou_colapso"
    elif triggers or "?" in clean:
        tension = "paradoxo_ou_curiosidade_aberta"
    else:
        tension = "promessa_de_descoberta_ou_transformacao"

    # Thumbnail text must complement title instead of repeating title verbatim
    t_tokens = {w.lower() for w in re.findall(r"[a-z0-9]{3,}", thumbnail_text)}
    title_tokens = {w.lower() for w in words if len(w) >= 3}
    overlap = len(t_tokens & title_tokens) / max(1, len(t_tokens)) if t_tokens else 0.0
    complements = overlap < 0.75

    return PackageAutopsy(
        original_title=clean,
        syntactic_skeleton=_build_syntactic_skeleton(clean),
        central_tension_or_risk=tension,
        curiosity_trigger_words=triggers,
        keywords_frontloaded=keywords_frontloaded,
        thumbnail_single_focus=thumbnail_focus or "Elemento central isolado com alto contraste",
        thumbnail_visual_question=thumbnail_visual_question or "O que aconteceu imediatamente antes ou depois desta cena?",
        thumbnail_emotion=thumbnail_emotion,
        thumbnail_text_complements_title=complements,
    )


def autopsy_script_and_retention(
    *,
    transcript_or_notes: str,
    first_visual_description: str = "",
    timed_blocks: list[dict[str, Any]] | None = None,
) -> ScriptRetentionAutopsy:
    raw = transcript_or_notes.strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", raw) if s.strip()]
    first_sentence = sentences[0] if sentences else ""
    fluff_markers = ("bem vindo ao canal", "inscreva-se antes", "ola pessoal tudo bem", "hey guys welcome")
    no_fluff = bool(first_sentence) and not any(m in first_sentence.lower() for m in fluff_markers)

    conflict_15_30 = sentences[1] if len(sentences) > 1 else (first_sentence or "")
    planted_risk = bool(_OPEN_LOOP_RE.search(conflict_15_30) or len(conflict_15_30) >= 20)

    blocks: list[dict[str, Any]] = []
    if timed_blocks:
        blocks = list(timed_blocks)
    else:
        # Partition body after first 2 sentences into structured narrative blocks
        body_sents = sentences[2:] if len(sentences) > 2 else sentences
        chunk_size = max(1, len(body_sents) // 3) if body_sents else 1
        for idx in range(0, max(1, len(body_sents)), chunk_size):
            part = " ".join(body_sents[idx : idx + chunk_size])
            if not part:
                continue
            loops = len(_OPEN_LOOP_RE.findall(part))
            proofs = len(_VISUAL_PROOF_RE.findall(part))
            blocks.append(
                {
                    "block_index": len(blocks) + 1,
                    "summary": part[:160],
                    "estimated_duration_sec": max(30, len(part.split()) // 2),
                    "open_loops": loops,
                    "visual_proofs": proofs,
                }
            )

    total_loops = sum(int(b.get("open_loops", 0)) for b in blocks) + len(_OPEN_LOOP_RE.findall(raw))
    total_turns = sum(1 for b in blocks if int(b.get("open_loops", 0)) > 0)
    total_proofs = sum(int(b.get("visual_proofs", 0)) for b in blocks) + len(_VISUAL_PROOF_RE.findall(raw))

    return ScriptRetentionAutopsy(
        hook_0_15s_first_sentence=first_sentence,
        hook_0_15s_first_visual=first_visual_description or "Cena de impacto / prova visual coerente com a capa",
        hook_0_15s_confirms_promise_no_fluff=no_fluff,
        segment_15_30s_conflict_or_value=conflict_15_30,
        segment_15_30s_planted_risk_before_context=planted_risk,
        middle_blocks=blocks,
        open_loops_count=total_loops,
        tension_turns_count=total_turns,
        visual_proofs_count=total_proofs,
    )


def mine_comment_gaps(comments: list[str]) -> CommentGapMining:
    questions: list[str] = []
    missing: list[str] = []
    sequels: list[str] = []

    for c in comments:
        txt = c.strip()
        if not txt:
            continue
        low = txt.lower()
        if any(k in low for k in ("faltou", "nao explicou", "não explicou", "cade", "cadê", "esqueceram", "missed", "forgot")):
            missing.append(txt[:200])
        elif any(k in low for k in ("parte 2", "part 2", "continuacao", "continuação", "faz um video sobre", "make a video on")):
            sequels.append(txt[:200])
        elif "?" in txt or any(low.startswith(p) for p in ("como ", "por que ", "porque ", "qual ", "why ", "how ")):
            questions.append(txt[:200])

    top_gaps = (missing[:4] + questions[:4] + sequels[:3])[:8]
    return CommentGapMining(
        unanswered_questions=questions[:10],
        missing_detail_complaints=missing[:10],
        sequel_requests=sequels[:10],
        top_audience_gaps=top_gaps,
    )


def infer_narrative_archetype(title: str, transcript_or_notes: str) -> str:
    combined = f"{title} {transcript_or_notes}".lower()
    if any(k in combined for k in ("golpe", "fraude", "enganou", "esquema", "vitima", "scam", "fraud")):
        return "fraude_alerta::vitima_metodo_escala_consequencia_prevencao"
    if any(k in combined for k in ("um dia comum", "amanhecer", "24 horas", "viagem no tempo", "anos atras", "day in the life")):
        return "cronologico_imersivo::manha_tarde_noite_contraste"
    if any(k in combined for k in ("desapareceu", "colapso", "climax", "noite", "ruina", "vanished", "collapse")):
        return "documentario_climax_invertido::abre_desastre_volta_causa"
    return "investigacao_causal::hook_tensao_provas_virada_revelacao"


def run_full_video_autopsy(
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
    timed_blocks: list[dict[str, Any]] | None = None,
) -> VideoAutopsyReport:
    pkg = autopsy_package(
        title=title,
        thumbnail_focus=thumbnail_focus,
        thumbnail_visual_question=thumbnail_visual_question,
        thumbnail_emotion=thumbnail_emotion,
        thumbnail_text=thumbnail_text,
    )
    scr = autopsy_script_and_retention(
        transcript_or_notes=transcript_or_notes,
        first_visual_description=first_visual_description,
        timed_blocks=timed_blocks,
    )
    cmt = mine_comment_gaps(comments)
    archetype = infer_narrative_archetype(title, transcript_or_notes)

    conf = 0.45
    if transcript_or_notes.strip():
        conf += 0.25
    if comments:
        conf += 0.20
    if thumbnail_focus or thumbnail_text:
        conf += 0.10

    return VideoAutopsyReport(
        external_video_id=external_video_id,
        package=pkg,
        script_retention=scr,
        comments=cmt,
        detected_narrative_archetype=archetype,
        confidence=round(min(0.98, conf), 2),
    )
