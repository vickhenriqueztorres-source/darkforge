import type { StudioOverview, StudioOverviewAgent, StudioOverviewChannel } from "../hq-types";
import type { AgentKey, AgentVisualStatus, RoomKey } from "../types";

const AGENT_ROOMS: Array<[AgentKey, RoomKey]> = [
  ["dados", "sala_dados"],
  ["pesquisa", "pesquisa"],
  ["estrategia", "mesa_agentes"],
  ["titulos", "mesa_agentes"],
  ["roteiro", "mesa_agentes"],
  ["thumbnail", "design_thumbnail"],
  ["edicao", "gravacao"],
  ["publicacao", "estrategia_publicacao"],
];

export function makeAgents(
  overrides: Partial<Record<AgentKey, Partial<Pick<StudioOverviewAgent, "status" | "enabled" | "progress">>>> = {}
): StudioOverviewAgent[] {
  return AGENT_ROOMS.map(([agent_key, room_key]) => {
    const ov = overrides[agent_key];
    return {
      agent_key,
      room_key,
      status: ov?.status ?? "idle",
      enabled: ov?.enabled ?? agent_key !== "edicao",
      progress: ov?.progress ?? null,
    };
  });
}

export function makeStudioChannel(
  index: number,
  opts: {
    id?: string;
    display_name: string;
    handle?: string | null;
    status?: string;
    avatar_url?: string | null;
    niche?: string | null;
    provisioned?: boolean;
    agents?: StudioOverviewAgent[];
    active_item?: { id: string; working_title: string; stage: string } | null;
    last_event_at?: string | null;
  }
): StudioOverviewChannel {
  const provisioned = opts.provisioned ?? true;
  const agents = provisioned ? (opts.agents ?? makeAgents()) : [];
  const enabledAgents = agents.filter((a) => a.enabled);
  const working = enabledAgents.filter((a) => a.status === "working").length;
  const awaiting_human = enabledAgents.filter(
    (a) => a.status === "needs_review" || a.status === "waiting_approval"
  ).length;
  const blocked = enabledAgents.filter((a) => a.status === "blocked" || a.status === "no_signal").length;
  const failed = enabledAgents.filter((a) => a.status === "failed").length;

  return {
    channel: {
      id: opts.id ?? `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      display_name: opts.display_name,
      handle: opts.handle ?? `@canal_${index + 1}`,
      status: opts.status ?? "active",
      avatar_url: opts.avatar_url ?? null,
      niche: opts.niche ?? "Mistérios & Documentários",
    },
    provisioned,
    agents,
    counts: {
      working,
      awaiting_human,
      blocked,
      failed,
      agents: enabledAgents.length,
      disabled_agents: agents.length - enabledAgents.length,
    },
    active_item: opts.active_item ?? null,
    last_event_at: opts.last_event_at ?? null,
  };
}

const SAMPLE_DEFS: Array<Parameters<typeof makeStudioChannel>[1]> = [
  {
    display_name: "O Outro Lado",
    handle: "@outroladodetudo",
    niche: "Mistérios & Ciência",
    agents: makeAgents({
      dados: { status: "done" },
      pesquisa: { status: "working", progress: 0.62 },
      roteiro: { status: "working", progress: 0.35 },
      edicao: { status: "disabled", enabled: false },
    }),
    active_item: { id: "item-1", working_title: "O sinal de 1977 que ninguém decifrou", stage: "roteiro" },
    last_event_at: "2026-11-17T17:10:00Z",
  },
  {
    display_name: "Crônicas da Noite",
    handle: "@cronicasdanoite",
    niche: "História Oculta",
    agents: makeAgents({
      estrategia: { status: "waiting_approval" },
      titulos: { status: "needs_review" },
      publicacao: { status: "waiting_input" },
    }),
    active_item: { id: "item-2", working_title: "As cidades submersas do Mediterrâneo", stage: "estrategia" },
    last_event_at: "2026-11-17T17:04:00Z",
  },
  {
    display_name: "Viajante Zero 🚀 — Expedições Extremas & Relatos Reais",
    handle: "@ViajanteZero-films",
    niche: "Documentários",
    agents: makeAgents({
      pesquisa: { status: "failed" },
      dados: { status: "blocked" },
      thumbnail: { status: "no_signal" },
    }),
    active_item: { id: "item-3", working_title: "Travessia no Ártico sem bússola", stage: "pesquisa" },
    last_event_at: "2026-11-17T16:50:00Z",
  },
  {
    display_name: "Sonar 0300",
    handle: "@Sonar0300",
    niche: "Oceano Profundo",
    provisioned: false,
    agents: [],
    active_item: null,
    last_event_at: null,
  },
  {
    display_name: "Arquivo Cinzento",
    handle: "@arquivocinzento",
    status: "archived",
    niche: "True Crime",
    agents: makeAgents({ dados: { status: "idle" }, pesquisa: { status: "cancelled" } }),
    active_item: null,
    last_event_at: "2026-11-10T12:00:00Z",
  },
  {
    display_name: "Éden Sintético",
    handle: "@edensintetico",
    niche: "Ficção Científica",
    agents: makeAgents({
      dados: { status: "queued" },
      pesquisa: { status: "working", progress: 0.8 },
      titulos: { status: "done" },
    }),
    active_item: { id: "item-6", working_title: "Quando a IA aprende a sonhar", stage: "pesquisa" },
    last_event_at: "2026-11-17T17:12:00Z",
  },
];

const EXTRA_STATUSES: AgentVisualStatus[] = [
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
];

export function buildOverviewFixture(count: 0 | 1 | 3 | 7 | 12 | 13 | 24 | number): StudioOverview {
  const channels: StudioOverviewChannel[] = [];
  for (let i = 0; i < count; i++) {
    if (i < SAMPLE_DEFS.length) {
      channels.push(makeStudioChannel(i, SAMPLE_DEFS[i]));
    } else {
      const st = EXTRA_STATUSES[i % EXTRA_STATUSES.length];
      channels.push(
        makeStudioChannel(i, {
          display_name: i === 10 ? "Ação & Reação: Ciência em Ação na Prática!" : `Estúdio Canal ${i + 1}`,
          niche: i % 2 === 0 ? "Ciência" : "História",
          agents: makeAgents({
            pesquisa: { status: st, progress: st === "working" ? 0.5 : null },
          }),
          active_item:
            st === "working" || st === "waiting_approval"
              ? { id: `item-${i + 1}`, working_title: `Episódio #${i + 1}`, stage: "roteiro" }
              : null,
          last_event_at: "2026-11-17T16:00:00Z",
        })
      );
    }
  }

  return {
    workspace_id: "ws-demo-00000000-0000-4000-8000-000000000001",
    snapshot_at: "2026-11-17T17:15:00Z",
    totals: {
      channels: channels.length,
      working: channels.reduce((sum, c) => sum + c.counts.working, 0),
      awaiting_human: channels.reduce((sum, c) => sum + c.counts.awaiting_human, 0),
      problems: channels.reduce((sum, c) => sum + c.counts.blocked + c.counts.failed, 0),
    },
    channels,
  };
}

export const HQ_OVERVIEW_FIXTURES = {
  empty: buildOverviewFixture(0),
  one: buildOverviewFixture(1),
  three: buildOverviewFixture(3),
  seven: buildOverviewFixture(7),
  twelve: buildOverviewFixture(12),
  thirteen: buildOverviewFixture(13),
  twentyFour: buildOverviewFixture(24),
};
