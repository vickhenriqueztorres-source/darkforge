from __future__ import annotations

import json

import httpx
import pytest

from adapters.youtube.public_channel import (
    PublicChannelCollector,
    compute_insights,
    parse_channel_page,
    parse_channel_ref,
    parse_compact_count,
    parse_duration_clock,
    parse_rss_feed,
    parse_search_results_page,
    parse_view_count_text,
)
from core.errors import AppError

CID = "UCf6Ox9rzQbIkDeE94to9AEQ"

RSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <entry>
  <yt:videoId>AAAAAAAAAAA</yt:videoId>
  <title>Video longo</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=AAAAAAAAAAA"/>
  <published>2026-11-10T12:00:00+00:00</published>
  <media:group>
   <media:thumbnail url="https://i2.ytimg.com/vi/AAAAAAAAAAA/hqdefault.jpg" width="480" height="360"/>
   <media:community><media:starRating count="12" average="5.00"/><media:statistics views="400"/></media:community>
  </media:group>
 </entry>
 <entry>
  <yt:videoId>BBBBBBBBBBB</yt:videoId>
  <title>Short</title>
  <link rel="alternate" href="https://www.youtube.com/shorts/BBBBBBBBBBB"/>
  <published>2026-11-12T12:00:00+00:00</published>
  <media:group>
   <media:thumbnail url="https://i3.ytimg.com/vi/BBBBBBBBBBB/hqdefault.jpg" width="480" height="360"/>
   <media:community><media:starRating count="3" average="5.00"/><media:statistics views="50"/></media:community>
  </media:group>
 </entry>
</feed>"""

PAGE = (
    '<meta property="og:title" content="O Outro Lado">'
    '<meta property="og:image" content="https://yt3.googleusercontent.com/avatar=s900">'
    f'"externalId":"{CID}" "canonicalBaseUrl":"/@outroladodetudo"'
    '"metadataParts":[{"text":{"content":"1.2K subscribers"}},{"text":{"content":"93 videos"}}]'
    '"case1":"Delete 1 video?"'
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("@outroladodetudo", ("handle", "outroladodetudo")),
        ("youtube.com/@ViajanteZero-films", ("handle", "ViajanteZero-films")),
        ("https://www.youtube.com/@Sonar0300/videos?x=1", ("handle", "Sonar0300")),
        (f"https://youtube.com/channel/{CID}", ("channel_id", CID)),
        (CID, ("channel_id", CID)),
    ],
)
def test_parse_channel_ref(raw, expected):
    ref = parse_channel_ref(raw)
    assert getattr(ref, expected[0]) == expected[1]


def test_parse_channel_ref_rejects_garbage():
    with pytest.raises(AppError):
        parse_channel_ref("   ")


@pytest.mark.parametrize("text,val", [("142", 142), ("1.2K", 1200), ("3,4M", 3_400_000), ("1,234", 1234), ("x", None)])
def test_parse_compact_count(text, val):
    assert parse_compact_count(text) == val


def test_parse_channel_page_ignores_ui_strings():
    info = parse_channel_page(PAGE)
    assert info["channel_id"] == CID
    assert info["handle"] == "@outroladodetudo"
    assert info["subscribers"] == 1200
    assert info["video_count"] == 93
    assert info["title"] == "O Outro Lado"


def test_parse_rss_marks_shorts_and_normalizes_thumbs():
    vids = parse_rss_feed(RSS)
    assert [v["format"] for v in vids] == ["long", "short"]
    assert vids[0]["views"] == 400 and vids[0]["likes"] == 12
    assert vids[1]["thumbnail_url"].startswith("https://i.ytimg.com/")


def test_insights_compare_against_same_format():
    vids = [
        {"video_id": "a", "format": "long", "views": 100, "published_at": "2026-11-01T00:00:00Z"},
        {"video_id": "b", "format": "long", "views": 300, "published_at": "2026-11-05T00:00:00Z"},
        {"video_id": "c", "format": "long", "views": 1000, "published_at": "2026-11-09T00:00:00Z"},
        {"video_id": "d", "format": "short", "views": 10, "published_at": "2026-11-10T00:00:00Z"},
    ]
    ins = compute_insights(vids)
    assert ins["median_by_format"] == {"long": 300, "short": 10}
    assert vids[2]["outlier_ratio"] == pytest.approx(3.33, abs=0.01)
    assert vids[3]["outlier_ratio"] == 1.0
    assert ins["outliers"] == ["c"]
    assert ins["best_video_id"] == "c"


def _transport(with_api: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "googleapis.com/youtube/v3/channels" in url:
            assert request.url.params["forHandle"] == "@outroladodetudo"
            return httpx.Response(200, json={"items": [{
                "id": CID,
                "snippet": {"title": "O Outro Lado", "customUrl": "@outroladodetudo", "thumbnails": {"high": {"url": "https://x/avatar"}}},
                "statistics": {"subscriberCount": "142", "viewCount": "55555", "videoCount": "93", "hiddenSubscriberCount": False},
                "contentDetails": {"relatedPlaylists": {"uploads": "UUf6Ox9rzQbIkDeE94to9AEQ"}},
                "brandingSettings": {"image": {"bannerExternalUrl": "https://x/banner"}},
            }]})
        if "playlistItems" in url:
            return httpx.Response(200, json={"items": [
                {"contentDetails": {"videoId": "AAAAAAAAAAA"}}, {"contentDetails": {"videoId": "BBBBBBBBBBB"}},
            ]})
        if "googleapis.com/youtube/v3/videos" in url:
            return httpx.Response(200, json={"items": [
                {"id": "AAAAAAAAAAA", "snippet": {"title": "Longo", "publishedAt": "2026-11-10T12:00:00Z", "thumbnails": {}},
                 "statistics": {"viewCount": "400", "likeCount": "12", "commentCount": "3"}, "contentDetails": {"duration": "PT12M5S"}},
                {"id": "BBBBBBBBBBB", "snippet": {"title": "Short", "publishedAt": "2026-11-12T12:00:00Z", "thumbnails": {}},
                 "statistics": {"viewCount": "50"}, "contentDetails": {"duration": "PT2M10S"}},
            ]})
        if "feeds/videos.xml" in url:
            return httpx.Response(200, text=RSS)
        if "youtube.com/@outroladodetudo" in url:
            return httpx.Response(200, text=PAGE)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_data_api_path_is_exact_and_fixes_shorts_via_rss():
    col = PublicChannelCollector(api_key="k", http_transport=_transport(True))
    ov = col.fetch_overview(parse_channel_ref("@outroladodetudo"))
    assert ov["source"] == "youtube_data_api_v3"
    assert ov["stats"] == {
        "subscribers": 142, "subscribers_approximate": True, "subscribers_hidden": False,
        "total_views": 55555, "video_count": 93,
    }
    by_id = {v["video_id"]: v for v in ov["videos"]}
    assert by_id["BBBBBBBBBBB"]["format"] == "short"  # 2m10s, mas o RSS confirma /shorts/
    assert by_id["AAAAAAAAAAA"]["duration_seconds"] == 725
    assert by_id["AAAAAAAAAAA"]["engagement_rate"] == 3.75
    assert ov["channel"]["banner_url"] == "https://x/banner"
    assert col.fetch_overview(parse_channel_ref("@outroladodetudo"))["cache"] == "hit"


def test_fallback_without_api_key():
    col = PublicChannelCollector(api_key="", http_transport=_transport(False))
    ov = col.fetch_overview(parse_channel_ref("youtube.com/@outroladodetudo"))
    assert ov["source"] == "public_page_rss"
    assert ov["quota_cost"] == 0
    assert ov["stats"]["subscribers"] == 1200 and ov["stats"]["video_count"] == 93
    assert ov["stats"]["total_views"] is None
    assert len(ov["videos"]) == 2
    assert ov["warnings"] and "YOUTUBE_API_KEY" in ov["warnings"][0]
    json.dumps(ov)  # serializavel para a API


def test_parse_view_count_and_duration_clock():
    assert parse_view_count_text("286.878 visualizações") == 286_878
    assert parse_view_count_text("1.2M views") == 1_200_000
    assert parse_view_count_text("45 mil visualizações") == 45_000
    assert parse_view_count_text("Nenhuma visualização") == 0
    assert parse_duration_clock("12:05") == 725
    assert parse_duration_clock("1:02:03") == 3723
    assert parse_duration_clock("ao vivo") is None


def test_search_public_videos_via_html_and_data_api():
    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "VID12345678",
                                                "title": {"runs": [{"text": "Misterio da Ilha Submersa"}]},
                                                "ownerText": {
                                                    "runs": [
                                                        {
                                                            "text": "Canal Docs",
                                                            "navigationEndpoint": {"browseEndpoint": {"browseId": CID}},
                                                        }
                                                    ]
                                                },
                                                "viewCountText": {"simpleText": "286.878 visualizações"},
                                                "lengthText": {"simpleText": "14:20"},
                                                "publishedTimeText": {"simpleText": "há 2 meses"},
                                                "thumbnail": {"thumbnails": [{"url": "https://i.ytimg.com/vi/VID12345678/hq720.jpg"}]},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "VID12345678",  # duplicado deve ser ignorado
                                                "title": {"runs": [{"text": "Duplicado"}]},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    search_html = f"<html><script>var ytInitialData = {json.dumps(initial_data)};</script></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if "youtube.com/results" in u:
            return httpx.Response(200, text=search_html)
        if "googleapis.com/youtube/v3/search" in u:
            return httpx.Response(200, json={"items": [{"id": {"videoId": "APIVID12345"}}]})
        if "googleapis.com/youtube/v3/videos" in u:
            return httpx.Response(200, json={"items": [{
                "id": "APIVID12345",
                "snippet": {"title": "API Video", "channelId": CID, "channelTitle": "Canal API", "publishedAt": "2026-11-01T00:00:00Z", "thumbnails": {}},
                "statistics": {"viewCount": "95000", "likeCount": "4000", "commentCount": "120"},
                "contentDetails": {"duration": "PT10M0S"},
            }]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    parsed = parse_search_results_page(search_html, max_results=5)
    assert len(parsed) == 1
    assert parsed[0]["video_id"] == "VID12345678"
    assert parsed[0]["views"] == 286_878
    assert parsed[0]["duration_seconds"] == 860
    assert parsed[0]["format"] == "long"
    assert parsed[0]["channel_id"] == CID

    col_pub = PublicChannelCollector(api_key="", http_transport=transport)
    res_pub = col_pub.search_public_videos("ilha submersa", max_results=5)
    assert len(res_pub) == 1 and res_pub[0]["source"] == "youtube_public_search"

    col_api = PublicChannelCollector(api_key="key123", http_transport=transport)
    res_api = col_api.search_public_videos("ilha submersa", max_results=5)
    assert len(res_api) == 1 and res_api[0]["video_id"] == "APIVID12345"
    assert res_api[0]["views"] == 95000 and res_api[0]["source"] == "youtube_data_api_v3"
