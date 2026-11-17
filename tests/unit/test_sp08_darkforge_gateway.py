from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from adapters.darkforge.gateway import DarkForgeGateway
from core.darkforge_gateway.service import ProductionIntentService
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceMember, WorkspaceRole
from core.workspaces.service import WorkspaceService


class _FakeWsRepo:
    def __init__(self, ws_id, user_id):
        self.ws_id = ws_id
        self.user_id = user_id

    def get_membership(self, actor, workspace_id):
        if workspace_id == self.ws_id and actor.user_id == self.user_id:
            return WorkspaceMember(id=uuid4(), workspace_id=workspace_id, user_id=actor.user_id, role=WorkspaceRole.OWNER)
        return None


class _FakeProdRepo:
    def __init__(self, brief_status="APPROVED"):
        self.brief_id = uuid4()
        self.ch_id = uuid4()
        self.brief_status = brief_status
        self.intents = {}
        self.storage_objs = {}

    def get_brief(self, ws_id, brief_id):
        if brief_id == self.brief_id:
            return {
                "id": brief_id,
                "channel_id": self.ch_id,
                "version": 1,
                "status": self.brief_status,
                "content_sha256": "a" * 64,
                "title": "Brief Teste",
                "hook": "Hook",
                "angle": "Angle",
                "outline_json": [],
                "cta": "CTA",
            }
        return None

    def find_intent_by_idempotency(self, ws_id, key):
        for i in self.intents.values():
            if i["idempotency_key"] == key:
                return i
        return None

    def insert_intent(self, **kwargs):
        iid = uuid4()
        row = {**kwargs, "id": iid, "status": "INTENT_CREATED", "manifest_validated": False}
        self.intents[iid] = row
        return row

    def get_intent(self, ws_id, iid):
        return self.intents.get(iid)

    def mark_intent_status(self, **kwargs):
        row = self.intents[kwargs["intent_id"]]
        row["status"] = kwargs["status"]
        row["error_code"] = kwargs.get("error_code")
        return row

    def get_storage_object(self, ws_id, oid):
        return self.storage_objs.get(oid)

    def mark_intent_ready(self, **kwargs):
        row = self.intents[kwargs["intent_id"]]
        row["status"] = "READY"
        row["manifest_validated"] = True
        row["manifest_json"] = kwargs["manifest_json"]
        return row


def test_only_approved_brief_becomes_idempotent_intent_and_missing_core_blocks() -> None:
    ws_id, uid = uuid4(), uuid4()
    ws = WorkspaceService(_FakeWsRepo(ws_id, uid))
    actor = AuthenticatedUser(user_id=uid, email="owner@example.com")

    # DRAFT brief rejected
    draft_repo = _FakeProdRepo(brief_status="DRAFT")
    svc_draft = ProductionIntentService(ws, draft_repo, DarkForgeGateway(core_path=None))
    with pytest.raises(AppError) as exc:
        svc_draft.create_production_intent(actor, ws_id, draft_repo.brief_id, idempotency_key="idem-draft-01")
    assert exc.value.code == ErrorCode.VERSION_CONFLICT

    # APPROVED brief creates idempotent intent; dispatch blocks honestly when DARKFORGE_CORE_PATH missing
    app_repo = _FakeProdRepo(brief_status="APPROVED")
    svc = ProductionIntentService(ws, app_repo, DarkForgeGateway(core_path=None))
    r1 = svc.create_production_intent(actor, ws_id, app_repo.brief_id, idempotency_key="idem-ok-0001")
    r2 = svc.create_production_intent(actor, ws_id, app_repo.brief_id, idempotency_key="idem-ok-0001")
    assert r1["deduplicated"] is False
    assert r2["deduplicated"] is True
    assert r1["intent"]["id"] == r2["intent"]["id"]

    with pytest.raises(AppError) as d_exc:
        svc.dispatch_intent(actor, ws_id, r1["intent"]["id"])
    assert d_exc.value.code == ErrorCode.DARKFORGE_UNAVAILABLE
    assert app_repo.intents[r1["intent"]["id"]]["status"] == "BLOCKED"


def test_manifest_validation_requires_ready_storage_object_and_checksum(tmp_path: Path) -> None:
    ws_id, uid = uuid4(), uuid4()
    ws = WorkspaceService(_FakeWsRepo(ws_id, uid))
    actor = AuthenticatedUser(user_id=uid, email="owner@example.com")

    core_dir = tmp_path / "df_core"
    core_dir.mkdir()
    (core_dir / "pyproject.toml").write_text("[project]\nname='df'\n", encoding="utf-8")

    repo = _FakeProdRepo(brief_status="APPROVED")
    svc = ProductionIntentService(ws, repo, DarkForgeGateway(core_path=str(core_dir)))
    intent = svc.create_production_intent(actor, ws_id, repo.brief_id, idempotency_key="idem-ok-0002")["intent"]
    dispatched = svc.dispatch_intent(actor, ws_id, intent["id"])
    assert dispatched["intent"]["status"] == "DISPATCHED"

    # Reject manifest pointing to missing or mismatched storage object
    bad_obj_id = uuid4()
    digest = sha256(b"video-bytes").hexdigest()
    with pytest.raises(AppError) as m_exc:
        svc.complete_with_validated_manifest(
            actor,
            ws_id,
            intent["id"],
            {"pipeline_version": "media_vertical_v1", "artifacts": [{"sha256": digest, "storage_object_id": str(bad_obj_id)}]},
        )
    assert m_exc.value.code == ErrorCode.STORAGE_CHECKSUM_MISMATCH

    # Register READY object with matching SHA-256 -> READY allowed
    repo.storage_objs[bad_obj_id] = {"id": bad_obj_id, "status": "READY", "sha256": digest}
    ready = svc.complete_with_validated_manifest(
        actor,
        ws_id,
        intent["id"],
        {"pipeline_version": "media_vertical_v1", "artifacts": [{"sha256": digest, "storage_object_id": str(bad_obj_id)}]},
    )
    assert ready["intent"]["status"] == "READY"
    assert ready["manifest_validated"] is True
