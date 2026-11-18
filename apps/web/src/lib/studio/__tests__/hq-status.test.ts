import assert from "node:assert/strict";
import { matchesFilter, studioLamp, studioSummaryText } from "../hq-status";
import { HQ_OVERVIEW_FIXTURES, makeAgents, makeStudioChannel } from "../__fixtures__/hq-overview";
import type { AgentVisualStatus } from "../types";

export function runHqStatusTests(): number {
  let passed = 0;

  // 1. Table of all AgentVisualStatus cases for studioLamp
  const cases: Array<{ status: AgentVisualStatus; enabled: boolean; expected: ReturnType<typeof studioLamp> }> = [
    { status: "idle", enabled: true, expected: "ok" },
    { status: "queued", enabled: true, expected: "ok" },
    { status: "done", enabled: true, expected: "ok" },
    { status: "cancelled", enabled: true, expected: "ok" },
    { status: "working", enabled: true, expected: "working" },
    { status: "waiting_approval", enabled: true, expected: "awaiting" },
    { status: "needs_review", enabled: true, expected: "awaiting" },
    { status: "waiting_input", enabled: true, expected: "awaiting" },
    { status: "failed", enabled: true, expected: "problem" },
    { status: "blocked", enabled: true, expected: "problem" },
    { status: "no_signal", enabled: true, expected: "problem" },
    { status: "disabled", enabled: false, expected: "off" }, // disabled agent ignored, other idle -> ok below; tested explicitly
  ];

  for (const c of cases) {
    if (c.status === "disabled") {
      // Disabled agent with problem status must NOT trigger problem lamp
      const ch = makeStudioChannel(0, {
        display_name: "Canal Teste",
        agents: makeAgents({
          pesquisa: { status: "failed", enabled: false },
          edicao: { status: "disabled", enabled: false },
        }),
      });
      assert.equal(studioLamp(ch), "ok", "disabled failing agent should not turn lamp red");
      continue;
    }
    const ch = makeStudioChannel(0, {
      display_name: "Canal Teste",
      agents: makeAgents({ pesquisa: { status: c.status, enabled: c.enabled } }),
    });
    assert.equal(studioLamp(ch), c.expected, `status ${c.status} should produce ${c.expected}`);
  }
  passed++;

  // 2. Priority order: problem > awaiting > working > ok; off for unprovisioned or disconnected
  const priorityProblem = makeStudioChannel(0, {
    display_name: "P",
    agents: makeAgents({
      dados: { status: "working" },
      estrategia: { status: "waiting_approval" },
      pesquisa: { status: "failed" },
    }),
  });
  assert.equal(studioLamp(priorityProblem), "problem");

  const priorityAwaiting = makeStudioChannel(1, {
    display_name: "A",
    agents: makeAgents({
      dados: { status: "working" },
      estrategia: { status: "waiting_input" },
    }),
  });
  assert.equal(studioLamp(priorityAwaiting), "awaiting");

  const unprovisioned = makeStudioChannel(2, {
    display_name: "Obras",
    provisioned: false,
    agents: [],
  });
  assert.equal(studioLamp(unprovisioned), "off");

  const disconnected = makeStudioChannel(3, {
    display_name: "Arquivado",
    status: "archived",
    agents: makeAgents({ pesquisa: { status: "failed" } }),
  });
  assert.equal(studioLamp(disconnected), "off");
  passed++;

  // 3. matchesFilter & studioSummaryText
  assert.equal(matchesFilter(unprovisioned, "unprovisioned"), true);
  assert.equal(matchesFilter(unprovisioned, "working"), false);
  assert.equal(matchesFilter(priorityAwaiting, "awaiting"), true);
  assert.equal(matchesFilter(priorityAwaiting, "working"), true);
  assert.equal(matchesFilter(priorityProblem, "problem"), true);
  assert.equal(matchesFilter(disconnected, "problem"), false);

  assert.equal(studioSummaryText(unprovisioned), "Obras, em obras (sem agentes)");
  assert.equal(studioSummaryText(disconnected), "Arquivado, desconectado");
  assert.equal(studioSummaryText(priorityProblem), "P, 1 trabalhando, 1 aguardando você, 1 com problema");
  passed++;

  // 4. Fixtures cover 0, 1, 3, 7, 12, 13, 24 channels
  assert.equal(HQ_OVERVIEW_FIXTURES.empty.channels.length, 0);
  assert.equal(HQ_OVERVIEW_FIXTURES.one.channels.length, 1);
  assert.equal(HQ_OVERVIEW_FIXTURES.three.channels.length, 3);
  assert.equal(HQ_OVERVIEW_FIXTURES.seven.channels.length, 7);
  assert.equal(HQ_OVERVIEW_FIXTURES.twelve.channels.length, 12);
  assert.equal(HQ_OVERVIEW_FIXTURES.thirteen.channels.length, 13);
  assert.equal(HQ_OVERVIEW_FIXTURES.twentyFour.channels.length, 24);
  assert.ok(HQ_OVERVIEW_FIXTURES.three.channels[2].channel.display_name.length >= 40);
  assert.ok(HQ_OVERVIEW_FIXTURES.three.channels[2].channel.display_name.includes("🚀"));
  assert.equal(HQ_OVERVIEW_FIXTURES.seven.channels[3].provisioned, false);
  assert.equal(HQ_OVERVIEW_FIXTURES.seven.channels[4].channel.status, "archived");
  passed++;

  return passed;
}
