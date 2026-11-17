from __future__ import annotations

import httpx

from adapters.youtube.client import OfficialYouTubeAdapter
from core.research.outlier_engine import compute_channel_baseline, rank_outlier_videos
from core.research.studio_models import StudioVideoCandidate


def test_outlier_score_calculation_tiers_and_insufficient_baseline() -> None:
    assert compute_channel_baseline([1000, 2000]) is None
    assert compute_channel_baseline([1000, 10000, 12000, 11000, 9000]) == 10000.0

    cands = [
        StudioVideoCandidate(
            external_video_id="vid_5x0000001",
            canonical_url="https://www.youtube.com/watch?v=vid_5x0000001",
            title="Video 6x Outlier",
            external_channel_id="UC1",
            channel_name="Canal 1",
            public_views=60_000,
            watched_by_my_viewers=True,
        ),
        StudioVideoCandidate(
            external_video_id="vid_2x0000002",
            canonical_url="https://www.youtube.com/watch?v=vid_2x0000002",
            title="Video Normal 2x",
            external_channel_id="UC1",
            channel_name="Canal 1",
            public_views=20_000,
            watched_by_my_viewers=True,
        ),
        StudioVideoCandidate(
            external_video_id="vid_12x000003",
            canonical_url="https://www.youtube.com/watch?v=vid_12x000003",
            title="Video 12x Viral",
            external_channel_id="UC2",
            channel_name="Canal 2",
            public_views=120_000,
            watched_by_my_viewers=False,
        ),
        StudioVideoCandidate(
            external_video_id="vid_insuf0004",
            canonical_url="https://www.youtube.com/watch?v=vid_insuf0004",
            title="Canal Pequeno Sem Baseline",
            external_channel_id="UC_NEW",
            channel_name="Canal Novo",
            public_views=50_000,
        ),
    ]
    baselines = {
        "UC1": [9_000, 10_000, 11_000, 12_000, 8_000],
        "UC2": [10_000, 10_000, 10_000],
        "UC_NEW": [1_000, 2_000],
    }

    only_3x = rank_outlier_videos(cands, baselines, min_outlier_ratio=3.0)
    assert [o.video.external_video_id for o in only_3x] == ["vid_12x000003", "vid_5x0000001"]
    assert only_3x[0].outlier_ratio == 12.0
    assert only_3x[0].outlier_tier == "10x+"
    assert only_3x[1].outlier_ratio == 6.0
    assert only_3x[1].outlier_tier == "5x+"

    all_scored = rank_outlier_videos(cands, baselines, min_outlier_ratio=3.0, include_below_threshold=True)
    assert len(all_scored) == 4
    insuf = [o for o in all_scored if o.video.external_video_id == "vid_insuf0004"][0]
    assert insuf.outlier_tier == "insufficient_baseline"
    assert insuf.outlier_ratio is None


def test_official_youtube_adapter_fetches_public_channel_baseline_via_mock_transport() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if "/channels" in url:
            return httpx.Response(200, json={"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]})
        if "/playlistItems" in url:
            return httpx.Response(
                200,
                json={"items": [{"contentDetails": {"videoId": "v1"}}, {"contentDetails": {"videoId": "v2"}}, {"contentDetails": {"videoId": "v3"}}]},
            )
        if "/videos" in url:
            return httpx.Response(
                200,
                json={"items": [{"statistics": {"viewCount": "5000"}}, {"statistics": {"viewCount": "7000"}}, {"statistics": {"viewCount": "6000"}}]},
            )
        return httpx.Response(404)

    adapter = OfficialYouTubeAdapter("", "", http_transport=httpx.MockTransport(handler))
    counts, cost = adapter.fetch_public_channel_recent_view_counts("UC123", api_key="AIzaMock")
    assert counts == [5000, 7000, 6000]
    assert cost == 3
