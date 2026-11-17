from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from adapters.studio_browser.trends_extractor import (
    _SHADOW_DOM_COLLECT_JS,
    parse_compact_int,
    parse_days_ago,
    parse_studio_dom_cards,
    parse_studio_network_payloads,
)
from core.research.studio_models import AudienceInterestLevel


def test_parse_studio_network_payloads_extracts_all_5_blocks() -> None:
    sample_json = [
        {
            "contents": {
                "topSearches": [
                    {"searchTerm": "como montar canal dark", "audienceInterestLevel": "Muito alto", "weeklyViewsGt1000": True},
                    {"searchTerm": "edicao automatica ia", "audienceInterestLevel": "Medium", "weeklyViewsGt1000": True},
                ],
                "contentGaps": [
                    {"query": "canal dark documentos historicos pt-br", "searchVolumeTier": "HIGH", "isContentGap": True},
                ],
                "videos": [
                    {
                        "videoId": "dQw4w9WgXcQ",
                        "title": {"simpleText": "O Arquivo Secreto de 1945"},
                        "channelId": "UCabc12345678",
                        "channelTitle": "Arquivos Ocultos",
                        "viewCountText": "240K",
                        "publishedTimeText": "6 dias atras",
                        "watchedByYourViewers": True,
                    }
                ],
            }
        }
    ]
    terms, videos = parse_studio_network_payloads(sample_json)
    assert len(terms) == 3
    gaps = [t for t in terms if t.block_type == "content_gap"]
    assert len(gaps) == 1
    assert gaps[0].is_hypothesis is True
    assert gaps[0].audience_interest == AudienceInterestLevel.HIGH

    very_high = [t for t in terms if t.term == "como montar canal dark"][0]
    assert very_high.audience_interest == AudienceInterestLevel.VERY_HIGH

    assert len(videos) == 1
    assert videos[0].external_video_id == "dQw4w9WgXcQ"
    assert videos[0].public_views == 240_000
    assert videos[0].published_days_ago == 6
    assert videos[0].watched_by_my_viewers is True


def test_parse_studio_dom_cards_and_compact_counters() -> None:
    assert parse_compact_int("1.5M") == 1_500_000
    assert parse_compact_int("45K") == 45_000
    assert parse_days_ago("2 semanas atras") == 14

    cards = [
        {"kind": "top_search", "term": "historias reais", "interest": "Alto"},
        {"kind": "content_gap", "term": "misterios medicina", "interest": "Médio"},
        {
            "kind": "video",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "title": "O Caso Real",
            "views": "120k views",
            "published_text": "10 days ago",
            "watched_by_my_viewers": True,
        },
    ]
    terms, videos = parse_studio_dom_cards(cards)
    assert len(terms) == 2
    assert terms[0].audience_interest == AudienceInterestLevel.HIGH
    assert terms[1].is_hypothesis is True
    assert terms[1].audience_interest == AudienceInterestLevel.MEDIUM
    assert len(videos) == 1
    assert videos[0].external_video_id == "abcdefghijk"
    assert videos[0].public_views == 120_000


def test_playwright_headless_shadow_dom_traversal_on_local_fixture(tmp_path: Path) -> None:
    html = """
    <!doctype html>
    <html><body>
      <div id="host"></div>
      <script>
        const host = document.getElementById('host');
        const sr = host.attachShadow({ mode: 'open' });
        sr.innerHTML = `
          <div data-block="top-searches"><div>documentarios historicos reais</div><div>Muito alto</div></div>
          <div data-block="content-gaps"><div>mapas medievais perdidos</div><div>Alto</div></div>
          <div class="ytcp-video-row">
            <a href="https://www.youtube.com/watch?v=xyz12345678">O Mapa Secreto</a>
            <span>320K views • 5 days ago • Watched by your viewers</span>
          </div>
        `;
      </script>
    </body></html>
    """
    html_file = tmp_path / "studio_fixture.html"
    html_file.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(html_file.as_uri())
        cards = page.evaluate(_SHADOW_DOM_COLLECT_JS)
        browser.close()

    terms, videos = parse_studio_dom_cards(cards)
    assert len(terms) == 2
    assert any(t.term == "documentarios historicos reais" and t.audience_interest == AudienceInterestLevel.VERY_HIGH for t in terms)
    assert any(t.term == "mapas medievais perdidos" and t.is_hypothesis is True for t in terms)
    assert len(videos) == 1
    assert videos[0].external_video_id == "xyz12345678"
    assert videos[0].public_views == 320_000
    assert videos[0].watched_by_my_viewers is True
