import type { AgentKey, AgentVisualStatus, RoomKey } from "./types";

export type HQFilter = "all" | "working" | "awaiting" | "problem" | "unprovisioned";

export type StudioLamp = "ok" | "working" | "awaiting" | "problem" | "off";

export interface StudioOverviewAgent {
  agent_key: AgentKey;
  room_key: RoomKey;
  status: AgentVisualStatus;
  enabled: boolean;
  progress: number | null;
}

export interface StudioOverviewChannel {
  channel: {
    id: string;
    display_name: string;
    handle: string | null;
    status: string;
    avatar_url: string | null;
    niche: string | null;
  };
  provisioned: boolean;
  agents: StudioOverviewAgent[];
  counts: {
    working: number;
    awaiting_human: number;
    blocked: number;
    failed: number;
    agents: number;
    disabled_agents: number;
  };
  active_item: {
    id: string;
    working_title: string;
    stage: string;
  } | null;
  last_event_at: string | null;
}

export interface StudioOverview {
  workspace_id: string;
  snapshot_at: string;
  totals: {
    channels: number;
    working: number;
    awaiting_human: number;
    problems: number;
  };
  channels: StudioOverviewChannel[];
}
