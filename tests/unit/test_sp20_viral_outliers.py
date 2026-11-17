from __future__ import annotations

import httpx

from adapters.youtube.client import OfficialYouTubeAdapter
from core.research.viral_outlier_analyzer import (
    ChannelVideoRecord,
    compute_channel_20_30_mean,
    detect_multi_channel_patterns,
    isolate_channel_outliers,
)


def _sample_channel(ch_id: str, extra_videos: list[ChannelVideoRecord]) -> list[ChannelVideoRecord]:
    base = [
        ChannelVideoRecord(
            external_video_id=f"{ch_id}_b{i}",
            external_channel_id=ch_id,
            channel_name=f"Channel {ch_id}",
            title=f"Episodio Padrao {i}",
            views=5_000,
            days_since_upload=40 + i,
            topic="rotina comum",
        )
        for i in range(20)
    ]
    return extra_videos + base


def test_20_30_mean_views_per_day_small_niche_and_false_positive_discard() -> None:
    ch1_videos = _sample_channel(
        "UC1",
        [
            ChannelVideoRecord("v_out1", "UC1", "Canal 1", "A cidade que desapareceu", 80_000, days_since_upload=10, topic="cidade desapareceu", in_suggested_feed=True),
            ChannelVideoRecord("v_small", "UC1", "Canal 1", "Cidade submersa", 24_000, days_since_upload=20, topic="cidade submersa"),
            ChannelVideoRecord("v_news", "UC1", "Canal 1", "URGENTE Breaking News hoje terremoto", 95_000, days_since_upload=2, topic="terremoto", is_breaking_news=True),
            ChannelVideoRecord("v_collab", "UC1", "Canal 1", "Entrevista com Celebridade", 90_000, days_since_upload=15, topic="entrevista", has_celebrity_collab=True),
        ],
    )
    mean_v, count, warn = compute_channel_20_30_mean(ch1_videos)
    assert count == 24
    assert warn is None
    assert mean_v > 5_000

    # Normal niche (3x threshold): v_news & v_collab discarded as false positives, v_out1 stays (vpd = 8000)
    res_3x = isolate_channel_outliers(ch1_videos, small_niche=False)
    assert len(res_3x["outliers"]) == 1
    assert res_3x["outliers"][0].video.external_video_id == "v_out1"
    assert res_3x["outliers"][0].views_per_day == 8000.0
    assert len(res_3x["discarded_false_positives"]) == 2

    # Smaller niche (2x threshold) can capture v_small if above 2x mean (here ~16k mean, adjust base to test 2x cleanly)
    low_base = [ChannelVideoRecord(f"lb_{i}", "UCL", "Low", f"V {i}", 4_000, 30) for i in range(20)] + [
        ChannelVideoRecord("lb_2x", "UCL", "Low", "Nicho Menor 2.4x", 11_000, 10, topic="mapa raro")
    ]
    res_2x = isolate_channel_outliers(low_base, small_niche=True)
    assert [o.video.external_video_id for o in res_2x["outliers"]] == ["lb_2x"]


def test_multi_channel_pattern_confirmation_rejects_single_channel_coincidence() -> None:
    o1 = isolate_channel_outliers(
        _sample_channel("UC_A", [ChannelVideoRecord("va", "UC_A", "A", "A cidade desaparecida", 80_000, 10, topic="cidade desaparecida")]),
        small_niche=False,
    )["outliers"]
    o2 = isolate_channel_outliers(
        _sample_channel("UC_B", [ChannelVideoRecord("vb", "UC_B", "B", "Cidade desaparecida", 75_000, 14, topic="cidade desaparecida")]),
        small_niche=False,
    )["outliers"]
    o_single = isolate_channel_outliers(
        _sample_channel("UC_C", [ChannelVideoRecord("vc", "UC_C", "C", "Coincidencia unica", 70_000, 20, topic="coincidencia unica")]),
        small_niche=False,
    )["outliers"]

    grouped = detect_multi_channel_patterns(o1 + o2 + o_single)
    assert len(grouped["confirmed_patterns"]) == 1
    assert set(grouped["confirmed_patterns"][0].distinct_channels) == {"UC_A", "UC_B"}
    assert len(grouped["discarded_single_channel"]) == 1


def test_adapter_fetches_20_30_detailed_videos_via_mock_transport() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if "/channels" in u:
            return httpx.Response(200, json={"items": [{"snippet": {"title": "Canal Ref"}, "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if "/playlistItems" in u:
            return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": f"vid_{i:07d}"}} for i in range(22)]})
        if "/videos" in u:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": f"vid_{i:07d}",
                            "snippet": {"title": f"Ep {i}", "publishedAt": "2026-11-01T00:00:00Z", "thumbnails": {"high": {"url": f"https://img/{i}.jpg"}}},
                            "statistics": {"viewCount": str(5000 if i > 0 else 80000)},
                            "contentDetails": {"duration": "PT12M30S"},
                        }
                        for i in range(22)
                    ]
                },
            )
        return httpx.Response(404)

    yt = OfficialYouTubeAdapter("", "", http_transport=httpx.MockTransport(handler))
    vids, cost = yt.fetch_channel_last_20_30_videos("UC_TEST", api_key="AIzaMock", count=22)
    assert len(vids) == 22
    assert vids[0]["duration_seconds"] == 750
    assert vids[0]["views"] == 80000
    assert cost == 3
