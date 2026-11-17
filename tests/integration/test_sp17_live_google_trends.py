"""Live Supabase SP-15..SP-18 Google Trends validation, CSV import, 24h cache, Opportunity penalty/boost & RLS tests."""
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
def test_live_sp17_google_trends_csv_cache_opportunity_penalty_and_rls() -> None:
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
    email_a = f"sp17-a-{suffix}@darkforge.invalid"
    email_b = f"sp17-b-{suffix}@darkforge.invalid"
    password = f"DfSp17!{suffix}99"
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

        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"GT A {suffix}", "slug": f"ws17a-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"GT B {suffix}", "slug": f"ws17b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])
        ws_hdr_a = {**hdr_a, "X-Workspace-Id": ws_a}

        ch_id = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr_a,
            json={
                "display_name": "Canal Trends BR",
                "profile": {
                    "name": "Canal Trends BR",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Documentarios IA",
                    "positioning": "Evergreen",
                    "editorial_theme": "IA",
                    "pillars": ["ia aplicada"],
                },
            },
        ).json()["channel"]["id"]

        # 1. Import SUSTAINABLE_GO + Breakout (>5000%) CSV for "ia aplicada"
        tl_12m_ok = "\n".join(["Semana,ia aplicada"] + [f"2026-{m:02d}-01,{35 + m * 5}" for m in range(1, 13)])
        tl_5y_ok = "\n".join(
            ["Mes,ia aplicada"] + [f"{2022 + i // 12}-{(i % 12) + 1:02d}-01,{45 + (i % 6) * 4}" for i in range(60)]
        )
        rel_csv = "Principais\nia aplicada tutorial,100\n\nEm ascensão\nia aplicada agentes 2026,Mais de 5.000%\nedicao ia,+210%\n"

        imp_ok = api_client.post(
            "/api/v1/research/google-trends/import-csv",
            headers=ws_hdr_a,
            json={
                "keyword": "ia aplicada",
                "channel_id": ch_id,
                "geo": "BR",
                "gprop": "youtube",
                "timeline_12m_csv": tl_12m_ok,
                "timeline_5y_csv": tl_5y_ok,
                "related_queries_csv": rel_csv,
            },
        )
        assert imp_ok.status_code == 200, imp_ok.text
        v_ok = imp_ok.json()["validation"]
        assert v_ok["verdict"] == "SUSTAINABLE_GO"
        assert len(v_ok["breakout_queries_json"]) == 1

        # 2. Calling /validate for same keyword hits 24h cache without hitting network
        cached_res = api_client.post(
            "/api/v1/research/google-trends/validate",
            headers=ws_hdr_a,
            json={"keyword": "ia aplicada", "channel_id": ch_id, "gprop": "youtube"},
        )
        assert cached_res.status_code == 200, cached_res.text
        assert cached_res.json()["cached"] is True

        # 3. Generate Opportunity on "ia aplicada" -> boosts score & cites google_trends_validation
        opp_go = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "topic_hint": "ia aplicada"},
        )
        assert opp_go.status_code == 200, opp_go.text
        go_ev = {e["source_kind"] for e in opp_go.json()["evidence"]}
        assert "google_trends_validation" in go_ev
        score_go = float(opp_go.json()["opportunity"]["score"])

        # 4. Import AVOID_DEAD_PEAK CSV for "pico morto 2024" -> Opportunity gets penalized!
        tl_12m_dead = "\n".join(["Semana,pico morto"] + [f"2026-{m:02d}-01,{max(1, 70 - m * 8)}" for m in range(1, 13)])
        vals_dead = [2] * 24 + [100, 80, 20] + [2] * 33
        tl_5y_dead = "\n".join(["Mes,pico morto"] + [f"{2022 + i // 12}-{(i % 12) + 1:02d}-01,{v}" for i, v in enumerate(vals_dead)])

        imp_dead = api_client.post(
            "/api/v1/research/google-trends/import-csv",
            headers=ws_hdr_a,
            json={
                "keyword": "pico morto 2024",
                "channel_id": ch_id,
                "geo": "BR",
                "gprop": "youtube",
                "timeline_12m_csv": tl_12m_dead,
                "timeline_5y_csv": tl_5y_dead,
                "related_queries_csv": "",
            },
        )
        assert imp_dead.status_code == 200
        assert imp_dead.json()["validation"]["verdict"] == "AVOID_DEAD_PEAK"

        opp_dead = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "topic_hint": "pico morto 2024"},
        ).json()["opportunity"]
        assert float(opp_dead["score"]) < score_go
        assert any("PICO MORTO" in lim for lim in opp_dead["limitations_json"])

        # 5. Cross-workspace RLS isolation
        assert api_client.get("/api/v1/research/google-trends", headers={**hdr_b, "X-Workspace-Id": ws_a}).status_code == 403
        assert len(api_client.get("/api/v1/research/google-trends", headers={**hdr_b, "X-Workspace-Id": ws_b}).json()["items"]) == 0
    finally:
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
