"""Live Supabase SP-10..SP-14 Studio Trends, Outlier Scoring, RLS & Opportunity Integration tests."""
from __future__ import annotations

import os
from uuid import uuid4

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app

load_dotenv()


def _env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


@pytest.mark.live_supabase
def test_live_sp13_studio_trends_outliers_opportunity_and_rls() -> None:
    url = _env("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
    pub_key = _env("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    srv_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    jwt_secret = _env("SUPABASE_JWT_SECRET")
    db_url = _env("DATABASE_URL")

    admin_headers = {
        "apikey": srv_key,
        "Authorization": f"Bearer {srv_key}",
        "Content-Type": "application/json",
    }
    suffix = uuid4().hex[:8]
    email_a = f"sp13-a-{suffix}@darkforge.invalid"
    email_b = f"sp13-b-{suffix}@darkforge.invalid"
    password = f"DfSp13!{suffix}99"
    user_ids: list[str] = []
    ws_ids: list[str] = []

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
        supabase_service_role_key=srv_key,
        database_url=db_url,
    )
    api_client = TestClient(create_app(settings=settings))

    try:
        with httpx.Client(timeout=20.0) as http:
            for mail in (email_a, email_b):
                r_user = http.post(
                    f"{url}/auth/v1/admin/users",
                    headers=admin_headers,
                    json={"email": mail, "password": password, "email_confirm": True},
                )
                assert r_user.status_code in (200, 201), r_user.text
                user_ids.append(r_user.json()["id"])

            def _login(mail: str) -> str:
                r_tok = http.post(
                    f"{url}/auth/v1/token?grant_type=password",
                    headers={"apikey": pub_key, "Content-Type": "application/json"},
                    json={"email": mail, "password": password},
                )
                assert r_tok.status_code == 200, r_tok.text
                return r_tok.json()["access_token"]

            tok_a = _login(email_a)
            tok_b = _login(email_b)

        hdr_a = {"Authorization": f"Bearer {tok_a}"}
        hdr_b = {"Authorization": f"Bearer {tok_b}"}

        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"StudioA {suffix}", "slug": f"ws13a-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"StudioB {suffix}", "slug": f"ws13b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])
        ws_hdr_a = {**hdr_a, "X-Workspace-Id": ws_a}

        ch_id = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr_a,
            json={
                "display_name": "Canal Studio Trends",
                "profile": {
                    "name": "Canal Studio Trends",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Historia",
                    "positioning": "Investigativo",
                    "editorial_theme": "Arquivos",
                    "pillars": ["arquivos secretos"],
                },
            },
        ).json()["channel"]["id"]

        # 1. Create Studio run queued (execute_now=False), verify linked Job created
        run_res = api_client.post(
            "/api/v1/research/studio-runs",
            headers={**ws_hdr_a, "Idempotency-Key": f"idem-st-{suffix}"},
            json={
                "channel_id": ch_id,
                "broad_topic": "arquivos secretos",
                "min_interest": "medium",
                "only_watched_by_my_viewers": True,
                "upload_window_days": 28,
                "min_outlier_ratio": 3.0,
                "execute_now": False,
            },
        )
        assert run_res.status_code == 201, run_res.text
        run_id = run_res.json()["run"]["id"]
        assert run_res.json()["run"]["job_id"] is not None

        # 2. Ingest captured Studio 5-block terms + videos & compute Outliers (6x vs 1.5x)
        ingest = api_client.post(
            f"/api/v1/research/studio-runs/{run_id}/ingest",
            headers=ws_hdr_a,
            json={
                "terms": [
                    {"term": "arquivos secretos 1945", "block_type": "top_search", "audience_interest": "very_high"},
                    {"term": "codice secreto desconhecido", "block_type": "content_gap", "audience_interest": "high"},
                ],
                "videos": [
                    {
                        "external_video_id": "out6x000001",
                        "title": "O Dossie de 1945 Que Mudou Tudo",
                        "external_channel_id": "UC_COMP_1",
                        "channel_name": "Canal Alpha",
                        "public_views": 60000,
                        "published_days_ago": 8,
                        "watched_by_my_viewers": True,
                    },
                    {
                        "external_video_id": "norm1500002",
                        "title": "Resumo Simples",
                        "external_channel_id": "UC_COMP_1",
                        "channel_name": "Canal Alpha",
                        "public_views": 15000,
                        "published_days_ago": 12,
                        "watched_by_my_viewers": True,
                    },
                ],
                "channel_baselines": {"UC_COMP_1": [9000, 10000, 11000, 10000]},
                "min_outlier_ratio": 3.0,
            },
        )
        assert ingest.status_code == 200, ingest.text
        detail = ingest.json()
        assert detail["run"]["status"] == "SUCCEEDED"
        assert len(detail["terms"]) == 2
        gap_term = [t for t in detail["terms"] if t["block_type"] == "content_gap"][0]
        assert gap_term["is_hypothesis"] is True

        outlier_viral = [o for o in detail["outliers"] if o["external_video_id"] == "out6x000001"][0]
        assert outlier_viral["outlier_ratio"] == 6.0
        assert outlier_viral["outlier_tier"] == "5x+"
        assert outlier_viral["watched_by_my_viewers"] is True

        # 3. Opportunity Engine consumes Studio Trends terms & >= 3x outliers as cited evidence!
        opp_res = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "topic_hint": "arquivos secretos"},
        )
        assert opp_res.status_code == 200, opp_res.text
        opp_json = opp_res.json()
        opp = opp_json["opportunity"]
        assert opp["insufficient_data"] is False
        ev_kinds = {e["source_kind"] for e in opp_json["evidence"]}
        assert "studio_trend_term" in ev_kinds
        assert "studio_outlier_video" in ev_kinds

        # 4. Cross-workspace isolation: User B blocked 403/404
        assert api_client.get(f"/api/v1/research/studio-runs/{run_id}", headers={**hdr_b, "X-Workspace-Id": ws_a}).status_code == 403
        assert api_client.get(f"/api/v1/research/studio-runs/{run_id}", headers={**hdr_b, "X-Workspace-Id": ws_b}).status_code == 404
    finally:
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
