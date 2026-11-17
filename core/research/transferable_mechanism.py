from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from core.generation.title_thumbnail import check_originality
from core.research.video_autopsy import VideoAutopsyReport


@dataclass(frozen=True)
class ExtractedMechanismFormula:
    dominant_archetype: str
    dominant_emotion: str
    dominant_tension: str
    dominant_skeleton: str
    average_middle_blocks: int
    recurring_comment_gaps: list[str]
    reference_titles: list[str]
    autopsies_analyzed: int
    sample_warning: str | None


@dataclass(frozen=True)
class SynthesizedEpisodeConcept:
    formula_theme: str
    formula_angle: str
    formula_emotion: str
    formula_structure: str
    formula_format: str
    synthesized_title: str
    synthesized_thumb_concept: str
    synthesized_outline: list[dict[str, Any]]
    filled_comment_gaps: list[str]
    originality_max_similarity: float
    originality_blocked: bool


def extract_transferable_mechanism(autopsies: list[VideoAutopsyReport]) -> ExtractedMechanismFormula:
    """
    Fase 4.1 — Cruza 10 a 20 autopsias de outliers de canais diferentes para extrair
    o Mecanismo Transferivel comum sem copiar texto/identidade.
    """
    if not autopsies:
        raise ValueError("Pelo menos 1 autopsia obrigatoria para extrair mecanismo.")

    archetypes = Counter(a.detected_narrative_archetype for a in autopsies)
    emotions = Counter(a.package.thumbnail_emotion for a in autopsies)
    tensions = Counter(a.package.central_tension_or_risk for a in autopsies)
    skeletons = Counter(a.package.syntactic_skeleton for a in autopsies)
    avg_blocks = max(3, round(sum(max(1, len(a.script_retention.middle_blocks)) for a in autopsies) / len(autopsies)))

    gaps: list[str] = []
    seen_gaps: set[str] = set()
    for a in autopsies:
        for g in a.comments.top_audience_gaps:
            k = g.lower().strip()
            if k and k not in seen_gaps:
                seen_gaps.add(k)
                gaps.append(g)

    warning = None
    if len(autopsies) < 10:
        warning = f"Foram analisadas {len(autopsies)} autopsias (recomendado cruzar 10 a 20 outliers de canais distintos)."

    return ExtractedMechanismFormula(
        dominant_archetype=archetypes.most_common(1)[0][0],
        dominant_emotion=emotions.most_common(1)[0][0],
        dominant_tension=tensions.most_common(1)[0][0],
        dominant_skeleton=skeletons.most_common(1)[0][0],
        average_middle_blocks=avg_blocks,
        recurring_comment_gaps=gaps[:8],
        reference_titles=[a.package.original_title for a in autopsies],
        autopsies_analyzed=len(autopsies),
        sample_warning=warning,
    )


def synthesize_original_episode_concept(
    mechanism: ExtractedMechanismFormula,
    *,
    own_validated_topic: str,
    new_angle: str,
    target_format: str = "long",
    reference_titles_extra: list[str] | None = None,
) -> SynthesizedEpisodeConcept:
    """
    Fase 4.2 — Aplica Tema + Angulo + Emocao + Estrutura + Formato = Mecanismo Transferivel,
    criando titulo, conceito de capa e blocos de roteiro 100% ineditos e auditados por ORIG-001.
    """
    topic = own_validated_topic.strip()
    angle = new_angle.strip()
    arch = mechanism.dominant_archetype

    if arch.startswith("documentario_climax_invertido"):
        cand_title = f"{topic}: o colapso oculto por tras de {angle}"
        structure_label = "Climax inicial -> Regressao causal -> Provas -> Virada -> Consequencia"
        outline = [
            {"window": "00:00-00:15", "section": "Hook (Climax)", "notes": f"Abrir no momento critico de '{topic}' sem intro lenta, confirmando a capa."},
            {"window": "00:15-00:30", "section": "Conflito / Risco", "notes": f"Plantar o erro ou risco invisivel ligado a {angle} antes de dar contexto historico."},
            {"window": "00:30-03:00", "section": "Bloco 1 (Regressao)", "notes": "Voltar na origem com provas visuais e abrir primeiro open loop."},
            {"window": "03:00-07:00", "section": "Bloco 2 (Virada + Lacunas)", "notes": "Responder diretamente as lacunas deixadas nos comentarios concorrentes."},
            {"window": "07:00-fim", "section": "Fechamento", "notes": "Revelar a causa definitiva e conectar com o proximo episodio."},
        ]
    elif arch.startswith("cronologico_imersivo"):
        cand_title = f"Como funcionava '{topic}' sob a otica de {angle}"
        structure_label = "Linha cronologica 24h (Manha -> Tarde -> Noite) + Contraste com o presente"
        outline = [
            {"window": "00:00-00:15", "section": "Imersao 06:00", "notes": f"Primeira cena sensorial do cotidiano em '{topic}'."},
            {"window": "00:15-00:30", "section": "Contraste Imediato", "notes": f"Mostrar o choque de realidade usando o angulo: {angle}."},
            {"window": "00:30-05:00", "section": "Jornada Tarde/Noite", "notes": "Sequencia cronologica com viradas de rotina e provas visuais."},
            {"window": "05:00-fim", "section": "Sintese", "notes": "Fechar comparando com a vida atual e cobrindo duvidas dos comentarios."},
        ]
    elif arch.startswith("fraude_alerta"):
        cand_title = f"A engrenagem silenciosa em '{topic}' ({angle})"
        structure_label = "Vitima -> Metodo do esquema -> Escala -> Consequencia -> Prevencao"
        outline = [
            {"window": "00:00-00:15", "section": "Impacto Real", "notes": f"Apresentar o dano ou anomalia central de '{topic}' nos primeiros segundos."},
            {"window": "00:15-00:30", "section": "Promessa de Prevencao", "notes": f"Explicar por que o mecanismo de '{angle}' passa despercebido."},
            {"window": "00:30-06:00", "section": "Metodo e Escala", "notes": "Dissecar cada etapa do processo com evidencias publicas."},
            {"window": "06:00-fim", "section": "Consequencia e Licao", "notes": "Fechar com prevencao pratica e lacunas respondidas."},
        ]
    else:
        cand_title = f"O fator ignorado em '{topic}': {angle}"
        structure_label = "Hook paradoxico -> Risco -> Cadeia de evidencias -> Virada -> Conclusao"
        outline = [
            {"window": "00:00-00:15", "section": "Hook Paradoxico", "notes": f"Quebrar crenca comum sobre '{topic}'."},
            {"window": "00:15-00:30", "section": "Loop Aberto", "notes": f"Introduzir tensao central via '{angle}'."},
            {"window": "00:30-06:00", "section": "Blocos de Provas", "notes": "Alternar evidencia documental com novos open loops."},
        ]

    all_refs = list(dict.fromkeys(mechanism.reference_titles + list(reference_titles_extra or [])))
    orig = check_originality(cand_title, all_refs)
    thumb_concept = (
        f"Foco visual unico simbolizando '{topic}' com contraste forte e pergunta visual sobre '{angle}' "
        f"(emocao: {mechanism.dominant_emotion}; maximo 3 palavras complementares sem repetir o titulo)."
    )

    return SynthesizedEpisodeConcept(
        formula_theme=topic,
        formula_angle=angle,
        formula_emotion=mechanism.dominant_emotion,
        formula_structure=structure_label,
        formula_format=target_format,
        synthesized_title=cand_title,
        synthesized_thumb_concept=thumb_concept,
        synthesized_outline=outline,
        filled_comment_gaps=mechanism.recurring_comment_gaps[:5],
        originality_max_similarity=float(orig["max_similarity"]),
        originality_blocked=bool(orig["approval_blocked"]),
    )
