"""Live Supabase Postgres + pgvector + FTS SP-06 RAG evaluation tests (T-RAG-001, T-RAG-002, T-AI-001)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from apps.api.config import Settings
from apps.api.main import create_app

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]


def _env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


@pytest.mark.live_supabase
def test_live_rag_golden_curation_isolation_citations_archive_and_rebuild() -> None:
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
    email_a = f"sp06-a-{suffix}@darkforge.invalid"
    email_b = f"sp06-b-{suffix}@darkforge.invalid"
    password = f"DfSp06!{suffix}99"
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

    ds_path = ROOT / "tests" / "evaluation" / "datasets" / "rag_security_golden.jsonl"
    golden = {c["case_id"]: c for c in (json.loads(l) for l in ds_path.read_text(encoding="utf-8").splitlines() if l.strip())}

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
                json={"name": f"SP06 WS A {suffix}", "slug": f"sp06-a-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_a)

            ws_b = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_b}"},
                json={"name": f"SP06 WS B {suffix}", "slug": f"sp06-b-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_b)

            # RAG-001: L0 source imported -> NOT indexed or retrieved by default
            l0 = api_client.post(
                "/api/v1/knowledge/sources",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"title": "Fonte L0", "source_type": "hook", "content_text": golden["RAG-001"]["sources"][0]["text"]},
            )
            assert l0.status_code == 201

            # RAG-002: L3 canonical source -> approved & indexed
            l3 = api_client.post(
                "/api/v1/knowledge/sources",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"title": "Fonte L3 Canonica", "source_type": "brand_doc", "content_text": golden["RAG-002"]["sources"][0]["text"]},
            ).json()["source"]
            l3_id = l3["id"]
            rev_l3 = api_client.post(
                f"/api/v1/knowledge/sources/{l3_id}/review",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"curation_level": "L3", "status": "APPROVED"},
            )
            assert rev_l3.status_code == 200

            # RAG-003: Source that will be archived later
            s_arch = api_client.post(
                "/api/v1/knowledge/sources",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"title": "Fonte Arquivavel", "source_type": "script", "content_text": golden["RAG-003"]["sources"][0]["text"]},
            ).json()["source"]["id"]
            api_client.post(
                f"/api/v1/knowledge/sources/{s_arch}/review",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"curation_level": "L2", "status": "APPROVED"},
            )

            # RAG-004: Workspace B imports & indexes secret L3 source
            ws_b_src = api_client.post(
                "/api/v1/knowledge/sources",
                headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_b},
                json={"title": "Segredo B", "source_type": "brand_doc", "content_text": golden["RAG-004"]["other_workspace_sources"][0]["text"]},
            ).json()["source"]["id"]
            api_client.post(
                f"/api/v1/knowledge/sources/{ws_b_src}/review",
                headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_b},
                json={"curation_level": "L3", "status": "APPROVED"},
            )
            api_client.post("/api/v1/knowledge/reindex", headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_b}, json={})

            # Index WS A
            idx_a = api_client.post(
                "/api/v1/knowledge/reindex",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={},
            )
            assert idx_a.status_code == 200
            assert idx_a.json()["indexed_sources"] == 2  # L0 excluded!

            # Search RAG-001 (L0 query) must not return L0 source
            q_l0 = api_client.post(
                "/api/v1/knowledge/search",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"query": golden["RAG-001"]["query"]},
            )
            assert q_l0.status_code == 200
            assert all(c["curation_level"] in ("L2", "L3") for c in q_l0.json()["chunks"])

            # Search RAG-004 in WS A must NEVER leak WS B's source
            q_cross = api_client.post(
                "/api/v1/knowledge/search",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"query": golden["RAG-004"]["query"]},
            )
            assert q_cross.status_code == 200
            assert all(str(c["source_id"]) != ws_b_src for c in q_cross.json()["chunks"])

            # Grounded generation + citation provenance (RAG-002)
            gen = api_client.post(
                "/api/v1/generations",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"goal": golden["RAG-002"]["query"]},
            )
            assert gen.status_code == 201, gen.text
            gen_id = gen.json()["generation"]["id"]
            assert any(str(c["source_id"]) == l3_id for c in gen.json()["citations"])

            prov = api_client.get(
                f"/api/v1/generations/{gen_id}/provenance",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
            )
            assert prov.status_code == 200
            assert len(prov.json()["cited_chunks"]) >= 1

            # External consent blocked when not granted (T-AI-001)
            no_consent = api_client.post(
                "/api/v1/generations",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"goal": golden["RAG-002"]["query"], "use_external": True, "external_consent_granted": False},
            )
            assert no_consent.status_code == 412
            assert no_consent.json()["code"] == "AI_EXTERNAL_CONSENT_REQUIRED"

            # RAG-003 / T-RAG-002: Archive source -> excluded from new searches immediately
            arch_res = api_client.delete(
                f"/api/v1/knowledge/sources/{s_arch}?hard_delete=false",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
            )
            assert arch_res.status_code == 200
            assert arch_res.json()["embeddings_removed"] >= 1

            q_after_arch = api_client.post(
                "/api/v1/knowledge/search",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"query": golden["RAG-003"]["query"]},
            )
            assert all(str(c["source_id"]) != s_arch for c in q_after_arch.json()["chunks"])

            # EmbeddingRevision rebuild (T-RAG-002)
            reb = api_client.post(
                "/api/v1/knowledge/reindex",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"force_new_revision": True},
            )
            assert reb.status_code == 200
            assert reb.json()["revision"]["status"] == "ACTIVE"
            assert reb.json()["revision"]["embedding_version"].endswith("-rebuild")

            # Hard delete removes chunks + embeddings
            hard_del = api_client.delete(
                f"/api/v1/knowledge/sources/{l3_id}?hard_delete=true",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
            )
            assert hard_del.status_code == 200
            assert hard_del.json()["action"] == "deleted"
            assert hard_del.json()["chunks_removed"] >= 1
    finally:
        with psycopg.connect(db_url) as conn:
            for ws_id in ws_ids:
                conn.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
            conn.commit()
        with httpx.Client(timeout=10.0) as client:
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
