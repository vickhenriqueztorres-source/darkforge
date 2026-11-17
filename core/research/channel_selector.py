from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReferenceChannelCandidate:
    external_channel_id: str
    display_name: str
    language: str
    market_country: str
    recent_video_views_90d: list[int]  # Views of videos published in last 30-90 days
    all_recent_20_30_views: list[int]  # Baseline 20-30 videos
    production_format: str  # e.g. 'long_documentary', 'faceless_essay', 'studio_podcast'
    audience_profile_tags: list[str]
    is_celebrity_or_mega_brand: bool = False
    subscriber_count: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class TargetChannelFit:
    language: str
    market_country: str
    feasible_formats: list[str]
    target_audience_tags: list[str]
    min_outlier_ratio: float = 3.0


@dataclass(frozen=True)
class ChannelCriterionEvaluation:
    external_channel_id: str
    display_name: str
    approved: bool
    passed_criteria: list[str]
    failed_criteria: list[str]
    channel_mean_views: float
    outlier_hits_count: int
    max_outlier_ratio: float
    ranking_score: float
    warnings: list[str] = field(default_factory=list)


def evaluate_reference_channel(
    candidate: ReferenceChannelCandidate,
    target: TargetChannelFit,
) -> ChannelCriterionEvaluation:
    """
    Fase 1 — Filtro obrigatorio de 6 criterios para Canais de Referencia (SP-19).
    Prioriza canais com mediana/media normal e picos claros de explosao (outliers),
    descartando celebridades/marcas gigantes onde tudo tem alto volume sem variacao real.
    """
    passed: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []

    # 1. Mesmo mercado/idioma
    lang_ok = candidate.language.split("-")[0].lower() == target.language.split("-")[0].lower()
    if lang_ok:
        passed.append("same_market_language")
    else:
        failed.append("same_market_language")

    # Baseline mean of last 20-30 videos
    baseline_list = [max(0, v) for v in candidate.all_recent_20_30_views if isinstance(v, int)]
    mean_views = (sum(baseline_list) / len(baseline_list)) if baseline_list else 0.0

    # 2. Tracao recente (videos novos últimos 30-90 dias performando acima da base)
    recent_list = [max(0, v) for v in candidate.recent_video_views_90d if isinstance(v, int)]
    recent_threshold = max(1_000.0, mean_views * 1.2)
    recent_performing = [v for v in recent_list if v >= recent_threshold]
    if recent_performing:
        passed.append("recent_traction")
    else:
        failed.append("recent_traction")

    # 3. Consistência de acertos (> 1 video com tracao outlier; nao apenas 1 hit isolado por sorte)
    outlier_threshold = max(1_000.0, mean_views * target.min_outlier_ratio)
    outlier_hits = [v for v in baseline_list if mean_views > 0 and v >= outlier_threshold]
    if not outlier_hits and recent_list and mean_views > 0:
        outlier_hits = [v for v in recent_list if v >= outlier_threshold]
    max_ratio = round(max([v / mean_views for v in baseline_list], default=0.0), 2) if mean_views > 0 else 0.0
    if len(outlier_hits) >= 2:
        passed.append("repeat_hit_consistency")
    else:
        failed.append("repeat_hit_consistency")
        if len(outlier_hits) == 1:
            warnings.append("Canal possui apenas 1 hit isolado (possivel sorte unica).")

    # 4. Formato viavel
    feasible_set = {f.strip().lower() for f in target.feasible_formats}
    if candidate.production_format.strip().lower() in feasible_set:
        passed.append("feasible_format")
    else:
        failed.append("feasible_format")

    # 5. Mesma audiencia-alvo
    cand_tags = {t.strip().lower() for t in candidate.audience_profile_tags if t.strip()}
    targ_tags = {t.strip().lower() for t in target.target_audience_tags if t.strip()}
    if cand_tags & targ_tags:
        passed.append("target_audience_fit")
    else:
        failed.append("target_audience_fit")

    # 6. Independencia de fama (nao ser celebridade / marca gigante / canal onde tudo ja da 500k sem contraste)
    is_flat_mega = mean_views >= 250_000 and max_ratio < 2.2
    if not candidate.is_celebrity_or_mega_brand and not is_flat_mega:
        passed.append("fame_independence")
    else:
        failed.append("fame_independence")
        if is_flat_mega:
            warnings.append("Canal gigante com alta media e baixo contraste de outliers (peso de fama).")

    approved = len(failed) == 0
    # Ranking rewards high outlier contrast & repeatable hits rather than raw subscriber count
    ranking_score = round(
        (len(passed) * 15.0)
        + min(30.0, len(outlier_hits) * 6.0)
        + min(25.0, max_ratio * 2.5)
        - (40.0 if not approved else 0.0),
        2,
    )

    return ChannelCriterionEvaluation(
        external_channel_id=candidate.external_channel_id,
        display_name=candidate.display_name,
        approved=approved,
        passed_criteria=passed,
        failed_criteria=failed,
        channel_mean_views=round(mean_views, 2),
        outlier_hits_count=len(outlier_hits),
        max_outlier_ratio=max_ratio,
        ranking_score=ranking_score,
        warnings=warnings,
    )


def select_reference_channels(
    candidates: list[ReferenceChannelCandidate],
    target: TargetChannelFit,
    *,
    min_channels: int = 5,
    max_channels: int = 10,
) -> dict[str, object]:
    """Selects top 5-10 reference channels meeting all 6 criteria, flagging gaps if < min_channels."""
    evals = [evaluate_reference_channel(c, target) for c in candidates]
    approved = sorted([e for e in evals if e.approved], key=lambda x: x.ranking_score, reverse=True)[:max_channels]
    rejected = sorted([e for e in evals if not e.approved], key=lambda x: len(x.failed_criteria))
    return {
        "selected": approved,
        "rejected": rejected,
        "selected_count": len(approved),
        "meets_5_to_10_target": len(approved) >= min_channels,
        "recommendation": (
            f"{len(approved)} canais qualificados nos 6 criterios (meta {min_channels}-{max_channels})."
            if len(approved) >= min_channels
            else f"Apenas {len(approved)} canais passaram nos 6 criterios; busque pelo menos {min_channels} antes de avançar."
        ),
    }
