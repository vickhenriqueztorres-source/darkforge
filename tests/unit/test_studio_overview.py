from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.youtube.public_channel import PublicChannelCollector
from apps.api.dependencies import ServiceContainer, get_container, get_current_user, get_workspace_id
from apps.api.routes.studio import router as studio_router
from core.errors import AppError, ErrorCode
from core.studio.service import StudioService
from core.workspaces.models import AuthenticatedUser, WorkspaceMember, WorkspaceRole


class FakeWorkspaceRepo:
    def __init__(self, memberships: dict[tuple[UUID, UUID], WorkspaceRole]) -> None:
        self._memberships = memberships

    def list_user_workspaces(self, actor: AuthenticatedUser) -> list[Any]:
        return []

    def get_membership(self, actor: AuthenticatedUser, workspace_id: UUID) -> WorkspaceMember | None:
        role = self._memberships.get((actor.user_id, workspace_id))
        if role is None:
            return None
        return WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=actor.user_id,
            role=role,
            created_at=None,
        )

    def create_workspace(self, actor: AuthenticatedUser, name: str, slug: str) -> Any:
        raise NotImplementedError


class FakeWorkspaceService:
    def __init__(self, memberships: dict[tuple[UUID, UUID], WorkspaceRole]) -> None:
        self._memberships = memberships

    def require_membership(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        allowed_roles: tuple[WorkspaceRole, ...] | None = None,
    ) -> WorkspaceMember:
        role = self._memberships.get((actor.user_id, workspace_id))
        if role is None:
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Sem permissao neste workspace.", http_status=403)
        if allowed_roles and role not in allowed_roles:
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Papel insuficiente.", http_status=403)
        return WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=actor.user_id,
            role=role,
            created_at=None,
        )


class FakeStudioRepo:
    def __init__(self, rows_by_ws: dict[UUID, list[dict[str, Any]]]) -> None:
        self._rows_by_ws = rows_by_ws
        self.ensure_called = False

    def ensure_channel_agents(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        self.ensure_called = True
        raise AssertionError("get_overview nao deve chamar ensure_channel_agents")

    def get_studio_overview(self, workspace_id: UUID) -> list[dict[str, Any]]:
        return self._rows_by_ws.get(workspace_id, [])


def test_studio_overview_service_with_and_without_agents_totals_and_no_external_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    ws_id = uuid4()
    other_ws = uuid4()
    owner = AuthenticatedUser(user_id=uuid4(), email="owner@darkforge.local")
    outsider = AuthenticatedUser(user_id=uuid4(), email="other@darkforge.local")

    ch_with_agents = uuid4()
    ch_empty = uuid4()

    rows = {
        ws_id: [
            {
                "workspace_id": str(ws_id),
                "channel_id": str(ch_with_agents),
                "display_name": "O Outro Lado",
                "handle": "@outroladodetudo",
                "status": "active",
                "external_channel_id": "UCf6Ox9rzQbIkDeE94to9AEQ",
                "niche": "Mistérios",
                "agents_json": [
                    {"agent_key": "dados", "room_key": "sala_dados", "status": "working", "enabled": True, "progress": 0.4},
                    {"agent_key": "estrategia", "room_key": "mesa_agentes", "status": "waiting_approval", "enabled": True, "progress": None},
                    {"agent_key": "pesquisa", "room_key": "pesquisa", "status": "failed", "enabled": True, "progress": None},
                ],
                "working": 1,
                "awaiting_human": 1,
                "blocked": 0,
                "failed": 1,
                "agents": 3,
                "disabled_agents": 0,
                "active_item_json": {"id": str(uuid4()), "working_title": "Sinal 1977", "stage": "roteiro"},
                "last_event_at": "2026-11-17T17:10:00+00:00",
            },
            {
                "workspace_id": str(ws_id),
                "channel_id": str(ch_empty),
                "display_name": "Sonar 0300",
                "handle": "@Sonar0300",
                "status": "active",
                "external_channel_id": None,
                "niche": None,
                "agents_json": [],
                "working": 0,
                "awaiting_human": 0,
                "blocked": 0,
                "failed": 0,
                "agents": 0,
                "disabled_agents": 0,
                "active_item_json": None,
                "last_event_at": None,
            },
        ]
    }

    collector = PublicChannelCollector()

    def forbid_network(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Rota overview nunca pode fazer chamada externa ao YouTube")

    monkeypatch.setattr(collector, "fetch_overview", forbid_network)
    monkeypatch.setattr(collector, "_client", forbid_network)
    # Warm cache manually for one channel
    collector._cache["UCf6Ox9rzQbIkDeE94to9AEQ|30"] = (
        9999999999.0,
        {"channel": {"avatar_url": "https://yt3.googleusercontent.com/cached-avatar"}},
    )

    repo = FakeStudioRepo(rows)
    ws_svc = FakeWorkspaceService({(owner.user_id, ws_id): WorkspaceRole.OWNER})
    svc = StudioService(ws_svc, repo, avatar_lookup=collector.get_cached_avatar_url)  # type: ignore[arg-type]

    res = svc.get_overview(owner, ws_id)
    assert repo.ensure_called is False
    assert res["workspace_id"] == str(ws_id)
    assert res["totals"] == {"channels": 2, "working": 1, "awaiting_human": 1, "problems": 1}

    first, second = res["channels"]
    assert first["provisioned"] is True
    assert first["channel"]["avatar_url"] == "https://yt3.googleusercontent.com/cached-avatar"
    assert first["active_item"]["working_title"] == "Sinal 1977"

    assert second["provisioned"] is False
    assert second["agents"] == []
    assert second["channel"]["avatar_url"] is None

    # Outsider from another workspace receives 403
    with pytest.raises(AppError) as err:
        svc.get_overview(outsider, ws_id)
    assert err.value.http_status == 403

    with pytest.raises(AppError) as err2:
        svc.get_overview(owner, other_ws)
    assert err2.value.http_status == 403


def test_studio_overview_route_handles_empty_workspace() -> None:
    ws_id = uuid4()
    owner = AuthenticatedUser(user_id=uuid4(), email="owner@darkforge.local")
    repo = FakeStudioRepo({})
    ws_svc = FakeWorkspaceService({(owner.user_id, ws_id): WorkspaceRole.OWNER})
    studio_svc = StudioService(ws_svc, repo)  # type: ignore[arg-type]

    app = FastAPI()
    app.include_router(studio_router)
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_workspace_id] = lambda: ws_id
    app.dependency_overrides[get_container] = lambda: ServiceContainer(
        jwt_verifier=None,  # type: ignore[arg-type]
        supabase_client=None,  # type: ignore[arg-type]
        workspaces=ws_svc,  # type: ignore[arg-type]
        channels=None,  # type: ignore[arg-type]
        command_bus=None,  # type: ignore[arg-type]
        studio=studio_svc,
    )

    client = TestClient(app)
    resp = client.get("/api/v1/studio/overview", headers={"Origin": "http://127.0.0.1:3000"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_id"] == str(ws_id)
    assert body["totals"] == {"channels": 0, "working": 0, "awaiting_human": 0, "problems": 0}
    assert body["channels"] == []
