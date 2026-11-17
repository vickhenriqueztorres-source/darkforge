from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any
from uuid import UUID, uuid4

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


def compute_brief_sha256(
    *,
    title: str,
    hook: str,
    angle: str,
    outline: list[dict[str, Any]],
    cta: str,
    target_format: str,
    source_refs: list[dict[str, Any]],
    generation_refs: list[str],
) -> str:
    canonical = json.dumps(
        {
            "title": title.strip(),
            "hook": hook.strip(),
            "angle": angle.strip(),
            "outline": outline,
            "cta": cta.strip(),
            "target_format": target_format,
            "source_refs": source_refs,
            "generation_refs": generation_refs,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EditorialStudioService:
    """EpisodeBrief versioning/freeze + portable exports + manual editorial calendar (EDIT-001..006)."""

    def __init__(self, workspaces: WorkspaceService, repo: Any) -> None:
        self._workspaces = workspaces
        self._repo = repo

    def create_brief(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        *,
        opportunity_id: UUID,
        title: str,
        hook: str,
        angle: str,
        outline: list[dict[str, Any]],
        cta: str = "",
        target_format: str = "long",
        generation_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        opp = self._repo.get_opportunity(workspace_id, opportunity_id)
        if opp is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Oportunidade vinculada nao encontrada.", http_status=404)
        if opp["status"] == "REJECTED":
            raise AppError(ErrorCode.VERSION_CONFLICT, "Oportunidade rejeitada nao pode gerar brief.", http_status=409)

        if not title.strip() or not hook.strip() or not angle.strip():
            raise AppError(ErrorCode.VALIDATION_ERROR, "title, hook e angle sao obrigatorios.", http_status=422)

        evidence = self._repo.list_evidence(workspace_id, "opportunity", opportunity_id)
        source_refs = [
            {
                "source_kind": ev["source_kind"],
                "source_id": ev["source_id"],
                "snippet": ev["snippet"],
                "source_url": ev.get("source_url"),
            }
            for ev in evidence
        ]
        gen_refs = list(generation_refs or [])
        digest = compute_brief_sha256(
            title=title,
            hook=hook,
            angle=angle,
            outline=outline,
            cta=cta,
            target_format=target_format,
            source_refs=source_refs,
            generation_refs=gen_refs,
        )
        group_id = uuid4()
        brief = self._repo.insert_brief(
            workspace_id=workspace_id,
            brief_group_id=group_id,
            version=1,
            parent_brief_id=None,
            opportunity_id=opportunity_id,
            channel_id=UUID(str(opp["channel_id"])),
            profile_version_id=UUID(str(opp["profile_version_id"])),
            title=title.strip(),
            hook=hook.strip(),
            angle=angle.strip(),
            outline_json=outline,
            cta=cta.strip(),
            target_format=target_format,
            source_refs_json=source_refs,
            generation_refs_json=gen_refs,
            content_sha256=digest,
            actor_id=actor.user_id,
        )
        history = self._repo.list_brief_history(workspace_id, UUID(str(brief["id"])))
        return {"brief": brief, "history": history}

    def list_briefs(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_briefs(workspace_id, channel_id=channel_id)

    def get_brief(self, actor: AuthenticatedUser, workspace_id: UUID, brief_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        brief = self._repo.get_brief(workspace_id, brief_id)
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)
        history = self._repo.list_brief_history(workspace_id, brief_id)
        versions = self._repo.list_brief_versions(workspace_id, UUID(str(brief["brief_group_id"])))
        return {"brief": brief, "history": history, "versions": versions}

    def update_draft(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        brief_id: UUID,
        *,
        title: str | None = None,
        hook: str | None = None,
        angle: str | None = None,
        outline: list[dict[str, Any]] | None = None,
        cta: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        brief = self._repo.get_brief(workspace_id, brief_id)
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)
        if brief["status"] in ("APPROVED", "SUPERSEDED", "ARCHIVED"):
            raise AppError(
                ErrorCode.VERSION_CONFLICT,
                f"EpisodeBrief v{brief['version']} ({brief['status']}) esta congelado; use create-version para editar.",
                http_status=409,
                details={"brief_id": str(brief_id), "status": brief["status"], "version": brief["version"]},
            )
        new_title = (title if title is not None else brief["title"]).strip()
        new_hook = (hook if hook is not None else brief["hook"]).strip()
        new_angle = (angle if angle is not None else brief["angle"]).strip()
        new_outline = outline if outline is not None else brief["outline_json"]
        new_cta = (cta if cta is not None else brief["cta"]).strip()
        digest = compute_brief_sha256(
            title=new_title,
            hook=new_hook,
            angle=new_angle,
            outline=new_outline,
            cta=new_cta,
            target_format=brief["target_format"],
            source_refs=brief["source_refs_json"],
            generation_refs=brief["generation_refs_json"],
        )
        updated = self._repo.update_brief_draft(
            workspace_id=workspace_id,
            brief_id=brief_id,
            title=new_title,
            hook=new_hook,
            angle=new_angle,
            outline_json=new_outline,
            cta=new_cta,
            content_sha256=digest,
            actor_id=actor.user_id,
            from_status=brief["status"],
            notes=notes,
        )
        history = self._repo.list_brief_history(workspace_id, brief_id)
        return {"brief": updated, "history": history}

    def approve_brief(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        brief_id: UUID,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER,))
        brief = self._repo.get_brief(workspace_id, brief_id)
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)
        if brief["status"] == "APPROVED":
            return {"brief": brief, "history": self._repo.list_brief_history(workspace_id, brief_id), "already_approved": True}
        if brief["status"] not in ("DRAFT", "IN_REVIEW"):
            raise AppError(ErrorCode.VERSION_CONFLICT, f"Nao e possivel aprovar brief em estado {brief['status']}.", http_status=409)
        approved = self._repo.approve_brief(
            workspace_id=workspace_id,
            brief_id=brief_id,
            from_status=brief["status"],
            actor_id=actor.user_id,
            notes=notes,
        )
        history = self._repo.list_brief_history(workspace_id, brief_id)
        return {"brief": approved, "history": history, "already_approved": False}

    def create_new_version(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        brief_id: UUID,
        *,
        title: str | None = None,
        hook: str | None = None,
        angle: str | None = None,
        outline: list[dict[str, Any]] | None = None,
        cta: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        current = self._repo.get_brief(workspace_id, brief_id)
        if current is None:
            raise AppError(ErrorCode.NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)

        new_title = (title if title is not None else current["title"]).strip()
        new_hook = (hook if hook is not None else current["hook"]).strip()
        new_angle = (angle if angle is not None else current["angle"]).strip()
        new_outline = outline if outline is not None else current["outline_json"]
        new_cta = (cta if cta is not None else current["cta"]).strip()
        digest = compute_brief_sha256(
            title=new_title,
            hook=new_hook,
            angle=new_angle,
            outline=new_outline,
            cta=new_cta,
            target_format=current["target_format"],
            source_refs=current["source_refs_json"],
            generation_refs=current["generation_refs_json"],
        )
        new_brief = self._repo.create_next_brief_version(
            workspace_id=workspace_id,
            parent_brief=current,
            title=new_title,
            hook=new_hook,
            angle=new_angle,
            outline_json=new_outline,
            cta=new_cta,
            content_sha256=digest,
            actor_id=actor.user_id,
            notes=notes,
        )
        versions = self._repo.list_brief_versions(workspace_id, UUID(str(current["brief_group_id"])))
        history = self._repo.list_brief_history(workspace_id, UUID(str(new_brief["id"])))
        return {"brief": new_brief, "versions": versions, "history": history}

    def export_brief(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        brief_id: UUID,
        fmt: str = "markdown",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        if fmt not in ("markdown", "json", "csv"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Formato de exportacao suportado: markdown, json, csv.", http_status=422)
        brief = self._repo.get_brief(workspace_id, brief_id)
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)

        self._repo.record_brief_action(
            workspace_id=workspace_id,
            brief_id=brief_id,
            action="EXPORT",
            from_status=brief["status"],
            to_status=brief["status"],
            notes=f"format={fmt}",
            actor_id=actor.user_id,
        )

        if fmt == "json":
            content = json.dumps(
                {
                    "brief_id": str(brief["id"]),
                    "brief_group_id": str(brief["brief_group_id"]),
                    "version": brief["version"],
                    "status": brief["status"],
                    "content_sha256": brief["content_sha256"],
                    "profile_version_id": str(brief["profile_version_id"]),
                    "opportunity_id": str(brief["opportunity_id"]),
                    "title": brief["title"],
                    "hook": brief["hook"],
                    "angle": brief["angle"],
                    "outline": brief["outline_json"],
                    "cta": brief["cta"],
                    "source_refs": brief["source_refs_json"],
                    "generation_refs": brief["generation_refs_json"],
                },
                indent=2,
                ensure_ascii=False,
            )
            return {"format": "json", "filename": f"brief-v{brief['version']}.json", "content": content}

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["brief_id", "version", "status", "content_sha256", "title", "hook", "angle", "cta", "sources_count"])
            writer.writerow([
                str(brief["id"]),
                brief["version"],
                brief["status"],
                brief["content_sha256"],
                brief["title"],
                brief["hook"],
                brief["angle"],
                brief["cta"],
                len(brief["source_refs_json"]),
            ])
            return {"format": "csv", "filename": f"brief-v{brief['version']}.csv", "content": buf.getvalue()}

        lines = [
            f"# {brief['title']} (v{brief['version']} - {brief['status']})",
            "",
            f"- **Brief ID:** `{brief['id']}`",
            f"- **Group ID:** `{brief['brief_group_id']}`",
            f"- **SHA-256:** `{brief['content_sha256']}`",
            f"- **Profile Version ID:** `{brief['profile_version_id']}`",
            f"- **Opportunity ID:** `{brief['opportunity_id']}`",
            "",
            "## Hook",
            brief["hook"],
            "",
            "## Angulo Editorial",
            brief["angle"],
            "",
            "## Estrutura (Outline)",
        ]
        for idx, block in enumerate(brief["outline_json"] or [], start=1):
            lines.append(f"{idx}. **{block.get('section', 'Bloco')}**: {block.get('notes', '')}")
        lines.extend(["", "## CTA", brief["cta"] or "-", "", "## Fontes & Evidencias"])
        for src in brief["source_refs_json"] or []:
            lines.append(f"- [{src.get('source_kind')}] `{src.get('source_id')}`: {src.get('snippet', '')}")
        return {"format": "markdown", "filename": f"brief-v{brief['version']}.md", "content": "\n".join(lines)}

    def create_calendar_item(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        *,
        channel_id: UUID,
        title: str,
        scheduled_for: str,
        brief_id: UUID | None = None,
        notes: str | None = None,
        auto_publish_enabled: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if auto_publish_enabled:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Publicacao automatica no YouTube e proibida nesta plataforma (EDIT-005).",
                http_status=422,
            )
        return self._repo.insert_calendar_item(
            workspace_id=workspace_id,
            channel_id=channel_id,
            brief_id=brief_id,
            title=title.strip(),
            scheduled_for=scheduled_for,
            notes=notes,
            actor_id=actor.user_id,
        )

    def list_calendar_items(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_calendar_items(workspace_id)

    def update_calendar_status(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        item_id: UUID,
        status: str,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if status not in ("PLANNED", "IN_PRODUCTION", "READY_FOR_MANUAL_PUBLISH", "PUBLISHED_MANUALLY", "CANCELED"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Status de calendario invalido.", http_status=422)
        item = self._repo.update_calendar_status(workspace_id, item_id, status)
        if item is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Item de calendario nao encontrado.", http_status=404)
        return item
