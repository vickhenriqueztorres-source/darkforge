from __future__ import annotations

import os
from uuid import UUID, uuid4

import psycopg
import pytest
from dotenv import load_dotenv

from adapters.supabase_db.external_agents_repo import PostgresExternalAgentsRepository

load_dotenv(".env")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL nao configurada")
def test_live_external_agents_catalog_ingest_and_cleanup() -> None:
    repo = PostgresExternalAgentsRepository(DATABASE_URL)

    with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM public.external_agent_catalog WHERE active = true")
        total = cur.fetchone()[0]
        assert total == 88

        cur.execute("SELECT workspace_id, id FROM public.channels LIMIT 1")
        row = cur.fetchone()
        assert row is not None
        ws_id, ch_id = UUID(str(row[0])), UUID(str(row[1]))

    test_run_id = f"pytest-ext-run-{uuid4().hex[:8]}"
    token_id: str | None = None
    try:
        # 1. Token lifecycle
        tok = repo.create_ingest_token(ws_id, ch_id, uuid4(), "Pytest Integration Token")
        token_id = tok["id"]
        assert tok["token"].startswith("df_ext_")
        resolved = repo.resolve_ingest_token(tok["token"])
        assert resolved is not None
        assert resolved["workspace_id"] == str(ws_id)

        # 2. Ingest working -> done across multiple squads
        out = repo.ingest_events(
            ws_id,
            ch_id,
            [
                {
                    "agent_key": "firefly-worker",
                    "status": "working",
                    "external_run_id": test_run_id,
                    "pipeline_kind": "firefly_batch",
                    "run_title": "Pytest Firefly Batch",
                    "stage_label": "Subindo start frame no Kling 3.0",
                    "progress": 0.5,
                    "model_name": "Kling 3.0",
                },
                {
                    "agent_key": "agent_04_moment_miner",
                    "status": "done",
                    "external_run_id": test_run_id,
                    "pipeline_kind": "shorts_cutter",
                    "stage_label": "7 candidatos extraidos",
                    "metrics": {"candidates": 7},
                },
                {
                    "agent_key": "LoudnessQaAgent",
                    "status": "gate_passed",
                    "external_run_id": test_run_id,
                    "pipeline_kind": "hsl_episode",
                    "stage_label": "-16.0 LUFS validado",
                },
            ],
        )
        assert len(out) == 3

        # 3. Read snapshot and detail
        snap = repo.get_snapshot(ws_id, ch_id)
        assert len(snap["agents"]) == 88
        by_key = {a["agent_key"]: a for a in snap["agents"]}
        assert by_key["firefly-worker"]["status"] == "working"
        assert by_key["agent_04_moment_miner"]["status"] == "done"
        assert by_key["LoudnessQaAgent"]["status"] == "gate_passed"

        detail = repo.get_agent_detail(ws_id, ch_id, "firefly-worker")
        assert detail is not None
        assert len(detail["executions"]) >= 1
        assert len(detail["events"]) >= 1

        revoked = repo.revoke_ingest_token(ws_id, UUID(token_id))
        assert revoked is not None
        assert repo.resolve_ingest_token(tok["token"]) is None
    finally:
        # Clean up test telemetry rows cleanly (events table is immutable, so disable trigger briefly or delete run after)
        with psycopg.connect(DATABASE_URL) as conn, conn.cursor() as cur:
            cur.execute("ALTER TABLE public.external_agent_events DISABLE TRIGGER trg_ext_events_immutable")
            cur.execute("DELETE FROM public.external_pipeline_runs WHERE channel_id = %s AND external_run_id = %s", (str(ch_id), test_run_id))
            cur.execute("ALTER TABLE public.external_agent_events ENABLE TRIGGER trg_ext_events_immutable")
            if token_id:
                cur.execute("DELETE FROM public.external_ingest_tokens WHERE id = %s", (token_id,))
            conn.commit()
