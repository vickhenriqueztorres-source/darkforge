from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChannelVideoRecord:
    external_video_id: str
    external_channel_id: str
    channel_name: str
    title: str
    views: int
    days_since_upload: int
    duration_seconds: int | None = None
    topic: str = ""
    format_name: str = "long"
    thumbnail_url: str = ""
    published_at_iso: str = ""
    is_breaking_news: bool = False
    has_celebrity_collab: bool = False
    channel_authority_only: bool = False
    in_suggested_feed: bool = False


@dataclass(frozen=True)
class ViralOutlierResult:
    video: ChannelVideoRecord
    channel_mean_views: float
    sample_size: int
    outlier_ratio: float
    views_per_day: float
    is_recent_window_90d: bool
    is_false_positive: bool
    false_positive_reasons: list[str]
    priority_score: float


@dataclass(frozen=True)
class MultiChannelPattern:
    pattern_key: str
    distinct_channels: list[str]
    outliers: list[ViralOutlierResult]
    confirmed_pattern: bool


_NEWS_RE = re.compile(r"\b(urgente|plantao|breaking news|ao vivo agora|ultima hora|hoje)\b", re.IGNORECASE)


def normalize_pattern_key(topic: str, format_name: str) -> str:
    tokens = sorted(set(re.findall(r"[a-z0-9]{3,}", topic.lower())))[:4]
    return f"{'_'.join(tokens) or 'geral'}::{format_name.lower()}"


def compute_channel_20_30_mean(videos: list[ChannelVideoRecord]) -> tuple[float, int, str | None]:
    """
    Fase 2.1 — Media do canal baseada nos ultimos 20 a 30 videos:
    Media = sum(views) / count.
    """
    sample = videos[:30]
    if not sample:
        return 0.0, 0, "Sem videos para calcular linha de base."
    mean_val = sum(max(0, v.views) for v in sample) / len(sample)
    warn = None if len(sample) >= 20 else f"Amostra reduzida ({len(sample)} videos; ideal 20-30)."
    return round(mean_val, 2), len(sample), warn


def isolate_channel_outliers(
    channel_videos: list[ChannelVideoRecord],
    *,
    small_niche: bool = False,
    max_per_channel: int = 5,
    recent_window_days: int = 90,
) -> dict[str, object]:
    """
    Fase 2.2, 2.3 & 2.4:
    - Isola 3 a 5 outliers (>= 3x media, ou >= 2x em nichos menores).
    - Calcula velocidade (views / dias desde upload), priorizando 30-90d e Sugeridos.
    - Descarta falsos positivos (noticia passageira, collab celebridade, autoridade pura).
    """
    mean_views, sample_size, baseline_warning = compute_channel_20_30_mean(channel_videos)
    min_mult = 2.0 if small_niche else 3.0

    accepted: list[ViralOutlierResult] = []
    discarded_fp: list[ViralOutlierResult] = []

    for v in channel_videos:
        if mean_views <= 0:
            continue
        ratio = round(v.views / mean_views, 2)
        if ratio < min_mult:
            continue

        fp_reasons: list[str] = []
        if v.is_breaking_news or _NEWS_RE.search(v.title):
            fp_reasons.append("breaking_news_efemera")
        if v.has_celebrity_collab:
            fp_reasons.append("celebrity_collab")
        if v.channel_authority_only:
            fp_reasons.append("channel_authority_only")

        days = max(1, v.days_since_upload)
        vpd = round(v.views / days, 2)
        recent_flag = days <= recent_window_days
        prio = round(
            ratio * 10.0
            + min(50.0, vpd / 500.0)
            + (20.0 if recent_flag else 0.0)
            + (15.0 if v.in_suggested_feed else 0.0),
            2,
        )
        res = ViralOutlierResult(
            video=v,
            channel_mean_views=mean_views,
            sample_size=sample_size,
            outlier_ratio=ratio,
            views_per_day=vpd,
            is_recent_window_90d=recent_flag,
            is_false_positive=bool(fp_reasons),
            false_positive_reasons=fp_reasons,
            priority_score=prio,
        )
        if fp_reasons:
            discarded_fp.append(res)
        else:
            accepted.append(res)

    accepted.sort(key=lambda r: r.priority_score, reverse=True)
    return {
        "channel_mean_views": mean_views,
        "sample_size": sample_size,
        "baseline_warning": baseline_warning,
        "min_multiplier_used": min_mult,
        "outliers": accepted[:max_per_channel],
        "discarded_false_positives": discarded_fp,
    }


def detect_multi_channel_patterns(outliers: list[ViralOutlierResult]) -> dict[str, object]:
    """
    Fase 2.4 — Padrao vs Coincidencia:
    So avanca se o mesmo mecanismo tema+formato se repetir em >= 2 canais distintos.
    """
    grouped: dict[str, list[ViralOutlierResult]] = defaultdict(list)
    for item in outliers:
        if item.is_false_positive:
            continue
        topic_src = item.video.topic or item.video.title
        key = normalize_pattern_key(topic_src, item.video.format_name)
        grouped[key].append(item)

    confirmed: list[MultiChannelPattern] = []
    single_channel_coincidences: list[MultiChannelPattern] = []
    for key, items in grouped.items():
        channels = sorted({i.video.external_channel_id for i in items})
        pat = MultiChannelPattern(
            pattern_key=key,
            distinct_channels=channels,
            outliers=sorted(items, key=lambda x: x.priority_score, reverse=True),
            confirmed_pattern=len(channels) >= 2,
        )
        if pat.confirmed_pattern:
            confirmed.append(pat)
        else:
            single_channel_coincidences.append(pat)

    return {
        "confirmed_patterns": confirmed,
        "discarded_single_channel": single_channel_coincidences,
    }
