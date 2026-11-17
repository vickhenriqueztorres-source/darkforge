from __future__ import annotations

import base64
import json
import os
from datetime import date, datetime, timezone
from uuid import uuid4

import httpx
import pytest

from adapters.youtube.client import OfficialYouTubeAdapter
from adapters.youtube.token_vault import TokenVault
from core.analytics.catalog import assert_compatible_comparison, validate_metric_fact_spec
from core.analytics.models import MetricAvailability, MetricFactInput, MetricFactView
from core.errors import AppError, ErrorCode


def test_token_vault_roundtrip_and_missing_key_fails() -> None:
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    vault = TokenVault(key)
    ct = vault.encrypt("ya29.secret-token")
    assert ct != "ya29.secret-token"
    assert vault.decrypt(ct) == "ya29.secret-token"

    broken = TokenVault("")
    with pytest.raises(AppError) as exc:
        broken.decrypt(ct)
    assert exc.value.code == ErrorCode.OAUTH_REQUIRED_OR_REVOKED


def test_unavailable_metric_cannot_have_zero_or_numeric_value() -> None:
    with pytest.raises(ValueError):
        MetricFactInput(
            metric_id="yt.analytics.impressions_ctr",
            visibility_scope="private_authorized",
            source="youtube_analytics_api",
            period_start=date(2026, 11, 1),
            period_end=date(2026, 11, 15),
            granularity="period_total",
            dimensions_json={},
            availability=MetricAvailability.UNKNOWN,
            value_num=0.0,
        )


def test_incompatible_comparison_blocked() -> None:
    now = datetime.now(timezone.utc)
    f_priv = MetricFactView(
        id=uuid4(),
        metric_id="yt.analytics.views",
        display_name="Views",
        visibility_scope="private_authorized",
        source="youtube_analytics_api",
        source_revision=1,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 10),
        granularity="period_total",
        dimensions_json={},
        availability=MetricAvailability.AVAILABLE,
        value_num=1000.0,
        is_estimate=False,
        fetched_at=now,
    )
    f_day = MetricFactView(**{**f_priv.__dict__, "granularity": "day"})
    with pytest.raises(AppError) as exc:
        assert_compatible_comparison([f_priv, f_day])
    assert exc.value.code == ErrorCode.VALIDATION_ERROR

    validate_metric_fact_spec("yt.analytics.views", "day", {"country": "BR"}, "private_authorized")
    with pytest.raises(AppError):
        validate_metric_fact_spec("yt.analytics.views", "day", {"country": "BR", "traffic_source": "SEARCH"}, "private_authorized")


def test_official_youtube_adapter_contract_and_error_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "acc-1", "refresh_token": "ref-1", "expires_in": 3600})
        if "youtube/v3/channels" in str(request.url):
            return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
        return httpx.Response(404)

    adapter = OfficialYouTubeAdapter("cid", "csec", http_transport=httpx.MockTransport(handler))
    url = adapter.build_authorize_url("st1", "chal1", "http://127.0.0.1:8000/cb")
    assert "youtube.readonly" in url
    assert "youtube.upload" not in url  # No write/upload scope in MVP

    bundle = adapter.exchange_code("code1", "ver1", "http://127.0.0.1:8000/cb")
    assert bundle.access_token == "acc-1"

    with pytest.raises(AppError) as exc:
        adapter.fetch_own_channel_and_videos_page("acc-1")
    assert exc.value.code == ErrorCode.YOUTUBE_QUOTA_EXCEEDED
