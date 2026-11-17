from __future__ import annotations

import re
from typing import Any, Protocol
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class DarkForgeGatewayPort(Protocol):
    def healthcheck(self) -> dict[str, Any]: ...

    def dispatch_production(self, intent: dict[str, Any], brief_snapshot: dict[str, Any]) -> dict[str, Any]: ...

    def validate_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]: ...


class ProductionIntentService:
    """DarkForge Production Gate & Single-Writer Orchestration (SP-08: PROD-001..005)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        gateway: DarkForgeGatewayPort,
        command_bus: Any = None,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._gateway = gateway
        self._bus = command_bus

    def gateway_health(self, actor: AuthenticatedUser, workspace_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._gateway.healthcheck()

    def create_production_intent(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        brief_id: UUID,
        *,
        idempotency_key: str,
        pipeline_version: str = "media_vertical_v1",
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        key = idempotency_key.strip()
        if not (8 <= len(key) <= 128):
            raise AppError(ErrorCode.VALIDATION_ERROR, "idempotency_key deve ter entre 8 e 128 caracteres.", http_status=422)

        existing = self._repo.find_intent_by_idempotency(workspace_id, key)
        if existing is not None:
            return {"intent": existing, "deduplicated": True}

        brief = self._repo.get_brief(workspace_id, brief_id)
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief nao encontrado.", http_status=404)
        if brief["status"] != "APPROVED":
            raise AppError(
                ErrorCode.VERSION_CONFLICT,
                f"Somente EpisodeBrief APPROVED pode virar intencao de producao (estado atual: {brief['status']}).",
                http_status=409,
                details={"brief_id": str(brief_id), "status": brief["status"]},
            )

        job_id: UUID | None = None
        if self._bus is not None:
            job_rec, _ = self._bus.dispatch_job_command(
                actor=actor,
                workspace_id=workspace_id,
                job_type="darkforge_production",
                idempotency_key=f"df-{key}",
                payload_json={
                    "brief_id": str(brief_id),
                    "brief_version": int(brief["version"]),
                    "brief_content_sha256": brief["content_sha256"],
                    "pipeline_version": pipeline_version,
                },
                channel_id=UUID(str(brief["channel_id"])),
                total_steps=5,
                priority=80,
            )
            job_id = job_rec.id

        intent = self._repo.insert_intent(
            workspace_id=workspace_id,
            channel_id=UUID(str(brief["channel_id"])),
            brief_id=brief_id,
            brief_version=int(brief["version"]),
            brief_content_sha256=str(brief["content_sha256"]),
            pipeline_version=pipeline_version,
            idempotency_key=key,
            job_id=job_id,
            created_by=actor.user_id,
        )
        return {"intent": intent, "deduplicated": False}

    def dispatch_intent(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        intent_id: UUID,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        intent = self._repo.get_intent(workspace_id, intent_id)
        if intent is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "ProductionIntent nao encontrada.", http_status=404)
        brief = self._repo.get_brief(workspace_id, UUID(str(intent["brief_id"])))
        if brief is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "EpisodeBrief vinculado nao encontrado.", http_status=404)

        try:
            dispatch_res = self._gateway.dispatch_production(intent, brief)
        except AppError as exc:
            self._repo.mark_intent_status(
                workspace_id=workspace_id,
                intent_id=intent_id,
                status="BLOCKED",
                error_code=exc.code.value,
                error_message=exc.message,
            )
            if intent.get("job_id"):
                self._repo.mark_job_blocked(
                    workspace_id=workspace_id,
                    job_id=UUID(str(intent["job_id"])),
                    error_code=exc.code.value,
                    error_message=exc.message,
                )
            raise

        updated = self._repo.mark_intent_status(
            workspace_id=workspace_id,
            intent_id=intent_id,
            status=dispatch_res.get("status", "DISPATCHED"),
            external_darkforge_job_id=dispatch_res.get("external_job_id"),
        )
        return {"intent": updated, "dispatch": dispatch_res}

    def complete_with_validated_manifest(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        intent_id: UUID,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        intent = self._repo.get_intent(workspace_id, intent_id)
        if intent is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "ProductionIntent nao encontrada.", http_status=404)

        validated = self._gateway.validate_manifest(manifest)
        artifacts = validated.get("artifacts", [])
        if not artifacts:
            raise AppError(
                ErrorCode.STORAGE_CHECKSUM_MISMATCH,
                "Manifest DarkForge sem artefatos reais; conclusao bloqueada (PROD-005).",
                http_status=422,
            )

        for art in artifacts:
            digest = str(art.get("sha256", "")).lower()
            storage_obj_id = art.get("storage_object_id")
            if not SHA256_RE.match(digest) or not storage_obj_id:
                raise AppError(
                    ErrorCode.STORAGE_CHECKSUM_MISMATCH,
                    "Todo artefato exige sha256 valido (64 hex) e storage_object_id no bucket production.",
                    http_status=422,
                )
            obj = self._repo.get_storage_object(workspace_id, UUID(str(storage_obj_id)))
            if obj is None or obj["status"] != "READY" or obj["sha256"] != digest:
                raise AppError(
                    ErrorCode.STORAGE_CHECKSUM_MISMATCH,
                    "StorageObject ausente, nao READY ou com checksum divergente do manifest.",
                    http_status=422,
                    details={"storage_object_id": str(storage_obj_id)},
                )

        updated = self._repo.mark_intent_ready(
            workspace_id=workspace_id,
            intent_id=intent_id,
            manifest_json=validated,
        )
        return {"intent": updated, "manifest_validated": True}

    def list_intents(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_intents(workspace_id)
