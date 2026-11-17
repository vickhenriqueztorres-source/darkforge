"""Live Supabase SP-19..SP-22 4-Phase Reverse Engineering Pipeline, Anti-Plagiarism & RLS tests."""
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
def test_live_4phase_reverse_engineering_end_to_end_and_rls() -> None:
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
    email_a = f"sp22-a-{suffix}@darkforge.invalid"
    email_b = f"sp22-b-{suffix}@darkforge.invalid"
    password = f"DfSp22!{suffix}99"
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

        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"RE A {suffix}", "slug": f"ws22a-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"RE B {suffix}", "slug": f"ws22b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])
        ws_hdr_a = {**hdr_a, "X-Workspace-Id": ws_a}

        ch_id = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr_a,
            json={
                "display_name": "Canal Historico",
                "profile": {
                    "name": "Canal Historico",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Documentario",
                    "positioning": "Mecanismos historicos",
                    "editorial_theme": "Colapsos urbanos",
                    "pillars": ["cidades perdidas"],
                },
            },
        ).json()["channel"]["id"]

        # Phase 1: Evaluate channels (good outlier-rich vs celebrity channel)
        p1 = api_client.post(
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
                        "external_channel_id": "UC_GOOD",
                        "display_name": "Canal Bom",
                        "language": "pt-BR",
                        "recent_video_views_90d": [45000, 90000],
                        "all_recent_20_30_views": [4000] * 20 + [45000, 60000, 90000],
                        "production_format": "faceless_essay",
                        "audience_profile_tags": ["historia"],
                    },
                    {
                        "external_channel_id": "UC_CELEB",
                        "display_name": "Celebridade 500k",
                        "language": "pt-BR",
                        "recent_video_views_90d": [500000],
                        "all_recent_20_30_views": [500000] * 20,
                        "production_format": "faceless_essay",
                        "audience_profile_tags": ["historia"],
                        "is_celebrity_or_mega_brand": False,
                    },
                ],
            },
        )
        assert p1.status_code == 200, p1.text
        assert p1.json()["selected_count"] == 1

        # Phase 2: Find viral outliers & multi-channel convergence
        base_vids_a = [
            {"external_video_id": f"a_{i}", "external_channel_id": "UC_A", "channel_name": "A", "title": f"Base {i}", "views": 5000, "days_since_upload": 45, "topic": "geral"}
            for i in range(20)
        ] + [
            {"external_video_id": "out_a", "external_channel_id": "UC_A", "channel_name": "A", "title": "Cidade sumiu numa noite", "views": 80000, "days_since_upload": 10, "topic": "cidade desapareceu"}
        ]
        base_vids_b = [
            {"external_video_id": f"b_{i}", "external_channel_id": "UC_B", "channel_name": "B", "title": f"Base {i}", "views": 4000, "days_since_upload": 50, "topic": "geral"}
            for i in range(20)
        ] + [
            {"external_video_id": "out_b", "external_channel_id": "UC_B", "channel_name": "B", "title": "A cidade desaparecida", "views": 70000, "days_since_upload": 12, "topic": "cidade desapareceu"}
        ]
        p2 = api_client.post(
            "/api/v1/research/reverse-engineering/phase2-outliers",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "videos": base_vids_a + base_vids_b},
        )
        assert p2.status_code == 200, p2.text
        assert p2.json()["confirmed_patterns_count"] == 1

        # Phase 3: Full Autopsy (Package + 0-15s/15-30s/Middle + Comments)
        p3 = api_client.post(
            "/api/v1/research/reverse-engineering/phase3-autopsy",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "external_video_id": "out_a",
                "title": "A cidade que desapareceu em uma noite",
                "transcript_or_notes": "Em uma noite o porto afundou completamente. Mas as rachaduras ja apareciam antes no mapa oficial.",
                "comments": ["Faltou mostrar os mapas de profundidade!", "Faz parte 2 sobre os sobreviventes!"],
                "thumbnail_text": "SUMIU TUDO",
            },
        )
        assert p3.status_code == 200, p3.text
        autopsy_id = p3.json()["autopsy"]["id"]

        # Phase 4: Synthesize Transferable Mechanism (anti-plagiarism) + Experiment Batch
        p4 = api_client.post(
            "/api/v1/research/reverse-engineering/phase4-synthesize",
            headers=ws_hdr_a,
            json={
                "channel_id": ch_id,
                "autopsy_ids": [autopsy_id],
                "own_validated_topic": "Vila Romana Submersa em Baia",
                "new_angle": "erro geologico ignorado pelo imperio",
                "target_format": "long",
            },
        )
        assert p4.status_code == 200, p4.text
        mech = p4.json()["mechanism"]
        assert mech["originality_blocked"] is False
        assert "Vila Romana" in mech["synthesized_title"]
        assert len(mech["filled_comment_gaps_json"]) >= 1

        batch = api_client.post(
            "/api/v1/research/reverse-engineering/batches",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "mechanism_id": mech["id"], "title": mech["synthesized_title"]},
        )
        assert batch.status_code == 200, batch.text
        b_id = batch.json()["batch"]["id"]

        upd = api_client.patch(
            f"/api/v1/research/reverse-engineering/batches/{b_id}",
            headers=ws_hdr_a,
            json={"status": "VALIDATED", "impressions": 25000, "ctr_pct": 8.4, "retention_30s_pct": 71.2, "outcome_notes": "CTR e retencao 30s acima da meta"},
        )
        assert upd.status_code == 200
        assert upd.json()["batch"]["ctr_pct"] == 8.4

        # Cross-workspace RLS check
        assert api_client.get("/api/v1/research/reverse-engineering/state", headers={**hdr_b, "X-Workspace-Id": ws_a}).status_code == 403
        b_state = api_client.get("/api/v1/research/reverse-engineering/state", headers={**hdr_b, "X-Workspace-Id": ws_b}).json()
        assert len(b_state["mechanisms"]) == 0
    finally:
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
