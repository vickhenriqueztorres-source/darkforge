import type { AgentKey, RoomKey } from "./types";

export type ExternalGroupKey =
  | "standalone"
  | "hsl_editorial"
  | "hsl_cinematic"
  | "hsl_media"
  | "hsl_postprod"
  | "shorts_cutter";

export type ExternalAgentKind = "agent" | "bot" | "subagent" | "gate" | "orchestrator";

export type ExternalExecutionStatus =
  | "idle"
  | "queued"
  | "working"
  | "waiting_input"
  | "waiting_approval"
  | "blocked"
  | "no_signal"
  | "done"
  | "gate_passed"
  | "gate_failed"
  | "failed"
  | "skipped"
  | "cancelled";

export interface ExternalAgentState {
  workspace_id: string;
  channel_id: string;
  agent_key: string;
  display_name: string;
  group_key: ExternalGroupKey;
  sub_group: string;
  agent_kind: ExternalAgentKind;
  source_path: string;
  runtime_lang: "python" | "typescript" | "mixed";
  studio_room_key: RoomKey;
  studio_agent_key: AgentKey;
  pipeline_order: number;
  description: string;
  active: boolean;
  execution_id: string | null;
  pipeline_run_id: string | null;
  external_run_id: string | null;
  pipeline_title: string | null;
  pipeline_kind: string | null;
  external_execution_id: string | null;
  status: ExternalExecutionStatus;
  stage_label: string | null;
  progress: number | null;
  attempt: number | null;
  model_name: string | null;
  input_summary: Record<string, unknown> | null;
  output_summary: Record<string, unknown> | null;
  artifacts: Array<Record<string, unknown>> | null;
  metrics: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  heartbeat_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  execution_updated_at: string | null;
}

export interface ExternalPipelineRun {
  id: string;
  workspace_id: string;
  channel_id: string;
  content_item_id: string | null;
  external_run_id: string;
  pipeline_kind: string;
  title: string;
  status: "queued" | "running" | "waiting_human" | "completed" | "failed" | "cancelled";
  current_agent_key: string | null;
  progress: number | null;
  total_agents: number | null;
  completed_agents: number;
  failed_agents: number;
  host_name: string | null;
  source_repo: string | null;
  metadata: Record<string, unknown>;
  started_at: string;
  finished_at: string | null;
  updated_at: string;
  active_agents_json: Array<{
    agent_key: string;
    status: ExternalExecutionStatus;
    stage_label: string | null;
    progress: number | null;
  }>;
}

export interface ExternalRoomRollup {
  workspace_id: string;
  channel_id: string;
  room_key: RoomKey;
  total_agents: number;
  working: number;
  queued: number;
  awaiting_human: number;
  done: number;
  failed: number;
}

export interface ExternalAgentEvent {
  id: number;
  workspace_id: string;
  channel_id: string;
  pipeline_run_id: string | null;
  execution_id: string | null;
  agent_key: string;
  event_type: string;
  level: "debug" | "info" | "warn" | "error";
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ExternalAgentsSummary {
  total: number;
  working: number;
  queued: number;
  waiting_human: number;
  done: number;
  failed: number;
  idle: number;
}

export interface ExternalAgentsSnapshot {
  agents: ExternalAgentState[];
  pipeline_runs: ExternalPipelineRun[];
  run_executions: Record<string, unknown>[];
  room_rollups: ExternalRoomRollup[];
  recent_events: ExternalAgentEvent[];
  last_event_id: number;
  summary: ExternalAgentsSummary;
}

export interface ExternalAgentDetailResponse {
  agent: ExternalAgentState;
  executions: Array<{
    id: string;
    external_execution_id: string;
    external_run_id: string | null;
    pipeline_title: string | null;
    pipeline_kind: string | null;
    status: ExternalExecutionStatus;
    stage_label: string | null;
    progress: number | null;
    attempt: number;
    model_name: string | null;
    input_summary: Record<string, unknown>;
    output_summary: Record<string, unknown>;
    artifacts: Array<Record<string, unknown>>;
    metrics: Record<string, unknown>;
    error_code: string | null;
    error_message: string | null;
    started_at: string | null;
    finished_at: string | null;
    duration_ms: number | null;
    updated_at: string;
  }>;
  events: ExternalAgentEvent[];
}

export interface ExternalIngestToken {
  id: string;
  workspace_id: string;
  channel_id: string | null;
  label: string;
  token_prefix: string;
  revoked_at: string | null;
  last_used_at: string | null;
  created_at: string;
  token?: string;
}
