from __future__ import annotations

import urllib.parse
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from core.analytics.models import (
    AnalyticsBatchResult,
    CatalogPageResult,
    MetricAvailability,
    MetricFactInput,
    OAuthTokenBundle,
)
from core.analytics.ports import YouTubePlatformPort
from core.errors import AppError, ErrorCode

MIN_YOUTUBE_SCOPES = (
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


def _parse_iso_duration_seconds(raw: str | None) -> int | None:
    if not raw or not raw.startswith("PT"):
        return None
    total = 0
    num = ""
    for ch in raw[2:]:
        if ch.isdigit():
            num += ch
        elif ch in ("H", "M", "S") and num:
            val = int(num)
            num = ""
            if ch == "H":
                total += val * 3600
            elif ch == "M":
                total += val * 60
            else:
                total += val
    return total


class OfficialYouTubeAdapter(YouTubePlatformPort):
    """Official Google OAuth + YouTube Data API v3 + YouTube Analytics API v2 adapter (ADR-005)."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        timeout_seconds: float = 12.0,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._timeout = timeout_seconds
        self._transport = http_transport

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, transport=self._transport)

    def _require_oauth_creds(self) -> None:
        if not self._client_id or not self._client_secret:
            raise AppError(
                code=ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                message="Credenciais YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET nao configuradas.",
                http_status=412,
                details={"next_action": "Configure YOUTUBE_CLIENT_ID e YOUTUBE_CLIENT_SECRET no servidor."},
            )

    def build_authorize_url(self, state: str, code_challenge: str, redirect_uri: str) -> str:
        self._require_oauth_creds()
        params = urllib.parse.urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(MIN_YOUTUBE_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> OAuthTokenBundle:
        self._require_oauth_creds()
        try:
            with self._client() as client:
                resp = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "code": code,
                        "code_verifier": code_verifier,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha de rede ao trocar codigo OAuth.", http_status=503, retryable=True) from exc

        if resp.status_code >= 400:
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Autorizacao OAuth YouTube recusada ou expirada.", http_status=401)
        data = resp.json()
        expires_in = int(data.get("expires_in", 3600))
        scopes = str(data.get("scope", " ".join(MIN_YOUTUBE_SCOPES))).split()
        return OAuthTokenBundle(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scopes=scopes,
        )

    def refresh_access_token(self, refresh_token: str) -> OAuthTokenBundle:
        self._require_oauth_creds()
        try:
            with self._client() as client:
                resp = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Falha de rede no refresh OAuth.", http_status=503, retryable=True) from exc

        if resp.status_code in (400, 401):
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Refresh token OAuth expirado ou revogado.", http_status=401)
        if resp.status_code >= 500:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Provedor OAuth temporariamente indisponivel.", http_status=503, retryable=True)
        data = resp.json()
        expires_in = int(data.get("expires_in", 3600))
        return OAuthTokenBundle(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scopes=str(data.get("scope", " ".join(MIN_YOUTUBE_SCOPES))).split(),
        )

    def revoke_token(self, token: str) -> None:
        try:
            with self._client() as client:
                client.post("https://oauth2.googleapis.com/revoke", params={"token": token})
        except httpx.RequestError:
            pass

    def fetch_own_channel_and_videos_page(
        self, access_token: str, page_token: str | None = None, max_results: int = 25
    ) -> CatalogPageResult:
        headers = {"Authorization": f"Bearer {access_token}"}
        quota_cost = 0
        try:
            with self._client() as client:
                ch_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    headers=headers,
                    params={"part": "id,snippet,contentDetails,statistics", "mine": "true"},
                )
                quota_cost += 1
                self._check_yt_error(ch_resp)
                ch_items = ch_resp.json().get("items") or []
                if not ch_items:
                    return CatalogPageResult(external_channel_id="", videos=[], next_page_token=None, quota_cost=quota_cost)
                ch = ch_items[0]
                ext_channel_id = ch["id"]
                uploads_pl = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if not uploads_pl:
                    return CatalogPageResult(external_channel_id=ext_channel_id, videos=[], next_page_token=None, quota_cost=quota_cost)

                pl_params: dict[str, Any] = {"part": "snippet,contentDetails", "playlistId": uploads_pl, "maxResults": max_results}
                if page_token:
                    pl_params["pageToken"] = page_token
                pl_resp = client.get("https://www.googleapis.com/youtube/v3/playlistItems", headers=headers, params=pl_params)
                quota_cost += 1
                self._check_yt_error(pl_resp)
                pl_json = pl_resp.json()
                next_token = pl_json.get("nextPageToken")
                video_ids = [
                    it.get("contentDetails", {}).get("videoId")
                    for it in pl_json.get("items") or []
                    if it.get("contentDetails", {}).get("videoId")
                ]
                if not video_ids:
                    return CatalogPageResult(external_channel_id=ext_channel_id, videos=[], next_page_token=next_token, quota_cost=quota_cost)

                v_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    headers=headers,
                    params={"part": "snippet,contentDetails,statistics,status", "id": ",".join(video_ids)},
                )
                quota_cost += 1
                self._check_yt_error(v_resp)
                videos: list[dict[str, Any]] = []
                for item in v_resp.json().get("items") or []:
                    sn = item.get("snippet") or {}
                    cd = item.get("contentDetails") or {}
                    st = item.get("status") or {}
                    dur = _parse_iso_duration_seconds(cd.get("duration"))
                    fmt = "short" if (dur is not None and dur <= 60) else ("long" if dur is not None else "unknown")
                    thumbs = sn.get("thumbnails") or {}
                    thumb_url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
                    videos.append(
                        {
                            "external_video_id": item["id"],
                            "canonical_url": f"https://www.youtube.com/watch?v={item['id']}",
                            "title": sn.get("title", ""),
                            "description": sn.get("description", ""),
                            "format": fmt,
                            "duration_seconds": dur,
                            "published_at": sn.get("publishedAt"),
                            "thumbnail_url": thumb_url,
                            "privacy_status": st.get("privacyStatus", "unknown"),
                            "tags_json": sn.get("tags") or [],
                            "statistics": item.get("statistics") or {},
                        }
                    )
                return CatalogPageResult(
                    external_channel_id=ext_channel_id,
                    videos=videos,
                    next_page_token=next_token,
                    quota_cost=quota_cost,
                )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Erro de rede ao consultar YouTube Data API.", http_status=503, retryable=True) from exc

    def fetch_channel_analytics(
        self,
        access_token: str,
        external_channel_id: str,
        start_date: date,
        end_date: date,
        external_video_ids: list[str],
    ) -> AnalyticsBatchResult:
        headers = {"Authorization": f"Bearer {access_token}"}
        facts: list[MetricFactInput] = []
        partial_errors: list[dict[str, Any]] = []
        quota_cost = 0

        try:
            with self._client() as client:
                rep = client.get(
                    "https://youtubeanalytics.googleapis.com/v2/reports",
                    headers=headers,
                    params={
                        "ids": "channel==MINE",
                        "startDate": start_date.isoformat(),
                        "endDate": end_date.isoformat(),
                        "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost",
                    },
                )
                quota_cost += 2
                if rep.status_code == 200:
                    data = rep.json()
                    col_names = [c["name"] for c in data.get("columnHeaders") or []]
                    rows = data.get("rows") or []
                    mapping = {
                        "views": "yt.analytics.views",
                        "estimatedMinutesWatched": "yt.analytics.watch_time_minutes",
                        "averageViewDuration": "yt.analytics.avg_view_duration_sec",
                        "averageViewPercentage": "yt.analytics.avg_view_percentage",
                        "subscribersGained": "yt.analytics.subscribers_gained",
                        "subscribersLost": "yt.analytics.subscribers_lost",
                    }
                    values_by_col = dict(zip(col_names, rows[0])) if rows else {}
                    for api_col, metric_id in mapping.items():
                        raw_val = values_by_col.get(api_col)
                        if raw_val is None:
                            facts.append(
                                MetricFactInput(
                                    metric_id=metric_id,
                                    visibility_scope="private_authorized",
                                    source="youtube_analytics_api",
                                    period_start=start_date,
                                    period_end=end_date,
                                    granularity="period_total",
                                    dimensions_json={},
                                    availability=MetricAvailability.UNKNOWN,
                                    value_num=None,
                                )
                            )
                        else:
                            facts.append(
                                MetricFactInput(
                                    metric_id=metric_id,
                                    visibility_scope="private_authorized",
                                    source="youtube_analytics_api",
                                    period_start=start_date,
                                    period_end=end_date,
                                    granularity="period_total",
                                    dimensions_json={},
                                    availability=MetricAvailability.AVAILABLE,
                                    value_num=float(raw_val),
                                )
                            )
                elif rep.status_code == 401:
                    raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Token expirado ou revogado no Analytics API.", http_status=401)
                else:
                    partial_errors.append({"source": "youtube_analytics_api", "status": rep.status_code, "message": "Metricas privadas indisponiveis"})
                    for m_id in ("yt.analytics.views", "yt.analytics.watch_time_minutes"):
                        facts.append(
                            MetricFactInput(
                                metric_id=m_id,
                                visibility_scope="private_authorized",
                                source="youtube_analytics_api",
                                period_start=start_date,
                                period_end=end_date,
                                granularity="period_total",
                                dimensions_json={},
                                availability=MetricAvailability.UNKNOWN,
                                value_num=None,
                            )
                        )

                # Impressions & CTR often unavailable in standard Analytics API -> explicitly UNKNOWN
                for unavailable_id in ("yt.analytics.impressions", "yt.analytics.impressions_ctr"):
                    facts.append(
                        MetricFactInput(
                            metric_id=unavailable_id,
                            visibility_scope="private_authorized",
                            source="youtube_analytics_api",
                            period_start=start_date,
                            period_end=end_date,
                            granularity="period_total",
                            dimensions_json={},
                            availability=MetricAvailability.UNKNOWN,
                            value_num=None,
                        )
                    )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Erro de rede no YouTube Analytics API.", http_status=503, retryable=True) from exc

        return AnalyticsBatchResult(facts=facts, partial_errors=partial_errors, quota_cost=quota_cost)

    def fetch_public_channel_recent_view_counts(
        self,
        external_channel_id: str,
        *,
        api_key: str = "",
        access_token: str = "",
        max_videos: int = 20,
    ) -> tuple[list[int], int]:
        """Fetches recent public video view counts for Outlier baseline via official Data API v3."""
        if not external_channel_id or (not api_key.strip() and not access_token.strip()):
            return [], 0
        headers: dict[str, str] = {}
        auth_params: dict[str, str] = {}
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        elif api_key.strip():
            auth_params["key"] = api_key.strip()

        quota_cost = 0
        try:
            with self._client() as client:
                ch_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    headers=headers,
                    params={"part": "contentDetails", "id": external_channel_id, **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(ch_resp)
                items = ch_resp.json().get("items") or []
                if not items:
                    return [], quota_cost
                uploads_pl = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if not uploads_pl:
                    return [], quota_cost

                pl_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    headers=headers,
                    params={"part": "contentDetails", "playlistId": uploads_pl, "maxResults": min(50, max_videos), **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(pl_resp)
                vids = [
                    it.get("contentDetails", {}).get("videoId")
                    for it in (pl_resp.json().get("items") or [])
                    if it.get("contentDetails", {}).get("videoId")
                ]
                if not vids:
                    return [], quota_cost

                v_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    headers=headers,
                    params={"part": "statistics", "id": ",".join(vids), **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(v_resp)
                counts: list[int] = []
                for v in v_resp.json().get("items") or []:
                    vc = v.get("statistics", {}).get("viewCount")
                    if vc is not None:
                        counts.append(int(vc))
                return counts, quota_cost
        except httpx.RequestError:
            return [], quota_cost

    def fetch_channel_last_20_30_videos(
        self,
        external_channel_id: str,
        *,
        api_key: str = "",
        access_token: str = "",
        count: int = 25,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetches detailed metadata (views, publishedAt, duration, thumbnail) of last 20-30 videos."""
        if not external_channel_id or (not api_key.strip() and not access_token.strip()):
            return [], 0
        headers: dict[str, str] = {}
        auth_params: dict[str, str] = {}
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        elif api_key.strip():
            auth_params["key"] = api_key.strip()

        quota_cost = 0
        try:
            with self._client() as client:
                ch_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    headers=headers,
                    params={"part": "contentDetails,snippet", "id": external_channel_id, **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(ch_resp)
                items = ch_resp.json().get("items") or []
                if not items:
                    return [], quota_cost
                channel_name = items[0].get("snippet", {}).get("title") or external_channel_id
                uploads_pl = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
                if not uploads_pl:
                    return [], quota_cost

                pl_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/playlistItems",
                    headers=headers,
                    params={"part": "contentDetails", "playlistId": uploads_pl, "maxResults": max(20, min(30, count)), **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(pl_resp)
                vids = [
                    it.get("contentDetails", {}).get("videoId")
                    for it in (pl_resp.json().get("items") or [])
                    if it.get("contentDetails", {}).get("videoId")
                ]
                if not vids:
                    return [], quota_cost

                v_resp = client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    headers=headers,
                    params={"part": "snippet,statistics,contentDetails", "id": ",".join(vids), **auth_params},
                )
                quota_cost += 1
                self._check_yt_error(v_resp)
                now_utc = datetime.now(timezone.utc)
                results: list[dict[str, Any]] = []
                for v in v_resp.json().get("items") or []:
                    sn = v.get("snippet") or {}
                    st = v.get("statistics") or {}
                    cd = v.get("contentDetails") or {}
                    pub_raw = sn.get("publishedAt") or ""
                    days_ago = 30
                    if pub_raw:
                        try:
                            pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
                            days_ago = max(1, (now_utc - pub_dt).days)
                        except ValueError:
                            pass
                    thumbs = sn.get("thumbnails") or {}
                    thumb_url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
                    results.append(
                        {
                            "external_video_id": v["id"],
                            "external_channel_id": external_channel_id,
                            "channel_name": channel_name,
                            "title": sn.get("title", ""),
                            "views": int(st.get("viewCount") or 0),
                            "published_at_iso": pub_raw,
                            "days_since_upload": days_ago,
                            "duration_seconds": _parse_iso_duration_seconds(cd.get("duration")),
                            "thumbnail_url": thumb_url,
                        }
                    )
                return results, quota_cost
        except httpx.RequestError:
            return [], quota_cost

    def fetch_public_video_comments(
        self,
        external_video_id: str,
        *,
        api_key: str = "",
        access_token: str = "",
        max_results: int = 40,
    ) -> tuple[list[str], int]:
        """Fetches top public video comments via YouTube Data API v3 commentThreads.list for gap mining."""
        if not external_video_id or (not api_key.strip() and not access_token.strip()):
            return [], 0
        headers: dict[str, str] = {}
        auth_params: dict[str, str] = {}
        if access_token.strip():
            headers["Authorization"] = f"Bearer {access_token.strip()}"
        elif api_key.strip():
            auth_params["key"] = api_key.strip()
        try:
            with self._client() as client:
                resp = client.get(
                    "https://www.googleapis.com/youtube/v3/commentThreads",
                    headers=headers,
                    params={
                        "part": "snippet",
                        "videoId": external_video_id,
                        "order": "relevance",
                        "maxResults": max(1, min(100, max_results)),
                        "textFormat": "plainText",
                        **auth_params,
                    },
                )
                if resp.status_code >= 400:
                    return [], 1
                items = resp.json().get("items") or []
                comments = [
                    str(it.get("snippet", {}).get("topLevelComment", {}).get("snippet", {}).get("textDisplay") or "").strip()
                    for it in items
                ]
                return [c for c in comments if c], 1
        except httpx.RequestError:
            return [], 0

    @staticmethod
    def _check_yt_error(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Token YouTube expirado ou revogado.", http_status=401)
        if resp.status_code == 403:
            text = resp.text.lower()
            if "quotaexceeded" in text or "ratelimitexceeded" in text:
                raise AppError(ErrorCode.YOUTUBE_QUOTA_EXCEEDED, "Quota da API YouTube esgotada.", http_status=429, retryable=True)
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Escopo ou permissao YouTube insuficiente.", http_status=403)
        if resp.status_code >= 500:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "YouTube API temporariamente indisponivel.", http_status=503, retryable=True)
        if resp.status_code >= 400:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"Erro na API do YouTube ({resp.status_code}).", http_status=422)
