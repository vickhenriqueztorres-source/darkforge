from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from adapters.supabase_db.client import SupabaseRestClient
from core.channels.models import (
    Channel,
    ChannelProfileInput,
    ChannelProfileVersion,
    EditorialThemeChange,
)
from core.channels.ports import ChannelRepositoryPort
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, Workspace, WorkspaceMember, WorkspaceRole
from core.workspaces.ports import WorkspaceRepositoryPort


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    return datetime.fromisoformat(val.replace("Z", "+00:00"))


class SupabaseWorkspaceRepository(WorkspaceRepositoryPort):
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    def list_user_workspaces(self, actor: AuthenticatedUser) -> list[tuple[Workspace, WorkspaceMember]]:
        if not (actor.email or "").lower().endswith("@darkforge.invalid"):
            try:
                self._client.request(
                    "POST",
                    "rpc/claim_launcher_workspaces",
                    actor.access_token,
                    json_body={},
                )
            except Exception:
                pass
        rows = self._client.request(
            "GET",
            "workspace_members",
            actor.access_token,
            params={
                "select": "id,workspace_id,user_id,role,created_at,workspaces(id,name,slug,settings_json,version,created_by,created_at,updated_at)",
                "user_id": f"eq.{actor.user_id}",
                "order": "created_at.asc",
            },
        )
        result: list[tuple[Workspace, WorkspaceMember]] = []
        for row in rows or []:
            ws_data = row.get("workspaces")
            if not ws_data:
                continue
            ws = Workspace(
                id=UUID(ws_data["id"]),
                name=ws_data["name"],
                slug=ws_data["slug"],
                settings_json=ws_data.get("settings_json") or {},
                version=int(ws_data.get("version", 1)),
                created_by=UUID(ws_data["created_by"]),
                created_at=_parse_dt(ws_data.get("created_at")),
                updated_at=_parse_dt(ws_data.get("updated_at")),
            )
            member = WorkspaceMember(
                id=UUID(row["id"]),
                workspace_id=UUID(row["workspace_id"]),
                user_id=UUID(row["user_id"]),
                role=WorkspaceRole(row["role"]),
                created_at=_parse_dt(row.get("created_at")),
            )
            result.append((ws, member))
        return result

    def get_membership(self, actor: AuthenticatedUser, workspace_id: UUID) -> WorkspaceMember | None:
        rows = self._client.request(
            "GET",
            "workspace_members",
            actor.access_token,
            params={
                "select": "id,workspace_id,user_id,role,created_at",
                "workspace_id": f"eq.{workspace_id}",
                "user_id": f"eq.{actor.user_id}",
                "limit": "1",
            },
        )
        if not rows:
            return None
        row = rows[0]
        return WorkspaceMember(
            id=UUID(row["id"]),
            workspace_id=UUID(row["workspace_id"]),
            user_id=UUID(row["user_id"]),
            role=WorkspaceRole(row["role"]),
            created_at=_parse_dt(row.get("created_at")),
        )

    def create_workspace(self, actor: AuthenticatedUser, name: str, slug: str) -> tuple[Workspace, WorkspaceMember]:
        workspace_id_raw = self._client.request(
            "POST",
            "rpc/create_workspace_with_owner",
            actor.access_token,
            json_body={"p_name": name, "p_slug": slug},
        )
        ws_id = UUID(str(workspace_id_raw))
        for ws, member in self.list_user_workspaces(actor):
            if ws.id == ws_id:
                return ws, member
        raise AppError(
            code=ErrorCode.SUPABASE_UNAVAILABLE,
            message="Workspace criado, mas nao foi possivel confirmar sua leitura.",
            http_status=503,
            retryable=True,
        )


class SupabaseChannelRepository(ChannelRepositoryPort):
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    def list_channels(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[Channel]:
        rows = self._client.request(
            "GET",
            "channels",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "order": "created_at.desc",
            },
        )
        return [self._to_channel(r) for r in rows or []]

    def get_channel(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID) -> Channel | None:
        rows = self._client.request(
            "GET",
            "channels",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "id": f"eq.{channel_id}",
                "limit": "1",
            },
        )
        return self._to_channel(rows[0]) if rows else None

    def create_channel_with_profile(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        display_name: str,
        handle: str | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion]:
        ch_rows = self._client.request(
            "POST",
            "channels",
            actor.access_token,
            prefer="return=representation",
            json_body={
                "workspace_id": str(workspace_id),
                "platform": "youtube",
                "display_name": display_name,
                "handle": handle,
                "created_by": str(actor.user_id),
            },
        )
        channel = self._to_channel(ch_rows[0])
        ver_rows = self._client.request(
            "POST",
            "channel_profile_versions",
            actor.access_token,
            prefer="return=representation",
            json_body=self._profile_payload(actor, workspace_id, channel.id, 1, profile),
        )
        version = self._to_version(ver_rows[0])
        upd_rows = self._client.request(
            "PATCH",
            "channels",
            actor.access_token,
            params={"id": f"eq.{channel.id}", "workspace_id": f"eq.{workspace_id}"},
            prefer="return=representation",
            json_body={"active_profile_version_id": str(version.id), "version": channel.version + 1},
        )
        return self._to_channel(upd_rows[0]), version

    def create_profile_version(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel: Channel,
        previous_version: ChannelProfileVersion | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion, EditorialThemeChange | None]:
        next_num = (previous_version.version_number + 1) if previous_version else 1
        ver_rows = self._client.request(
            "POST",
            "channel_profile_versions",
            actor.access_token,
            prefer="return=representation",
            json_body=self._profile_payload(actor, workspace_id, channel.id, next_num, profile),
        )
        new_version = self._to_version(ver_rows[0])
        upd_rows = self._client.request(
            "PATCH",
            "channels",
            actor.access_token,
            params={"id": f"eq.{channel.id}", "workspace_id": f"eq.{workspace_id}"},
            prefer="return=representation",
            json_body={"active_profile_version_id": str(new_version.id), "version": channel.version + 1},
        )
        theme_change: EditorialThemeChange | None = None
        prev_theme = previous_version.editorial_theme if previous_version else ""
        if profile.editorial_theme.strip() and profile.editorial_theme.strip() != prev_theme:
            tc_rows = self._client.request(
                "POST",
                "editorial_theme_changes",
                actor.access_token,
                prefer="return=representation",
                json_body={
                    "workspace_id": str(workspace_id),
                    "channel_id": str(channel.id),
                    "previous_version_id": str(previous_version.id) if previous_version else None,
                    "new_version_id": str(new_version.id),
                    "previous_theme": prev_theme,
                    "new_theme": profile.editorial_theme.strip(),
                    "reason": profile.theme_change_reason.strip(),
                    "changed_by": str(actor.user_id),
                },
            )
            theme_change = self._to_theme_change(tc_rows[0])
        return self._to_channel(upd_rows[0]), new_version, theme_change

    def list_profile_versions(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[ChannelProfileVersion]:
        rows = self._client.request(
            "GET",
            "channel_profile_versions",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "channel_id": f"eq.{channel_id}",
                "order": "version_number.desc",
            },
        )
        return [self._to_version(r) for r in rows or []]

    def list_theme_changes(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[EditorialThemeChange]:
        rows = self._client.request(
            "GET",
            "editorial_theme_changes",
            actor.access_token,
            params={
                "select": "*",
                "workspace_id": f"eq.{workspace_id}",
                "channel_id": f"eq.{channel_id}",
                "order": "effective_at.desc",
            },
        )
        return [self._to_theme_change(r) for r in rows or []]

    @staticmethod
    def _profile_payload(
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        version_number: int,
        profile: ChannelProfileInput,
    ) -> dict[str, Any]:
        return {
            "workspace_id": str(workspace_id),
            "channel_id": str(channel_id),
            "version_number": version_number,
            "name": profile.name.strip(),
            "platform": "youtube",
            "language": profile.language.strip(),
            "country": profile.country.strip(),
            "timezone": profile.timezone.strip(),
            "niche": profile.niche.strip(),
            "positioning": profile.positioning.strip(),
            "editorial_theme": profile.editorial_theme.strip(),
            "audience_json": profile.audience_json,
            "pillars_json": profile.pillars_json,
            "voice_json": profile.voice_json,
            "formats_json": profile.formats_json,
            "objectives_json": profile.objectives_json,
            "restrictions_json": profile.restrictions_json,
            "change_summary": profile.change_summary.strip() or f"Versao {version_number}",
            "created_by": str(actor.user_id),
        }

    @staticmethod
    def _to_channel(r: dict[str, Any]) -> Channel:
        return Channel(
            id=UUID(r["id"]),
            workspace_id=UUID(r["workspace_id"]),
            platform=r["platform"],
            display_name=r["display_name"],
            status=r["status"],
            created_by=UUID(r["created_by"]),
            external_channel_id=r.get("external_channel_id"),
            handle=r.get("handle"),
            active_profile_version_id=UUID(r["active_profile_version_id"]) if r.get("active_profile_version_id") else None,
            version=int(r.get("version", 1)),
            created_at=_parse_dt(r.get("created_at")),
            updated_at=_parse_dt(r.get("updated_at")),
        )

    @staticmethod
    def _to_version(r: dict[str, Any]) -> ChannelProfileVersion:
        return ChannelProfileVersion(
            id=UUID(r["id"]),
            workspace_id=UUID(r["workspace_id"]),
            channel_id=UUID(r["channel_id"]),
            version_number=int(r["version_number"]),
            name=r["name"],
            platform=r["platform"],
            language=r["language"],
            country=r["country"],
            timezone=r["timezone"],
            niche=r["niche"],
            positioning=r.get("positioning", ""),
            editorial_theme=r.get("editorial_theme", ""),
            audience_json=r.get("audience_json") or {},
            pillars_json=r.get("pillars_json") or [],
            voice_json=r.get("voice_json") or {},
            formats_json=r.get("formats_json") or [],
            objectives_json=r.get("objectives_json") or [],
            restrictions_json=r.get("restrictions_json") or {},
            effective_from=_parse_dt(r.get("effective_from")) or datetime.now(timezone.utc),
            change_summary=r.get("change_summary", ""),
            created_by=UUID(r["created_by"]),
            created_at=_parse_dt(r.get("created_at")),
        )

    @staticmethod
    def _to_theme_change(r: dict[str, Any]) -> EditorialThemeChange:
        return EditorialThemeChange(
            id=UUID(r["id"]),
            workspace_id=UUID(r["workspace_id"]),
            channel_id=UUID(r["channel_id"]),
            previous_version_id=UUID(r["previous_version_id"]) if r.get("previous_version_id") else None,
            new_version_id=UUID(r["new_version_id"]),
            previous_theme=r.get("previous_theme", ""),
            new_theme=r["new_theme"],
            reason=r.get("reason", ""),
            effective_at=_parse_dt(r.get("effective_at")) or datetime.now(timezone.utc),
            changed_by=UUID(r["changed_by"]),
        )
