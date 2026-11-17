from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TrendDirection12m(StrEnum):
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT = "insufficient"


class Durability5y(StrEnum):
    EVERGREEN = "evergreen"
    SEASONAL = "seasonal"
    ONE_OFF_SPIKE = "one_off_spike"
    INSUFFICIENT = "insufficient"


class SustainabilityVerdict(StrEnum):
    SUSTAINABLE_GO = "SUSTAINABLE_GO"
    SEASONAL_TIMING = "SEASONAL_TIMING"
    CAUTION_DECLINING = "CAUTION_DECLINING"
    AVOID_DEAD_PEAK = "AVOID_DEAD_PEAK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class TrendsSeriesPoint:
    date_label: str
    value: float
    timestamp_sec: int | None = None


@dataclass(frozen=True)
class TrendsQueryItem:
    term: str
    growth_type: str  # 'top' | 'rising' | 'breakout'
    growth_pct: float | None = None
    raw_label: str = ""


@dataclass(frozen=True)
class GoogleTrendsReport:
    keyword: str
    geo: str
    gprop: str
    direction_12m: TrendDirection12m
    recent_avg_12m: float
    baseline_avg_12m: float
    slope_12m: float
    durability_5y: Durability5y
    peak_decay_pct: float
    seasonal_months: list[int]
    verdict: SustainabilityVerdict
    confidence: float
    summary: str
    points_12m: list[TrendsSeriesPoint] = field(default_factory=list)
    points_5y: list[TrendsSeriesPoint] = field(default_factory=list)
    top_queries: list[TrendsQueryItem] = field(default_factory=list)
    rising_queries: list[TrendsQueryItem] = field(default_factory=list)
    breakout_queries: list[TrendsQueryItem] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
