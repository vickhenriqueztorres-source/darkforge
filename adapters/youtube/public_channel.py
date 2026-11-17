"""Coletor de dados PUBLICOS de canais YouTube (sem OAuth, sem worker, sem fila).

Estrategia em camadas, sempre honesta sobre a origem de cada numero:

1. ``YOUTUBE_API_KEY`` configurada -> YouTube Data API v3 (numeros exatos):
   channels.list (snippet, statistics, brandingSettings) + uploads playlist + videos.list.
   Custo aproximado: 3 unidades de cota por canal.
2. Sem chave (ou chave falhou) -> pagina publica do canal + feed RSS oficial:
   ID, nome, avatar, banner, inscritos (arredondados pelo YouTube), total de videos
   e os 15 ultimos uploads com thumbnail, views e likes. Custo de cota: zero.

O resultado inclui metricas derivadas (media/mediana de views, outliers, cadencia).
"""

from __future__ import annotations

import html
import re
import statistics
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from core.errors import AppError, ErrorCode

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    # Evita a tela de consentimento de cookies (EU) que esconde o HTML do canal.
    "Cookie": "CONSENT=YES+cb; SOCS=CAI",
}

_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")
_HANDLE_RE = re.compile(r"^@?[\w.\-]{3,100}$")
_ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


@dataclass(frozen=True)
class ChannelRef:
    """Referencia normalizada: ou um channel_id (UC...) ou um @handle."""

    channel_id: str | None = None
    handle: str | None = None

    @property
    def cache_key(self) -> str:
        return (self.channel_id or f"@{(self.handle or '').lower()}").strip()


def parse_channel_ref(raw: str | None) -> ChannelRef:
    """Aceita '@handle', 'handle', URL do canal (@, /channel/, /c/ com sufixos) ou 'UC...'."""
    value = (raw or "").strip()
    if not value:
        raise AppError(ErrorCode.VALIDATION_ERROR, "Informe o @handle ou a URL do canal.", http_status=422)

    value = re.sub(r"^https?://", "", value, flags=re.I)
    value = re.sub(r"^(www\.|m\.)?youtube\.com/?", "", value, flags=re.I)
    value = value.split("?")[0].split("#")[0].strip("/")

    if value.lower().startswith("channel/"):
        cid = value.split("/")[1] if "/" in value else ""
        if _CHANNEL_ID_RE.match(cid):
            return ChannelRef(channel_id=cid)
    if _CHANNEL_ID_RE.match(value):
        return ChannelRef(channel_id=value)

    first = value.split("/")[0]
    if first.lower() in ("c", "user") and "/" in value:
        first = value.split("/")[1]
    if _HANDLE_RE.match(first):
        return ChannelRef(handle=first.lstrip("@"))

    raise AppError(
        ErrorCode.VALIDATION_ERROR,
        "Formato de canal nao reconhecido. Use @handle, youtube.com/@handle ou o ID UC...",
        http_status=422,
        details={"field": "channel_ref"},
    )


def parse_compact_count(text: str | None) -> int | None:
    """'1.2K' -> 1200, '3,4M' -> 3400000, '142' -> 142."""
    if not text:
        return None
    m = re.match(r"^\s*([\d.,]+)\s*([KMB])?\s*$", text.strip(), flags=re.I)
    if not m:
        return None
    num_raw, suffix = m.group(1), (m.group(2) or "").upper()
    if suffix:
        num = float(num_raw.replace(",", "."))
    else:
        num = float(num_raw.replace(",", "").replace(".", ""))
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(round(num * mult))


def _parse_iso_duration(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", raw)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _to_int(val: Any) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _best_thumb(thumbs: dict[str, Any], video_id: str | None = None) -> str | None:
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = (thumbs.get(key) or {}).get("url")
        if url:
            return url
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None


class PublicChannelCollector:
    def __init__(
        self,
        api_key: str = "",
        cache_ttl_seconds: int = 900,
        timeout_seconds: float = 15.0,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._ttl = cache_ttl_seconds
        self._timeout = timeout_seconds
        self._transport = http_transport
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport, follow_redirects=True)

    # ------------------------------------------------------------------ public API

    def fetch_overview(self, ref: ChannelRef, *, force_refresh: bool = False, max_videos: int = 30) -> dict[str, Any]:
        key = f"{ref.cache_key}|{max_videos}"
        now = time.time()
        if not force_refresh:
            with self._lock:
                hit = self._cache.get(key)
            if hit and hit[0] > now:
                return {**hit[1], "cache": "hit"}

        warnings: list[str] = []
        overview: dict[str, Any] | None = None
        if self._api_key:
            try:
                overview = self._fetch_via_data_api(ref, max_videos=max_videos)
            except AppError as exc:
                if exc.code == ErrorCode.RESOURCE_NOT_FOUND:
                    raise
                warnings.append(f"Data API falhou ({exc.message}); usando página pública + RSS.")
        if overview is None:
            overview = self._fetch_via_public_page(ref)
            if not self._api_key:
                warnings.append(
                    "Sem YOUTUBE_API_KEY: inscritos arredondados pelo YouTube, views totais indisponíveis "
                    "e apenas os 15 últimos vídeos (RSS). Configure a chave no .env da API para números exatos."
                )

        self._mark_shorts_from_rss(overview)
        apply_format_thumbnails(overview["videos"])
        overview["insights"] = compute_insights(overview["videos"])
        overview["warnings"] = warnings + overview.get("warnings", [])
        overview["fetched_at"] = datetime.now(timezone.utc).isoformat()
        overview["cache"] = "miss"

        resolved_id = overview["channel"].get("channel_id")
        with self._lock:
            self._cache[key] = (now + self._ttl, overview)
            if resolved_id:
                self._cache[f"{resolved_id}|{max_videos}"] = (now + self._ttl, overview)
            # Mantem o cache pequeno (uso local, poucos canais).
            if len(self._cache) > 200:
                oldest = sorted(self._cache.items(), key=lambda kv: kv[1][0])[:50]
                for k, _ in oldest:
                    self._cache.pop(k, None)
        return overview

    # ------------------------------------------------------------------ Data API v3

    def _api_get(self, client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = client.get(f"https://www.googleapis.com/youtube/v3/{path}", params={**params, "key": self._api_key})
        if resp.status_code == 403:
            reason = ""
            try:
                reason = (resp.json().get("error", {}).get("errors") or [{}])[0].get("reason", "")
            except ValueError:
                pass
            if "quota" in reason.lower():
                raise AppError(ErrorCode.YOUTUBE_QUOTA_EXCEEDED, "Cota diaria da YouTube Data API esgotada.", http_status=429, retryable=True)
            raise AppError(ErrorCode.VALIDATION_ERROR, f"YOUTUBE_API_KEY recusada ({reason or 'forbidden'}).", http_status=403)
        if resp.status_code == 400:
            raise AppError(ErrorCode.VALIDATION_ERROR, "YOUTUBE_API_KEY invalida ou requisicao recusada.", http_status=400)
        if resp.status_code >= 500:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "YouTube Data API indisponivel.", http_status=503, retryable=True)
        resp.raise_for_status()
        return resp.json()

    def _fetch_via_data_api(self, ref: ChannelRef, *, max_videos: int) -> dict[str, Any]:
        try:
            with self._client() as client:
                params: dict[str, Any] = {"part": "snippet,statistics,contentDetails,brandingSettings"}
                if ref.channel_id:
                    params["id"] = ref.channel_id
                else:
                    params["forHandle"] = f"@{ref.handle}"
                items = self._api_get(client, "channels", params).get("items") or []
                if not items:
                    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado no YouTube.", http_status=404)
                ch = items[0]
                sn = ch.get("snippet") or {}
                st = ch.get("statistics") or {}
                branding = (ch.get("brandingSettings") or {}).get("image") or {}
                uploads = (ch.get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")

                video_ids: list[str] = []
                if uploads:
                    pl = self._api_get(
                        client,
                        "playlistItems",
                        {"part": "contentDetails", "playlistId": uploads, "maxResults": min(50, max_videos)},
                    )
                    video_ids = [
                        it["contentDetails"]["videoId"]
                        for it in pl.get("items") or []
                        if (it.get("contentDetails") or {}).get("videoId")
                    ]

                videos: list[dict[str, Any]] = []
                if video_ids:
                    vr = self._api_get(
                        client,
                        "videos",
                        {"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)},
                    )
                    for it in vr.get("items") or []:
                        vsn = it.get("snippet") or {}
                        vst = it.get("statistics") or {}
                        dur = _parse_iso_duration((it.get("contentDetails") or {}).get("duration"))
                        videos.append(
                            {
                                "video_id": it["id"],
                                "url": f"https://www.youtube.com/watch?v={it['id']}",
                                "title": vsn.get("title", ""),
                                "published_at": vsn.get("publishedAt"),
                                "thumbnail_url": _best_thumb(vsn.get("thumbnails") or {}, it["id"]),
                                "duration_seconds": dur,
                                "format": "short" if (dur is not None and dur <= 60) else ("long" if dur else "unknown"),
                                "views": _to_int(vst.get("viewCount")),
                                "likes": _to_int(vst.get("likeCount")),
                                "comments": _to_int(vst.get("commentCount")),
                                "live": vsn.get("liveBroadcastContent") not in (None, "none"),
                            }
                        )
                    videos.sort(key=lambda v: v.get("published_at") or "", reverse=True)

                hidden_subs = bool(st.get("hiddenSubscriberCount"))
                return {
                    "source": "youtube_data_api_v3",
                    "channel": {
                        "channel_id": ch["id"],
                        "handle": (sn.get("customUrl") or (f"@{ref.handle}" if ref.handle else None)),
                        "title": sn.get("title", ""),
                        "description": sn.get("description", ""),
                        "avatar_url": _best_thumb(sn.get("thumbnails") or {}),
                        "banner_url": branding.get("bannerExternalUrl"),
                        "country": sn.get("country"),
                        "created_at": sn.get("publishedAt"),
                        "url": f"https://www.youtube.com/channel/{ch['id']}",
                    },
                    "stats": {
                        "subscribers": None if hidden_subs else _to_int(st.get("subscriberCount")),
                        "subscribers_approximate": not hidden_subs,  # A API arredonda para 3 digitos significativos
                        "subscribers_hidden": hidden_subs,
                        "total_views": _to_int(st.get("viewCount")),
                        "video_count": _to_int(st.get("videoCount")),
                    },
                    "videos": videos,
                    "quota_cost": 3 if video_ids else 2,
                    "warnings": [],
                }
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha de rede ao consultar a YouTube Data API.", http_status=503, retryable=True) from exc

    # ------------------------------------------------------------------ Public page + RSS

    def _fetch_channel_page(self, client: httpx.Client, ref: ChannelRef) -> str:
        path = f"channel/{ref.channel_id}" if ref.channel_id else f"@{ref.handle}"
        resp = client.get(f"https://www.youtube.com/{path}", params={"hl": "en", "gl": "US"}, headers=_BROWSER_HEADERS)
        if resp.status_code == 404:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado no YouTube.", http_status=404)
        if resp.status_code >= 400:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, f"YouTube respondeu HTTP {resp.status_code}.", http_status=503, retryable=True)
        return resp.text

    def _fetch_via_public_page(self, ref: ChannelRef) -> dict[str, Any]:
        try:
            with self._client() as client:
                page = self._fetch_channel_page(client, ref)
                info = parse_channel_page(page)
                channel_id = info.get("channel_id") or ref.channel_id
                if not channel_id:
                    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Canal nao encontrado no YouTube.", http_status=404)
                videos = self._fetch_rss_videos(client, channel_id)
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha de rede ao acessar youtube.com.", http_status=503, retryable=True) from exc

        return {
            "source": "public_page_rss",
            "channel": {
                "channel_id": channel_id,
                "handle": info.get("handle") or (f"@{ref.handle}" if ref.handle else None),
                "title": info.get("title") or "",
                "description": info.get("description") or "",
                "avatar_url": info.get("avatar_url"),
                "banner_url": info.get("banner_url"),
                "country": None,
                "created_at": None,
                "url": f"https://www.youtube.com/channel/{channel_id}",
            },
            "stats": {
                "subscribers": info.get("subscribers"),
                "subscribers_approximate": True,
                "subscribers_hidden": info.get("subscribers") is None,
                "total_views": None,
                "video_count": info.get("video_count"),
            },
            "videos": videos,
            "quota_cost": 0,
            "warnings": [],
        }

    def _fetch_rss_videos(self, client: httpx.Client, channel_id: str) -> list[dict[str, Any]]:
        resp = client.get("https://www.youtube.com/feeds/videos.xml", params={"channel_id": channel_id})
        if resp.status_code >= 400:
            return []
        return parse_rss_feed(resp.text)

    def _mark_shorts_from_rss(self, overview: dict[str, Any]) -> None:
        """O RSS publica Shorts com link /shorts/ID; usamos isso para corrigir o formato (gratuito)."""
        if overview.get("source") == "public_page_rss":
            return
        channel_id = overview["channel"].get("channel_id")
        if not channel_id:
            return
        try:
            with self._client() as client:
                rss = self._fetch_rss_videos(client, channel_id)
        except httpx.RequestError:
            return
        shorts = {v["video_id"] for v in rss if v.get("format") == "short"}
        longs = {v["video_id"] for v in rss if v.get("format") == "long"}
        for v in overview["videos"]:
            if v["video_id"] in shorts:
                v["format"] = "short"
            elif v["video_id"] in longs:
                v["format"] = "long"


def parse_channel_page(page: str) -> dict[str, Any]:
    def meta(prop: str) -> str | None:
        m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', page)
        return html.unescape(m.group(1)) if m else None

    cid = re.search(r'"externalId":"(UC[\w-]{22})"', page) or re.search(
        r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page
    )
    handle = re.search(r'"canonicalBaseUrl":"/(@[^"]+)"', page) or re.search(r'"vanityChannelUrl":"https?://www\.youtube\.com/(@[^"]+)"', page)
    # Os contadores ficam no metadataParts do cabecalho: {"text":{"content":"93 videos"}}
    subs = re.search(r'"content":"([\d.,]+[KMB]?) subscribers?"', page) or re.search(r'"([\d.,]+[KMB]?) subscribers?"', page)
    vids = re.search(r'"content":"([\d.,]+[KMB]?) videos?"', page)
    banner = re.search(r'"imageBannerViewModel":\{"image":\{"sources":\[\{"url":"([^"]+)"', page)

    banner_url = banner.group(1).replace("\\u0026", "&") if banner else None

    return {
        "channel_id": cid.group(1) if cid else None,
        "handle": html.unescape(handle.group(1)) if handle else None,
        "title": meta("og:title"),
        "description": meta("og:description"),
        "avatar_url": meta("og:image"),
        "banner_url": banner_url,
        "subscribers": parse_compact_count(subs.group(1)) if subs else None,
        "video_count": parse_compact_count(vids.group(1)) if vids else None,
    }


def parse_rss_feed(xml_text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        vid = entry.findtext("yt:videoId", default="", namespaces=_ATOM_NS)
        if not vid:
            continue
        link_el = entry.find("atom:link", _ATOM_NS)
        href = link_el.get("href", "") if link_el is not None else ""
        group = entry.find("media:group", _ATOM_NS)
        thumb = None
        views = likes = None
        if group is not None:
            th = group.find("media:thumbnail", _ATOM_NS)
            thumb = th.get("url") if th is not None else None
            stats_el = group.find("media:community/media:statistics", _ATOM_NS)
            rating_el = group.find("media:community/media:starRating", _ATOM_NS)
            views = _to_int(stats_el.get("views")) if stats_el is not None else None
            likes = _to_int(rating_el.get("count")) if rating_el is not None else None
        out.append(
            {
                "video_id": vid,
                "url": href or f"https://www.youtube.com/watch?v={vid}",
                "title": entry.findtext("atom:title", default="", namespaces=_ATOM_NS),
                "published_at": entry.findtext("atom:published", default=None, namespaces=_ATOM_NS),
                "thumbnail_url": re.sub(r"//i\d\.ytimg\.com", "//i.ytimg.com", thumb or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"),
                "duration_seconds": None,
                "format": "short" if "/shorts/" in href else "long",
                "views": views,
                "likes": likes,
                "comments": None,
                "live": False,
            }
        )
    return out


def apply_format_thumbnails(videos: list[dict[str, Any]]) -> None:
    """hqdefault/sddefault sao 4:3 com faixas pretas. Shorts tem capa vertical (oardefault, 9:16);
    longos tem hq720 (16:9 HD). hqdefault fica como fallback garantido."""
    for v in videos:
        vid = v["video_id"]
        v["thumbnail_fallback_url"] = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        if v.get("format") == "short":
            v["thumbnail_url"] = f"https://i.ytimg.com/vi/{vid}/oardefault.jpg"
        else:
            v["thumbnail_url"] = f"https://i.ytimg.com/vi/{vid}/hq720.jpg"


def _age_days(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, (now - dt).total_seconds() / 86400)


def compute_insights(videos: list[dict[str, Any]]) -> dict[str, Any]:
    """Metricas derivadas; cada video ganha outlier_ratio contra a mediana do MESMO formato."""
    now = datetime.now(timezone.utc)
    by_format: dict[str, list[int]] = {}
    for v in videos:
        v["age_days"] = _age_days(v.get("published_at"), now)
        if v.get("views") is not None:
            by_format.setdefault(v.get("format") or "unknown", []).append(v["views"])

    medians = {fmt: statistics.median(vals) for fmt, vals in by_format.items() if vals}
    for v in videos:
        med = medians.get(v.get("format") or "unknown")
        views = v.get("views")
        v["outlier_ratio"] = round(views / med, 2) if (views is not None and med) else None
        likes, comments = v.get("likes"), v.get("comments")
        if views:
            eng = (likes or 0) + (comments or 0)
            v["engagement_rate"] = round(eng / views * 100, 2) if (likes is not None or comments is not None) else None
        else:
            v["engagement_rate"] = None

    all_views = [v["views"] for v in videos if v.get("views") is not None]
    ages = sorted(a for a in (v.get("age_days") for v in videos) if a is not None)
    gaps = [ages[i + 1] - ages[i] for i in range(len(ages) - 1)]
    best = max((v for v in videos if v.get("views") is not None), key=lambda v: v["views"], default=None)
    engagement = [v["engagement_rate"] for v in videos if v.get("engagement_rate") is not None]

    return {
        "sample_size": len(videos),
        "views_sum": sum(all_views) if all_views else None,
        "views_avg": round(statistics.mean(all_views)) if all_views else None,
        "views_median": round(statistics.median(all_views)) if all_views else None,
        "median_by_format": {k: round(v) for k, v in medians.items()},
        "shorts_count": sum(1 for v in videos if v.get("format") == "short"),
        "longs_count": sum(1 for v in videos if v.get("format") == "long"),
        "uploads_last_30d": sum(1 for a in ages if a <= 30),
        "days_since_last_upload": round(ages[0], 1) if ages else None,
        "avg_days_between_uploads": round(statistics.mean(gaps), 1) if gaps else None,
        "engagement_rate_avg": round(statistics.mean(engagement), 2) if engagement else None,
        "best_video_id": best["video_id"] if best else None,
        "outliers": [
            v["video_id"]
            for v in sorted(videos, key=lambda x: x.get("outlier_ratio") or 0, reverse=True)
            if (v.get("outlier_ratio") or 0) >= 2
        ][:6],
    }
