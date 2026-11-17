from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.errors import AppError, ErrorCode

_AUTH_MARKERS = (
    "accounts.google.com",
    "servicelogin",
    "signin",
    "verify it's you",
    "verifique sua identidade",
    "confirm it's you",
    "2-step verification",
    "verificacao em duas etapas",
    "recaptcha",
    "captcha",
    "unusual traffic",
)


def default_studio_profile_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(local_app_data) / "DarkForge" / "studio-browser-profile"


def build_studio_research_url(external_channel_id: str | None = None) -> str:
    if external_channel_id and external_channel_id.strip():
        clean = external_channel_id.strip()
        return f"https://studio.youtube.com/channel/{clean}/analytics/tab-research"
    return "https://studio.youtube.com/"


def detect_auth_or_challenge(current_url: str, page_text: str = "") -> str | None:
    """
    Detects login redirect, 2FA or anti-bot challenge.
    Never bypasses CAPTCHA/auth (ADR-017): returns reason code to pause job in BLOCKED.
    """
    haystack = f"{current_url} {page_text}".lower()
    if "accounts.google.com" in haystack or "servicelogin" in haystack:
        return "google_login_required"
    for marker in _AUTH_MARKERS[2:]:
        if marker in haystack:
            return f"challenge_or_auth_detected:{marker}"
    return None


@dataclass(frozen=True)
class StudioSessionConfig:
    profile_dir: Path | None = None
    headless: bool = True
    navigation_timeout_ms: int = 30000
    max_runs_per_hour: int = 6
    channel_handle_hint: str | None = None

    @property
    def resolved_profile_dir(self) -> Path:
        return self.profile_dir or default_studio_profile_dir()


class StudioBrowserSessionManager:
    """
    Manages persistent Chromium session for YouTube Studio via Playwright (SP-10, ADR-017).
    Strict rate-limiting and zero automatic credential or CAPTCHA bypass.
    """

    def __init__(self, config: StudioSessionConfig | None = None) -> None:
        self._config = config or StudioSessionConfig()
        self._recent_runs: deque[float] = deque()

    @property
    def config(self) -> StudioSessionConfig:
        return self._config

    def check_rate_limit(self, now_ts: float | None = None) -> None:
        now = now_ts if now_ts is not None else time.monotonic()
        cutoff = now - 3600.0
        while self._recent_runs and self._recent_runs[0] < cutoff:
            self._recent_runs.popleft()
        if len(self._recent_runs) >= self._config.max_runs_per_hour:
            raise AppError(
                ErrorCode.STUDIO_RATE_LIMITED,
                f"Limite de seguranca atingido ({self._config.max_runs_per_hour} coletas/hora no Studio). Aguarde antes de rodar outra busca.",
                http_status=429,
                retryable=True,
                details={"next_action": "Aguarde a janela de 1h ou ajuste STUDIO_MAX_RUNS_PER_HOUR com cautela."},
            )
        self._recent_runs.append(now)

    def _import_playwright_sync(self) -> Any:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
            return sync_playwright
        except Exception as exc:
            raise AppError(
                ErrorCode.STUDIO_AUTH_REQUIRED,
                "Playwright nao instalado ou Chromium ausente no ambiente.",
                http_status=503,
                retryable=True,
                details={"next_action": "Instale playwright e execute 'playwright install chromium'."},
            ) from exc

    def open_manual_login_window(
        self,
        external_channel_id: str | None = None,
        wait_seconds: int = 180,
    ) -> dict[str, Any]:
        """Opens a visible Chromium window so the user can manually authenticate in Google/YouTube Studio."""
        sync_playwright = self._import_playwright_sync()
        profile_dir = self._config.resolved_profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)
        target_url = build_studio_research_url(external_channel_id)

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                viewport={"width": 1366, "height": 860},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(self._config.navigation_timeout_ms)
            page.goto(target_url, wait_until="domcontentloaded")
            deadline = time.monotonic() + max(10, wait_seconds)
            authenticated = False
            while time.monotonic() < deadline:
                cur_url = page.url or ""
                if "studio.youtube.com" in cur_url and detect_auth_or_challenge(cur_url) is None:
                    # Wait briefly to ensure Studio shell rendered
                    body_text = ""
                    try:
                        body_text = page.locator("body").inner_text(timeout=2000)
                    except Exception:
                        pass
                    if detect_auth_or_challenge(cur_url, body_text) is None and len(body_text.strip()) > 30:
                        authenticated = True
                        break
                page.wait_for_timeout(1500)
            final_url = page.url or ""
            ctx.close()
        return {
            "authenticated": authenticated,
            "profile_dir": str(profile_dir),
            "final_url": final_url,
            "next_action": None if authenticated else "Conclua login/2FA na janela do YouTube Studio e tente novamente.",
        }

    def check_session_status(self, external_channel_id: str | None = None) -> dict[str, Any]:
        """Verifies headless if persistent Chromium profile still has an active YouTube Studio session."""
        sync_playwright = self._import_playwright_sync()
        profile_dir = self._config.resolved_profile_dir
        if not profile_dir.exists():
            return {
                "authenticated": False,
                "reason": "profile_not_initialized",
                "profile_dir": str(profile_dir),
            }
        target_url = build_studio_research_url(external_channel_id)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self._config.headless,
                viewport={"width": 1366, "height": 860},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(self._config.navigation_timeout_ms)
            page.goto(target_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            cur_url = page.url or ""
            body_text = ""
            try:
                body_text = page.locator("body").inner_text(timeout=3000)
            except Exception:
                pass
            challenge = detect_auth_or_challenge(cur_url, body_text)
            ctx.close()
        return {
            "authenticated": challenge is None and "studio.youtube.com" in cur_url,
            "reason": challenge or ("ok" if "studio.youtube.com" in cur_url else "unexpected_url"),
            "current_url": cur_url,
            "profile_dir": str(profile_dir),
        }
