"""Drop-in Telemetry Client (Python) para o projeto separado O Outro Lado.

Suporta envio via HTTP para a API Central (`POST /api/v1/external-agents/report`)
ou diretamente via Supabase RPC (`POST /rest/v1/rpc/ingest_external_agent_event`).
Sempre fail-open por padrao para nunca interromper o pipeline se a rede oscilar.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Iterator


class CentralTelemetryClient:
    def __init__(
        self,
        *,
        api_base_url: str | None = None,
        ingest_token: str | None = None,
        channel_id: str | None = None,
        supabase_url: str | None = None,
        supabase_service_role_key: str | None = None,
        workspace_id: str | None = None,
        source_repo: str = "O-OUTRO-LADO",
        fail_open: bool = True,
        timeout_sec: float = 5.0,
    ) -> None:
        self.api_base_url = (api_base_url or os.getenv("MANAGET_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.ingest_token = ingest_token or os.getenv("MANAGET_INGEST_TOKEN", "")
        self.channel_id = channel_id or os.getenv("MANAGET_CHANNEL_ID", "")
        self.supabase_url = (supabase_url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.supabase_key = supabase_service_role_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.workspace_id = workspace_id or os.getenv("MANAGET_WORKSPACE_ID", "")
        self.source_repo = source_repo
        self.host_name = socket.gethostname()
        self.fail_open = fail_open
        self.timeout_sec = timeout_sec

    def report(
        self,
        *,
        agent_key: str,
        status: str,
        external_run_id: str,
        pipeline_kind: str = "custom",
        run_title: str | None = None,
        external_execution_id: str | None = None,
        stage_label: str | None = None,
        progress: float | None = None,
        model_name: str | None = None,
        event_type: str | None = None,
        level: str = "info",
        message: str | None = None,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        metrics: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        attempt: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self.ingest_token:
            url = f"{self.api_base_url}/api/v1/external-agents/report"
            headers = {
                "Content-Type": "application/json",
                "X-Ingest-Token": self.ingest_token,
            }
            body: dict[str, Any] = {
                "channel_id": self.channel_id or None,
                "agent_key": agent_key,
                "status": status,
                "external_run_id": external_run_id,
                "pipeline_kind": pipeline_kind,
                "run_title": run_title,
                "external_execution_id": external_execution_id,
                "stage_label": stage_label,
                "progress": progress,
                "model_name": model_name,
                "event_type": event_type,
                "level": level,
                "message": message,
                "input_summary": input_summary or {},
                "output_summary": output_summary or {},
                "artifacts": artifacts or [],
                "metrics": metrics or {},
                "error_code": error_code,
                "error_message": error_message,
                "host_name": self.host_name,
                "source_repo": self.source_repo,
                "attempt": attempt,
                "metadata": metadata or {},
            }
        elif self.supabase_url and self.supabase_key:
            url = f"{self.supabase_url}/rest/v1/rpc/ingest_external_agent_event"
            headers = {
                "Content-Type": "application/json",
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
            }
            body = {
                "p_workspace_id": self.workspace_id,
                "p_channel_id": self.channel_id,
                "p_agent_key": agent_key,
                "p_status": status,
                "p_external_run_id": external_run_id,
                "p_pipeline_kind": pipeline_kind,
                "p_run_title": run_title,
                "p_external_execution_id": external_execution_id,
                "p_stage_label": stage_label,
                "p_progress": progress,
                "p_model_name": model_name,
                "p_event_type": event_type,
                "p_level": level,
                "p_message": message,
                "p_input_summary": input_summary or {},
                "p_output_summary": output_summary or {},
                "p_artifacts": artifacts or [],
                "p_metrics": metrics or {},
                "p_error_code": error_code,
                "p_error_message": error_message,
                "p_host_name": self.host_name,
                "p_source_repo": self.source_repo,
                "p_attempt": attempt,
                "p_metadata": metadata or {},
            }
        else:
            if not self.fail_open:
                raise RuntimeError("Configure MANAGET_INGEST_TOKEN ou SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY")
            return None

        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            if not self.fail_open:
                raise
            return None

    @contextmanager
    def track_agent(
        self,
        *,
        agent_key: str,
        external_run_id: str,
        pipeline_kind: str = "shorts_cutter",
        run_title: str | None = None,
        stage_label: str = "Executando",
        model_name: str | None = None,
        is_gate: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Context manager pratico: marca working no inicio e done/failed ao sair."""
        ctx: dict[str, Any] = {
            "metrics": {},
            "artifacts": [],
            "output_summary": {},
            "gate_passed": True,
        }
        self.report(
            agent_key=agent_key,
            status="working",
            external_run_id=external_run_id,
            pipeline_kind=pipeline_kind,
            run_title=run_title,
            stage_label=stage_label,
            progress=0.05,
            model_name=model_name,
        )
        try:
            yield ctx
        except Exception as exc:
            self.report(
                agent_key=agent_key,
                status="gate_failed" if is_gate else "failed",
                external_run_id=external_run_id,
                pipeline_kind=pipeline_kind,
                run_title=run_title,
                stage_label=f"Erro: {str(exc)[:180]}",
                model_name=model_name,
                error_code=type(exc).__name__,
                error_message=str(exc)[:1500],
            )
            raise
        else:
            final_status = ("gate_passed" if ctx.get("gate_passed", True) else "gate_failed") if is_gate else "done"
            self.report(
                agent_key=agent_key,
                status=final_status,
                external_run_id=external_run_id,
                pipeline_kind=pipeline_kind,
                run_title=run_title,
                stage_label="Concluído",
                progress=1.0,
                model_name=model_name,
                output_summary=ctx.get("output_summary") or {},
                artifacts=ctx.get("artifacts") or [],
                metrics=ctx.get("metrics") or {},
            )
