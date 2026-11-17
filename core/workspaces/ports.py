from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from core.workspaces.models import AuthenticatedUser, Workspace, WorkspaceMember


class WorkspaceRepositoryPort(ABC):
    @abstractmethod
    def list_user_workspaces(self, actor: AuthenticatedUser) -> list[tuple[Workspace, WorkspaceMember]]:
        raise NotImplementedError

    @abstractmethod
    def get_membership(self, actor: AuthenticatedUser, workspace_id: UUID) -> WorkspaceMember | None:
        raise NotImplementedError

    @abstractmethod
    def create_workspace(self, actor: AuthenticatedUser, name: str, slug: str) -> tuple[Workspace, WorkspaceMember]:
        raise NotImplementedError
