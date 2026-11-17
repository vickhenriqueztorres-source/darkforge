"""Live Supabase SP-08 ProductionIntent gate, idempotency, manifest check & DARKFORGE_UNAVAILABLE test (T-DF-001)."""
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
def test_live_sp08_production_gate_and_honest_darkforge_block() -> None:
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
    email = f"sp08-{suffix}@darkforge.invalid"
    password = f"DfSp08!{suffix}99"
    user_ids: list[str] = []
    ws_ids: list[str] = []

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
        supabase_service_role_key=srv_key,
        database_url=db_url,
        darkforge_core_path="",
        darkforge_history_path=r"C:\Users\brend\Documents\DarkForge",
    )
    api_client = TestClient(create_app(settings=settings))

    try:
        with httpx.Client(timeout=20.0) as http:
            r_user = http.post(
                f"{url}/auth/v1/admin/users",
                headers=admin_headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            assert r_user.status_code in (200, 201), r_user.text
            user_ids.append(r_user.json()["id"])

            r_tok = http.post(
                f"{url}/auth/v1/token?grant_type=password",
                headers={"apikey": pub_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            )
            assert r_tok.status_code == 200, r_tok.text
            tok = r_tok.json()["access_token"]

        hdr = {"Authorization": f"Bearer {tok}"}
        ws_id = api_client.post("/api/v1/workspaces", headers=hdr, json={"name": f"WS8 {suffix}", "slug": f"ws8-{suffix}"}).json()["workspace"]["id"]
        ws_ids.append(ws_id)
        ws_hdr = {**hdr, "X-Workspace-Id": ws_id}

        ch_id = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr,
            json={
                "display_name": "Canal Producao",
                "profile": {
                    "name": "Canal Producao",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Documentario",
                    "positioning": "Factual",
                    "editorial_theme": "Historia",
                    "pillars": ["historia"],
                },
            },
        ).json()["channel"]["id"]

        opp_id = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr,
            json={"channel_id": ch_id, "topic_hint": "historia antiga"},
        ).json()["opportunity"]["id"]

        brief = api_client.post(
            "/api/v1/briefs",
            headers=ws_hdr,
            json={
                "opportunity_id": opp_id,
                "title": "Brief Producao SP-08",
                "hook": "Gancho inicial.",
                "angle": "Linha do tempo verificada.",
                "outline": [{"section": "Intro", "notes": "Contexto"}],
            },
        ).json()["brief"]

        # 1. Gateway health reports missing core honestly (and lists readonly historical manifests if present)
        health = api_client.get("/api/v1/production/health", headers=ws_hdr)
        assert health.status_code == 200
        assert health.json()["available"] is False
        assert health.json()["mode"] == "blocked_missing_core"

        # 2. DRAFT brief MUST NOT become production intent (PROD-001)
        draft_attempt = api_client.post(
            f"/api/v1/briefs/{brief['id']}/production",
            headers={**ws_hdr, "Idempotency-Key": f"idem-draft-{suffix}"},
            json={"pipeline_version": "media_vertical_v1"},
        )
        assert draft_attempt.status_code == 409, draft_attempt.text

        # 3. Approve brief -> create idempotent production intent + linked Job
        assert api_client.post(f"/api/v1/briefs/{brief['id']}/approve", headers=ws_hdr).status_code == 200
        idem = f"idem-prod-{suffix}"
        p1 = api_client.post(f"/api/v1/briefs/{brief['id']}/production", headers={**ws_hdr, "Idempotency-Key": idem})
        p2 = api_client.post(f"/api/v1/briefs/{brief['id']}/production", headers={**ws_hdr, "Idempotency-Key": idem})
        assert p1.status_code == 200, p1.text
        assert p1.json()["deduplicated"] is False
        assert p2.json()["deduplicated"] is True
        intent_id = p1.json()["intent"]["id"]
        assert p1.json()["intent"]["job_id"] is not None

        # 4. Dispatching without real DARKFORGE_CORE_PATH blocks honestly (503 DARKFORGE_UNAVAILABLE) and updates intent+job to BLOCKED
        disp = api_client.post(f"/api/v1/production/intents/{intent_id}/dispatch", headers=ws_hdr)
        assert disp.status_code == 503, disp.text
        assert disp.json()["code"] == "DARKFORGE_UNAVAILABLE"

        intents = api_client.get("/api/v1/production/intents", headers=ws_hdr).json()["items"]
        assert intents[0]["status"] == "BLOCKED"
        assert intents[0]["error_code"] == "DARKFORGE_UNAVAILABLE"

        # 5. DB constraint blocks READY without manifest_validated = true (PROD-005)
        with psycopg.connect(db_url) as conn, conn.cursor() as cur:
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(
                    "UPDATE public.production_intents SET status = 'READY' WHERE id = %s",
                    (intent_id,),
                )
            conn.rollback()
    finally:
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
