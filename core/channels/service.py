from __future__ import annotations

from uuid import UUID

from core.channels.models import (
    Channel,
    ChannelProfileInput,
    ChannelProfileVersion,
    EditorialThemeChange,
)
from core.channels.ports import ChannelRepositoryPort
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class ChannelService:
    """Manages channels and immutable ChannelProfileVersion history (CH-001..CH-004)."""

    def __init__(self, workspaces: WorkspaceService, repo: ChannelRepositoryPort) -> None:
        self._workspaces = workspaces
        self._repo = repo

    def list_channels(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[Channel]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_channels(actor, workspace_id)

    def create_channel(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        display_name: str,
        handle: str | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        self._validate_profile_input(profile)
        clean_display = display_name.strip()
        if not clean_display:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Nome de exibicao do canal e obrigatorio.",
                http_status=422,
                details={"field": "display_name"},
            )
        return self._repo.create_channel_with_profile(actor, workspace_id, clean_display, handle, profile)

    def update_profile(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion, EditorialThemeChange | None]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        self._validate_profile_input(profile)
        channel = self._repo.get_channel(actor, workspace_id, channel_id)
        if channel is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Canal nao encontrado neste workspace.",
                http_status=404,
            )
        versions = self._repo.list_profile_versions(actor, workspace_id, channel_id)
        previous_version = versions[0] if versions else None
        return self._repo.create_profile_version(actor, workspace_id, channel, previous_version, profile)

    def list_profile_versions(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[ChannelProfileVersion]:
        self._workspaces.require_membership(actor, workspace_id)
        channel = self._repo.get_channel(actor, workspace_id, channel_id)
        if channel is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Canal nao encontrado neste workspace.",
                http_status=404,
            )
        return self._repo.list_profile_versions(actor, workspace_id, channel_id)

    def list_theme_changes(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[EditorialThemeChange]:
        self._workspaces.require_membership(actor, workspace_id)
        channel = self._repo.get_channel(actor, workspace_id, channel_id)
        if channel is None:
            raise AppError(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message="Canal nao encontrado neste workspace.",
                http_status=404,
            )
        return self._repo.list_theme_changes(actor, workspace_id, channel_id)

    @staticmethod
    def _validate_profile_input(profile: ChannelProfileInput) -> None:
        required_text = {
            "name": profile.name,
            "language": profile.language,
            "country": profile.country,
            "timezone": profile.timezone,
            "niche": profile.niche,
        }
        for field_name, val in required_text.items():
            if not val or not val.strip():
                raise AppError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Campo obrigatorio ausente no perfil editorial: {field_name}.",
                    http_status=422,
                    details={"field": field_name},
                )
