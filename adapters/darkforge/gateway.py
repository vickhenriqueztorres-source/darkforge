from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.errors import AppError, ErrorCode


class DarkForgeGateway:
    """
    Single-writer gateway to external DarkForge Core executor (SP-08, ADR-016).
    Never invents a fake video renderer or writes to local SQLite.
    """

    def __init__(self, core_path: str | None = None, history_path: str | None = None) -> None:
        self._core_path = Path(core_path) if core_path and core_path.strip() else None
        self._history_path = Path(history_path) if history_path and history_path.strip() else None

    def _is_core_ready(self) -> bool:
        if self._core_path is None or not self._core_path.exists():
            return False
        # Core repo/entrypoint must actually exist with recognizable code/manifest contract
        if self._core_path.is_dir():
            return any((self._core_path / marker).exists() for marker in ("pyproject.toml", "darkforge", "cli.py", "main.py"))
        return self._core_path.is_file()

    def healthcheck(self) -> dict[str, Any]:
        ready = self._is_core_ready()
        historical_manifests: list[str] = []
        if self._history_path and self._history_path.exists():
            for mf in self._history_path.glob("job_*/manifest.json"):
                historical_manifests.append(mf.parent.name)
        return {
            "available": ready,
            "core_path": str(self._core_path) if self._core_path else None,
            "mode": "real_core" if ready else "blocked_missing_core",
            "supported_pipelines": ["media_vertical_v1"] if ready else [],
            "historical_manifests_readonly": historical_manifests,
            "reason": None
            if ready
            else "Nucleo DarkForge ausente (DARKFORGE_CORE_PATH nao configurado ou sem codigo-fonte). Execucao real bloqueada conforme ADR-016.",
        }

    def dispatch_production(self, intent: dict[str, Any], brief_snapshot: dict[str, Any]) -> dict[str, Any]:
        if not self._is_core_ready():
            raise AppError(
                ErrorCode.DARKFORGE_UNAVAILABLE,
                "Executor DarkForge indisponivel: configure DARKFORGE_CORE_PATH com o nucleo real (sem executor simulado).",
                http_status=503,
                retryable=True,
                details={
                    "intent_id": str(intent["id"]),
                    "brief_id": str(brief_snapshot["id"]),
                    "next_action": "Fornecer DARKFORGE_CORE_PATH valido e re-despachar a intencao.",
                },
            )
        # When real core path exists, dispatch contract creates a traceable handoff packet (single-writer stays in Postgres)
        assert self._core_path is not None
        handoff_dir = self._core_path / "handoffs"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        handoff_file = handoff_dir / f"intent_{intent['id']}.json"
        handoff_payload = {
            "intent_id": str(intent["id"]),
            "workspace_id": str(intent["workspace_id"]),
            "brief_id": str(brief_snapshot["id"]),
            "brief_version": brief_snapshot["version"],
            "brief_content_sha256": brief_snapshot["content_sha256"],
            "pipeline_version": intent.get("pipeline_version", "media_vertical_v1"),
            "title": brief_snapshot["title"],
            "hook": brief_snapshot["hook"],
            "angle": brief_snapshot["angle"],
            "outline": brief_snapshot.get("outline_json", []),
            "cta": brief_snapshot.get("cta", ""),
        }
        handoff_file.write_text(json.dumps(handoff_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "status": "DISPATCHED",
            "external_job_id": f"df-handoff-{intent['id']}",
            "handoff_file": str(handoff_file),
        }

    def validate_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        if not manifest.get("pipeline_version"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "manifest.pipeline_version obrigatorio.", http_status=422)
        if not isinstance(manifest.get("artifacts"), list):
            raise AppError(ErrorCode.VALIDATION_ERROR, "manifest.artifacts deve ser lista.", http_status=422)
        return manifest
