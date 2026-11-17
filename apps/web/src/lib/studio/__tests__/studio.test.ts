import assert from "node:assert/strict";
import {
  PIPELINE_ORDER,
  resolveAgentPosition,
  STUDIO_LAYOUT,
} from "../studio-layout";
import { applyStudioEvent, detectEventGap } from "../reducer";
import type { AgentVisualStatus, StudioAgentState, StudioEvent, StudioSnapshot } from "../types";

export function runStudioUnitTests(): { passed: number } {
  let passed = 0;

  // 1. UI-04-T01: All polygon/anchor points within [0, 1] and desks cover agents
  const roomAgentCounts: Record<string, number> = {
    sala_dados: 1,
    pesquisa: 1,
    mesa_agentes: 3,
    gravacao: 1,
    design_thumbnail: 1,
    estrategia_publicacao: 1,
  };
  for (const [key, room] of Object.entries(STUDIO_LAYOUT)) {
    assert.ok(room.polygon.length >= 3, `${key} polygon needs >= 3 points`);
    for (const pt of [...room.polygon, room.labelAnchor, room.door, ...room.desks, ...(room.meeting ?? [])]) {
      assert.ok(pt.x >= 0 && pt.x <= 1, `${key} point x out of range: ${pt.x}`);
      assert.ok(pt.y >= 0 && pt.y <= 1, `${key} point y out of range: ${pt.y}`);
    }
    assert.ok(
      room.desks.length >= (roomAgentCounts[key] ?? 1),
      `${key} needs at least ${roomAgentCounts[key]} desk(s)`
    );
  }
  passed++;

  // 2. UI-04-T04: resolveAgentPosition covers every status correctly
  const baseAgent: Pick<StudioAgentState, "agent_key" | "room_key" | "status" | "enabled"> = {
    agent_key: "pesquisa",
    room_key: "pesquisa",
    status: "idle",
    enabled: true,
  };
  const statuses: AgentVisualStatus[] = [
    "idle",
    "queued",
    "working",
    "waiting_input",
    "needs_review",
    "waiting_approval",
    "blocked",
    "no_signal",
    "failed",
    "cancelled",
    "done",
    "disabled",
  ];
  for (const st of statuses) {
    const res = resolveAgentPosition({ ...baseAgent, status: st, enabled: st !== "disabled" }, STUDIO_LAYOUT, 0, 2);
    assert.ok(res.x >= 0 && res.x <= 1);
    assert.ok(res.y >= 0 && res.y <= 1);
    if (st === "queued") assert.equal(res.anchorKind, "door");
    if (st === "waiting_approval") {
      assert.equal(res.anchorKind, "meeting");
      assert.equal(res.targetRoom, "mesa_agentes");
    }
    if (st === "working") assert.equal(res.animated, true);
    if (st === "no_signal") assert.equal(res.badge, "no_signal");
  }
  passed++;

  // 3. UI-03-T04: Pure reducer handles event types and ignores out-of-order seq
  const chId = "11111111-1111-1111-1111-111111111111";
  const wsId = "22222222-2222-2222-2222-222222222222";
  const runId = "33333333-3333-3333-3333-333333333333";
  const initial: StudioSnapshot = {
    channel: {
      id: chId,
      workspace_id: wsId,
      display_name: "Canal Teste",
      handle: "@teste",
      status: "active",
      external_channel_id: null,
      active_profile_version_id: null,
      profile_version_number: 1,
      niche: "Tech",
      language: "pt-BR",
      editorial_theme: "IA",
    },
    rooms: [
      {
        workspace_id: wsId,
        channel_id: chId,
        room_key: "pesquisa",
        room_label: "Pesquisa",
        sort_order: 20,
        working: 0,
        awaiting_human: 0,
        blocked: 0,
        failed: 0,
        agents: 1,
        disabled_agents: 0,
      },
    ],
    agents: [
      {
        workspace_id: wsId,
        channel_id: chId,
        channel_agent_id: "ca-1",
        agent_key: "pesquisa",
        enabled: true,
        config: {},
        model_policy: { mode: "local_only" },
        monthly_budget_cents: null,
        room_key: "pesquisa",
        description: "Pesquisa",
        requires_approval: false,
        contract_version: 1,
        display_name: "Pesquisador",
        avatar_key: "pesquisa",
        run_id: null,
        job_id: null,
        content_item_id: null,
        status: "idle",
        stage_label: null,
        progress: null,
        attempt: null,
        heartbeat_at: null,
        started_at: null,
        finished_at: null,
        error_code: null,
        error_message: null,
        cost_estimate_cents: null,
        run_created_at: null,
      },
    ],
    content_items: [],
    active_content_item: null,
    latest_opportunity: null,
    metrics_panel: { cards: [], series: [], fetched_at: null, availability: "unknown", stale: false },
    recent_events: [],
    latest_event_by_agent: {},
    item_outputs: [],
    handoffs: [],
    approvals: [],
    last_event_id: 0,
    darkforge_available: false,
    snapshot_at: "2026-11-17T00:00:00Z",
  };

  const makeEvt = (id: number, seq: number, event_type: StudioEvent["event_type"], summary: string): StudioEvent => ({
    id,
    workspace_id: wsId,
    channel_id: chId,
    run_id: runId,
    content_item_id: null,
    agent_key: "pesquisa",
    seq,
    event_type,
    summary,
    payload: event_type === "progress" ? { progress: 0.5, stage_label: "buscando" } : {},
    created_at: "2026-11-17T00:01:00Z",
  });

  let s = applyStudioEvent(initial, makeEvt(1, 1, "run_queued", "Na fila"));
  assert.equal(s.agents[0].status, "queued");
  assert.equal(s.last_event_id, 1);

  s = applyStudioEvent(s, makeEvt(2, 2, "run_started", "Iniciado"));
  assert.equal(s.agents[0].status, "working");
  assert.equal(s.rooms[0].working, 1);

  s = applyStudioEvent(s, makeEvt(3, 3, "progress", "Progresso"));
  assert.equal(s.agents[0].progress, 0.5);

  // Out-of-order seq <= 3 must be ignored
  const ignored = applyStudioEvent(s, makeEvt(4, 2, "failed", "Fora de ordem"));
  assert.equal(ignored.agents[0].status, "working");

  s = applyStudioEvent(s, makeEvt(5, 4, "completed", "Concluído"));
  assert.equal(s.agents[0].status, "done");
  assert.equal(s.rooms[0].working, 0);
  assert.equal(detectEventGap(5, 8), true);
  assert.equal(detectEventGap(5, 6), false);
  assert.equal(PIPELINE_ORDER.length, 8);
  passed++;

  return { passed };
}
