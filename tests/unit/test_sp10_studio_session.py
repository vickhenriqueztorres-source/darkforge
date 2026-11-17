from __future__ import annotations

from pathlib import Path

import pytest

from adapters.studio_browser.session import (
    StudioBrowserSessionManager,
    StudioSessionConfig,
    build_studio_research_url,
    detect_auth_or_challenge,
)
from core.errors import AppError, ErrorCode


def test_detect_auth_redirect_2fa_and_captcha_never_bypasses() -> None:
    assert detect_auth_or_challenge("https://accounts.google.com/ServiceLogin?continue=...") == "google_login_required"
    assert detect_auth_or_challenge("https://studio.youtube.com/...", "Verificacao em duas etapas") is not None
    assert detect_auth_or_challenge("https://studio.youtube.com/...", "Please complete reCAPTCHA") is not None
    assert detect_auth_or_challenge("https://studio.youtube.com/channel/UC123/analytics/tab-research", "Top searches Audience interest") is None


def test_build_studio_research_url_and_rate_limit(tmp_path: Path) -> None:
    assert build_studio_research_url("UC_ABC123") == "https://studio.youtube.com/channel/UC_ABC123/analytics/tab-research"
    assert build_studio_research_url(None) == "https://studio.youtube.com/"

    mgr = StudioBrowserSessionManager(StudioSessionConfig(profile_dir=tmp_path / "prof", max_runs_per_hour=2))
    mgr.check_rate_limit(now_ts=1000.0)
    mgr.check_rate_limit(now_ts=1010.0)
    with pytest.raises(AppError) as exc:
        mgr.check_rate_limit(now_ts=1020.0)
    assert exc.value.code == ErrorCode.STUDIO_RATE_LIMITED
    assert exc.value.http_status == 429

    # Window clears after > 3600s
    mgr.check_rate_limit(now_ts=4700.0)
