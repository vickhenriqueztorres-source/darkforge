from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from core.research.google_trends_models import (
    Durability5y,
    GoogleTrendsReport,
    SustainabilityVerdict,
    TrendDirection12m,
    TrendsQueryItem,
    TrendsSeriesPoint,
)

_YM_RE = re.compile(r"(\d{4})-(\d{2})")


def _parse_year_month(pt: TrendsSeriesPoint) -> tuple[int, int] | None:
    m = _YM_RE.search(pt.date_label)
    if m:
        return int(m.group(1)), int(m.group(2))
    if pt.timestamp_sec is not None:
        dt = datetime.fromtimestamp(pt.timestamp_sec, tz=timezone.utc)
        return dt.year, dt.month
    return None


def analyze_12m_momentum(points_12m: list[TrendsSeriesPoint]) -> tuple[TrendDirection12m, float, float, float]:
    """Analyzes 12-month search momentum: compares last ~25% window vs prior 75% + linear slope."""
    if len(points_12m) < 6:
        return TrendDirection12m.INSUFFICIENT, 0.0, 0.0, 0.0

    vals = [max(0.0, float(p.value)) for p in points_12m]
    split = max(3, int(len(vals) * 0.25))
    prior = vals[:-split]
    recent = vals[-split:]
    prior_avg = sum(prior) / max(1, len(prior))
    recent_avg = sum(recent) / max(1, len(recent))

    # Linear slope across points
    n = len(vals)
    x_mean = (n - 1) / 2.0
    y_mean = sum(vals) / n
    num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n)) or 1.0
    slope = round(num / den, 4)

    if recent_avg < 5.0 and prior_avg < 5.0:
        return TrendDirection12m.DECLINING, round(recent_avg, 2), round(prior_avg, 2), slope

    delta = (recent_avg - prior_avg) / max(1.0, prior_avg)
    if delta >= 0.15 or (slope > 0.35 and recent_avg >= prior_avg):
        direction = TrendDirection12m.RISING
    elif delta <= -0.25 and recent_avg < 60.0:
        direction = TrendDirection12m.DECLINING
    else:
        direction = TrendDirection12m.STABLE

    return direction, round(recent_avg, 2), round(prior_avg, 2), slope


def classify_5y_durability(points_5y: list[TrendsSeriesPoint]) -> tuple[Durability5y, list[int], float]:
    """Separates Evergreen vs Seasonal vs One-Off Dead Spike across a 5-year series."""
    if len(points_5y) < 12:
        return Durability5y.INSUFFICIENT, [], 0.0

    vals = [max(0.0, float(p.value)) for p in points_5y]
    peak = max(vals)
    if peak <= 0.0:
        return Durability5y.ONE_OFF_SPIKE, [], 100.0

    mean_all = sum(vals) / len(vals)
    tail_len = max(3, int(len(vals) * 0.15))
    recent_avg = sum(vals[-tail_len:]) / tail_len
    recent_ratio = recent_avg / peak
    peak_decay_pct = round(max(0.0, (1.0 - recent_ratio) * 100.0), 2)
    active_ratio = sum(1 for v in vals if v >= 0.20 * peak) / len(vals)

    # Detect recurring seasonal months across distinct years
    by_month_years: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for pt, val in zip(points_5y, vals):
        ym = _parse_year_month(pt)
        if ym is not None:
            by_month_years[ym[1]].append((ym[0], val))

    seasonal_months: list[int] = []
    for m, pairs in sorted(by_month_years.items()):
        years_high = {y for y, v in pairs if v >= max(25.0, 1.35 * mean_all)}
        if len(years_high) >= 2:
            seasonal_months.append(m)

    if seasonal_months and active_ratio < 0.72:
        return Durability5y.SEASONAL, seasonal_months, peak_decay_pct

    if active_ratio < 0.25 and recent_ratio < 0.20:
        return Durability5y.ONE_OFF_SPIKE, [], peak_decay_pct

    if active_ratio >= 0.35 or recent_ratio >= 0.30:
        return Durability5y.EVERGREEN, seasonal_months, peak_decay_pct

    if recent_ratio < 0.15:
        return Durability5y.ONE_OFF_SPIKE, [], peak_decay_pct
    return Durability5y.SEASONAL if seasonal_months else Durability5y.EVERGREEN, seasonal_months, peak_decay_pct


def split_related_queries(
    items: list[TrendsQueryItem],
) -> tuple[list[TrendsQueryItem], list[TrendsQueryItem], list[TrendsQueryItem]]:
    top_q: list[TrendsQueryItem] = []
    rising_q: list[TrendsQueryItem] = []
    breakout_q: list[TrendsQueryItem] = []
    seen: set[tuple[str, str]] = set()

    for q in items:
        clean = q.term.strip()
        if not clean:
            continue
        key = (clean.lower(), q.growth_type)
        if key in seen:
            continue
        seen.add(key)
        is_breakout = (
            q.growth_type == "breakout"
            or "breakout" in q.raw_label.lower()
            or "5.000%" in q.raw_label.lower()
            or "5,000%" in q.raw_label.lower()
            or (q.growth_pct is not None and q.growth_pct >= 5000.0)
        )
        if is_breakout:
            breakout_q.append(TrendsQueryItem(term=clean, growth_type="breakout", growth_pct=q.growth_pct or 5000.0, raw_label=q.raw_label or "Breakout (>5000%)"))
        elif q.growth_type == "rising":
            rising_q.append(q)
        else:
            top_q.append(q)

    return top_q, rising_q, breakout_q


def evaluate_topic_sustainability(
    *,
    keyword: str,
    geo: str,
    gprop: str,
    points_12m: list[TrendsSeriesPoint],
    points_5y: list[TrendsSeriesPoint],
    related_queries: list[TrendsQueryItem],
) -> GoogleTrendsReport:
    """Combines 12m momentum, 5y durability, regional relevance & Breakout signals into a final verdict."""
    dir_12m, rec_avg, base_avg, slope = analyze_12m_momentum(points_12m)
    dur_5y, seasonal_months, peak_decay = classify_5y_durability(points_5y)
    top_q, rising_q, breakout_q = split_related_queries(related_queries)

    limitations: list[str] = []
    if dir_12m == TrendDirection12m.INSUFFICIENT:
        limitations.append("Serie de 12 meses com menos de 6 pontos para calcular momentum.")
    if dur_5y == Durability5y.INSUFFICIENT:
        limitations.append("Serie de 5 anos com menos de 12 pontos para separar demanda perene/sazonal/pico.")
    if not rising_q and not breakout_q:
        limitations.append("Nenhuma consulta em ascensao (Rising/Breakout) retornada para a regiao.")

    if dir_12m == TrendDirection12m.INSUFFICIENT and dur_5y == Durability5y.INSUFFICIENT:
        verdict = SustainabilityVerdict.INSUFFICIENT_DATA
        confidence = 0.25
        summary = f"Dados insuficientes do Google Trends para '{keyword}' ({geo or 'GLOBAL'})."
    elif dur_5y == Durability5y.ONE_OFF_SPIKE or (dir_12m == TrendDirection12m.DECLINING and peak_decay >= 75.0):
        verdict = SustainabilityVerdict.AVOID_DEAD_PEAK
        confidence = 0.85
        summary = (
            f"Pico isolado ou queda severa pós-pico ({peak_decay:.0f}% abaixo do topo em 5a). "
            f"Evitar investir producao neste tema como demanda continua."
        )
    elif dur_5y == Durability5y.SEASONAL:
        verdict = SustainabilityVerdict.SEASONAL_TIMING
        confidence = 0.80
        months_str = ", ".join(str(m) for m in seasonal_months) or "recorrente"
        summary = f"Demanda sazonal identificada em 5 anos (meses de pico: {months_str}); alinhar calendario editorial."
    elif dir_12m == TrendDirection12m.DECLINING:
        verdict = SustainabilityVerdict.CAUTION_DECLINING
        confidence = 0.72
        summary = f"Tendencia de queda nos ultimos 12 meses (media recente {rec_avg:.1f} vs {base_avg:.1f}), apesar de base em 5 anos."
    else:
        verdict = SustainabilityVerdict.SUSTAINABLE_GO
        confidence = 0.88 if breakout_q or dir_12m == TrendDirection12m.RISING else 0.78
        summary = (
            f"Demanda sustentavel ({dur_5y.value}, 12m={dir_12m.value}) em {geo or 'GLOBAL'} "
            f"com {len(breakout_q)} queries Breakout e {len(rising_q)} Rising."
        )

    return GoogleTrendsReport(
        keyword=keyword.strip(),
        geo=geo.strip().upper() or "GLOBAL",
        gprop=gprop.strip() or "youtube",
        direction_12m=dir_12m,
        recent_avg_12m=rec_avg,
        baseline_avg_12m=base_avg,
        slope_12m=slope,
        durability_5y=dur_5y,
        peak_decay_pct=peak_decay,
        seasonal_months=seasonal_months,
        verdict=verdict,
        confidence=confidence,
        summary=summary,
        points_12m=points_12m,
        points_5y=points_5y,
        top_queries=top_q,
        rising_queries=rising_q,
        breakout_queries=breakout_q,
        limitations=limitations,
    )
