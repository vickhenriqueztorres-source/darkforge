from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from core.channels.models import (
    Channel,
    ChannelProfileInput,
    ChannelProfileVersion,
    EditorialThemeChange,
)
from core.workspaces.models import AuthenticatedUser


class ChannelRepositoryPort(ABC):
    @abstractmethod
    def list_channels(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[Channel]:
        raise NotImplementedError

    @abstractmethod
    def get_channel(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID) -> Channel | None:
        raise NotImplementedError

    @abstractmethod
    def create_channel_with_profile(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        display_name: str,
        handle: str | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion]:
        raise NotImplementedError

    @abstractmethod
    def create_profile_version(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel: Channel,
        previous_version: ChannelProfileVersion | None,
        profile: ChannelProfileInput,
    ) -> tuple[Channel, ChannelProfileVersion, EditorialThemeChange | None]:
        raise NotImplementedError

    @abstractmethod
    def list_profile_versions(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[ChannelProfileVersion]:
        raise NotImplementedError

    @abstractmethod
    def list_theme_changes(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID
    ) -> list[EditorialThemeChange]:
        raise NotImplementedError
