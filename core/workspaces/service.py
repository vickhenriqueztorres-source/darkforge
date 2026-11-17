from __future__ import annotations

import re
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, Workspace, WorkspaceMember, WorkspaceRole
from core.workspaces.ports import WorkspaceRepositoryPort

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


class WorkspaceService:
    """Enforces workspace membership and isolation on every call (AUTH-002, AUTH-003)."""

    def __init__(self, repo: WorkspaceRepositoryPort) -> None:
        self._repo = repo

    def list_workspaces(self, actor: AuthenticatedUser) -> list[tuple[Workspace, WorkspaceMember]]:
        return self._repo.list_user_workspaces(actor)

    def create_workspace(self, actor: AuthenticatedUser, name: str, slug: str) -> tuple[Workspace, WorkspaceMember]:
        clean_name = name.strip()
        clean_slug = slug.strip().lower()
        if len(clean_name) < 2 or len(clean_name) > 120:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Nome do workspace deve ter entre 2 e 120 caracteres.",
                http_status=422,
                details={"field": "name"},
            )
        if not _SLUG_RE.match(clean_slug):
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Slug invalido: use 3 a 64 caracteres minusculos, numeros ou hifen.",
                http_status=422,
                details={"field": "slug"},
            )
        return self._repo.create_workspace(actor, clean_name, clean_slug)

    def require_membership(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        allowed_roles: tuple[WorkspaceRole, ...] = (
            WorkspaceRole.OWNER,
            WorkspaceRole.EDITOR,
            WorkspaceRole.VIEWER,
        ),
    ) -> WorkspaceMember:
        member = self._repo.get_membership(actor, workspace_id)
        if member is None:
            raise AppError(
                code=ErrorCode.WORKSPACE_FORBIDDEN,
                message="Acesso negado: usuario nao pertence ao workspace informado.",
                http_status=403,
                details={"next_action": "Selecione um workspace autorizado."},
            )
        if member.role not in allowed_roles:
            raise AppError(
                code=ErrorCode.WORKSPACE_FORBIDDEN,
                message=f"Papel '{member.role.value}' nao possui permissao para esta operacao.",
                http_status=403,
                details={"next_action": "Solicite papel editor ou owner no workspace."},
            )
        return member
