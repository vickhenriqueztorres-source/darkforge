from __future__ import annotations

from core.research.channel_selector import (
    ReferenceChannelCandidate,
    TargetChannelFit,
    evaluate_reference_channel,
    select_reference_channels,
)


def _good_channel(idx: int) -> ReferenceChannelCandidate:
    # 20 median videos around 4,000 + 3 clear outliers >= 3x mean (45k, 60k, 90k)
    base = [3_500, 4_000, 4_200, 3_800, 4_500] * 4 + [45_000, 60_000, 90_000]
    return ReferenceChannelCandidate(
        external_channel_id=f"UC_GOOD_{idx}",
        display_name=f"Canal Referencia {idx}",
        language="pt-BR",
        market_country="BR",
        recent_video_views_90d=[4_500, 45_000, 90_000],
        all_recent_20_30_views=base,
        production_format="faceless_essay",
        audience_profile_tags=["historia", "misterio"],
        is_celebrity_or_mega_brand=False,
        subscriber_count=18_000,
    )


def test_6_criteria_approves_outlier_rich_small_channel_and_rejects_celebrity_and_one_hit() -> None:
    target = TargetChannelFit(
        language="pt-BR",
        market_country="BR",
        feasible_formats=["faceless_essay", "documentary"],
        target_audience_tags=["historia", "misterio"],
        min_outlier_ratio=3.0,
    )
    good = _good_channel(1)
    ev_good = evaluate_reference_channel(good, target)
    assert ev_good.approved is True
    assert len(ev_good.passed_criteria) == 6
    assert ev_good.outlier_hits_count == 3
    assert ev_good.max_outlier_ratio >= 6.0

    # Celebrity giant channel where every video hits 500k (no relative outlier contrast)
    celeb = ReferenceChannelCandidate(
        external_channel_id="UC_CELEB",
        display_name="Canal Famoso Gigante",
        language="pt-BR",
        market_country="BR",
        recent_video_views_90d=[500_000, 520_000],
        all_recent_20_30_views=[500_000] * 20,
        production_format="faceless_essay",
        audience_profile_tags=["historia"],
        is_celebrity_or_mega_brand=False,
    )
    ev_celeb = evaluate_reference_channel(celeb, target)
    assert ev_celeb.approved is False
    assert "fame_independence" in ev_celeb.failed_criteria

    # Single lucky hit channel
    one_hit = ReferenceChannelCandidate(
        external_channel_id="UC_LUCK",
        display_name="Um Hit So",
        language="pt-BR",
        market_country="BR",
        recent_video_views_90d=[40_000, 2_000],
        all_recent_20_30_views=[2_000] * 19 + [40_000],
        production_format="faceless_essay",
        audience_profile_tags=["historia"],
    )
    ev_luck = evaluate_reference_channel(one_hit, target)
    assert ev_luck.approved is False
    assert "repeat_hit_consistency" in ev_luck.failed_criteria


def test_select_5_to_10_reference_channels_cap_and_target() -> None:
    target = TargetChannelFit(
        language="pt-BR",
        market_country="BR",
        feasible_formats=["faceless_essay"],
        target_audience_tags=["historia"],
    )
    res_six = select_reference_channels([_good_channel(i) for i in range(6)], target)
    assert res_six["selected_count"] == 6
    assert res_six["meets_5_to_10_target"] is True

    res_twelve = select_reference_channels([_good_channel(i) for i in range(12)], target)
    assert res_twelve["selected_count"] == 10  # Caps at 10
