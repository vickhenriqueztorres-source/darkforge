from __future__ import annotations

import csv
import io
import re

from core.research.google_trends_models import TrendsQueryItem, TrendsSeriesPoint

_DATE_ROW_RE = re.compile(r"^\d{4}-\d{2}(?:-\d{2})?$")
_PCT_NUM_RE = re.compile(r"([0-9]+(?:[.,][0-9]+)?)")


def _parse_trend_value(raw: str) -> float:
    clean = raw.strip().lower()
    if clean in ("<1", "< 1"):
        return 0.5
    try:
        return float(clean.replace(",", "."))
    except ValueError:
        return 0.0


def parse_timeline_csv(csv_text: str) -> list[TrendsSeriesPoint]:
    """Parses official Google Trends multiTimeline.csv exports (EN & PT-BR)."""
    points: list[TrendsSeriesPoint] = []
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if len(row) < 2:
            continue
        dt_cell = row[0].strip()
        if not _DATE_ROW_RE.match(dt_cell):
            continue
        points.append(TrendsSeriesPoint(date_label=dt_cell, value=_parse_trend_value(row[1])))
    return points


def parse_related_queries_csv(csv_text: str) -> list[TrendsQueryItem]:
    """Parses official Google Trends relatedQueries.csv exports (TOP + RISING + Breakout)."""
    items: list[TrendsQueryItem] = []
    mode = "top"
    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if not row:
            continue
        joined = ",".join(row).strip().lower()
        if joined in ("top", "principais"):
            mode = "top"
            continue
        if joined in ("rising", "em ascensão", "em ascensao", "em aumento"):
            mode = "rising"
            continue
        if len(row) < 2:
            continue
        term = row[0].strip()
        val_raw = row[1].strip()
        if not term or term.lower() in ("query", "consulta"):
            continue
        lower_val = val_raw.lower()
        if mode == "rising" or "+" in val_raw or "breakout" in lower_val or "aumento repentino" in lower_val:
            is_breakout = "breakout" in lower_val or "aumento repentino" in lower_val or "5.000%" in lower_val or "5,000%" in lower_val
            m = _PCT_NUM_RE.search(val_raw.replace(".", "").replace(",", ""))
            pct = float(m.group(1)) if m else (5000.0 if is_breakout else None)
            if pct is not None and pct >= 5000.0:
                is_breakout = True
            items.append(
                TrendsQueryItem(
                    term=term,
                    growth_type="breakout" if is_breakout else "rising",
                    growth_pct=pct,
                    raw_label=val_raw,
                )
            )
        else:
            items.append(TrendsQueryItem(term=term, growth_type="top", raw_label=val_raw))
    return items
