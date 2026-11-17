from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from adapters.supabase_auth.jwt_verifier import SupabaseJWTVerifier
from apps.api.config import Settings
from apps.api.dependencies import ServiceContainer
from apps.api.main import create_app
from core.errors import AppError, ErrorCode
from core.jobs.models import (
    ClaimedJob,
    JobEventRecord,
    JobRecord,
    JobStatus,
    StorageObjectRecord,
    StorageObjectStatus,
)
from core.jobs.ports import JobRepositoryPort, StorageMetadataPort, WorkerQueuePort
from core.jobs.service import CommandBus
from core.workspaces.models import AuthenticatedUser
from core.workspaces.service import WorkspaceService
from tests.unit.test_sp01_workspace_and_channels import (
    TEST_JWT_SECRET,
    FakeSupabaseClient,
    InMemoryChannelRepo,
    InMemoryWorkspaceRepo,
    _make_token,
)
from core.channels.service import ChannelService
from adapters.supabase_storage.client import StorageService


class InMemoryJobSystem(JobRepositoryPort, WorkerQueuePort):
    def __init__(self) -> None:
        self.jobs: dict[UUID, JobRecord] = {}
        self.events: dict[UUID, list[JobEventRecord]] = {}
        self.effects: dict[tuple[UUID, str, str], dict[str, Any]] = {}
        self.seq = 0
        self.simulate_outage = False

    def enqueue_job(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID | None,
        job_type: str,
        idempotency_key: str,
        payload_hash: str,
        payload_json: dict[str, Any],
        total_steps: int,
        priority: int,
        correlation_id: UUID,
    ) -> tuple[JobRecord, bool]:
        if self.simulate_outage:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Supabase offline", http_status=503, retryable=True)
        for existing in self.jobs.values():
            if (
                existing.workspace_id == workspace_id
                and existing.job_type == job_type
                and existing.idempotency_key == idempotency_key
            ):
                if existing.payload_hash != payload_hash:
                    raise AppError(ErrorCode.IDEMPOTENCY_CONFLICT, "Payload divergente", http_status=409)
                return existing, True
        job = JobRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            channel_id=channel_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            priority=priority,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
            payload_json=payload_json,
            checkpoint_json={},
            current_step="queued",
            total_steps=total_steps,
            completed_steps=0,
            fencing_token=0,
            worker_id=None,
            attempt_count=0,
            max_attempts=5,
            pause_requested=False,
            cancel_requested=False,
            error_code=None,
            error_message=None,
            retryable=False,
            correlation_id=correlation_id,
            created_by=actor.user_id,
            created_at=datetime.now(timezone.utc),
        )
        self.jobs[job.id] = job
        self.events[job.id] = []
        return job, False

    def list_jobs(self, actor: AuthenticatedUser, workspace_id: UUID, status=None, job_type=None, limit=50):
        return [
            j for j in self.jobs.values()
            if j.workspace_id == workspace_id
            and (status is None or j.status.value == status)
            and (job_type is None or j.job_type == job_type)
        ]

    def get_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID):
        j = self.jobs.get(job_id)
        return j if j and j.workspace_id == workspace_id else None

    def list_job_events(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID, after_sequence: int = 0):
        return [e for e in self.events.get(job_id, []) if e.sequence_no > after_sequence]

    def request_pause(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        j = self.jobs[job_id]
        new_status = JobStatus.PAUSED if j.status in (JobStatus.QUEUED, JobStatus.RECOVERABLE) else j.status
        updated = JobRecord(**{**j.__dict__, "status": new_status, "pause_requested": new_status != JobStatus.PAUSED})
        self.jobs[job_id] = updated
        return updated

    def resume_job(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        j = self.jobs[job_id]
        updated = JobRecord(**{**j.__dict__, "status": JobStatus.QUEUED, "pause_requested": False, "error_code": None})
        self.jobs[job_id] = updated
        return updated

    def request_cancel(self, actor: AuthenticatedUser, workspace_id: UUID, job_id: UUID) -> JobRecord:
        j = self.jobs[job_id]
        new_status = JobStatus.CANCELLED if j.status in (JobStatus.QUEUED, JobStatus.PAUSED) else JobStatus.CANCEL_REQUESTED
        updated = JobRecord(**{**j.__dict__, "status": new_status, "cancel_requested": True})
        self.jobs[job_id] = updated
        return updated

    def claim_next(self, worker_id: str, lease_seconds: int = 30, job_types=None) -> ClaimedJob | None:
        eligible = sorted(
            [j for j in self.jobs.values() if j.status in (JobStatus.QUEUED, JobStatus.RECOVERABLE)],
            key=lambda x: -x.priority,
        )
        if not eligible:
            return None
        j = eligible[0]
        updated = JobRecord(
            **{
                **j.__dict__,
                "status": JobStatus.RUNNING,
                "worker_id": worker_id,
                "fencing_token": j.fencing_token + 1,
                "attempt_count": j.attempt_count + 1,
                "pause_requested": False,
            }
        )
        self.jobs[j.id] = updated
        self._emit(updated, "job.state_changed", "claimed", f"Claimed by {worker_id}")
        return ClaimedJob(
            job_id=updated.id,
            workspace_id=updated.workspace_id,
            channel_id=updated.channel_id,
            job_type=updated.job_type,
            payload_json=updated.payload_json,
            checkpoint_json=updated.checkpoint_json,
            fencing_token=updated.fencing_token,
            attempt_count=updated.attempt_count,
            correlation_id=updated.correlation_id,
        )

    def heartbeat(self, job_id: UUID, worker_id: str, fencing_token: int, lease_seconds: int = 30) -> bool:
        j = self.jobs.get(job_id)
        return bool(j and j.status == JobStatus.RUNNING and j.worker_id == worker_id and j.fencing_token == fencing_token)

    def checkpoint(self, job_id: UUID, fencing_token: int, current_step: str, completed_steps: int, checkpoint_json: dict, message: str = ""):
        j = self.jobs.get(job_id)
        if not j or j.fencing_token != fencing_token:
            return False, False, False
        updated = JobRecord(**{**j.__dict__, "current_step": current_step, "completed_steps": completed_steps, "checkpoint_json": checkpoint_json})
        self.jobs[job_id] = updated
        self._emit(updated, "job.progress_updated", current_step, message)
        return True, updated.pause_requested, updated.cancel_requested

    def transition(self, job_id: UUID, fencing_token: int, target_status: str, checkpoint_json=None, error_code=None, error_message=None, retryable=False, next_retry_at=None) -> bool:
        j = self.jobs.get(job_id)
        if not j or j.fencing_token != fencing_token:
            return False
        updated = JobRecord(
            **{
                **j.__dict__,
                "status": JobStatus(target_status),
                "checkpoint_json": checkpoint_json if checkpoint_json is not None else j.checkpoint_json,
                "error_code": error_code,
                "error_message": error_message,
                "retryable": retryable,
            }
        )
        self.jobs[job_id] = updated
        self._emit(updated, "job.state_changed", updated.current_step, error_message or target_status)
        return True

    def reconcile_expired_leases(self) -> int:
        return 0

    def get_or_record_effect(self, workspace_id: UUID, effect_scope: str, effect_key: str, result_json=None):
        key = (workspace_id, effect_scope, effect_key)
        if key in self.effects:
            return self.effects[key]
        if result_json is not None:
            self.effects[key] = result_json
            return result_json
        return None

    def _emit(self, job: JobRecord, evt_type: str, step: str, msg: str) -> None:
        self.seq += 1
        self.events[job.id].append(
            JobEventRecord(
                sequence_no=self.seq,
                workspace_id=job.workspace_id,
                job_id=job.id,
                event_type=evt_type,
                step_name=step,
                status=job.status.value,
                message=msg,
            )
        )


def _setup():
    ws_repo = InMemoryWorkspaceRepo()
    ch_repo = InMemoryChannelRepo()
    job_sys = InMemoryJobSystem()
    ws_svc = WorkspaceService(ws_repo)
    ch_svc = ChannelService(ws_svc, ch_repo)
    bus = CommandBus(ws_svc, job_sys)
    verifier = SupabaseJWTVerifier("https://example.supabase.co", jwt_secret=TEST_JWT_SECRET)
    container = ServiceContainer(
        jwt_verifier=verifier,
        supabase_client=FakeSupabaseClient(),  # type: ignore[arg-type]
        workspaces=ws_svc,
        channels=ch_svc,
        command_bus=bus,
    )
    return TestClient(create_app(settings=Settings(), container=container)), job_sys


def test_idempotency_deduplication_and_conflict() -> None:
    client, job_sys = _setup()
    tok = _make_token(uuid4())
    ws_id = client.post("/api/v1/workspaces", headers={"Authorization": f"Bearer {tok}"}, json={"name": "WS", "slug": "ws-idem"}).json()["workspace"]["id"]

    r1 = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id, "Idempotency-Key": "cmd-key-0001"},
        json={"job_type": "diagnostic.multi_step", "payload": {"steps": ["a", "b"]}, "total_steps": 2},
    )
    assert r1.status_code == 202
    assert r1.json()["deduplicated"] is False

    # Same key + same payload -> deduplicated
    r2 = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id, "Idempotency-Key": "cmd-key-0001"},
        json={"job_type": "diagnostic.multi_step", "payload": {"steps": ["a", "b"]}, "total_steps": 2},
    )
    assert r2.status_code == 202
    assert r2.json()["deduplicated"] is True
    assert r2.json()["job_id"] == r1.json()["job_id"]

    # Same key + different payload -> 409 IDEMPOTENCY_CONFLICT
    r3 = client.post(
        "/api/v1/jobs",
        headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id, "Idempotency-Key": "cmd-key-0001"},
        json={"job_type": "diagnostic.multi_step", "payload": {"steps": ["a", "c"]}, "total_steps": 2},
    )
    assert r3.status_code == 409
    assert r3.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_worker_crash_recovery_fencing_and_sse_replay() -> None:
    from workers.runner import JobWorker

    client, job_sys = _setup()
    tok = _make_token(uuid4())
    ws_id = client.post("/api/v1/workspaces", headers={"Authorization": f"Bearer {tok}"}, json={"name": "WS", "slug": "ws-rec"}).json()["workspace"]["id"]

    job_id = UUID(
        client.post(
            "/api/v1/jobs",
            headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id, "Idempotency-Key": "crash-key-001"},
            json={"job_type": "diagnostic.multi_step", "payload": {"steps": ["s1", "s2", "s3"]}, "total_steps": 3},
        ).json()["job_id"]
    )

    effect_calls = {"s1": 0, "s2": 0, "s3": 0}

    def crash_on_s2(job, ctx):
        for step in ["s1", "s2", "s3"]:
            if step in job.checkpoint_json.get("completed_step_names", []):
                continue
            def _do(st=step):
                effect_calls[st] += 1
                return {"done": st}
            ctx.run_idempotent_effect("test", f"{job.id if hasattr(job, 'id') else job.job_id}:{step}", _do)
            if step == "s2" and job.attempt_count == 1:
                raise RuntimeError("Simulated crash before commit on s2!")
            done = list(job.checkpoint_json.get("completed_step_names", [])) + [step]
            job = ClaimedJob(**{**job.__dict__, "checkpoint_json": {"completed_step_names": done}})
            ctx.checkpoint(step, len(done), {"completed_step_names": done}, f"Done {step}")
        job_sys.transition(job.job_id, job.fencing_token, "SUCCEEDED", checkpoint_json=job.checkpoint_json)

    # Attempt 1 crashes on s2 after effect ran
    w1 = JobWorker(job_sys, "w1", handlers={"diagnostic.multi_step": crash_on_s2})
    try:
        w1.run_once()
    except RuntimeError:
        pass

    # Zombie worker 1 tries to commit with stale fencing=1 after reconciler gives fencing=2
    j_cur = job_sys.jobs[job_id]
    job_sys.jobs[job_id] = JobRecord(**{**j_cur.__dict__, "status": JobStatus.RECOVERABLE})

    w2 = JobWorker(job_sys, "w2", handlers={"diagnostic.multi_step": crash_on_s2})
    w2.run_once()

    assert job_sys.jobs[job_id].status == JobStatus.SUCCEEDED
    # s1 ran once via checkpoint, s2 ran once via idempotent_effects, s3 ran once!
    assert effect_calls == {"s1": 1, "s2": 1, "s3": 1}
    # Stale fencing token 1 cannot overwrite SUCCEEDED
    assert job_sys.transition(job_id, 1, "FAILED", error_message="stale") is False
    assert job_sys.jobs[job_id].status == JobStatus.SUCCEEDED

    # SSE replay from sequence_no=1 skips event #1 and returns newer events
    sse = client.get(
        f"/api/v1/jobs/{job_id}/events?last_event_id=1",
        headers={"Authorization": f"Bearer {tok}", "X-Workspace-Id": ws_id},
    )
    assert sse.status_code == 200
    assert "id: 1\n" not in sse.text
    assert "id: 2\n" in sse.text


def test_storage_path_traversal_and_checksum_mismatch_rejected() -> None:
    class FakeMeta(StorageMetadataPort):
        def __init__(self) -> None:
            self.recs: dict[UUID, StorageObjectRecord] = {}
        def create_uploading_record(self, workspace_id, bucket, object_path, content_type, created_by, created_by_job=None):
            rec = StorageObjectRecord(uuid4(), workspace_id, bucket, object_path, None, None, content_type, StorageObjectStatus.UPLOADING, created_by_job, created_by)
            self.recs[rec.id] = rec
            return rec
        def update_status(self, workspace_id, object_id, status, sha256=None, size_bytes=None):
            r = self.recs[object_id]
            upd = StorageObjectRecord(r.id, r.workspace_id, r.bucket, r.object_path, sha256 or r.sha256, size_bytes or r.size_bytes, r.content_type, status, r.created_by_job, r.created_by)
            self.recs[object_id] = upd
            return upd
        def list_objects(self, workspace_id, bucket=None):
            return list(self.recs.values())

    class CorruptStorage:
        def upload_object(self, *a, **kw): return "abc"
        def download_bytes(self, *a, **kw): return b"corrupted-bytes"

    svc = StorageService(CorruptStorage(), FakeMeta())  # type: ignore[arg-type]
    try:
        svc.upload_and_verify_ready("tok", uuid4(), "exports", "../escape.txt", b"ok", "text/plain", uuid4())
        assert False, "Expected path traversal rejection"
    except AppError as err:
        assert err.code == ErrorCode.VALIDATION_ERROR

    try:
        svc.upload_and_verify_ready("tok", uuid4(), "exports", "good.txt", b"original", "text/plain", uuid4())
        assert False, "Expected checksum mismatch"
    except AppError as err:
        assert err.code == ErrorCode.STORAGE_CHECKSUM_MISMATCH
