from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from adapters.supabase_auth.jwt_verifier import SupabaseJWTVerifier
from apps.api.config import Settings
from apps.api.dependencies import ServiceContainer
from apps.api.main import create_app
from core.channels.models import (
    Channel,
    ChannelProfileInput,
    ChannelProfileVersion,
    EditorialThemeChange,
)
from core.channels.ports import ChannelRepositoryPort
from core.channels.service import ChannelService
from core.errors import AppError, ErrorCode
from core.jobs.service import CommandBus
from core.workspaces.models import AuthenticatedUser, Workspace, WorkspaceMember, WorkspaceRole
from core.workspaces.ports import WorkspaceRepositoryPort
from core.workspaces.service import WorkspaceService

TEST_JWT_SECRET = "test-only-hs256-secret-key-minimum-32-bytes"


class FakeSupabaseClient:
    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    def check_health(self) -> bool:
        return self.healthy


class InMemoryWorkspaceRepo(WorkspaceRepositoryPort):
    def __init__(self) -> None:
        self.workspaces: dict[UUID, Workspace] = {}
        self.members: list[WorkspaceMember] = []
        self.simulate_outage = False

    def list_user_workspaces(self, actor: AuthenticatedUser) -> list[tuple[Workspace, WorkspaceMember]]:
        if self.simulate_outage:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Supabase offline", http_status=503, retryable=True)
        return [
            (self.workspaces[m.workspace_id], m)
            for m in self.members
            if m.user_id == actor.user_id and m.workspace_id in self.workspaces
        ]

    def get_membership(self, actor: AuthenticatedUser, workspace_id: UUID) -> WorkspaceMember | None:
        if self.simulate_outage:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Supabase offline", http_status=503, retryable=True)
        for m in self.members:
            if m.workspace_id == workspace_id and m.user_id == actor.user_id:
                return m
        return None

    def create_workspace(self, actor: AuthenticatedUser, name: str, slug: str) -> tuple[Workspace, WorkspaceMember]:
        if self.simulate_outage:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Supabase offline", http_status=503, retryable=True)
        ws = Workspace(id=uuid4(), name=name, slug=slug, created_by=actor.user_id)
        member = WorkspaceMember(id=uuid4(), workspace_id=ws.id, user_id=actor.user_id, role=WorkspaceRole.OWNER)
        self.workspaces[ws.id] = ws
        self.members.append(member)
        return ws, member


class InMemoryChannelRepo(ChannelRepositoryPort):
    def __init__(self) -> None:
        self.channels: dict[UUID, Channel] = {}
        self.versions: dict[UUID, list[ChannelProfileVersion]] = {}
        self.theme_changes: dict[UUID, list[EditorialThemeChange]] = {}

    def list_channels(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[Channel]:
        return [c for c in self.channels.values() if c.workspace_id == workspace_id]

    def get_channel(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID) -> Channel | None:
        c = self.channels.get(channel_id)
        if c and c.workspace_id == workspace_id:
            return c
        return None

    def create_channel_with_profile(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        display_name: str,
        handle: str | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion]:
        ch_id = uuid4()
        ver_id = uuid4()
        ver = ChannelProfileVersion(
            id=ver_id,
            workspace_id=workspace_id,
            channel_id=ch_id,
            version_number=1,
            name=profile.name,
            platform="youtube",
            language=profile.language,
            country=profile.country,
            timezone=profile.timezone,
            niche=profile.niche,
            positioning=profile.positioning,
            editorial_theme=profile.editorial_theme,
            audience_json=profile.audience_json,
            pillars_json=profile.pillars_json,
            voice_json=profile.voice_json,
            formats_json=profile.formats_json,
            objectives_json=profile.objectives_json,
            restrictions_json=profile.restrictions_json,
            effective_from=datetime.now(timezone.utc),
            change_summary=profile.change_summary,
            created_by=actor.user_id,
        )
        ch = Channel(
            id=ch_id,
            workspace_id=workspace_id,
            platform="youtube",
            display_name=display_name,
            handle=handle,
            status="active",
            active_profile_version_id=ver_id,
            version=1,
            created_by=actor.user_id,
        )
        self.channels[ch_id] = ch
        self.versions[ch_id] = [ver]
        self.theme_changes[ch_id] = []
        return ch, ver

    def create_profile_version(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel: Channel,
        previous_version: ChannelProfileVersion | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion, EditorialThemeChange | None]:
        next_num = (previous_version.version_number + 1) if previous_version else 1
        ver_id = uuid4()
        ver = ChannelProfileVersion(
            id=ver_id,
            workspace_id=workspace_id,
            channel_id=channel.id,
            version_number=next_num,
            name=profile.name,
            platform="youtube",
            language=profile.language,
            country=profile.country,
            timezone=profile.timezone,
            niche=profile.niche,
            positioning=profile.positioning,
            editorial_theme=profile.editorial_theme,
            audience_json=profile.audience_json,
            pillars_json=profile.pillars_json,
            voice_json=profile.voice_json,
            formats_json=profile.formats_json,
            objectives_json=profile.objectives_json,
            restrictions_json=profile.restrictions_json,
            effective_from=datetime.now(timezone.utc),
            change_summary=profile.change_summary,
            created_by=actor.user_id,
        )
        updated_ch = Channel(
            id=channel.id,
            workspace_id=channel.workspace_id,
            platform=channel.platform,
            display_name=channel.display_name,
            handle=channel.handle,
            status=channel.status,
            active_profile_version_id=ver_id,
            version=channel.version + 1,
            created_by=channel.created_by,
        )
        self.channels[channel.id] = updated_ch
        self.versions[channel.id].insert(0, ver)

        tc: EditorialThemeChange | None = None
        prev_theme = previous_version.editorial_theme if previous_version else ""
        if profile.editorial_theme.strip() and profile.editorial_theme.strip() != prev_theme:
            tc = EditorialThemeChange(
                id=uuid4(),
                workspace_id=workspace_id,
                channel_id=channel.id,
                previous_version_id=previous_version.id if previous_version else None,
                new_version_id=ver_id,
                previous_theme=prev_theme,
                new_theme=profile.editorial_theme.strip(),
                reason=profile.theme_change_reason,
                effective_at=datetime.now(timezone.utc),
                changed_by=actor.user_id,
            )
            self.theme_changes[channel.id].insert(0, tc)
        return updated_ch, ver, tc

    def list_profile_versions(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[ChannelProfileVersion]:
        return list(self.versions.get(channel_id, []))

    def list_theme_changes(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[EditorialThemeChange]:
        return list(self.theme_changes.get(channel_id, []))


def _make_token(user_id: UUID, expired: bool = False) -> str:
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=30)
    return jwt.encode(
        {"sub": str(user_id), "aud": "authenticated", "exp": exp},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _build_test_client():
    ws_repo = InMemoryWorkspaceRepo()
    ch_repo = InMemoryChannelRepo()
    ws_svc = WorkspaceService(ws_repo)
    ch_svc = ChannelService(ws_svc, ch_repo)
    verifier = SupabaseJWTVerifier(supabase_url="https://example.supabase.co", jwt_secret=TEST_JWT_SECRET)
    supa_fake = FakeSupabaseClient()
    container = ServiceContainer(
        jwt_verifier=verifier,
        supabase_client=supa_fake,  # type: ignore[arg-type]
        workspaces=ws_svc,
        channels=ch_svc,
        command_bus=CommandBus(ws_svc, None),  # type: ignore[arg-type]
    )
    app = create_app(settings=Settings(), container=container)
    return TestClient(app), ws_repo, ch_repo, supa_fake


def test_unauthenticated_and_expired_token_blocked() -> None:
    client, _, _, _ = _build_test_client()
    r1 = client.get("/api/v1/workspaces")
    assert r1.status_code == 401
    assert r1.json()["code"] == "AUTH_UNAUTHENTICATED"

    expired_token = _make_token(uuid4(), expired=True)
    r2 = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {expired_token}"})
    assert r2.status_code == 401
    assert r2.json()["code"] == "AUTH_UNAUTHENTICATED"


def test_cross_workspace_isolation_never_returns_empty() -> None:
    client, _, _, _ = _build_test_client()
    user_a = uuid4()
    user_b = uuid4()
    tok_a = _make_token(user_a)
    tok_b = _make_token(user_b)

    ws_a_resp = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"name": "Workspace A", "slug": "workspace-a"},
    )
    assert ws_a_resp.status_code == 201
    ws_a_id = ws_a_resp.json()["workspace"]["id"]

    ws_b_resp = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {tok_b}"},
        json={"name": "Workspace B", "slug": "workspace-b"},
    )
    assert ws_b_resp.status_code == 201
    ws_b_id = ws_b_resp.json()["workspace"]["id"]

    # User A trying to read User B's workspace gets 403 WORKSPACE_FORBIDDEN, never empty 200
    cross = client.get(
        "/api/v1/channels",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_b_id},
    )
    assert cross.status_code == 403
    assert cross.json()["code"] == "WORKSPACE_FORBIDDEN"

    # User A in own workspace gets legitimate empty list
    own = client.get(
        "/api/v1/channels",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
    )
    assert own.status_code == 200
    assert own.json()["items"] == []


def test_channel_profile_versioning_and_theme_change_history() -> None:
    client, _, _, _ = _build_test_client()
    user_a = uuid4()
    tok_a = _make_token(user_a)
    ws_id = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"name": "Canal Studio", "slug": "canal-studio"},
    ).json()["workspace"]["id"]

    create_ch = client.post(
        "/api/v1/channels",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_id},
        json={
            "display_name": "Outrora Docs",
            "handle": "@outrora",
            "profile": {
                "name": "Outrora Docs",
                "language": "pt-BR",
                "country": "BR",
                "timezone": "America/Sao_Paulo",
                "niche": "Documentarios Historicos",
                "editorial_theme": "POV Imersivo 35mm",
                "pillars_json": ["Historia", "Imersao"],
                "restrictions_json": {"forbidden_topics": ["clickbait falso"]},
            },
        },
    )
    assert create_ch.status_code == 201
    ch_id = create_ch.json()["channel"]["id"]
    v1_id = create_ch.json()["profile_version"]["id"]
    assert create_ch.json()["profile_version"]["version_number"] == 1

    # Update editorial theme -> creates v2 and records EditorialThemeChange without rewriting v1
    upd = client.put(
        f"/api/v1/channels/{ch_id}/profile",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_id},
        json={
            "name": "Outrora Docs",
            "language": "pt-BR",
            "country": "BR",
            "timezone": "America/Sao_Paulo",
            "niche": "Documentarios Historicos",
            "editorial_theme": "Registros de Salto v2",
            "change_summary": "Mudanca para formato 6 atos",
            "theme_change_reason": "Maior retencao narrativa",
        },
    )
    assert upd.status_code == 200
    assert upd.json()["profile_version"]["version_number"] == 2
    assert upd.json()["theme_change"]["previous_theme"] == "POV Imersivo 35mm"
    assert upd.json()["theme_change"]["new_theme"] == "Registros de Salto v2"

    versions = client.get(
        f"/api/v1/channels/{ch_id}/profile/versions",
        headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_id},
    ).json()["items"]
    assert len(versions) == 2
    assert versions[1]["id"] == v1_id
    assert versions[1]["editorial_theme"] == "POV Imersivo 35mm"


def test_supabase_outage_is_explicit_503_and_health_degraded() -> None:
    client, ws_repo, _, supa_fake = _build_test_client()
    user_a = uuid4()
    tok_a = _make_token(user_a)

    ws_repo.simulate_outage = True
    supa_fake.healthy = False

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["supabase_reachable"] is False

    res = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {tok_a}"})
    assert res.status_code == 503
    assert res.json()["code"] == "SUPABASE_UNAVAILABLE"
    assert res.json()["retryable"] is True


def test_untrusted_origin_rejected_on_mutation() -> None:
    client, _, _, _ = _build_test_client()
    tok = _make_token(uuid4())
    res = client.post(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {tok}", "Origin": "https://evil.example"},
        json={"name": "Hack", "slug": "hack-ws"},
    )
    assert res.status_code == 403
    assert res.json()["code"] == "WORKSPACE_FORBIDDEN"
