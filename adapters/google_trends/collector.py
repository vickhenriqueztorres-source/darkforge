from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any

from adapters.studio_browser.session import StudioBrowserSessionManager, detect_auth_or_challenge
from core.errors import AppError, ErrorCode
from core.research.google_trends_models import TrendsQueryItem, TrendsSeriesPoint


def build_trends_explore_url(keyword: str, *, date_range: str = "today 12-m", geo: str = "BR", gprop: str = "youtube", hl: str = "pt-BR") -> str:
    params: dict[str, str] = {"date": date_range, "q": keyword, "hl": hl}
    if geo and geo.strip().upper() != "GLOBAL":
        params["geo"] = geo.strip().upper()
    if gprop and gprop.strip():
        params["gprop"] = gprop.strip()
    return f"https://trends.google.com/trends/explore?{urllib.parse.urlencode(params)}"


def strip_trends_xssi_prefix(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.lstrip()
    if cleaned.startswith(")]}',") or cleaned.startswith(")]}'"):
        cleaned = cleaned.split("\n", 1)[-1]
    return json.loads(cleaned)


def parse_trends_multiline_json(raw_text: str) -> list[TrendsSeriesPoint]:
    data = strip_trends_xssi_prefix(raw_text)
    rows = (data.get("default") or {}).get("timelineData") or []
    pts: list[TrendsSeriesPoint] = []
    for row in rows:
        vals = row.get("value") or []
        val = float(vals[0]) if vals else 0.0
        ts = int(row["time"]) if str(row.get("time", "")).isdigit() else None
        lbl = str(row.get("formattedAxisTime") or row.get("formattedTime") or row.get("time") or "")
        pts.append(TrendsSeriesPoint(date_label=lbl, value=val, timestamp_sec=ts))
    return pts


def parse_trends_related_json(raw_text: str) -> list[TrendsQueryItem]:
    data = strip_trends_xssi_prefix(raw_text)
    ranked = (data.get("default") or {}).get("rankedList") or []
    out: list[TrendsQueryItem] = []
    for idx, block in enumerate(ranked):
        keywords = block.get("rankedKeyword") or []
        # Google Trends rankedList[0] = Top, rankedList[1] = Rising/Breakout
        is_rising_block = idx == 1
        for kw in keywords:
            term = str(kw.get("query") or "").strip()
            if not term:
                continue
            fmt = str(kw.get("formattedValue") or "").strip()
            num_val = kw.get("value")
            pct = float(num_val) if isinstance(num_val, (int, float)) else None
            if is_rising_block or "breakout" in fmt.lower() or "aumento repentino" in fmt.lower() or "5.000%" in fmt or "+" in fmt:
                is_bo = "breakout" in fmt.lower() or "aumento repentino" in fmt.lower() or "5.000%" in fmt or (pct is not None and pct >= 5000.0)
                gtype = "breakout" if is_bo else "rising"
            else:
                gtype = "top"
            out.append(TrendsQueryItem(term=term, growth_type=gtype, growth_pct=pct, raw_label=fmt))
    return out


class GoogleTrendsPlaywrightCollector:
    """
    Collects 12m, 5y and Related Queries (Top/Rising/Breakout) via Playwright network interception.
    Respects rate limits and never bypasses CAPTCHA/429 (returns BLOCKED AppError).
    """

    def __init__(self, session_mgr: StudioBrowserSessionManager | None = None) -> None:
        self._session = session_mgr or StudioBrowserSessionManager()

    def collect(
        self,
        *,
        keyword: str,
        geo: str = "BR",
        gprop: str = "youtube",
        hl: str = "pt-BR",
    ) -> dict[str, Any]:
        self._session.check_rate_limit()
        sync_playwright = self._session._import_playwright_sync()
        profile_dir = self._session.config.resolved_profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)

        pts_12m: list[TrendsSeriesPoint] = []
        pts_5y: list[TrendsSeriesPoint] = []
        queries: list[TrendsQueryItem] = []
        rate_limited = False

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self._session.config.headless,
                viewport={"width": 1366, "height": 860},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(self._session.config.navigation_timeout_ms)

            current_phase = "12m"

            def on_response(resp: Any) -> None:
                nonlocal rate_limited, pts_12m, pts_5y, queries
                try:
                    u = str(resp.url or "").lower()
                    if resp.status == 429:
                        rate_limited = True
                        return
                    if resp.status == 200 and "/trends/api/widgetdata/multiline" in u:
                        parsed = parse_trends_multiline_json(resp.text())
                        if current_phase == "12m" and parsed:
                            pts_12m = parsed
                        elif current_phase == "5y" and parsed:
                            pts_5y = parsed
                    elif resp.status == 200 and "/trends/api/widgetdata/relatedsearches" in u:
                        queries.extend(parse_trends_related_json(resp.text()))
                except Exception:
                    pass

            page.on("response", on_response)

            for phase, timeframe in (("12m", "today 12-m"), ("5y", "today 5-y")):
                current_phase = phase
                target = build_trends_explore_url(keyword, date_range=timeframe, geo=geo, gprop=gprop, hl=hl)
                page.goto(target, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                body_text = ""
                try:
                    body_text = page.locator("body").inner_text(timeout=2000)
                except Exception:
                    pass
                challenge = detect_auth_or_challenge(page.url or "", body_text)
                if challenge is not None or rate_limited or "error 429" in body_text.lower():
                    ctx.close()
                    raise AppError(
                        ErrorCode.STUDIO_RATE_LIMITED,
                        "Google Trends solicitou verificacao humana ou retornou HTTP 429. Use importacao de CSV manual ou aguarde antes de tentar novamente.",
                        http_status=429,
                        retryable=True,
                        details={"next_action": "Exporte multiTimeline.csv / relatedQueries.csv no Google Trends e use Importar CSV."},
                    )

            ctx.close()

        return {
            "points_12m": pts_12m,
            "points_5y": pts_5y,
            "related_queries": queries,
            "captured_via": "playwright_json",
        }
