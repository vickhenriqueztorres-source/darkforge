from __future__ import annotations

from core.research.google_trends_analyzer import evaluate_topic_sustainability
from core.research.google_trends_models import (
    Durability5y,
    SustainabilityVerdict,
    TrendDirection12m,
    TrendsQueryItem,
    TrendsSeriesPoint,
)


def test_evergreen_rising_with_breakout_queries_returns_sustainable_go() -> None:
    pts_12m = [TrendsSeriesPoint(f"2026-{m:02d}-01", val) for m, val in enumerate([35, 38, 40, 42, 48, 52, 60, 65, 72, 80, 85, 92], start=1)]
    pts_5y = [TrendsSeriesPoint(f"{2022 + i // 12}-{(i % 12) + 1:02d}-01", 40.0 + (i % 6) * 4.0) for i in range(60)]
    queries = [
        TrendsQueryItem(term="tutorial completo canal dark", growth_type="top", raw_label="100"),
        TrendsQueryItem(term="narracao ia realista", growth_type="rising", growth_pct=350.0, raw_label="+350%"),
        TrendsQueryItem(term="agentic video workflow", growth_type="rising", raw_label="Mais de 5.000%"),
    ]
    report = evaluate_topic_sustainability(
        keyword="canal dark",
        geo="BR",
        gprop="youtube",
        points_12m=pts_12m,
        points_5y=pts_5y,
        related_queries=queries,
    )
    assert report.direction_12m == TrendDirection12m.RISING
    assert report.durability_5y == Durability5y.EVERGREEN
    assert report.verdict == SustainabilityVerdict.SUSTAINABLE_GO
    assert len(report.breakout_queries) == 1
    assert report.breakout_queries[0].term == "agentic video workflow"
    assert len(report.rising_queries) == 1


def test_one_off_dead_peak_flags_avoid_dead_peak() -> None:
    pts_12m = [TrendsSeriesPoint(f"2026-{m:02d}-01", val) for m, val in enumerate([80, 50, 25, 12, 8, 6, 4, 3, 2, 2, 1, 1], start=1)]
    # Single massive spike 2 years ago, flat near 2 afterwards
    vals_5y = [2.0] * 24 + [100.0, 85.0, 30.0] + [2.0] * 33
    pts_5y = [TrendsSeriesPoint(f"{2022 + i // 12}-{(i % 12) + 1:02d}-01", v) for i, v in enumerate(vals_5y)]

    report = evaluate_topic_sustainability(
        keyword="hype passageiro 2024",
        geo="BR",
        gprop="youtube",
        points_12m=pts_12m,
        points_5y=pts_5y,
        related_queries=[],
    )
    assert report.durability_5y == Durability5y.ONE_OFF_SPIKE
    assert report.verdict == SustainabilityVerdict.AVOID_DEAD_PEAK
    assert report.peak_decay_pct >= 90.0


def test_seasonal_recurring_months_detected_over_5_years() -> None:
    pts_12m = [TrendsSeriesPoint(f"2026-{m:02d}-01", 40.0 if m != 11 else 95.0) for m in range(1, 13)]
    vals_5y = []
    for y in range(2022, 2027):
        for m in range(1, 13):
            vals_5y.append(TrendsSeriesPoint(f"{y}-{m:02d}-01", 95.0 if m == 11 else 8.0))

    report = evaluate_topic_sustainability(
        keyword="black friday notebook",
        geo="BR",
        gprop="youtube",
        points_12m=pts_12m,
        points_5y=vals_5y,
        related_queries=[],
    )
    assert report.durability_5y == Durability5y.SEASONAL
    assert 11 in report.seasonal_months
    assert report.verdict == SustainabilityVerdict.SEASONAL_TIMING
    assert report.verdict != SustainabilityVerdict.INSUFFICIENT_DATA


def test_insufficient_data_returns_honest_verdict() -> None:
    report = evaluate_topic_sustainability(
        keyword="termo raro",
        geo="BR",
        gprop="youtube",
        points_12m=[],
        points_5y=[],
        related_queries=[],
    )
    assert report.verdict == SustainabilityVerdict.INSUFFICIENT_DATA
    assert report.confidence <= 0.30
    assert len(report.limitations) >= 2
