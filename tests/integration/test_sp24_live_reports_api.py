"""Live Supabase SP-24 Consolidated Reports Overview & Executive Markdown tests."""
from __future__ import annotations

import json
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
def test_live_reports_overview_executive_markdown_and_rls() -> None:
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
    email_a = f"sp24-a-{suffix}@darkforge.invalid"
    email_b = f"sp24-b-{suffix}@darkforge.invalid"
    password = f"DfSp24!{suffix}99"
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

        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"Rep A {suffix}", "slug": f"ws24a-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"Rep B {suffix}", "slug": f"ws24b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])
        ws_hdr_a = {**hdr_a, "X-Workspace-Id": ws_a}

        r_ch = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr_a,
            json={
                "display_name": "Canal Relatorio Live",
                "handle": f"@relatorio_{suffix}",
                "profile": {
                    "name": "Canal Relatorio Live",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "historia antiga",
                    "positioning": "Documentarios e colapsos",
                    "editorial_theme": "Cidades perdidas",
                    "pillars": ["historia", "misterio"],
                },
            },
        )
        assert r_ch.status_code == 201, r_ch.text
        ch_id = r_ch.json()["channel"]["id"]

        r_p1 = api_client.post(
            "/api/v1/research/reverse-engineering/phase1-channels",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "target_language": "pt-BR",
                "target_country": "BR",
                "feasible_formats": ["faceless_essay"],
                "target_audience_tags": ["historia"],
                "candidates": [
                    {
                        "external_channel_id": "UC-REL-1",
                        "display_name": "Cronica Oculta",
                        "language": "pt-BR",
                        "market_country": "BR",
                        "recent_video_views_90d": [52000, 44000, 39000],
                        "all_recent_20_30_views": [5000] * 20 + [52000, 44000, 39000],
                        "production_format": "faceless_essay",
                        "audience_profile_tags": ["historia"],
                        "is_celebrity_or_mega_brand": False,
                    }
                ],
            },
        )
        assert r_p1.status_code == 200, r_p1.text

        baseline = [
            {
                "external_video_id": f"vbase1-{i}",
                "external_channel_id": "UC-REL-1",
                "channel_name": "Cronica Oculta",
                "title": f"Video Base {i}",
                "views": 4000,
                "days_since_upload": 40 + i,
                "topic": "historia",
                "format_name": "long",
            }
            for i in range(18)
        ] + [
            {
                "external_video_id": f"vbase2-{i}",
                "external_channel_id": "UC-REL-2",
                "channel_name": "Arquivo Passado",
                "title": f"Arquivo Base {i}",
                "views": 3500,
                "days_since_upload": 45 + i,
                "topic": "historia",
                "format_name": "long",
            }
            for i in range(15)
        ]
        r_p2 = api_client.post(
            "/api/v1/research/reverse-engineering/phase2-outliers",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "videos": baseline
                + [
                    {
                        "external_video_id": "vout1",
                        "external_channel_id": "UC-REL-1",
                        "channel_name": "Cronica Oculta",
                        "title": "A cidade que sumiu",
                        "views": 95000,
                        "days_since_upload": 10,
                        "topic": "colapso cidade",
                        "format_name": "long",
                    },
                    {
                        "external_video_id": "vout2",
                        "external_channel_id": "UC-REL-2",
                        "channel_name": "Arquivo Passado",
                        "title": "O porto submerso",
                        "views": 64000,
                        "days_since_upload": 12,
                        "topic": "colapso cidade",
                        "format_name": "long",
                    },
                ],
            },
        )
        assert r_p2.status_code == 200, r_p2.text

        tl_12m_ok = "\n".join(["Semana,cidade submersa"] + [f"2026-{m:02d}-01,{35 + m * 5}" for m in range(1, 13)])
        tl_5y_ok = "\n".join(
            ["Mes,cidade submersa"] + [f"{2022 + i // 12}-{(i % 12) + 1:02d}-01,{45 + (i % 6) * 4}" for i in range(60)]
        )
        rel_csv = "Principais\ncidade submersa historia,100\n\nEm ascensão\ncomo era pompeia,Mais de 5.000%\n"
        r_gt = api_client.post(
            "/api/v1/research/google-trends/import-csv",
            headers=ws_hdr_a,
            json={
                "keyword": "cidade submersa",
                "channel_id": ch_id,
                "geo": "BR",
                "gprop": "youtube",
                "timeline_12m_csv": tl_12m_ok,
                "timeline_5y_csv": tl_5y_ok,
                "related_queries_csv": rel_csv,
            },
        )
        assert r_gt.status_code == 200, r_gt.text

        r_p3 = api_client.post(
            "/api/v1/research/reverse-engineering/phase3-autopsy",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "external_video_id": "vout1",
                "title": "A cidade que sumiu antes da aurora",
                "transcript_or_notes": "Naquele instante o porto desapareceu sem deixar sinal.",
                "comments": ["Faltou explicar como viviam antes?"],
                "thumbnail_focus": "ruina submersa",
                "thumbnail_visual_question": "O que afundou ali?",
                "thumbnail_emotion": "misterio",
                "thumbnail_text": "SUMIU EM 1 NOITE",
            },
        )
        assert r_p3.status_code == 200, r_p3.text
        aut_id = r_p3.json()["autopsy"]["id"]

        r_p4 = api_client.post(
            "/api/v1/research/reverse-engineering/phase4-synthesize",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "autopsy_ids": [aut_id],
                "own_validated_topic": "Babilonia esquecida",
                "new_angle": "o ultimo dia dos engenheiros do rio",
                "target_format": "long",
            },
        )
        assert r_p4.status_code == 200, r_p4.text

        r_opp = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "topic_hint": "cidade submersa", "target_format": "long"},
        )
        assert r_opp.status_code == 200, r_opp.text
        opp_id = r_opp.json()["opportunity"]["id"]

        r_brief = api_client.post(
            "/api/v1/briefs",
            headers=ws_hdr_a,
            json={
                "opportunity_id": opp_id,
                "title": "Como engenheiros perderam a cidade em 24h",
                "hook": "Antes do amanhecer, o canal secou.",
                "angle": "Foco tecnico na falha hidraulica",
                "outline": [{"block": "Hook", "duration": "15s", "notes": "Climax visual"}],
                "cta": "Inscreva-se",
                "target_format": "long",
            },
        )
        assert r_brief.status_code == 200, r_brief.text

        r_ov = api_client.get(f"/api/v1/reports/overview?channel_id={ch_id}", headers=ws_hdr_a)
        assert r_ov.status_code == 200, r_ov.text
        ov = r_ov.json()
        assert ov["summary"]["channels_count"] == 1
        assert ov["summary"]["phase1_selected_count"] == 1
        assert ov["summary"]["phase2_valid_outliers"] >= 2
        assert ov["summary"]["phase3_autopsies_count"] == 1
        assert ov["summary"]["phase4_mechanisms_count"] == 1
        assert ov["summary"]["google_trends_sustainable_count"] == 1
        assert ov["summary"]["opportunities_count"] == 1
        assert ov["summary"]["briefs_count"] == 1
        assert len(ov["reverse_engineering"]["viral_outliers"]) >= 2
        assert len(ov["opportunities"][0]["analyst_reports_json"]) == 4

        serialized_ov = json.dumps(ov)
        assert srv_key not in serialized_ov
        assert jwt_secret not in serialized_ov
        assert db_url not in serialized_ov

        r_md = api_client.get(f"/api/v1/reports/executive.md?channel_id={ch_id}", headers=ws_hdr_a)
        assert r_md.status_code == 200, r_md.text
        assert "# Relatorio Executivo" in r_md.text
        assert "Cronica Oculta" in r_md.text
        assert "Babilonia esquecida" in r_md.text
        assert "cidade submersa" in r_md.text
        assert srv_key not in r_md.text

        r_forb_ov = api_client.get("/api/v1/reports/overview", headers={**hdr_b, "X-Workspace-Id": ws_a})
        assert r_forb_ov.status_code == 403
        r_forb_md = api_client.get("/api/v1/reports/executive.md", headers={**hdr_b, "X-Workspace-Id": ws_a})
        assert r_forb_md.status_code == 403
    finally:
        with psycopg.connect(db_url) as conn, conn.cursor() as cur:
            for wid in ws_ids:
                cur.execute("DELETE FROM public.workspaces WHERE id = %s", (wid,))
            conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
