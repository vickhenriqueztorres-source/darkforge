from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from adapters.studio_browser.session import (
    StudioBrowserSessionManager,
    build_studio_research_url,
    detect_auth_or_challenge,
)
from core.errors import AppError, ErrorCode
from core.research.studio_models import (
    AudienceInterestLevel,
    StudioExtractionResult,
    StudioSearchTerm,
    StudioTrendsFilter,
    StudioVideoCandidate,
    normalize_interest_level,
)

_YT_ID_RE = re.compile(r"(?:watch\?v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})")


def parse_compact_int(raw: Any) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    text = str(raw or "").strip().lower().replace(",", ".")
    if not text:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(mil|mi|m|k)?", text)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2) or ""
    if unit in ("k", "mil"):
        val *= 1_000
    elif unit in ("m", "mi"):
        val *= 1_000_000
    return int(val)


def parse_days_ago(raw: str | None) -> int | None:
    txt = (raw or "").strip().lower()
    if not txt:
        return None
    m = re.search(r"(\d+)\s*(dia|day|semana|week|m[eê]s|month|ano|year|hora|hour)", txt)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit.startswith(("hora", "hour")):
        return 0
    if unit.startswith(("dia", "day")):
        return n
    if unit.startswith(("semana", "week")):
        return n * 7
    if unit.startswith(("m",)):
        return n * 30
    if unit.startswith(("ano", "year")):
        return n * 365
    return None


def parse_studio_network_payloads(payloads: list[dict[str, Any]]) -> tuple[list[StudioSearchTerm], list[StudioVideoCandidate]]:
    """Extracts Top Searches, Audience Interest, Content Gaps & Videos from Studio internal JSON payloads."""
    terms_by_key: dict[tuple[str, str], StudioSearchTerm] = {}
    videos_by_id: dict[str, StudioVideoCandidate] = {}

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        # 1. Search term candidate
        term_text = (
            node.get("searchTerm")
            or node.get("query")
            or node.get("term")
            or node.get("topicTitle")
        )
        if isinstance(term_text, dict):
            term_text = term_text.get("simpleText") or "".join(r.get("text", "") for r in term_text.get("runs", []))
        interest_raw = (
            node.get("audienceInterestLevel")
            or node.get("searchVolumeTier")
            or node.get("interestLevel")
        )
        if isinstance(term_text, str) and term_text.strip() and (interest_raw or "contentGap" in node or "isContentGap" in node or "blockType" in node):
            is_gap = bool(node.get("isContentGap") or node.get("contentGap") or node.get("blockType") == "content_gap")
            block = "content_gap" if is_gap else "top_search"
            lvl = normalize_interest_level(str(interest_raw or "medium"))
            clean_term = term_text.strip()
            terms_by_key[(clean_term.lower(), block)] = StudioSearchTerm(
                term=clean_term,
                block_type=block,
                audience_interest=lvl,
                is_hypothesis=is_gap,
                gap_note="Lacuna indicada pelo YouTube Studio Trends; validar volume antes de produzir." if is_gap else "",
                weekly_views_gt_1000=bool(node.get("weeklyViewsGt1000", True)),
            )

        # 2. Video candidate
        vid_id = node.get("videoId") or node.get("externalVideoId")
        if isinstance(vid_id, str) and len(vid_id.strip()) == 11:
            clean_id = vid_id.strip()
            title_val = node.get("title") or ""
            if isinstance(title_val, dict):
                title_val = title_val.get("simpleText") or "".join(r.get("text", "") for r in title_val.get("runs", []))
            ch_id = node.get("channelId") or node.get("externalChannelId")
            ch_name = node.get("channelTitle") or node.get("channelName") or "Canal Desconhecido"
            if isinstance(ch_name, dict):
                ch_name = ch_name.get("simpleText") or "Canal Desconhecido"
            views = parse_compact_int(node.get("viewCount") or node.get("viewCountText") or node.get("views"))
            pub_text = node.get("publishedTimeText") or node.get("publishedAt")
            if isinstance(pub_text, dict):
                pub_text = pub_text.get("simpleText")
            watched_flag = bool(
                node.get("watchedByYourViewers")
                or node.get("watchedByMyViewers")
                or node.get("watched_by_my_viewers")
            )
            videos_by_id[clean_id] = StudioVideoCandidate(
                external_video_id=clean_id,
                canonical_url=f"https://www.youtube.com/watch?v={clean_id}",
                title=str(title_val or clean_id).strip(),
                external_channel_id=str(ch_id).strip() if ch_id else None,
                channel_name=str(ch_name).strip(),
                public_views=views,
                published_at_iso=str(node.get("publishedAt")) if node.get("publishedAt") else None,
                published_days_ago=parse_days_ago(str(pub_text)) if pub_text else None,
                watched_by_my_viewers=watched_flag,
            )

        for val in node.values():
            if isinstance(val, (dict, list)):
                walk(val)

    for p in payloads:
        walk(p)
    return list(terms_by_key.values()), list(videos_by_id.values())


def parse_studio_dom_cards(cards: list[dict[str, Any]]) -> tuple[list[StudioSearchTerm], list[StudioVideoCandidate]]:
    """Parses normalized Shadow-DOM card dicts captured from YouTube Studio UI."""
    terms: list[StudioSearchTerm] = []
    videos: list[StudioVideoCandidate] = []
    seen_terms: set[tuple[str, str]] = set()
    seen_videos: set[str] = set()

    for c in cards:
        kind = str(c.get("kind", "")).lower()
        if kind in ("top_search", "content_gap"):
            t = str(c.get("term", "")).strip()
            if not t:
                continue
            key = (t.lower(), kind)
            if key in seen_terms:
                continue
            seen_terms.add(key)
            is_gap = kind == "content_gap"
            terms.append(
                StudioSearchTerm(
                    term=t,
                    block_type=kind,
                    audience_interest=normalize_interest_level(c.get("interest")),
                    is_hypothesis=is_gap,
                    gap_note="Lacuna (Content gap) a validar contra volume real." if is_gap else "",
                )
            )
        elif kind == "video":
            href = str(c.get("url", ""))
            m = _YT_ID_RE.search(href)
            vid = str(c.get("video_id") or (m.group(1) if m else "")).strip()
            if len(vid) != 11 or vid in seen_videos:
                continue
            seen_videos.add(vid)
            videos.append(
                StudioVideoCandidate(
                    external_video_id=vid,
                    canonical_url=f"https://www.youtube.com/watch?v={vid}",
                    title=str(c.get("title") or vid).strip(),
                    external_channel_id=c.get("channel_id"),
                    channel_name=str(c.get("channel_name") or "Canal").strip(),
                    public_views=parse_compact_int(c.get("views")),
                    published_days_ago=parse_days_ago(c.get("published_text")),
                    watched_by_my_viewers=bool(c.get("watched_by_my_viewers", False)),
                )
            )
    return terms, videos


_SHADOW_DOM_COLLECT_JS = """
() => {
  const results = [];
  function walkShadow(root) {
    if (!root) return [];
    let nodes = Array.from(root.querySelectorAll('*'));
    for (const el of nodes) {
      if (el.shadowRoot) {
        nodes = nodes.concat(walkShadow(el.shadowRoot));
      }
    }
    return nodes;
  }
  const all = walkShadow(document);
  for (const el of all) {
    const tag = (el.tagName || '').toLowerCase();
    const txt = (el.innerText || '').trim();
    if (!txt) continue;
    if (tag.includes('research-search-term') || tag.includes('trends-term') || el.getAttribute('data-block') === 'top-searches' || el.getAttribute('data-block') === 'content-gaps') {
      const lower = txt.toLowerCase();
      const isGap = el.getAttribute('data-block') === 'content-gaps' || lower.includes('content gap') || lower.includes('lacuna');
      const lines = txt.split(/\\n+/).map(s => s.trim()).filter(Boolean);
      results.push({
        kind: isGap ? 'content_gap' : 'top_search',
        term: lines[0] || '',
        interest: lines.find(l => /(muito alto|very high|alto|high|m[eé]dio|medium|baixo|low)/i.test(l)) || ''
      });
    }
    if (tag === 'a' && el.href && (el.href.includes('watch?v=') || el.href.includes('/shorts/'))) {
      const parentText = (el.closest('ytcp-video-row, ytcd-card, div')?.innerText || '').toLowerCase();
      results.push({
        kind: 'video',
        url: el.href,
        title: txt.split('\\n')[0],
        views: parentText,
        published_text: parentText,
        watched_by_my_viewers: parentText.includes('watched by your viewers') || parentText.includes('assistido pelo seu p')
      });
    }
  }
  return results;
}
"""


class StudioTrendsExtractor:
    """
    Executes assisted YouTube Studio Trends extraction via Playwright (SP-11, ADR-017).
    Combines network JSON interception and Shadow-DOM traversal.
    """

    def __init__(self, session_mgr: StudioBrowserSessionManager | None = None) -> None:
        self._session = session_mgr or StudioBrowserSessionManager()

    def extract(
        self,
        *,
        external_channel_id: str | None,
        filters: StudioTrendsFilter,
    ) -> StudioExtractionResult:
        self._session.check_rate_limit()
        sync_playwright = self._session._import_playwright_sync()
        profile_dir = self._session.config.resolved_profile_dir
        if not profile_dir.exists():
            raise AppError(
                ErrorCode.STUDIO_AUTH_REQUIRED,
                "Sessao persistente do YouTube Studio nao inicializada. Abra a janela de login manual primeiro.",
                http_status=412,
                retryable=True,
                details={"next_action": "Clique em 'Abrir Login YouTube Studio' para autenticar manualmente."},
            )

        target_url = build_studio_research_url(external_channel_id)
        captured_json: list[dict[str, Any]] = []

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self._session.config.headless,
                viewport={"width": 1366, "height": 860},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.set_default_timeout(self._session.config.navigation_timeout_ms)

            def on_response(resp: Any) -> None:
                try:
                    u = str(resp.url or "").lower()
                    if any(tok in u for tok in ("youtubei", "research", "inspiration", "trends")) and resp.status == 200:
                        ctype = (resp.headers or {}).get("content-type", "")
                        if "json" in ctype:
                            captured_json.append(resp.json())
                except Exception:
                    pass

            page.on("response", on_response)
            page.goto(target_url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            cur_url = page.url or ""
            body_text = ""
            try:
                body_text = page.locator("body").inner_text(timeout=3000)
            except Exception:
                pass
            challenge = detect_auth_or_challenge(cur_url, body_text)
            if challenge is not None:
                ctx.close()
                raise AppError(
                    ErrorCode.STUDIO_AUTH_REQUIRED,
                    f"Autenticacao ou verificacao humana necessaria no YouTube Studio ({challenge}).",
                    http_status=412,
                    retryable=True,
                    details={"reason": challenge, "next_action": "Execute login manual na janela do Studio (zero bypass de CAPTCHA/2FA)."},
                )

            # Enter broad topic into search box if present
            try:
                search_input = page.locator("input[type='search'], input[aria-label*='Search'], input[aria-label*='Pesquisar']").first
                if search_input.count() > 0:
                    search_input.click()
                    search_input.fill(filters.broad_topic)
                    search_input.press("Enter")
                    page.wait_for_timeout(2500)
            except Exception:
                pass

            # Optional toggle for "Watched by my viewers"
            if filters.only_watched_by_my_viewers:
                try:
                    chip = page.get_by_text(re.compile(r"Watched by|Assistido pelo seu", re.IGNORECASE)).first
                    if chip.count() > 0:
                        chip.click()
                        page.wait_for_timeout(1200)
                except Exception:
                    pass

            dom_cards: list[dict[str, Any]] = []
            try:
                dom_cards = page.evaluate(_SHADOW_DOM_COLLECT_JS) or []
            except Exception:
                dom_cards = []
            ctx.close()

        net_terms, net_videos = parse_studio_network_payloads(captured_json)
        dom_terms, dom_videos = parse_studio_dom_cards(dom_cards)

        # Merge + filter by min_interest & upload_window_days
        merged_terms = {(t.term.lower(), t.block_type): t for t in (dom_terms + net_terms)}
        filtered_terms = [
            t for t in merged_terms.values()
            if t.audience_interest == AudienceInterestLevel.UNKNOWN or t.audience_interest.rank >= filters.min_interest.rank
        ]

        merged_videos = {v.external_video_id: v for v in (dom_videos + net_videos)}
        filtered_videos = [
            v for v in merged_videos.values()
            if (not filters.only_watched_by_my_viewers or v.watched_by_my_viewers)
            and (filters.upload_window_days is None or v.published_days_ago is None or v.published_days_ago <= filters.upload_window_days)
        ]

        limitations: list[str] = [
            "Content gaps no Studio sao tratados como hipoteses editorialmente nao validadas (podem indicar baixo volume).",
        ]
        if not captured_json:
            limitations.append("Nenhuma resposta JSON youtubei interceptada; extracao baseada em DOM/Shadow DOM.")

        return StudioExtractionResult(
            broad_topic=filters.broad_topic,
            terms=filtered_terms,
            videos=filtered_videos,
            captured_via="hybrid" if (captured_json and dom_cards) else ("network_json" if captured_json else "dom"),
            limitations=limitations,
        )


def extraction_fingerprint(result: StudioExtractionResult) -> str:
    raw = json.dumps(
        {
            "topic": result.broad_topic,
            "terms": [t.term for t in result.terms],
            "videos": [v.external_video_id for v in result.videos],
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
