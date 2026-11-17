"""Live E2E + Redacted Diagnostics (JOB-007) + Logical Backup & Isolated Restore (JOB-008, T-REL-001, T-E2E-001)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from adapters.supabase_db.jobs_repo import PostgresStorageMetadataRepository
from adapters.supabase_storage.client import StorageService, SupabaseStorageClient
from apps.api.config import Settings
from apps.api.main import create_app
from core.telemetry import TelemetryRecorder, redact_text
from scripts.backup.backup_and_restore import backup_workspace_bundle, restore_workspace_isolated

load_dotenv()


def _env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


def test_telemetry_allowlist_and_secret_redaction() -> None:
    rec = TelemetryRecorder()
    with pytest.raises(ValueError):
        rec.record("forbidden_arbitrary_event", workspace_id=uuid4(), actor_id=uuid4())

    ev = rec.record(
        "brief_approved",
        workspace_id=uuid4(),
        actor_id=uuid4(),
        metadata={
            "brief_id": str(uuid4()),
            "access_token": "secret-jwt-should-disappear",
            "note": "Authorization Bearer abc.def.ghi sb_secret_123456",
        },
    )
    assert ev.metadata["access_token"] == "[REDACTED]"
    assert "abc.def.ghi" not in ev.metadata["note"]
    assert "sb_secret_123456" not in ev.metadata["note"]
    assert "secret-pass" not in redact_text("postgresql://postgres:secret-pass@db.example.com:5432/postgres")


@pytest.mark.live_supabase
def test_live_e2e_diagnostics_redaction_and_isolated_backup_restore(tmp_path: Path) -> None:
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
    email_a = f"sp09-a-{suffix}@darkforge.invalid"
    email_b = f"sp09-b-{suffix}@darkforge.invalid"
    password = f"DfSp09!{suffix}99"
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
    storage_client = SupabaseStorageClient(supabase_url=url, publishable_key=pub_key, service_role_key=srv_key)
    storage_service = StorageService(storage_client, PostgresStorageMetadataRepository(db_url))

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

        owner_a_uid = UUID(user_ids[0])
        hdr_a = {"Authorization": f"Bearer {tok_a}"}
        hdr_b = {"Authorization": f"Bearer {tok_b}"}

        # 1. Create workspace + channel + profile v1
        ws_a = api_client.post("/api/v1/workspaces", headers=hdr_a, json={"name": f"Pilot {suffix}", "slug": f"ws9-{suffix}"}).json()["workspace"]["id"]
        ws_b = api_client.post("/api/v1/workspaces", headers=hdr_b, json={"name": f"Other {suffix}", "slug": f"ws9b-{suffix}"}).json()["workspace"]["id"]
        ws_ids.extend([ws_a, ws_b])
        ws_hdr_a = {**hdr_a, "X-Workspace-Id": ws_a}

        ch_id = api_client.post(
            "/api/v1/channels",
            headers=ws_hdr_a,
            json={
                "display_name": "Canal Piloto",
                "profile": {
                    "name": "Canal Piloto",
                    "language": "pt-BR",
                    "country": "BR",
                    "timezone": "America/Sao_Paulo",
                    "niche": "Ciencia e Historia",
                    "positioning": "Evidencia primaria",
                    "editorial_theme": "Arquivos",
                    "pillars": ["arquivos", "ciencia"],
                },
            },
        ).json()["channel"]["id"]

        # 2. Private Storage upload & READY check via StorageService
        blob_bytes = b"darkforge-pilot-reference-asset-v1"
        blob_sha = hashlib.sha256(blob_bytes).hexdigest()
        stored_rec = storage_service.upload_and_verify_ready(
            access_token=tok_a,
            workspace_id=UUID(ws_a),
            bucket="exports",
            opaque_name="pilot-notes.txt",
            data=blob_bytes,
            content_type="text/plain",
            actor_user_id=owner_a_uid,
        )
        assert stored_rec.status.value == "READY"
        assert stored_rec.sha256 == blob_sha

        # 3. Knowledge L2 + Opportunity + Frozen Approved Brief v1 + Blocked Production Intent
        src_id = api_client.post(
            "/api/v1/knowledge/sources",
            headers=ws_hdr_a,
            json={
                "title": "Roteiro Piloto",
                "source_type": "script",
                "content_text": "[HOOK] Evidencia verificada de arquivo.\n[BODY] Detalhe cronologico.\n[CTA] Assine.",
                "rights_status": "owned",
                "channel_id": ch_id,
            },
        ).json()["source"]["id"]
        assert api_client.post(f"/api/v1/knowledge/sources/{src_id}/review", headers=ws_hdr_a, json={"curation_level": "L2", "status": "APPROVED"}).status_code == 200
        assert api_client.post("/api/v1/knowledge/reindex", headers=ws_hdr_a, json={"force_new_revision": False}).status_code == 200

        opp_id = api_client.post(
            "/api/v1/opportunities/generate",
            headers=ws_hdr_a,
            json={"channel_id": ch_id, "topic_hint": "arquivo"},
        ).json()["opportunity"]["id"]
        brief = api_client.post(
            "/api/v1/briefs",
            headers=ws_hdr_a,
            json={
                "opportunity_id": opp_id,
                "title": "Episodio Piloto E2E",
                "hook": "Fato pouco conhecido.",
                "angle": "Baseado em arquivos",
                "outline": [{"section": "Hook", "notes": "Abertura"}],
            },
        ).json()["brief"]
        assert api_client.post(f"/api/v1/briefs/{brief['id']}/approve", headers=ws_hdr_a).status_code == 200

        intent = api_client.post(
            f"/api/v1/briefs/{brief['id']}/production",
            headers={**ws_hdr_a, "Idempotency-Key": f"idem-e2e-{suffix}"},
        ).json()["intent"]
        assert api_client.post(f"/api/v1/production/intents/{intent['id']}/dispatch", headers=ws_hdr_a).status_code == 503

        # 4. Telemetry + Redacted Diagnostics export (JOB-007)
        t_res = api_client.post(
            "/api/v1/telemetry/events",
            headers=ws_hdr_a,
            json={"event_name": "brief_approved", "metadata": {"brief_id": brief["id"], "access_token": "leak"}},
        )
        assert t_res.status_code == 200
        assert t_res.json()["event"]["metadata"]["access_token"] == "[REDACTED]"

        diag = api_client.get("/api/v1/diagnostics/export", headers=ws_hdr_a)
        assert diag.status_code == 200, diag.text
        diag_text = diag.text
        assert srv_key not in diag_text
        assert jwt_secret not in diag_text
        assert "Evidencia verificada de arquivo" not in diag_text
        assert diag.json()["redaction_applied"] is True

        # 5. Logical Backup & Isolated Workspace Restore (JOB-008 / T-REL-001)
        backup_dir = tmp_path / "backup_bundle"
        b_manifest = backup_workspace_bundle(
            database_url=db_url,
            storage_client=storage_client,
            workspace_id=UUID(ws_a),
            backup_dir=backup_dir,
            access_token=tok_a,
        )
        assert b_manifest["counts"]["channels"] == 1
        assert b_manifest["counts"]["episode_briefs"] == 1
        assert len(b_manifest["storage_objects_backed_up"]) == 1

        restore_res = restore_workspace_isolated(
            database_url=db_url,
            storage_client=storage_client,
            backup_dir=backup_dir,
            owner_user_id=owner_a_uid,
            access_token=tok_a,
        )
        restored_ws = restore_res["restored_workspace_id"]
        ws_ids.append(restored_ws)
        assert restored_ws != ws_a
        assert restore_res["restored_channels"] == 1
        assert restore_res["restored_opportunities"] == 1
        assert restore_res["restored_briefs"] == 1
        assert len(restore_res["restored_storage_objects"]) == 1

        # Verify restored brief hash matches and restored storage blob matches byte-for-byte
        restored_briefs = api_client.get("/api/v1/briefs", headers={**hdr_a, "X-Workspace-Id": restored_ws}).json()["items"]
        assert len(restored_briefs) == 1
        assert restored_briefs[0]["content_sha256"] == brief["content_sha256"]
        assert restored_briefs[0]["status"] == "APPROVED"

        restored_obj = restore_res["restored_storage_objects"][0]
        dl_bytes = storage_client.download_bytes(tok_a, restored_obj["bucket"], restored_obj["object_path"])
        assert hashlib.sha256(dl_bytes).hexdigest() == blob_sha

        # Original workspace intact and User B blocked on both ws_a and restored_ws
        assert api_client.get("/api/v1/briefs", headers={**hdr_b, "X-Workspace-Id": restored_ws}).status_code == 403
        assert len(api_client.get("/api/v1/briefs", headers=ws_hdr_a).json()["items"]) == 1
    finally:
        # Remove Storage objects created in exports bucket
        with httpx.Client(timeout=20.0) as http:
            for w in ws_ids:
                try:
                    objs = storage_client.list_workspace_objects("exports", UUID(w))
                    for p in objs:
                        http.delete(f"{url}/storage/v1/object/exports/{p}", headers=admin_headers)
                except Exception:
                    pass
        if ws_ids:
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                for ws_id in ws_ids:
                    cur.execute("DELETE FROM public.workspaces WHERE id = %s", (ws_id,))
                conn.commit()
        with httpx.Client(timeout=20.0) as http:
            for uid in user_ids:
                http.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
