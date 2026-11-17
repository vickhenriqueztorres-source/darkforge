export type AgentKey =
  | "dados"
  | "pesquisa"
  | "estrategia"
  | "titulos"
  | "roteiro"
  | "thumbnail"
  | "edicao"
  | "publicacao";

export type RoomKey =
  | "sala_dados"
  | "pesquisa"
  | "mesa_agentes"
  | "gravacao"
  | "design_thumbnail"
  | "estrategia_publicacao";

export type AgentVisualStatus =
  | "idle"
  | "queued"
  | "working"
  | "waiting_input"
  | "needs_review"
  | "waiting_approval"
  | "blocked"
  | "no_signal"
  | "failed"
  | "cancelled"
  | "done"
  | "disabled";

export type StudioEventType =
  | "run_queued"
  | "run_started"
  | "stage_changed"
  | "progress"
  | "output_saved"
  | "output_validated"
  | "needs_review"
  | "handoff_created"
  | "blocked"
  | "failed"
  | "cancelled"
  | "completed";

export interface StudioChannelInfo {
  id: string;
  workspace_id: string;
  display_name: string;
  handle: string | null;
  status: string;
  external_channel_id: string | null;
  active_profile_version_id: string | null;
  profile_version_number: number | null;
  niche: string | null;
  language: string | null;
  editorial_theme: string | null;
}

export interface StudioRoomState {
  workspace_id: string;
  channel_id: string;
  room_key: RoomKey;
  room_label: string;
  sort_order: number;
  working: number;
  awaiting_human: number;
  blocked: number;
  failed: number;
  agents: number;
  disabled_agents: number;
}

export interface StudioAgentState {
  workspace_id: string;
  channel_id: string;
  channel_agent_id: string;
  agent_key: AgentKey;
  enabled: boolean;
  config: Record<string, unknown>;
  model_policy: { mode: string; external_consent?: boolean };
  monthly_budget_cents: number | null;
  room_key: RoomKey;
  description: string;
  requires_approval: boolean;
  contract_version: number;
  display_name: string;
  avatar_key: string;
  run_id: string | null;
  job_id: string | null;
  content_item_id: string | null;
  status: AgentVisualStatus;
  stage_label: string | null;
  progress: number | null;
  attempt: number | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  cost_estimate_cents: number | null;
  run_created_at: string | null;
}

export interface ContentItemPipeline {
  content_item_id: string;
  workspace_id: string;
  channel_id: string;
  working_title: string;
  opportunity_id: string | null;
  brief_id: string | null;
  brief_version: number | null;
  stage: string;
  status: string;
  scheduled_for: string | null;
  published_video_url: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  latest_outputs: Record<
    string,
    {
      output_id: string;
      version: number;
      status: string;
      agent_key: AgentKey;
      created_at: string;
    }
  >;
}

export interface OutputSource {
  source_kind: string;
  source_id: string;
  locator: string | null;
  note?: string | null;
}

export interface AgentOutput {
  id: string;
  workspace_id: string;
  channel_id: string;
  run_id: string | null;
  content_item_id: string | null;
  agent_key: AgentKey;
  output_type: string;
  schema_version: number;
  version: number;
  content: Record<string, unknown>;
  content_hash: string;
  status: "draft" | "validated" | "needs_review" | "approved" | "rejected" | "superseded";
  validation: {
    valid?: boolean;
    review_reasons?: string[];
    warnings?: string[];
    human_revised?: boolean;
    reason?: string;
  };
  originality_score: number | null;
  author_kind: "agent" | "human";
  created_at: string;
  sources?: OutputSource[];
}

export interface StudioEvent {
  id: number;
  workspace_id: string;
  channel_id: string;
  run_id: string;
  content_item_id: string | null;
  agent_key: AgentKey;
  seq: number;
  event_type: StudioEventType;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface MetricCard {
  key: string;
  metric_id: string;
  label: string;
  unit: string;
  value: number | null;
  delta_pct: number | null;
  availability: "available" | "partial" | "delayed" | "unknown" | "not_applicable";
  stale: boolean;
  fetched_at: string | null;
  source: string | null;
}

export interface ChannelMetricsPanel {
  cards: MetricCard[];
  series: { day: string; value: number }[];
  fetched_at: string | null;
  availability: "available" | "stale" | "unknown";
  stale: boolean;
}

export interface ApprovalRecord {
  id: string;
  target_kind: string;
  target_id: string;
  target_version: number;
  decision: "approved" | "rejected" | "changes_requested";
  reason: string | null;
  decided_by: string;
  decided_at: string;
}

export interface AgentRunRecord {
  id: string;
  channel_agent_id: string;
  agent_key: AgentKey;
  content_item_id: string | null;
  job_id: string | null;
  parent_run_id: string | null;
  status: AgentVisualStatus;
  stage_label: string | null;
  progress: number | null;
  attempt: number;
  model_id: string | null;
  provider: string | null;
  cost_estimate_cents: number | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

export interface StudioSnapshot {
  channel: StudioChannelInfo;
  rooms: StudioRoomState[];
  agents: StudioAgentState[];
  content_items: ContentItemPipeline[];
  active_content_item: ContentItemPipeline | null;
  latest_opportunity: AgentOutput | null;
  metrics_panel: ChannelMetricsPanel;
  recent_events: StudioEvent[];
  latest_event_by_agent: Record<string, StudioEvent>;
  item_outputs: AgentOutput[];
  handoffs: Record<string, unknown>[];
  approvals: ApprovalRecord[];
  last_event_id: number;
  darkforge_available: boolean;
  snapshot_at: string;
}

export interface RoomDetailResponse {
  room: { key: RoomKey; label: string; sort_order: number };
  agents: StudioAgentState[];
  recent_runs: AgentRunRecord[];
  recent_outputs: AgentOutput[];
}

export interface AgentDetailResponse {
  agent: StudioAgentState;
  runs: AgentRunRecord[];
  outputs: AgentOutput[];
}
