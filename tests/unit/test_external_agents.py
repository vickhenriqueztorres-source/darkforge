from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.errors import AppError
from core.studio.external_agents_service import ExternalAgentsService
from core.workspaces.models import AuthenticatedUser, WorkspaceMember, WorkspaceRole


class FakeWorkspaceService:
    def __init__(self, role: WorkspaceRole | None = WorkspaceRole.OWNER) -> None:
        self._role = role

    def require_membership(self, actor, workspace_id, allowed_roles=(WorkspaceRole.OWNER, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER)):
        if self._role is None or self._role not in allowed_roles:
            raise AppError("WORKSPACE_FORBIDDEN", "Sem permissao", http_status=403)
        return WorkspaceMember(id=uuid4(), workspace_id=workspace_id, user_id=actor.user_id, role=self._role)


class FakeExternalAgentsRepo:
    def __init__(self) -> None:
        self.ingested: list[tuple] = []
        self.token_row = None

    def get_snapshot(self, workspace_id, channel_id, *, pipeline_run_id=None, events_limit=80):
        return {
            "agents": [
                {"agent_key": "sound-agent", "status": "working"},
                {"agent_key": "sfx-agent", "status": "done"},
                {"agent_key": "LoudnessQaAgent", "status": "gate_passed"},
                {"agent_key": "firefly-worker", "status": "failed"},
                {"agent_key": "agent_01_ingest", "status": "idle"},
            ],
            "pipeline_runs": [],
            "run_executions": [],
            "room_rollups": [],
            "recent_events": [],
            "last_event_id": 0,
        }

    def resolve_ingest_token(self, raw_token: str):
        return self.token_row

    def ingest_events(self, workspace_id, channel_id, items):
        self.ingested.append((workspace_id, channel_id, items))
        return [{"agent_key": i["agent_key"], "status": i["status"]} for i in items]


def test_external_agents_summary_counts() -> None:
    svc = ExternalAgentsService(FakeWorkspaceService(), FakeExternalAgentsRepo())  # type: ignore[arg-type]
    user = AuthenticatedUser(user_id=str(uuid4()), email="owner@example.com")
    snap = svc.get_snapshot(user, uuid4(), uuid4())
    assert snap["summary"] == {
        "total": 5,
        "working": 1,
        "queued": 0,
        "waiting_human": 0,
        "done": 2,
        "failed": 1,
        "idle": 1,
    }


def test_ingest_token_enforces_channel_binding() -> None:
    repo = FakeExternalAgentsRepo()
    ws_id = uuid4()
    ch_bound = uuid4()
    ch_other = uuid4()
    repo.token_row = {"id": str(uuid4()), "workspace_id": str(ws_id), "channel_id": str(ch_bound), "label": "bot"}
    svc = ExternalAgentsService(FakeWorkspaceService(), repo)  # type: ignore[arg-type]

    # Bound channel succeeds even when omitted
    res = svc.report_with_ingest_token("df_ext_ok", None, [{"agent_key": "sound-agent", "status": "working"}])
    assert res == [{"agent_key": "sound-agent", "status": "working"}]

    # Mismatched channel is forbidden
    with pytest.raises(AppError) as exc_info:
        svc.report_with_ingest_token("df_ext_ok", ch_other, [{"agent_key": "sound-agent", "status": "working"}])
    assert exc_info.value.http_status == 403
