"""Live Supabase SP-02 destructive recovery & Storage tests (T-JOB-001..003, T-STO-001)."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from adapters.supabase_db.jobs_repo import PostgresStorageMetadataRepository, PostgresWorkerQueue
from adapters.supabase_storage.client import StorageService, SupabaseStorageClient
from apps.api.config import Settings
from apps.api.main import create_app
from core.errors import AppError, ErrorCode
from core.jobs.models import JobStatus, StorageObjectStatus
from workers.runner import JobWorker

load_dotenv()


def _env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


@pytest.mark.live_supabase
def test_live_queue_concurrency_fencing_recovery_outbox_and_storage() -> None:
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
    email_a = f"sp02-a-{suffix}@darkforge.invalid"
    email_b = f"sp02-b-{suffix}@darkforge.invalid"
    password = f"DfSp02!{suffix}99"
    user_ids: list[str] = []
    ws_ids: list[str] = []
    uploaded_paths: list[tuple[str, str]] = []

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
        supabase_service_role_key=srv_key,
        database_url=db_url,
    )
    api_client = TestClient(create_app(settings=settings))
    queue = PostgresWorkerQueue(db_url)

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

            ws_a = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_a}"},
                json={"name": f"SP02 WS A {suffix}", "slug": f"sp02-a-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_a)

            ws_b = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_b}"},
                json={"name": f"SP02 WS B {suffix}", "slug": f"sp02-b-{suffix}"},
            ).json()["workspace"]["id"]
            ws_ids.append(ws_b)

            # --- T-JOB-001: Two workers race claim_next on 1 queued job ---
            job_type = f"sp02.race.{suffix}"
            enq = api_client.post(
                "/api/v1/jobs",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a, "Idempotency-Key": f"race-{suffix}"},
                json={"job_type": job_type, "payload": {"steps": ["s1", "s2"]}, "total_steps": 2},
            )
            assert enq.status_code == 202, enq.text
            job_id = UUID(enq.json()["job_id"])

            with ThreadPoolExecutor(max_workers=2) as pool:
                f1 = pool.submit(queue.claim_next, f"worker-1-{suffix}", 30, [job_type])
                f2 = pool.submit(queue.claim_next, f"worker-2-{suffix}", 30, [job_type])
                claims = [c for c in (f1.result(), f2.result()) if c is not None]
            assert len(claims) == 1, f"Expected exactly 1 claim, got {claims}"
            claimed_1 = claims[0]
            assert claimed_1.fencing_token == 1

            # --- T-JOB-002: Lease expires -> reconciler marks RECOVERABLE -> worker 2 wins fencing=2 ---
            with psycopg.connect(db_url) as conn:
                conn.execute(
                    "UPDATE public.jobs SET lease_expires_at = timezone('utc', now()) - interval '2 minutes' WHERE id = %s",
                    (str(job_id),),
                )
                conn.commit()

            reconciled = queue.reconcile_expired_leases()
            assert reconciled >= 1

            claimed_2 = queue.claim_next(f"worker-recovery-{suffix}", 30, [job_type])
            assert claimed_2 is not None
            assert claimed_2.job_id == job_id
            assert claimed_2.fencing_token == 2

            # Zombie worker with fencing=1 is blocked from heartbeat, checkpoint, and transition
            assert queue.heartbeat(job_id, f"worker-1-{suffix}", 1) is False
            assert queue.heartbeat(job_id, f"worker-2-{suffix}", 1) is False
            acc, _, _ = queue.checkpoint(job_id, 1, "zombie", 1, {})
            assert acc is False
            assert queue.transition(job_id, 1, "SUCCEEDED") is False

            # --- T-JOB-003: Idempotent effect + pause/resume + completion ---
            side_effect_runs = 0

            def exec_once(j, ctx):
                nonlocal side_effect_runs
                def _fx():
                    nonlocal side_effect_runs
                    side_effect_runs += 1
                    return {"ok": True}
                res1 = ctx.run_idempotent_effect("sp02_test", f"{j.job_id}:step1", _fx)
                res2 = ctx.run_idempotent_effect("sp02_test", f"{j.job_id}:step1", _fx)
                assert res1 == res2 == {"ok": True}
                ctx.checkpoint("step1", 1, {"done": ["step1"]}, "Etapa 1 ok")
                ctx.checkpoint("step2", 2, {"done": ["step1", "step2"]}, "Etapa 2 ok")
                queue.transition(j.job_id, j.fencing_token, "SUCCEEDED", checkpoint_json={"done": ["step1", "step2"]})

            # Simulate worker running on already claimed job_2 via WorkerContext
            from workers.runner import WorkerContext
            exec_once(claimed_2, WorkerContext(queue, claimed_2, f"worker-recovery-{suffix}", 30))
            assert side_effect_runs == 1

            detail = api_client.get(
                f"/api/v1/jobs/{job_id}",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
            )
            assert detail.status_code == 200
            assert detail.json()["job"]["status"] == "SUCCEEDED"
            assert detail.json()["job"]["completed_steps"] == 2

            # --- Outbox -> Inbox deduplication ---
            delivered = queue.dispatch_outbox_pending(f"test-consumer-{suffix}", limit=20)
            assert any(str(d["aggregate_id"]) == str(job_id) for d in delivered)

            # --- T-STO-001: Private Storage upload, SHA-256 verification, signed URL & cross-workspace block ---
            storage_client = SupabaseStorageClient(url, pub_key, srv_key)
            meta_repo = PostgresStorageMetadataRepository(db_url)
            storage_svc = StorageService(storage_client, meta_repo)

            payload_bytes = b'{"manifest":"valid-sp02"}'
            rec = storage_svc.upload_and_verify_ready(
                access_token=tok_a,
                workspace_id=UUID(ws_a),
                bucket="exports",
                opaque_name=f"test-{suffix}.json",
                data=payload_bytes,
                content_type="application/json",
                actor_user_id=UUID(user_ids[0]),
                job_id=job_id,
            )
            uploaded_paths.append(("exports", rec.object_path))
            assert rec.status == StorageObjectStatus.READY
            assert rec.size_bytes == len(payload_bytes)

            signed_url = storage_client.create_signed_url(tok_a, "exports", rec.object_path, expires_in=60)
            assert signed_url
            dl_signed = client.get(signed_url)
            assert dl_signed.status_code == 200
            assert dl_signed.content == payload_bytes

            # User B cannot read or sign User A's private object
            try:
                storage_client.download_bytes(tok_b, "exports", rec.object_path)
                assert False, "User B should not download User A's object"
            except AppError as err:
                assert err.code in (ErrorCode.WORKSPACE_FORBIDDEN, ErrorCode.RESOURCE_NOT_FOUND)

            # Reconcile clean bucket
            rep = api_client.post(
                "/api/v1/storage/reconcile",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a},
                json={"bucket": "exports"},
            )
            assert rep.status_code == 200
            assert rep.json()["report"]["missing_in_storage"] == []
            assert rep.json()["report"]["incomplete_uploads"] == []
    finally:
        with httpx.Client(timeout=10.0) as client:
            for bucket, path in uploaded_paths:
                client.delete(f"{url}/storage/v1/object/{bucket}/{path}", headers=admin_headers)
            for ws_id in ws_ids:
                client.delete(f"{url}/rest/v1/workspaces?id=eq.{ws_id}", headers=admin_headers)
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
