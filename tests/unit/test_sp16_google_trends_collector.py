from __future__ import annotations

import json

from adapters.google_trends.collector import (
    build_trends_explore_url,
    parse_trends_multiline_json,
    parse_trends_related_json,
)
from adapters.google_trends.csv_importer import parse_related_queries_csv, parse_timeline_csv


def test_parse_google_trends_xssi_json_responses() -> None:
    url = build_trends_explore_url("canal dark", date_range="today 5-y", geo="BR", gprop="youtube")
    assert "geo=BR" in url and "gprop=youtube" in url and "today+5-y" in url

    multiline_raw = ")]}',\n" + json.dumps(
        {
            "default": {
                "timelineData": [
                    {"time": "1735689600", "formattedTime": "Jan 2025", "formattedAxisTime": "2025-01-01", "value": [42]},
                    {"time": "1738368000", "formattedTime": "Feb 2025", "formattedAxisTime": "2025-02-01", "value": [78]},
                ]
            }
        }
    )
    pts = parse_trends_multiline_json(multiline_raw)
    assert len(pts) == 2
    assert pts[0].value == 42.0
    assert pts[1].timestamp_sec == 1738368000

    related_raw = ")]}',\n" + json.dumps(
        {
            "default": {
                "rankedList": [
                    {"rankedKeyword": [{"query": "canal dark historia", "value": 100, "formattedValue": "100"}]},
                    {
                        "rankedKeyword": [
                            {"query": "canal dark ia 2026", "value": 6500, "formattedValue": "Aumento repentino"},
                            {"query": "roteiro documental", "value": 240, "formattedValue": "+240%"},
                        ]
                    },
                ]
            }
        }
    )
    queries = parse_trends_related_json(related_raw)
    assert len(queries) == 3
    bo = [q for q in queries if q.growth_type == "breakout"]
    assert len(bo) == 1 and bo[0].term == "canal dark ia 2026"
    assert any(q.growth_type == "rising" and q.term == "roteiro documental" for q in queries)


def test_parse_google_trends_csv_exports_ptbr_and_en() -> None:
    timeline_csv = (
        "Categoria: Todas as categorias\n\n"
        "Semana,canal dark: (Brasil)\n"
        "2026-01-04,<1\n"
        "2026-01-11,55\n"
        "2026-01-18,88\n"
    )
    pts = parse_timeline_csv(timeline_csv)
    assert [p.value for p in pts] == [0.5, 55.0, 88.0]

    related_csv = (
        "Categoria: Todas\n\n"
        "Principais\n"
        "canal dark youtube,100\n\n"
        "Em ascensão\n"
        "canal dark historico ia,Mais de 5.000%\n"
        "edicao canal dark,+180%\n"
    )
    queries = parse_related_queries_csv(related_csv)
    assert len(queries) == 3
    assert any(q.term == "canal dark historico ia" and q.growth_type == "breakout" for q in queries)
    assert any(q.term == "edicao canal dark" and q.growth_type == "rising" for q in queries)
