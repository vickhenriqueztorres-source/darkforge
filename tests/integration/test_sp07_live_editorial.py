"""Live Supabase SP-07 Opportunity Engine, EpisodeBrief freeze/versioning (T-ED-001) & Calendar tests."""
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
def test_live_sp07_opportunities_brief_freeze_versions_export_and_isolation() -> None:
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
    email_a = f"sp07-a-{suffix}@darkforge.invalid"
    email_b = f"sp07-b-{suffix}@darkforge.invalid"
    password = f"DfSp07!{suffix}99"
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

        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"WS A {suffix}", "slug": f"ws7a-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"WS B {suffix}", "slug": f"ws7b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])

        ch_res = api_client.post(
            "/api/v1/channels",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={
                "display_name": "Misterios Hist",
                "profile": {
                    "name": "Misterios Hist",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Documentario historico",
                    "positioning": "Rigor factual",
                    "editorial_theme": "Arqueologia e arquivos",
                    "pillars": ["arqueologia", "arquivos reais"],
                },
            },
        )
        assert ch_res.status_code == 201, ch_res.text
        ch_id = ch_res.json()["channel"]["id"]

        # Seed approved L2 knowledge chunk so Opportunity Engine links real RAG evidence
        imp = api_client.post(
            "/api/v1/knowledge/sources",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={
                "title": "Hook Arquivos Perdidos",
                "source_type": "hook",
                "content_text": "[HOOK] Em 1924 um diario selado revelou a rota dos arquivos perdidos.\n[CTA] Assista a sequencia.",
                "rights_status": "owned",
                "channel_id": ch_id,
            },
        )
        assert imp.status_code in (200, 201), imp.text
        src_id = imp.json()["source"]["id"]
        assert api_client.post(
            f"/api/v1/knowledge/sources/{src_id}/review",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"curation_level": "L2", "status": "APPROVED"},
        ).status_code == 200
        assert api_client.post(
            "/api/v1/knowledge/reindex",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"force_new_revision": False},
        ).status_code == 200

        # 1. Generate opportunity + specialized analysts + explicit external fallback block (ADR-007)
        blocked_ext = api_client.post(
            "/api/v1/opportunities/generate",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"channel_id": ch_id, "topic_hint": "arquivos perdidos", "use_external": True, "external_consent_granted": False},
        )
        assert blocked_ext.status_code == 412, blocked_ext.text
        assert blocked_ext.json()["code"] == "AI_EXTERNAL_CONSENT_REQUIRED"

        gen_opp = api_client.post(
            "/api/v1/opportunities/generate",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"channel_id": ch_id, "topic_hint": "arquivos perdidos"},
        )
        assert gen_opp.status_code == 200, gen_opp.text
        opp = gen_opp.json()["opportunity"]
        assert opp["score_version"] == "v1.0.0"
        assert len(opp["analyst_reports_json"]) == 4

        # 2. Approve opportunity with feedback (no fine-tuning claimed)
        fb = api_client.post(
            f"/api/v1/opportunities/{opp['id']}/feedback",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"decision": "APPROVE", "reason_code": "fit_niche", "notes": "Excelente gancho"},
        )
        assert fb.status_code == 200, fb.text
        assert fb.json()["opportunity"]["status"] == "APPROVED"
        assert fb.json()["fine_tuning_claimed"] is False

        # 3. Create EpisodeBrief v1 -> edit draft -> approve & freeze -> verify freeze (T-ED-001)
        br = api_client.post(
            "/api/v1/briefs",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={
                "opportunity_id": opp["id"],
                "title": "Os Arquivos Perdidos de 1924",
                "hook": "O diario que ninguem leu ate hoje.",
                "angle": "Investigacao cronologica",
                "outline": [{"section": "Abertura", "notes": "Mostrar mapa"}],
                "cta": "Inscreva-se",
            },
        )
        assert br.status_code == 200, br.text
        v1 = br.json()["brief"]
        assert v1["version"] == 1
        assert v1["status"] == "DRAFT"

        app_res = api_client.post(
            f"/api/v1/briefs/{v1['id']}/approve",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"notes": "Pronto para congelamento"},
        )
        assert app_res.status_code == 200, app_res.text
        assert app_res.json()["brief"]["status"] == "APPROVED"

        # Trying to mutate frozen brief via API returns 409 CONFLICT
        upd_frozen = api_client.put(
            f"/api/v1/briefs/{v1['id']}",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"title": "Tentativa ilegal de mutacao"},
        )
        assert upd_frozen.status_code == 409, upd_frozen.text

        # Direct SQL UPDATE of title on APPROVED row also fails via Postgres freeze trigger!
        with psycopg.connect(db_url) as conn, conn.cursor() as cur:
            with pytest.raises(psycopg.errors.DataException):
                cur.execute("UPDATE public.episode_briefs SET title = 'Bypass' WHERE id = %s", (v1["id"],))
            conn.rollback()

        # Creating v2 creates new DRAFT version while keeping v1 intact
        v2_res = api_client.post(
            f"/api/v1/briefs/{v1['id']}/versions",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"title": "Os Arquivos Perdidos de 1924 (v2 Revisada)", "notes": "Ajuste pos-revisao"},
        )
        assert v2_res.status_code == 200, v2_res.text
        v2 = v2_res.json()["brief"]
        assert v2["version"] == 2
        assert len(v2_res.json()["versions"]) == 2

        # Export Markdown/JSON/CSV
        ex_md = api_client.get(f"/api/v1/briefs/{v1['id']}/export?format=markdown", headers={**hdr_a, "X-Workspace-Id": ws_a})
        assert ex_md.status_code == 200
        assert "Os Arquivos Perdidos de 1924" in ex_md.json()["content"]

        # Calendar item blocks auto_publish_enabled=true
        bad_cal = api_client.post(
            "/api/v1/calendar",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"channel_id": ch_id, "title": "Ep 01", "scheduled_for": "2026-11-25", "brief_id": v1["id"], "auto_publish_enabled": True},
        )
        assert bad_cal.status_code == 422

        ok_cal = api_client.post(
            "/api/v1/calendar",
            headers={**hdr_a, "X-Workspace-Id": ws_a},
            json={"channel_id": ch_id, "title": "Ep 01 Manual", "scheduled_for": "2026-11-25", "brief_id": v1["id"]},
        )
        assert ok_cal.status_code == 200
        assert ok_cal.json()["item"]["auto_publish_enabled"] is False

        # Cross-workspace isolation: User B cannot read User A brief/opportunity
        assert api_client.get(f"/api/v1/briefs/{v1['id']}", headers={**hdr_b, "X-Workspace-Id": ws_a}).status_code == 403
        assert api_client.get(f"/api/v1/briefs/{v1['id']}", headers={**hdr_b, "X-Workspace-Id": ws_b}).status_code == 404
    finally:
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
