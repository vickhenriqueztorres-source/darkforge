"""Live Supabase Postgres SP-04 (Research) & SP-05 (Title/Thumb) tests (T-RES-001)."""
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
def test_live_research_dedup_curation_isolation_and_title_thumb() -> None:
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
    email_a = f"sp04-a-{suffix}@darkforge.invalid"
    email_b = f"sp04-b-{suffix}@darkforge.invalid"
    password = f"DfSp04!{suffix}99"
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
        with httpx.Client(timeout=12.0) as client:
            for email in (email_a, email_b):
                r = client.post(
                    f"{url}/auth/v1/admin/users",
                    headers=admin_headers,
                    json={"email": email, "password": password, "email_confirm": True},
                )
                assert r.status_code in (200, 201), r.text
                user_ids.append(r.json()["id"])

            def sign_in(email: str) -> str:
                return client.post(
                    f"{url}/auth/v1/token?grant_type=password",
                    headers={"apikey": pub_key, "Content-Type": "application/json"},
                    json={"email": email, "password": password},
                ).json()["access_token"]

            tok_a = sign_in(email_a)
            tok_b = sign_in(email_b)

            ws_a = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_a}"},
                json={"name": f"SP04 WS A {suffix}", "slug": f"sp04-a-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_a)

            ws_b = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_b}"},
                json={"name": f"SP04 WS B {suffix}", "slug": f"sp04-b-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_b)

            ch_a = api_client.post(
                "/api/v1/channels",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={
                    "display_name": "Outrora Historia",
                    "profile": {"name": "Outrora Historia", "language": "pt-BR", "country": "BR", "timezone": "America/Sao_Paulo", "niche": "Historia"},
                },
            ).json()["channel"]["id"]

            # 1. Create Research Run with public candidate (idempotent)
            payload = {
                "channel_id": ch_a,
                "objective": "Encontrar canais de documentario historico",
                "query_terms": ["historia", "egito", "piramides"],
                "channel_niche": "historia antiga",
                "channel_pillars": ["egito", "piramides"],
                "candidates": [
                    {
                        "external_channel_id": f"UC_PUB_{suffix}",
                        "channel_name": "Arquivo Antigo",
                        "language": "pt-BR",
                        "external_video_id": f"VID_PUB_{suffix}",
                        "title": "Como as Piramides do Egito Foram Ergidas",
                        "format": "long",
                        "public_views": 180000,
                    }
                ],
            }
            r1 = api_client.post(
                "/api/v1/research/runs",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a, "Idempotency-Key": f"res-{suffix}"},
                json=payload,
            )
            assert r1.status_code == 201, r1.text
            assert r1.json()["deduplicated"] is False
            run_id = r1.json()["run"]["id"]

            # Retry same key -> deduplicated
            r2 = api_client.post(
                "/api/v1/research/runs",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a, "Idempotency-Key": f"res-{suffix}"},
                json=payload,
            )
            assert r2.status_code == 201
            assert r2.json()["deduplicated"] is True

            # Detail includes explicit scope notice (public vs private) and similarity breakdown
            det = api_client.get(
                f"/api/v1/research/runs/{run_id}",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
            )
            assert det.status_code == 200
            assert "metricas privadas" in det.json()["scope_notice"].lower()
            ref_vid_id = det.json()["videos"][0]["id"]

            # Curate reference video -> approved
            cur = api_client.post(
                f"/api/v1/research/references/{ref_vid_id}/curate",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"entity_type": "video", "status": "approved", "notes": "Boa narrativa POV", "collection_name": "egito"},
            )
            assert cur.status_code == 200
            assert cur.json()["curation_status"] == "approved"

            # Cross-workspace B cannot read WS A's research run
            cross = api_client.get(
                f"/api/v1/research/runs/{run_id}",
                headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_a},
            )
            assert cross.status_code == 403

            # 2. SP-05: Title structural analysis & unavailable thumbnail vision
            ta = api_client.post(
                "/api/v1/intel/titles/analyze",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"title": "Como 3 Descobertas Mudaram a Historia de Gize", "channel_id": ch_a, "reference_video_id": ref_vid_id},
            )
            assert ta.status_code == 200
            assert "number" in ta.json()["features_json"]["features"]

            th = api_client.post(
                "/api/v1/intel/thumbnails/analyze",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"source_url": "https://i.ytimg.com/vi/test123/hqdefault.jpg", "reference_video_id": ref_vid_id},
            )
            assert th.status_code == 200
            assert th.json()["vision_status"] == "unavailable"
            assert th.json()["ocr_text"] is None
    finally:
        with psycopg.connect(db_url) as conn:
            for ws_id in ws_ids:
                conn.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
            conn.commit()
        with httpx.Client(timeout=10.0) as client:
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
