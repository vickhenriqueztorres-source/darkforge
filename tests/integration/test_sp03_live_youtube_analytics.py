"""Live Supabase Postgres SP-03 tests (T-YT-001..003, T-AN-001)."""
from __future__ import annotations

import base64
import os
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from adapters.supabase_db.analytics_repo import PostgresAnalyticsRepository
from adapters.youtube.client import OfficialYouTubeAdapter
from adapters.youtube.token_vault import TokenVault
from apps.api.config import Settings
from apps.api.dependencies import build_default_container
from apps.api.main import create_app
from core.analytics.models import MetricAvailability, MetricFactInput, QuotaPool, RetentionPolicy
from core.analytics.service import AnalyticsService
from core.errors import AppError, ErrorCode

load_dotenv()


def _env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


@pytest.mark.live_supabase
def test_live_youtube_oauth_sync_cursor_quota_and_unknown_metrics() -> None:
    url = _env("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
    pub_key = _env("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    srv_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    jwt_secret = _env("SUPABASE_JWT_SECRET")
    db_url = _env("DATABASE_URL")
    enc_key = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip() or base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

    admin_headers = {
        "apikey": srv_key,
        "Authorization": f"Bearer {srv_key}",
        "Content-Type": "application/json",
    }

    suffix = uuid4().hex[:8]
    email = f"sp03-{suffix}@darkforge.invalid"
    password = f"DfSp03!{suffix}99"
    user_ids: list[str] = []
    ws_ids: list[str] = []

    views_metric_value = 1250

    def mock_yt_handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if "oauth2.googleapis.com/token" in u:
            body = request.content.decode("utf-8")
            if "grant_type=refresh_token" in body:
                return httpx.Response(200, json={"access_token": "acc-refreshed", "expires_in": 3600})
            return httpx.Response(200, json={"access_token": "acc-initial", "refresh_token": "ref-1", "expires_in": 3600})
        if "oauth2.googleapis.com/revoke" in u:
            return httpx.Response(200)
        if "youtube/v3/channels" in u:
            return httpx.Response(200, json={"items": [{"id": "UC_TEST_1", "contentDetails": {"relatedPlaylists": {"uploads": "UU_TEST_1"}}}]})
        if "youtube/v3/playlistItems" in u:
            if "pageToken=PAGE2" in u:
                return httpx.Response(200, json={"items": [{"contentDetails": {"videoId": f"vid2_{suffix}"}}]})
            return httpx.Response(200, json={"nextPageToken": "PAGE2", "items": [{"contentDetails": {"videoId": f"vid1_{suffix}"}}]})
        if "youtube/v3/videos" in u:
            vid = request.url.params["id"].split(",")[0]
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": vid,
                            "snippet": {"title": f"Video {vid}", "description": "Desc", "publishedAt": "2026-11-10T12:00:00Z"},
                            "contentDetails": {"duration": "PT8M10S"},
                            "status": {"privacyStatus": "public"},
                            "statistics": {"viewCount": "500"},  # likeCount/commentCount omitted -> UNKNOWN!
                        }
                    ]
                },
            )
        if "youtubeanalytics.googleapis.com/v2/reports" in u:
            return httpx.Response(
                200,
                json={
                    "columnHeaders": [{"name": "views"}, {"name": "estimatedMinutesWatched"}],
                    "rows": [[views_metric_value, 4200]],
                },
            )
        return httpx.Response(404)

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
        supabase_service_role_key=srv_key,
        database_url=db_url,
        token_encryption_key=enc_key,
        youtube_client_id="yt-client-test",
        youtube_client_secret="yt-secret-test",
    )
    container = build_default_container(settings)
    repo = PostgresAnalyticsRepository(db_url, TokenVault(enc_key), daily_quota_limit=100, own_sync_reserved_units=40)
    yt = OfficialYouTubeAdapter("yt-client-test", "yt-secret-test", http_transport=httpx.MockTransport(mock_yt_handler))
    container.analytics = AnalyticsService(container.workspaces, repo, yt, command_bus=container.command_bus)
    api_client = TestClient(create_app(settings=settings, container=container))

    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.post(
                f"{url}/auth/v1/admin/users",
                headers=admin_headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            assert r.status_code in (200, 201), r.text
            user_ids.append(r.json()["id"])

            tok = client.post(
                f"{url}/auth/v1/token?grant_type=password",
                headers={"apikey": pub_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            ).json()["access_token"]

            ws_resp = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok}"},
                json={"name": f"SP03 WS {suffix}", "slug": f"sp03-{suffix}"},
            )
            assert ws_resp.status_code == 201, ws_resp.text
            ws_id = ws_resp.json()["workspace"]["id"]
            ws_ids.append(ws_id)

            ch_id = api_client.post(
                "/api/v1/channels",
                headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
                json={
                    "display_name": "Canal SP03",
                    "profile": {"name": "Canal SP03", "language": "pt-BR", "country": "BR", "timezone": "America/Sao_Paulo", "niche": "Doc"},
                },
            ).json()["channel"]["id"]

            # --- T-YT-001: OAuth PKCE start + callback + secret isolation ---
            auth_res = api_client.post(
                "/api/v1/connections/youtube/authorize",
                headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
                json={"channel_id": ch_id},
            )
            assert auth_res.status_code == 200
            state = auth_res.json()["state"]

            cb_res = api_client.post(
                "/api/v1/connections/youtube/callback",
                headers={"Authorization": f"Bearer {tok}"},
                json={"state": state, "code": "auth-code-123"},
            )
            assert cb_res.status_code == 200, cb_res.text
            conn_id = UUID(cb_res.json()["connection"]["id"])

            # Authenticated user JWT cannot read platform_connection_secrets directly
            secret_probe = client.get(
                f"{url}/rest/v1/platform_connection_secrets?connection_id=eq.{conn_id}",
                headers={"apikey": pub_key, "Authorization": f"Bearer {tok}"},
            )
            assert secret_probe.status_code in (401, 403), secret_probe.text

            # --- T-YT-002 & T-AN-001: Multi-page atomic sync + unknown != 0 + revision preservation ---
            s_date = date(2026, 11, 1)
            e_date = date(2026, 11, 15)
            sync1 = container.analytics.execute_sync_unit(
                UUID(ws_id), conn_id, UUID(ch_id), max_pages=2, start_date=s_date, end_date=e_date
            )
            assert sync1["videos_upserted"] == 2

            # Revision update (late revised analytics) preserves rev 1 and writes rev 2
            views_metric_value = 1500
            container.analytics.execute_sync_unit(
                UUID(ws_id), conn_id, UUID(ch_id), max_pages=1, start_date=s_date, end_date=e_date
            )

            ch_an = api_client.get(
                f"/api/v1/channels/{ch_id}/analytics?start_date={s_date.isoformat()}&end_date={e_date.isoformat()}",
                headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
            )
            assert ch_an.status_code == 200, ch_an.text
            metrics_by_id = {m["metric_id"]: m for m in ch_an.json()["metrics"]}
            assert metrics_by_id["yt.analytics.views"]["value_num"] == 1500.0
            assert metrics_by_id["yt.analytics.views"]["source_revision"] == 2
            # Missing CTR/Impressions MUST be unknown and value_num=None (never 0!)
            assert metrics_by_id["yt.analytics.impressions_ctr"]["availability"] == "unknown"
            assert metrics_by_id["yt.analytics.impressions_ctr"]["value_num"] is None

            # Video detail shows public_likes as unknown (omitted in mock)
            v_id = ch_an.json()["videos"][0]["id"]
            v_det = api_client.get(
                f"/api/v1/videos/{v_id}",
                headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
            )
            assert v_det.status_code == 200
            v_metrics = {m["metric_id"]: m for m in v_det.json()["metrics"]}
            assert v_metrics["yt.video.public_likes"]["availability"] == "unknown"
            assert v_metrics["yt.video.public_likes"]["value_num"] is None

            # --- T-YT-003: Quota priority: public_research hits ceiling before starving own_sync ---
            # limit=100, own_sync_reserved=40 -> research ceiling = 60
            summary = repo.get_quota_summary(UUID(ws_id))
            research_headroom = max(0, 60 - summary["public_research_used"])
            if research_headroom > 0:
                res_ok = repo.reserve_quota(UUID(ws_id), QuotaPool.PUBLIC_RESEARCH, "search", research_headroom, uuid4())
                repo.commit_quota(res_ok, research_headroom)
            with pytest.raises(AppError) as q_exc:
                repo.reserve_quota(UUID(ws_id), QuotaPool.PUBLIC_RESEARCH, "search", 1, uuid4())
            assert q_exc.value.code == ErrorCode.YOUTUBE_QUOTA_EXCEEDED

            # own_sync can STILL reserve from the 40 reserved units!
            own_res = repo.reserve_quota(UUID(ws_id), QuotaPool.OWN_SYNC, "own_sync", 10, uuid4())
            repo.commit_quota(own_res, 10)

            # --- Disconnect with purge deletes secrets and videos, keeps Supabase Auth alive ---
            disc = api_client.delete(
                f"/api/v1/connections/{conn_id}?retention_policy=purge_synced_data",
                headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
            )
            assert disc.status_code == 200
            assert disc.json()["tokens_deleted"] is True
            assert disc.json()["purged_videos"] == 2
    finally:
        import psycopg
        with psycopg.connect(db_url) as conn:
            for ws_id in ws_ids:
                conn.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
            conn.commit()
        with httpx.Client(timeout=10.0) as client:
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
