"""Live Supabase Studio UI tests: RLS isolation (G-UI1), Agent Pipeline + Fencing + Recovery (G-UI2), Snapshot/Replay (G-UI3), Approvals/Manual Publish (G-UI6/G-UI7)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from adapters.supabase_db.jobs_repo import PostgresWorkerQueue
from adapters.supabase_db.studio_repo import PostgresStudioRepository
from apps.api.config import Settings
from apps.api.main import create_app
from core.errors import AppError, ErrorCode
from workers.agents.handler import AgentJobHandler, default_local_agent_model_caller
from workers.runner import JobWorker

load_dotenv()


def _require_env(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        pytest.fail(f"Variavel obrigatoria ausente: {name}")
    return val


@pytest.mark.live_supabase
def test_studio_ui_rls_pipeline_fencing_recovery_and_replay() -> None:
    url = _require_env("NEXT_PUBLIC_SUPABASE_URL").rstrip("/")
    pub_key = _require_env("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    srv_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")
    jwt_secret = _require_env("SUPABASE_JWT_SECRET")
    db_url = _require_env("DATABASE_URL")

    admin_headers = {
        "apikey": srv_key,
        "Authorization": f"Bearer {srv_key}",
        "Content-Type": "application/json",
    }

    suffix = uuid4().hex[:8]
    email_a = f"studio-a-{suffix}@darkforge.invalid"
    email_b = f"studio-b-{suffix}@darkforge.invalid"
    password = f"DfStudio!{suffix}99"

    user_ids: list[str] = []
    created_ws_ids: list[str] = []

    settings = Settings(
        next_public_supabase_url=url,
        next_public_supabase_publishable_key=pub_key,
        supabase_jwt_secret=jwt_secret,
        supabase_service_role_key=srv_key,
        database_url=db_url,
    )
    api_client = TestClient(create_app(settings=settings))

    try:
        with httpx.Client(timeout=15.0) as client:
            for email in (email_a, email_b):
                r = client.post(
                    f"{url}/auth/v1/admin/users",
                    headers=admin_headers,
                    json={"email": email, "password": password, "email_confirm": True},
                )
                assert r.status_code in (200, 201), r.text
                user_ids.append(r.json()["id"])

            def sign_in(email: str) -> str:
                r = client.post(
                    f"{url}/auth/v1/token?grant_type=password",
                    headers={"apikey": pub_key, "Content-Type": "application/json"},
                    json={"email": email, "password": password},
                )
                assert r.status_code == 200, r.text
                return r.json()["access_token"]

            tok_a = sign_in(email_a)
            tok_b = sign_in(email_b)

            # 1. Create Workspace A & Workspace B
            res_ws_a = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_a}"},
                json={"name": f"Studio WS A {suffix}", "slug": f"st-a-{suffix}"},
            )
            assert res_ws_a.status_code == 201, res_ws_a.text
            ws_a_id = res_ws_a.json()["workspace"]["id"]
            created_ws_ids.append(ws_a_id)

            res_ws_b = api_client.post(
                "/api/v1/workspaces",
                headers={"Authorization": f"Bearer {tok_b}"},
                json={"name": f"Studio WS B {suffix}", "slug": f"st-b-{suffix}"},
            )
            assert res_ws_b.status_code == 201, res_ws_b.text
            ws_b_id = res_ws_b.json()["workspace"]["id"]
            created_ws_ids.append(ws_b_id)

            # 2. User A creates Channel -> trigger seeds 8 channel_agents
            ch_res = api_client.post(
                "/api/v1/channels",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "display_name": f"Canal Studio {suffix}",
                    "handle": f"@studio_{suffix}",
                    "profile": {
                        "name": f"Canal Studio {suffix}",
                        "language": "pt-BR",
                        "country": "BR",
                        "timezone": "America/Sao_Paulo",
                        "niche": "Documentarios",
                        "pillars_json": ["Misterios", "Analises"],
                        "restrictions_json": {"forbidden_topics": ["cassino_proibido"]},
                    },
                },
            )
            assert ch_res.status_code == 201, ch_res.text
            ch_a_id = ch_res.json()["channel"]["id"]

            snap_res = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            )
            assert snap_res.status_code == 200, snap_res.text
            snap = snap_res.json()
            assert len(snap["agents"]) == 8
            assert len(snap["rooms"]) == 6
            assert snap["metrics_panel"]["availability"] == "unknown"
            assert all(c["value"] is None for c in snap["metrics_panel"]["cards"])

            # Verify edicao starts disabled when DARKFORGE_CORE_PATH is absent
            edicao_state = next(a for a in snap["agents"] if a["agent_key"] == "edicao")
            assert edicao_state["enabled"] is False
            assert edicao_state["status"] == "disabled"

            # 3. RLS tests (G-UI1): User B cannot see anything; browser cannot insert into agent_outputs
            for tbl in ("channel_agents", "content_items", "agent_runs", "agent_events", "agent_outputs", "v_studio_agent_state"):
                cross = client.get(
                    f"{url}/rest/v1/{tbl}?workspace_id=eq.{ws_a_id}",
                    headers={"apikey": pub_key, "Authorization": f"Bearer {tok_b}"},
                )
                assert cross.status_code == 200, f"{tbl}: {cross.text}"
                assert cross.json() == []

            browser_insert = client.post(
                f"{url}/rest/v1/agent_outputs",
                headers={"apikey": pub_key, "Authorization": f"Bearer {tok_a}", "Content-Type": "application/json"},
                json={
                    "workspace_id": ws_a_id,
                    "channel_id": ch_a_id,
                    "agent_key": "dados",
                    "output_type": "channel_insight",
                    "schema_version": 1,
                    "version": 1,
                    "content": {},
                    "content_hash": "abc",
                },
            )
            assert browser_insert.status_code in (401, 403), browser_insert.text

            api_cross = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot",
                headers={"Authorization": f"Bearer {tok_b}", "X-Workspace-Id": ws_b_id},
            )
            assert api_cross.status_code == 404

            # 4. Enable edicao for deterministic E2E & check external consent guard (UI-06-T05)
            bad_policy = api_client.patch(
                f"/api/v1/studio/channels/{ch_a_id}/agents/edicao",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"model_policy": {"mode": "external_consented", "external_consent": False}},
            )
            assert bad_policy.status_code == 412

            en_edicao = api_client.patch(
                f"/api/v1/studio/channels/{ch_a_id}/agents/edicao",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"enabled": True, "display_name": "Estudio DarkForge"},
            )
            assert en_edicao.status_code == 200, en_edicao.text
            assert en_edicao.json()["agent"]["enabled"] is True

            # 5. Create Content Item (idempotent) -> enqueues dados + pesquisa
            ci_res1 = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/content-items",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"working_title": "O enigma da ilha submersa"},
            )
            assert ci_res1.status_code == 201, ci_res1.text
            ci_id = ci_res1.json()["content_item"]["id"]
            assert ci_res1.json()["deduplicated"] is False
            assert len(ci_res1.json()["enqueued_runs"]) == 2

            ci_res2 = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/content-items",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"working_title": "O enigma da ilha submersa"},
            )
            assert ci_res2.json()["deduplicated"] is True
            assert ci_res2.json()["content_item"]["id"] == ci_id

            # 6. Execute Worker for dados + pesquisa -> verify handoff triggers estrategia ONLY after both finish
            studio_repo = PostgresStudioRepository(db_url)
            queue = PostgresWorkerQueue(db_url)

            # Use a deterministic fake model caller that injects forbidden topic on first titulos run to test needs_review + human revision
            titulos_calls = {"count": 0}

            def deterministic_caller(prompt: str, ctx: dict, meta: dict) -> dict:
                out = default_local_agent_model_caller(prompt, ctx, meta)
                if meta["agent_key"] == "titulos" and titulos_calls["count"] == 0:
                    titulos_calls["count"] += 1
                    out["payload"]["options"][0]["similarity"] = 0.85  # triggers needs_review
                return out

            worker = JobWorker(
                queue,
                worker_id=f"test-worker-{suffix}",
                handlers={"agent.execute": AgentJobHandler(studio_repo, model_caller=deterministic_caller)},
                lease_seconds=30,
            )

            # Drain dados, pesquisa, and estrategia
            processed = 0
            while processed < 6:
                jid = worker.run_once(job_types=["agent.execute"])
                if jid is None:
                    break
                processed += 1
            assert processed == 3  # dados, pesquisa, estrategia

            snap_after_strat = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot?content_item_id={ci_id}",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()
            opp_out = snap_after_strat["latest_opportunity"]
            assert opp_out is not None
            assert opp_out["output_type"] == "opportunity"
            assert opp_out["status"] == "validated"
            assert snap_after_strat["active_content_item"]["stage"] == "estrategia"
            assert snap_after_strat["active_content_item"]["status"] == "aguardando_aprovacao"

            # 7. Approve opportunity -> releases titulos, roteiro, thumbnail
            app_opp = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/approvals",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "target_kind": "opportunity",
                    "target_id": opp_out["id"],
                    "target_version": opp_out["version"],
                    "decision": "approved",
                    "reason": "Oportunidade validada no gate",
                },
            )
            assert app_opp.status_code == 200, app_opp.text
            assert len(app_opp.json()["enqueued_next_runs"]) == 3

            # Run titulos, roteiro, thumbnail
            for _ in range(3):
                assert worker.run_once(job_types=["agent.execute"]) is not None

            snap_after_brief_parts = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot?content_item_id={ci_id}",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()
            titulos_out = next(o for o in snap_after_brief_parts["item_outputs"] if o["output_type"] == "title_options")
            assert titulos_out["status"] == "needs_review"  # similarity 0.85 triggered review

            # Human revises titulos -> creates version 2 without overwriting v1
            rev_res = api_client.post(
                f"/api/v1/studio/outputs/{titulos_out['id']}/revise",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "action": "save_version",
                    "edited_content": {
                        "summary": "Titulos revisados pelo editor",
                        "confidence": "alta",
                        "limitations": [],
                        "options": [
                            {
                                "text": "A verdade oculta da ilha submersa",
                                "pattern": "documental",
                                "differentiation": "Angulo autoral revisado",
                                "closest_reference_id": None,
                                "similarity": 0.12,
                            }
                        ],
                    },
                    "reason": "Reducao de similaridade",
                },
            )
            assert rev_res.status_code == 200, rev_res.text
            assert rev_res.json()["output"]["version"] == 2
            assert rev_res.json()["output"]["author_kind"] == "human"

            # 8. Approve Brief stage -> releases edicao -> then publicacao
            app_brief = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/approvals",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "target_kind": "brief",
                    "target_id": ci_id,
                    "target_version": 1,
                    "decision": "approved",
                    "reason": "Brief congelado para producao",
                    "content_item_id": ci_id,
                },
            )
            assert app_brief.status_code == 200, app_brief.text
            assert len(app_brief.json()["enqueued_next_runs"]) == 1

            # Run edicao -> publicacao
            assert worker.run_once(job_types=["agent.execute"]) is not None  # edicao
            assert worker.run_once(job_types=["agent.execute"]) is not None  # publicacao

            snap_pub = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot?content_item_id={ci_id}",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()
            pub_out = next(o for o in snap_pub["item_outputs"] if o["output_type"] == "publication_plan")
            assert pub_out["content"]["requires_human_publish"] is True

            # 9. Approve publication plan & mark manually published
            app_pub = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/approvals",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={
                    "target_kind": "publication_plan",
                    "target_id": pub_out["id"],
                    "target_version": pub_out["version"],
                    "decision": "approved",
                    "reason": "Plano pronto para publicacao manual",
                },
            )
            assert app_pub.status_code == 200, app_pub.text

            pub_man = api_client.post(
                f"/api/v1/studio/content-items/{ci_id}/publish-manual",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"published_video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
            )
            assert pub_man.status_code == 200, pub_man.text
            assert pub_man.json()["content_item"]["stage"] == "publicado_manual"

            # 10. Test Fencing stale + Lease Expiry Recovery + no_signal view (G-UI2)
            enq_extra = api_client.post(
                f"/api/v1/studio/channels/{ch_a_id}/agents/dados/run",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
                json={"reason": "recovery_test", "idempotency_key": f"rec-{suffix}"},
            )
            assert enq_extra.status_code == 202
            rec_run = enq_extra.json()["run"]
            claimed = queue.claim_next(f"crash-worker-{suffix}", lease_seconds=5, job_types=["agent.execute"])
            assert claimed is not None
            studio_repo.mark_run_started(UUID(rec_run["id"]), claimed.fencing_token)

            # Simulate stale heartbeat -> v_studio_agent_state reports no_signal, and stale fencing fails commit
            with psycopg.connect(db_url) as conn, conn.cursor() as cur:
                old_hb = datetime.now(timezone.utc) - timedelta(minutes=5)
                cur.execute("UPDATE public.agent_runs SET heartbeat_at = %s WHERE id = %s", (old_hb, rec_run["id"]))
                cur.execute("UPDATE public.jobs SET lease_expires_at = %s WHERE id = %s", (old_hb, str(claimed.job_id)))
                conn.commit()

            snap_nosig = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/snapshot",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()
            dados_state = next(a for a in snap_nosig["agents"] if a["agent_key"] == "dados")
            assert dados_state["status"] == "no_signal"

            with pytest.raises(AppError) as stale_err:
                studio_repo.commit_agent_run_atomic(
                    run_id=UUID(rec_run["id"]),
                    job_id=claimed.job_id,
                    fencing_token=claimed.fencing_token - 1,  # stale token
                    workspace_id=UUID(ws_a_id),
                    channel_id=UUID(ch_a_id),
                    agent_key="dados",
                    content_item_id=None,
                    output_type="channel_insight",
                    schema_version=1,
                    summary="Nao deve gravar",
                    content_json={},
                    valid_sources=[],
                    output_status="validated",
                    validation_info={},
                    originality_score=None,
                    input_hash="h",
                    model_id="m",
                    provider="local",
                    cost_estimate_cents=0,
                    actor_id=UUID(user_ids[0]),
                )
            assert stale_err.value.code == ErrorCode.FENCING_TOKEN_STALE

            # Reconcile expired leases -> recovers run to queued, then worker finishes attempt 2
            reconciled_cnt = studio_repo.reconcile_expired_agent_runs()
            assert reconciled_cnt >= 1
            assert worker.run_once(job_types=["agent.execute"]) == claimed.job_id

            rec_run_done = studio_repo.get_run(UUID(ws_a_id), UUID(rec_run["id"]))
            assert rec_run_done is not None
            assert rec_run_done["status"] == "done"
            assert rec_run_done["attempt"] >= 2

            # 11. Cursor event replay check (G-UI3)
            all_evts = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/events?after_id=0&limit=500",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()["events"]
            assert len(all_evts) >= 10
            mid_cursor = all_evts[len(all_evts) // 2]["id"]
            tail_evts = api_client.get(
                f"/api/v1/studio/channels/{ch_a_id}/events?after_id={mid_cursor}&limit=500",
                headers={"Authorization": f"Bearer {tok_a}", "X-Workspace-Id": ws_a_id},
            ).json()["events"]
            assert [e["id"] for e in tail_evts] == [e["id"] for e in all_evts if e["id"] > mid_cursor]
    finally:
        with httpx.Client(timeout=10.0) as client:
            for ws_id in created_ws_ids:
                client.delete(f"{url}/rest/v1/workspaces?id=eq.{ws_id}", headers=admin_headers)
            for uid in user_ids:
                client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
