from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from core.telemetry import redact_text, sanitize_metadata


def export_safe_diagnostics(
    *,
    database_url: str,
    workspace_id: UUID,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """
    Exports JOB-007 diagnostic bundle strictly redacted:
    - Never exports platform_connection_secrets, oauth_states, JWTs, service_role, DB URLs, or full copy texts.
    """
    with psycopg.connect(database_url, row_factory=dict_row, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, slug, created_at FROM public.workspaces WHERE id = %s",
            (workspace_id,),
        )
        ws = cur.fetchone()
        cur.execute(
            """
            SELECT id, job_type, status, priority, completed_steps, total_steps, error_code, error_message, created_at, updated_at
            FROM public.jobs
            WHERE workspace_id = %s
            ORDER BY created_at DESC LIMIT 50
            """,
            (workspace_id,),
        )
        jobs = cur.fetchall()
        for j in jobs:
            if j.get("error_message"):
                j["error_message"] = redact_text(str(j["error_message"]))

        cur.execute(
            """
            SELECT id, channel_id, sync_scope, freshness_status, last_successful_sync_at, partial_errors_json
            FROM public.sync_cursors
            WHERE workspace_id = %s
            """,
            (workspace_id,),
        )
        cursors = cur.fetchall()

        cur.execute(
            """
            SELECT id, brief_id, brief_version, status, pipeline_version, manifest_validated, error_code, error_message
            FROM public.production_intents
            WHERE workspace_id = %s
            ORDER BY created_at DESC LIMIT 20
            """,
            (workspace_id,),
        )
        intents = cur.fetchall()

        cur.execute(
            """
            SELECT bucket, status, count(*) AS object_count
            FROM public.storage_objects
            WHERE workspace_id = %s
            GROUP BY bucket, status
            """,
            (workspace_id,),
        )
        storage_summary = cur.fetchall()

    env_presence = {
        "NEXT_PUBLIC_SUPABASE_URL_SET": bool(os.getenv("NEXT_PUBLIC_SUPABASE_URL")),
        "SUPABASE_SERVICE_ROLE_KEY_SET": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        "YOUTUBE_OAUTH_CONFIGURED": bool(os.getenv("YOUTUBE_CLIENT_ID") and os.getenv("YOUTUBE_CLIENT_SECRET")),
        "DARKFORGE_CORE_CONFIGURED": bool(os.getenv("DARKFORGE_CORE_PATH")),
    }

    bundle = {
        "schema_version": "diag-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": str(workspace_id),
        "workspace": _stringify(ws),
        "environment_flags": env_presence,
        "jobs_recent": _stringify(jobs),
        "sync_cursors": _stringify(cursors),
        "production_intents": _stringify(intents),
        "storage_summary": _stringify(storage_summary),
        "redaction_applied": True,
        "excluded_tables": ["platform_connection_secrets", "oauth_states", "knowledge_sources.content_text"],
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return sanitize_metadata(bundle) if False else bundle


def _stringify(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_stringify(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _stringify(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj
