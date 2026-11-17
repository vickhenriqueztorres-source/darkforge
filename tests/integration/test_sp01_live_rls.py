"""Live Supabase RLS isolation + API + Channel Profile Versioning test (T-SEC-001 / SP-01-T12)."""
from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app

load_dotenv()


def _require_env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Credencial/variavel obrigatoria ausente para teste vivo T-SEC-001: {name}")
    return val


@pytest.mark.live_supabase
def test_two_users_two_workspaces_rls_and_api_isolation() -> None:
    url = _require_env("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
    pub_key = _require_env("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    srv_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    jwt_secret = _require_env("SUPABASE_JWT_SECRET")

    admin_headers = {
        "apikey": srv_key,
        "Authorization": f"Bearer {srv_key}",
        "Content-Type": "application/json",
    }

    suffix = uuid4().hex[:8]
    email_a = f"test-a-{suffix}@darkforge.invalid"
    email_b = f"test-b-{suffix}@darkforge.invalid"
    password = f"DfTest!{suffix}99"

    user_ids: list[str] = []
    created_ws_ids: list[str] = []

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
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
                r = client.post(
                    f"{url}/auth/v1/token?grant_type=password",
                    headers={"apikey": pub_key, "Content-Type": "application/json"},
                    json={"email": email, "password": password},
                )
                assert r.status_code == 200, r.text
                return r.json()["access_token"]

            tok_a = sign_in(email_a)
            tok_b = sign_in(email_b)

            # 1. Create Workspace A & Workspace B via FastAPI -> Supabase RPC
            res_ws_a = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_a}"},
                json={"name": f"WS A {suffix}", "slug": f"ws-a-{suffix}"},
            )
            assert res_ws_a.status_code == 201, res_ws_a.text
            ws_a_id = res_ws_a.json()["workspace"]["id"]
            created_ws_ids.append(ws_a_id)

            res_ws_b = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_b}"},
                json={"name": f"WS B {suffix}", "slug": f"ws-b-{suffix}"},
            )
            assert res_ws_b.status_code == 201, res_ws_b.text
            ws_b_id = res_ws_b.json()["workspace"]["id"]
            created_ws_ids.append(ws_b_id)

            # 2. User A creates Channel + Profile v1, then updates -> v2 with theme change
            ch_res = api_client.post(
                "/api/v1/channels",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "display_name": f"Canal A {suffix}",
                    "handle": f"@canala_{suffix}",
                    "profile": {
                        "name": f"Canal A {suffix}",
                        "language": "pt-BR",
                        "country": "BR",
                        "timezone": "America/Sao_Paulo",
                        "niche": "Historia",
                        "editorial_theme": "Tema V1",
                    },
                },
            )
            assert ch_res.status_code == 201, ch_res.text
            ch_a_id = ch_res.json()["channel"]["id"]
            v1_id = ch_res.json()["profile_version"]["id"]

            upd_res = api_client.put(
                f"/api/v1/channels/{ch_a_id}/profile",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "name": f"Canal A {suffix}",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Historia",
                    "editorial_theme": "Tema V2",
                    "change_summary": "Evolucao editorial",
                    "theme_change_reason": "Teste de mudanca de tema",
                },
            )
            assert upd_res.status_code == 200, upd_res.text
            assert upd_res.json()["profile_version"]["version_number"] == 2
            assert upd_res.json()["theme_change"]["previous_theme"] == "Tema V1"
            assert upd_res.json()["theme_change"]["new_theme"] == "Tema V2"

            # 3. Direct PostgREST RLS isolation checks (User B cannot see or mutate Workspace A)
            cross_ws = client.get(
                f"{url}/rest/v1/workspaces?id=eq.{ws_a_id}",
                headers={"apikey": pub_key, "Authorization": f"Bearer {tok_b}"},
            )
            assert cross_ws.status_code == 200
            assert cross_ws.json() == []

            cross_ch = client.get(
                f"{url}/rest/v1/channels?workspace_id=eq.{ws_a_id}",
                headers={"apikey": pub_key, "Authorization": f"Bearer {tok_b}"},
            )
            assert cross_ch.status_code == 200
            assert cross_ch.json() == []

            cross_ver = client.get(
                f"{url}/rest/v1/channel_profile_versions?channel_id=eq.{ch_a_id}",
                headers={"apikey": pub_key, "Authorization": f"Bearer {tok_b}"},
            )
            assert cross_ver.status_code == 200
            assert cross_ver.json() == []

            cross_insert = client.post(
                f"{url}/rest/v1/channels",
                headers={
                    "apikey": pub_key,
                    "Authorization": f"Bearer {tok_b}",
                    "Content-Type": "application/json",
                },
                json={
                    "workspace_id": ws_a_id,
                    "display_name": "Injecao Cruzada",
                    "created_by": user_ids[1],
                },
            )
            assert cross_insert.status_code in (401, 403), cross_insert.text

            # 4. FastAPI distinguishes 403 WORKSPACE_FORBIDDEN from empty list
            api_cross = api_client.get(
                "/api/v1/channels",
                headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_a_id},
            )
            assert api_cross.status_code == 403
            assert api_cross.json()["code"] == "WORKSPACE_FORBIDDEN"

            # 5. Historical version v1 remains preserved and immutable
            vers = api_client.get(
                f"/api/v1/channels/{ch_a_id}/profile/versions",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            )
            assert vers.status_code == 200
            items = vers.json()["items"]
            assert [v["version_number"] for v in items] == [2, 1]
            assert items[1]["id"] == v1_id
            assert items[1]["editorial_theme"] == "Tema V1"
    finally:
        with httpx.Client(timeout=10.0) as client:
            for ws_id in created_ws_ids:
                client.delete(f"{url}/rest/v1/workspaces?id=eq.{ws_id}", headers=admin_headers)
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
