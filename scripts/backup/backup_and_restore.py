from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from adapters.supabase_storage.client import SupabaseStorageClient


def _json_default(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if type(obj).__name__ == "Decimal":
        return float(obj)
    return str(obj)


def backup_workspace_bundle(
    *,
    database_url: str,
    storage_client: SupabaseStorageClient,
    workspace_id: UUID,
    backup_dir: Path,
    access_token: str = "",
) -> dict[str, Any]:
    """
    Logical backup (ADR-014 / JOB-008) of a workspace's Postgres rows + private Storage bytes.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    files_dir = backup_dir / "storage_files"
    files_dir.mkdir(parents=True, exist_ok=True)

    snapshot: dict[str, list[dict[str, Any]]] = {}
    with psycopg.connect(database_url, row_factory=dict_row, prepare_threshold=None) as conn:
        conn.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        with conn.cursor() as cur:
            for tbl, order_col in (
                ("workspaces", "created_at"),
                ("workspace_members", "created_at"),
                ("channels", "created_at"),
                ("channel_profile_versions", "created_at"),
                ("opportunities", "created_at"),
                ("episode_briefs", "version"),
                ("editorial_calendar_items", "scheduled_for"),
                ("knowledge_sources", "created_at"),
                ("storage_objects", "created_at"),
            ):
                col_ws = "id" if tbl == "workspaces" else "workspace_id"
                cur.execute(f"SELECT * FROM public.{tbl} WHERE {col_ws} = %s ORDER BY {order_col} ASC", (workspace_id,))
                snapshot[tbl] = cur.fetchall()
        conn.commit()

    tok = access_token or storage_client._srv_key
    storage_manifest: list[dict[str, Any]] = []
    for sobj in snapshot["storage_objects"]:
        if sobj.get("status") != "READY":
            continue
        bucket = str(sobj["bucket"])
        object_path = str(sobj["object_path"])
        raw_bytes = storage_client.download_bytes(tok, bucket, object_path)
        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = str(sobj.get("sha256") or actual_sha)
        if actual_sha != expected_sha:
            raise ValueError(f"Checksum mismatch during backup for {object_path}: {actual_sha} != {expected_sha}")
        local_file = files_dir / f"{sobj['id']}.bin"
        local_file.write_bytes(raw_bytes)
        storage_manifest.append(
            {
                "old_object_id": str(sobj["id"]),
                "bucket": bucket,
                "old_object_path": object_path,
                "content_type": sobj.get("content_type", "application/octet-stream"),
                "sha256": actual_sha,
                "size_bytes": len(raw_bytes),
                "local_filename": local_file.name,
            }
        )

    tables_file = backup_dir / "tables.json"
    tables_file.write_text(json.dumps(snapshot, indent=2, default=_json_default, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "schema_version": "backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_workspace_id": str(workspace_id),
        "counts": {k: len(v) for k, v in snapshot.items()},
        "storage_objects_backed_up": storage_manifest,
    }
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def restore_workspace_isolated(
    *,
    database_url: str,
    storage_client: SupabaseStorageClient,
    backup_dir: Path,
    owner_user_id: UUID,
    access_token: str = "",
) -> dict[str, Any]:
    """
    Restores a backup bundle into a freshly isolated workspace_id, preserving versions, checksums,
    Storage bytes & RLS isolation (T-REL-001). Never overwrites existing production workspace.
    """
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((backup_dir / "tables.json").read_text(encoding="utf-8"))
    files_dir = backup_dir / "storage_files"

    new_ws_id = uuid4()
    ch_map: dict[str, UUID] = {}
    prof_map: dict[str, UUID] = {}
    opp_map: dict[str, UUID] = {}
    brief_map: dict[str, UUID] = {}
    brief_group_map: dict[str, UUID] = {}

    ws_src = snapshot["workspaces"][0]
    with psycopg.connect(database_url, row_factory=dict_row, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.workspaces (id, name, slug, created_by, settings_json)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                new_ws_id,
                f"{ws_src['name']} (Restored)",
                f"{ws_src['slug']}-r-{str(new_ws_id)[:6]}",
                owner_user_id,
                json.dumps(ws_src.get("settings_json") or {}),
            ),
        )
        cur.execute(
            """
            INSERT INTO public.workspace_members (workspace_id, user_id, role)
            VALUES (%s, %s, 'owner')
            """,
            (new_ws_id, owner_user_id),
        )

        for ch in snapshot["channels"]:
            new_ch = uuid4()
            ch_map[str(ch["id"])] = new_ch
            cur.execute(
                """
                INSERT INTO public.channels (id, workspace_id, platform, external_channel_id, display_name, handle, status, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (new_ch, new_ws_id, ch["platform"], ch.get("external_channel_id"), ch["display_name"], ch.get("handle"), ch["status"], owner_user_id),
            )

        for pv in snapshot["channel_profile_versions"]:
            new_pv = uuid4()
            prof_map[str(pv["id"])] = new_pv
            mapped_ch = ch_map[str(pv["channel_id"])]
            cur.execute(
                """
                INSERT INTO public.channel_profile_versions (
                    id, workspace_id, channel_id, version_number, name, platform, language, country,
                    timezone, niche, positioning, editorial_theme, audience_json, pillars_json,
                    voice_json, formats_json, objectives_json, restrictions_json, change_summary, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                """,
                (
                    new_pv,
                    new_ws_id,
                    mapped_ch,
                    pv["version_number"],
                    pv["name"],
                    pv["platform"],
                    pv["language"],
                    pv["country"],
                    pv["timezone"],
                    pv["niche"],
                    pv.get("positioning", ""),
                    pv.get("editorial_theme", ""),
                    json.dumps(pv.get("audience_json") or {}),
                    json.dumps(pv.get("pillars_json") or []),
                    json.dumps(pv.get("voice_json") or {}),
                    json.dumps(pv.get("formats_json") or []),
                    json.dumps(pv.get("objectives_json") or []),
                    json.dumps(pv.get("restrictions_json") or {}),
                    pv.get("change_summary", "Restore"),
                    owner_user_id,
                ),
            )

        for opp in snapshot["opportunities"]:
            new_opp = uuid4()
            opp_map[str(opp["id"])] = new_opp
            mapped_ch = ch_map[str(opp["channel_id"])]
            mapped_pv = prof_map.get(str(opp.get("profile_version_id")))
            cur.execute(
                """
                INSERT INTO public.opportunities (
                    id, workspace_id, channel_id, profile_version_id, theme, angle, target_format,
                    differentiation, score, score_version, score_breakdown_json, confidence,
                    limitations_json, data_freshness, insufficient_data, analyst_reports_json, status, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    new_opp,
                    new_ws_id,
                    mapped_ch,
                    mapped_pv,
                    opp["theme"],
                    opp["angle"],
                    opp["target_format"],
                    opp["differentiation"],
                    opp["score"],
                    opp["score_version"],
                    json.dumps(opp.get("score_breakdown_json") or {}),
                    opp["confidence"],
                    json.dumps(opp.get("limitations_json") or []),
                    opp["data_freshness"],
                    opp["insufficient_data"],
                    json.dumps(opp.get("analyst_reports_json") or []),
                    opp["status"],
                    owner_user_id,
                ),
            )

        for br in snapshot["episode_briefs"]:
            new_br = uuid4()
            brief_map[str(br["id"])] = new_br
            old_grp = str(br["brief_group_id"])
            if old_grp not in brief_group_map:
                brief_group_map[old_grp] = uuid4()
            cur.execute(
                """
                INSERT INTO public.episode_briefs (
                    id, workspace_id, brief_group_id, version, parent_brief_id, opportunity_id,
                    channel_id, profile_version_id, title, hook, angle, outline_json, cta,
                    target_format, source_refs_json, generation_refs_json, status, frozen_at,
                    approved_at, content_sha256, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
                """,
                (
                    new_br,
                    new_ws_id,
                    brief_group_map[old_grp],
                    br["version"],
                    brief_map.get(str(br.get("parent_brief_id"))) if br.get("parent_brief_id") else None,
                    opp_map[str(br["opportunity_id"])],
                    ch_map[str(br["channel_id"])],
                    prof_map[str(br["profile_version_id"])],
                    br["title"],
                    br["hook"],
                    br["angle"],
                    json.dumps(br.get("outline_json") or []),
                    br.get("cta", ""),
                    br["target_format"],
                    json.dumps(br.get("source_refs_json") or []),
                    json.dumps(br.get("generation_refs_json") or []),
                    br["status"],
                    br.get("frozen_at"),
                    br.get("approved_at"),
                    br["content_sha256"],
                    owner_user_id,
                ),
            )

        # Commit workspace & membership before uploading into RLS-protected Storage prefix {new_ws_id}/
        conn.commit()

        tok = access_token or storage_client._srv_key
        restored_storage_paths: list[dict[str, Any]] = []
        for sitem in manifest["storage_objects_backed_up"]:
            raw_bytes = (files_dir / sitem["local_filename"]).read_bytes()
            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha != sitem["sha256"]:
                raise ValueError("Corrupted backup blob checksum during restore")
            tail_name = Path(sitem["old_object_path"]).name
            new_path = f"{new_ws_id}/restored/{uuid4()}_{tail_name}"
            storage_client.upload_object(
                tok,
                sitem["bucket"],
                new_path,
                raw_bytes,
                content_type=sitem["content_type"],
            )
            cur.execute(
                """
                INSERT INTO public.storage_objects (
                    workspace_id, bucket, object_path, content_type, size_bytes, sha256, status, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'READY', %s)
                """,
                (new_ws_id, sitem["bucket"], new_path, sitem["content_type"], len(raw_bytes), actual_sha, owner_user_id),
            )
            restored_storage_paths.append({"bucket": sitem["bucket"], "object_path": new_path, "sha256": actual_sha})

        conn.commit()

    return {
        "restored_workspace_id": str(new_ws_id),
        "restored_channels": len(ch_map),
        "restored_opportunities": len(opp_map),
        "restored_briefs": len(brief_map),
        "restored_storage_objects": restored_storage_paths,
    }
