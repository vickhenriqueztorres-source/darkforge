import type {
  AgentDetailResponse,
  AgentOutput,
  AgentRunRecord,
  ContentItemPipeline,
  RoomDetailResponse,
  StudioEvent,
  StudioSnapshot,
} from "./studio/types";
import type { StudioOverview } from "./studio/hq-types";

export type ErrorEnvelope = {
  code: string;
  message: string;
  retryable: boolean;
  details?: { next_action?: string; field?: string; [k: string]: unknown };
  correlation_id?: string;
  job_id?: string | null;
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly envelope: ErrorEnvelope;

  constructor(status: number, envelope: ErrorEnvelope) {
    super(envelope.message);
    this.status = status;
    this.envelope = envelope;
  }
}

export type WorkspaceDTO = {
  id: string;
  name: string;
  slug: string;
  version: number;
};

export type WorkspaceListItem = {
  workspace: WorkspaceDTO;
  role: "owner" | "editor" | "viewer";
};

export type ChannelDTO = {
  id: string;
  workspace_id: string;
  platform: string;
  external_channel_id?: string | null;
  display_name: string;
  handle: string | null;
  status: string;
  active_profile_version_id: string | null;
  version: number;
};

export type YouTubePublicVideo = {
  video_id: string;
  url: string;
  title: string;
  published_at: string | null;
  thumbnail_url: string | null;
  thumbnail_fallback_url?: string | null;
  duration_seconds: number | null;
  format: "short" | "long" | "unknown";
  views: number | null;
  likes: number | null;
  comments: number | null;
  live: boolean;
  age_days: number | null;
  outlier_ratio: number | null;
  engagement_rate: number | null;
};

export type YouTubePublicOverview = {
  source: "youtube_data_api_v3" | "public_page_rss";
  channel: {
    channel_id: string;
    handle: string | null;
    title: string;
    description: string;
    avatar_url: string | null;
    banner_url: string | null;
    country: string | null;
    created_at: string | null;
    url: string;
  };
  stats: {
    subscribers: number | null;
    subscribers_approximate: boolean;
    subscribers_hidden: boolean;
    total_views: number | null;
    video_count: number | null;
  };
  videos: YouTubePublicVideo[];
  insights: {
    sample_size: number;
    views_sum: number | null;
    views_avg: number | null;
    views_median: number | null;
    median_by_format: Partial<Record<"short" | "long" | "unknown", number>>;
    shorts_count: number;
    longs_count: number;
    uploads_last_30d: number;
    days_since_last_upload: number | null;
    avg_days_between_uploads: number | null;
    engagement_rate_avg: number | null;
    best_video_id: string | null;
    outliers: string[];
  };
  warnings: string[];
  fetched_at: string;
  cache: "hit" | "miss";
  quota_cost: number;
};

export type ChannelYouTubeOverviewResponse = {
  channel_link: { handle: string | null; external_channel_id: string | null };
  has_api_key: boolean;
  overview: YouTubePublicOverview;
};

export type ChannelProfileVersionDTO = {
  id: string;
  channel_id: string;
  version_number: number;
  name: string;
  language: string;
  country: string;
  timezone: string;
  niche: string;
  positioning: string;
  editorial_theme: string;
  pillars_json: string[];
  formats_json: string[];
  objectives_json: string[];
  audience_json: Record<string, unknown>;
  voice_json: Record<string, unknown>;
  restrictions_json: Record<string, unknown>;
  effective_from: string;
  change_summary: string;
};

export type EditorialThemeChangeDTO = {
  id: string;
  previous_theme: string;
  new_theme: string;
  reason: string;
  effective_at: string;
  new_version_id: string;
};

export type HealthDTO = {
  status: "ok" | "degraded";
  supabase_reachable: boolean;
  service: string;
};

export type JobDTO = {
  id: string;
  workspace_id: string;
  channel_id: string | null;
  job_type: string;
  status: string;
  current_step: string;
  total_steps: number;
  completed_steps: number;
  attempt_count: number;
  pause_requested: boolean;
  cancel_requested: boolean;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  created_at: string | null;
};

export type JobEventDTO = {
  sequence_no: number;
  event_type: string;
  step_name: string;
  status: string;
  message: string;
  created_at: string | null;
};

export type StorageReconcileDTO = {
  workspace_id: string;
  bucket: string;
  missing_in_storage: string[];
  orphaned_in_storage: string[];
  incomplete_uploads: string[];
};

export type MetricFactDTO = {
  id: string;
  metric_id: string;
  display_name: string;
  visibility_scope: string;
  source: string;
  source_revision: number;
  period_start: string;
  period_end: string;
  granularity: string;
  availability: "available" | "unknown" | "delayed" | "partial" | "not_applicable";
  value_num: number | null;
  is_estimate: boolean;
  fetched_at: string;
};

export type SyncCursorDTO = {
  sync_scope: string;
  freshness_status: string;
  last_page_processed: number;
  last_successful_sync_at: string | null;
  partial_errors: { message?: string }[];
};

export type VideoDTO = {
  id: string;
  title: string;
  canonical_url: string;
  format: string;
  duration_seconds: number | null;
  published_at: string | null;
  source: string;
};

export type ConnectionDTO = {
  id: string;
  channel_id: string;
  platform: string;
  status: string;
  scopes: string[];
  external_channel_id: string | null;
  last_validated_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
};

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function apiFetch<T>(
  path: string,
  options: {
    method?: string;
    token?: string;
    workspaceId?: string;
    body?: unknown;
  } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;
  if (options.workspaceId) headers["X-Workspace-Id"] = options.workspaceId;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiClientError(503, {
      code: "SUPABASE_UNAVAILABLE",
      message: "API local ou rede inacessivel. Nenhuma escrita pode ser confirmada.",
      retryable: true,
      details: { next_action: "Verifique se a API local e a conexao com o Supabase estao ativas." },
    });
  }

  if (!response.ok) {
    let envelope: ErrorEnvelope = {
      code: response.status === 403 ? "WORKSPACE_FORBIDDEN" : "VALIDATION_ERROR",
      message: `Falha HTTP ${response.status}`,
      retryable: response.status >= 500,
    };
    try {
      const parsed = (await response.json()) as Partial<ErrorEnvelope>;
      if (parsed.code && parsed.message) {
        envelope = {
          code: parsed.code,
          message: parsed.message,
          retryable: Boolean(parsed.retryable),
          details: parsed.details,
          correlation_id: parsed.correlation_id,
          job_id: parsed.job_id,
        };
      }
    } catch {
      // Keep structured fallback envelope
    }
    throw new ApiClientError(response.status, envelope);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => apiFetch<HealthDTO>("/api/v1/health"),
  listWorkspaces: (token: string) =>
    apiFetch<{ items: WorkspaceListItem[] }>("/api/v1/workspaces", { token }),
  createWorkspace: (token: string, name: string, slug: string) =>
    apiFetch<WorkspaceListItem>("/api/v1/workspaces", {
      method: "POST",
      token,
      body: { name, slug },
    }),
  listChannels: (token: string, workspaceId: string) =>
    apiFetch<{ items: ChannelDTO[] }>("/api/v1/channels", { token, workspaceId }),
  createChannel: (
    token: string,
    workspaceId: string,
    payload: {
      display_name: string;
      handle?: string | null;
      profile: Record<string, unknown>;
    }
  ) =>
    apiFetch<{ channel: ChannelDTO; profile_version: ChannelProfileVersionDTO }>(
      "/api/v1/channels",
      { method: "POST", token, workspaceId, body: payload }
    ),
  updateProfile: (
    token: string,
    workspaceId: string,
    channelId: string,
    profile: Record<string, unknown>
  ) =>
    apiFetch<{
      channel: ChannelDTO;
      profile_version: ChannelProfileVersionDTO;
      theme_change: EditorialThemeChangeDTO | null;
    }>(`/api/v1/channels/${channelId}/profile`, {
      method: "PUT",
      token,
      workspaceId,
      body: profile,
    }),
  listProfileVersions: (token: string, workspaceId: string, channelId: string) =>
    apiFetch<{ items: ChannelProfileVersionDTO[] }>(
      `/api/v1/channels/${channelId}/profile/versions`,
      { token, workspaceId }
    ),
  listThemeChanges: (token: string, workspaceId: string, channelId: string) =>
    apiFetch<{ items: EditorialThemeChangeDTO[] }>(
      `/api/v1/channels/${channelId}/theme-changes`,
      { token, workspaceId }
    ),
  getChannelYouTubeOverview: (token: string, workspaceId: string, channelId: string, refresh = false) =>
    apiFetch<ChannelYouTubeOverviewResponse>(
      `/api/v1/channels/${channelId}/youtube/overview${refresh ? "?refresh=true" : ""}`,
      { token, workspaceId }
    ),
  linkChannelYouTube: (token: string, workspaceId: string, channelId: string, channelRef: string) =>
    apiFetch<{ channel: ChannelDTO; has_api_key: boolean; overview: YouTubePublicOverview }>(
      `/api/v1/channels/${channelId}/youtube/link`,
      { method: "PUT", token, workspaceId, body: { channel_ref: channelRef } }
    ),
  listJobs: (token: string, workspaceId: string, status?: string) =>
    apiFetch<{ items: JobDTO[] }>(
      `/api/v1/jobs${status ? `?status=${encodeURIComponent(status)}` : ""}`,
      { token, workspaceId }
    ),
  enqueueJob: (
    token: string,
    workspaceId: string,
    payload: { job_type: string; payload: Record<string, unknown>; total_steps: number },
    idempotencyKey: string
  ) =>
    fetch(`${API_BASE}/api/v1/jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-Workspace-Id": workspaceId,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(payload),
    }).then(async (r) => {
      if (!r.ok) throw new ApiClientError(r.status, await r.json());
      return r.json() as Promise<{ job_id: string; status: string; deduplicated: boolean }>;
    }),
  getJobDetail: (token: string, workspaceId: string, jobId: string) =>
    apiFetch<{ job: JobDTO; events: JobEventDTO[] }>(`/api/v1/jobs/${jobId}`, { token, workspaceId }),
  pauseJob: (token: string, workspaceId: string, jobId: string) =>
    apiFetch<{ job: JobDTO; control_result: string }>(`/api/v1/jobs/${jobId}/pause`, {
      method: "POST",
      token,
      workspaceId,
    }),
  resumeJob: (token: string, workspaceId: string, jobId: string) =>
    apiFetch<{ job: JobDTO; control_result: string }>(`/api/v1/jobs/${jobId}/resume`, {
      method: "POST",
      token,
      workspaceId,
    }),
  cancelJob: (token: string, workspaceId: string, jobId: string) =>
    apiFetch<{ job: JobDTO; control_result: string }>(`/api/v1/jobs/${jobId}/cancel`, {
      method: "POST",
      token,
      workspaceId,
    }),
  reconcileStorage: (token: string, workspaceId: string, bucket: string) =>
    apiFetch<{ report: StorageReconcileDTO }>("/api/v1/storage/reconcile", {
      method: "POST",
      token,
      workspaceId,
      body: { bucket },
    }),
  listConnections: (token: string, workspaceId: string) =>
    apiFetch<{ items: ConnectionDTO[] }>("/api/v1/connections", { token, workspaceId }),
  authorizeYouTube: (token: string, workspaceId: string, channelId: string) =>
    apiFetch<{ authorize_url: string; state: string }>("/api/v1/connections/youtube/authorize", {
      method: "POST",
      token,
      workspaceId,
      body: { channel_id: channelId },
    }),
  disconnectConnection: (
    token: string,
    workspaceId: string,
    connectionId: string,
    retentionPolicy: "keep_readonly" | "purge_synced_data"
  ) =>
    apiFetch<{ status: string; tokens_deleted: boolean; purged_videos: number }>(
      `/api/v1/connections/${connectionId}?retention_policy=${retentionPolicy}`,
      { method: "DELETE", token, workspaceId }
    ),
  syncChannel: (token: string, workspaceId: string, channelId: string) =>
    apiFetch<{ job_id: string; status: string; deduplicated: boolean }>(
      `/api/v1/channels/${channelId}/sync`,
      { method: "POST", token, workspaceId, body: { sync_scope: "catalog_incremental" } }
    ),
  getPortfolioAnalytics: (token: string, workspaceId: string) =>
    apiFetch<{
      period_start: string;
      period_end: string;
      channels: { channel_id: string; display_name: string; video_count: number; metrics: MetricFactDTO[]; cursors: SyncCursorDTO[] }[];
      quota: { daily_limit: number; own_sync_used: number; public_research_used: number };
    }>("/api/v1/analytics/portfolio", { token, workspaceId }),
  getChannelAnalytics: (token: string, workspaceId: string, channelId: string) =>
    apiFetch<{
      channel_id: string;
      period_start: string;
      period_end: string;
      metrics: MetricFactDTO[];
      cursors: SyncCursorDTO[];
      videos: VideoDTO[];
    }>(`/api/v1/channels/${channelId}/analytics`, { token, workspaceId }),
  getVideoDetail: (token: string, workspaceId: string, videoId: string) =>
    apiFetch<{ video: VideoDTO; metrics: MetricFactDTO[] }>(`/api/v1/videos/${videoId}`, {
      token,
      workspaceId,
    }),
  listReferences: (token: string, workspaceId: string, curationStatus?: string) =>
    apiFetch<{ channels: Record<string, unknown>[]; videos: Record<string, unknown>[] }>(
      `/api/v1/research/references${curationStatus ? `?curation_status=${curationStatus}` : ""}`,
      { token, workspaceId }
    ),
  curateReference: (
    token: string,
    workspaceId: string,
    refId: string,
    body: { entity_type: "channel" | "video"; status: string; notes: string; collection_name: string }
  ) =>
    apiFetch<Record<string, unknown>>(`/api/v1/research/references/${refId}/curate`, {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  analyzeTitle: (token: string, workspaceId: string, title: string, channelId?: string) =>
    apiFetch<{ features_json: { features: string[] }; editorial_formula: string; limitations_json: string[] }>(
      "/api/v1/intel/titles/analyze",
      { method: "POST", token, workspaceId, body: { title, channel_id: channelId } }
    ),
  generateTitleAlternatives: (
    token: string,
    workspaceId: string,
    body: { channel_name: string; niche: string; topic: string; reference_titles: string[]; forbidden_topics: string[] }
  ) =>
    apiFetch<{ items: { title: string; differentiation: string; originality: { approval_blocked: boolean; max_similarity: number } }[] }>(
      "/api/v1/intel/titles/generate",
      { method: "POST", token, workspaceId, body }
    ),
  listKnowledgeSources: (token: string, workspaceId: string) =>
    apiFetch<{ items: { id: string; title: string; source_type: string; curation_level: string; status: string; rights_status: string }[] }>(
      "/api/v1/knowledge/sources",
      { token, workspaceId }
    ),
  importKnowledgeSource: (
    token: string,
    workspaceId: string,
    body: { title: string; source_type: string; content_text: string; rights_status: string; collection_name: string }
  ) =>
    apiFetch<{ source: { id: string }; deduplicated: boolean }>("/api/v1/knowledge/sources", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  reviewKnowledgeSource: (
    token: string,
    workspaceId: string,
    sourceId: string,
    body: { curation_level: string; status: string }
  ) =>
    apiFetch<Record<string, unknown>>(`/api/v1/knowledge/sources/${sourceId}/review`, {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  reindexKnowledge: (token: string, workspaceId: string, forceNewRevision = false) =>
    apiFetch<{ indexed_sources: number; total_chunks: number; revision: { embedding_version: string; status: string } }>(
      "/api/v1/knowledge/reindex",
      { method: "POST", token, workspaceId, body: { force_new_revision: forceNewRevision } }
    ),
  searchKnowledge: (token: string, workspaceId: string, query: string) =>
    apiFetch<{ chunks: { chunk_id: string; source_id: string; source_title: string; curation_level: string; chunk_text: string; hybrid_score: number }[]; insufficient_context: boolean }>(
      "/api/v1/knowledge/search",
      { method: "POST", token, workspaceId, body: { query } }
    ),
  deleteKnowledgeSource: (token: string, workspaceId: string, sourceId: string, hardDelete: boolean) =>
    apiFetch<{ action: string; embeddings_removed: number }>(`/api/v1/knowledge/sources/${sourceId}?hard_delete=${hardDelete}`, {
      method: "DELETE",
      token,
      workspaceId,
    }),
  listOpportunities: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{ items: { id: string; theme: string; angle: string; score: number; score_version: string; confidence: number; status: string; insufficient_data: boolean; limitations_json: string[] }[] }>(
      `/api/v1/opportunities${channelId ? `?channel_id=${channelId}` : ""}`,
      { token, workspaceId }
    ),
  generateOpportunities: (
    token: string,
    workspaceId: string,
    body: { channel_id: string; topic_hint: string; target_format: string }
  ) =>
    apiFetch<{ opportunity: { id: string; theme: string; score: number; status: string } }>("/api/v1/opportunities/generate", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  reviewOpportunity: (
    token: string,
    workspaceId: string,
    opportunityId: string,
    body: { decision: string; notes?: string }
  ) =>
    apiFetch<{ opportunity: { id: string; status: string }; fine_tuning_claimed: boolean }>(
      `/api/v1/opportunities/${opportunityId}/feedback`,
      { method: "POST", token, workspaceId, body }
    ),
  listBriefs: (token: string, workspaceId: string) =>
    apiFetch<{ items: { id: string; brief_group_id: string; version: number; opportunity_id: string; title: string; hook: string; angle: string; status: string; content_sha256: string }[] }>(
      "/api/v1/briefs",
      { token, workspaceId }
    ),
  createBrief: (
    token: string,
    workspaceId: string,
    body: { opportunity_id: string; title: string; hook: string; angle: string; cta?: string }
  ) =>
    apiFetch<{ brief: { id: string; version: number; status: string } }>("/api/v1/briefs", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  approveBrief: (token: string, workspaceId: string, briefId: string) =>
    apiFetch<{ brief: { id: string; status: string } }>(`/api/v1/briefs/${briefId}/approve`, {
      method: "POST",
      token,
      workspaceId,
      body: { notes: "Aprovado via Studio UI" },
    }),
  createBriefVersion: (token: string, workspaceId: string, briefId: string, title: string) =>
    apiFetch<{ brief: { id: string; version: number; status: string } }>(`/api/v1/briefs/${briefId}/versions`, {
      method: "POST",
      token,
      workspaceId,
      body: { title, notes: "Nova versao via UI" },
    }),
  exportBrief: (token: string, workspaceId: string, briefId: string, format: "markdown" | "json" | "csv" = "markdown") =>
    apiFetch<{ format: string; filename: string; content: string }>(`/api/v1/briefs/${briefId}/export?format=${format}`, {
      token,
      workspaceId,
    }),
  listCalendar: (token: string, workspaceId: string) =>
    apiFetch<{ items: { id: string; title: string; scheduled_for: string; status: string; auto_publish_enabled: boolean }[] }>(
      "/api/v1/calendar",
      { token, workspaceId }
    ),
  createCalendarItem: (
    token: string,
    workspaceId: string,
    body: { channel_id: string; title: string; scheduled_for: string; brief_id?: string }
  ) =>
    apiFetch<{ item: { id: string } }>("/api/v1/calendar", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  getProductionHealth: (token: string, workspaceId: string) =>
    apiFetch<{ available: boolean; mode: string; reason: string | null }>("/api/v1/production/health", {
      token,
      workspaceId,
    }),
  listProductionIntents: (token: string, workspaceId: string) =>
    apiFetch<{ items: { id: string; brief_id: string; brief_version: number; status: string; manifest_validated: boolean; error_code: string | null; error_message: string | null }[] }>(
      "/api/v1/production/intents",
      { token, workspaceId }
    ),
  createProductionIntent: (token: string, workspaceId: string, briefId: string, idempotencyKey: string) =>
    apiFetch<{ intent: { id: string; status: string }; deduplicated: boolean }>(`/api/v1/briefs/${briefId}/production`, {
      method: "POST",
      token,
      workspaceId,
      body: { idempotency_key: idempotencyKey },
    }),
  dispatchProductionIntent: (token: string, workspaceId: string, intentId: string) =>
    apiFetch<{ intent: { id: string; status: string } }>(`/api/v1/production/intents/${intentId}/dispatch`, {
      method: "POST",
      token,
      workspaceId,
    }),
  exportDiagnostics: (token: string, workspaceId: string) =>
    apiFetch<Record<string, unknown>>("/api/v1/diagnostics/export", {
      token,
      workspaceId,
    }),
  studioSessionStatus: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{ authenticated: boolean; reason: string }>(`/api/v1/research/studio-session/status${channelId ? `?channel_id=${channelId}` : ""}`, {
      token,
      workspaceId,
    }),
  openStudioLoginWindow: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{ authenticated: boolean; final_url?: string; next_action?: string }>(`/api/v1/research/studio-session/login-window${channelId ? `?channel_id=${channelId}` : ""}`, {
      method: "POST",
      token,
      workspaceId,
    }),
  createStudioRun: (
    token: string,
    workspaceId: string,
    body: {
      channel_id: string;
      broad_topic: string;
      min_interest: string;
      only_watched_by_my_viewers: boolean;
      upload_window_days: number;
      min_outlier_ratio: number;
      execute_now: boolean;
    }
  ) =>
    apiFetch<{ run: { id: string; status: string }; terms: { id: string; term: string; block_type: string; audience_interest: string; is_hypothesis: boolean }[]; outliers: { id: string; external_video_id: string; title: string; canonical_url: string; outlier_ratio: number | null; outlier_tier: string; watched_by_my_viewers: boolean }[] }>(
      "/api/v1/research/studio-runs",
      { method: "POST", token, workspaceId, body }
    ),
  listStudioRuns: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{ items: { id: string; broad_topic: string; status: string; created_at: string }[] }>(
      `/api/v1/research/studio-runs${channelId ? `?channel_id=${channelId}` : ""}`,
      { token, workspaceId }
    ),
  getStudioRunDetail: (token: string, workspaceId: string, runId: string) =>
    apiFetch<{
      run: { id: string; status: string; broad_topic: string };
      terms: { id: string; term: string; block_type: string; audience_interest: string; is_hypothesis: boolean; gap_note: string }[];
      outliers: { id: string; title: string; canonical_url: string; outlier_ratio: number | null; outlier_tier: string; watched_by_my_viewers: boolean; public_views: number | null }[];
    }>(`/api/v1/research/studio-runs/${runId}`, { token, workspaceId }),
  listGoogleTrends: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{
      items: {
        id: string;
        keyword: string;
        geo: string;
        gprop: string;
        direction_12m: string;
        durability_5y: string;
        verdict: string;
        summary: string;
        points_12m_json: { value: number }[];
        points_5y_json: { value: number }[];
        breakout_queries_json: { term: string; raw_label: string }[];
        rising_queries_json: { term: string; raw_label: string }[];
      }[];
    }>(`/api/v1/research/google-trends${channelId ? `?channel_id=${channelId}` : ""}`, { token, workspaceId }),
  validateGoogleTrends: (
    token: string,
    workspaceId: string,
    body: { keyword: string; channel_id?: string; geo?: string; gprop?: string; force_refresh?: boolean }
  ) =>
    apiFetch<{ validation: Record<string, unknown>; cached: boolean }>("/api/v1/research/google-trends/validate", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  importGoogleTrendsCsv: (
    token: string,
    workspaceId: string,
    body: { keyword: string; channel_id?: string; geo: string; gprop: string; timeline_12m_csv: string; timeline_5y_csv: string; related_queries_csv: string }
  ) =>
    apiFetch<{ validation: Record<string, unknown> }>("/api/v1/research/google-trends/import-csv", {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  getReverseEngineeringState: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{
      audits: {
        id: string;
        external_channel_id: string;
        display_name: string;
        approved: boolean;
        channel_mean_views: number;
        outlier_hits_count: number;
        max_outlier_ratio: number;
        ranking_score: number;
        passed_criteria_json?: string[];
        failed_criteria_json?: string[];
        warnings_json?: string[];
      }[];
      viral_outliers: {
        id: string;
        external_video_id: string;
        channel_name: string;
        title: string;
        views: number;
        days_since_upload: number;
        views_per_day: number;
        channel_mean_views: number;
        outlier_ratio: number;
        pattern_key: string;
        confirmed_multi_channel: boolean;
        is_false_positive: boolean;
        false_positive_reasons_json: string[];
      }[];
      autopsies: {
        id: string;
        external_video_id: string;
        original_title: string;
        narrative_archetype: string;
        confidence: number;
        package_json?: Record<string, unknown>;
        script_retention_json?: Record<string, unknown>;
        comment_gaps_json?: Record<string, unknown>;
      }[];
      mechanisms: {
        id: string;
        formula_theme: string;
        formula_angle: string;
        formula_emotion: string;
        formula_structure: string;
        formula_format?: string;
        synthesized_title: string;
        synthesized_thumb_concept: string;
        originality_blocked: boolean;
        originality_max_similarity: number;
      }[];
      batches: { id: string; title: string; status: string; impressions: number | null; ctr_pct: number | null; retention_30s_pct: number | null }[];
    }>(`/api/v1/research/reverse-engineering/state${channelId ? `?channel_id=${channelId}` : ""}`, { token, workspaceId }),
  runPhase1Channels: (
    token: string,
    workspaceId: string,
    body: {
      channel_id: string;
      target_language: string;
      target_country: string;
      feasible_formats: string[];
      target_audience_tags: string[];
      min_outlier_ratio?: number;
      candidates: {
        external_channel_id: string;
        display_name: string;
        language: string;
        market_country: string;
        recent_video_views_90d: number[];
        all_recent_20_30_views: number[];
        production_format: string;
        audience_profile_tags: string[];
        is_celebrity_or_mega_brand: boolean;
      }[];
    }
  ) =>
    apiFetch<{ selected_count: number; meets_5_to_10_target: boolean; recommendation: string; audits: unknown[] }>(
      "/api/v1/research/reverse-engineering/phase1-channels",
      { method: "POST", token, workspaceId, body }
    ),
  runPhase2Outliers: (
    token: string,
    workspaceId: string,
    body: {
      channel_id: string;
      small_niche: boolean;
      videos: {
        external_video_id: string;
        external_channel_id: string;
        channel_name: string;
        title: string;
        views: number;
        days_since_upload: number;
        topic: string;
        format_name: string;
        is_breaking_news?: boolean;
        has_celebrity_collab?: boolean;
        channel_authority_only?: boolean;
        in_suggested_feed?: boolean;
      }[];
    }
  ) =>
    apiFetch<{ valid_outliers: unknown[]; confirmed_patterns: unknown[]; channel_summaries: unknown[] }>(
      "/api/v1/research/reverse-engineering/phase2-outliers",
      { method: "POST", token, workspaceId, body }
    ),
  runPhase3Autopsy: (
    token: string,
    workspaceId: string,
    body: { channel_id: string; external_video_id: string; title: string; transcript_or_notes: string; comments: string[]; thumbnail_text?: string }
  ) =>
    apiFetch<{ autopsy: { id: string; original_title: string; narrative_archetype: string } }>(
      "/api/v1/research/reverse-engineering/phase3-autopsy",
      { method: "POST", token, workspaceId, body }
    ),
  runPhase4Synthesize: (
    token: string,
    workspaceId: string,
    body: { channel_id: string; own_validated_topic: string; new_angle: string; target_format: string }
  ) =>
    apiFetch<{ mechanism: { id: string; synthesized_title: string; synthesized_thumb_concept: string } }>(
      "/api/v1/research/reverse-engineering/phase4-synthesize",
      { method: "POST", token, workspaceId, body }
    ),
  createExperimentBatch: (
    token: string,
    workspaceId: string,
    body: { channel_id: string; mechanism_id?: string; title: string }
  ) =>
    apiFetch<{ batch: { id: string; title: string; status: string } }>(
      "/api/v1/research/reverse-engineering/batches",
      { method: "POST", token, workspaceId, body }
    ),
  getReportsOverview: (token: string, workspaceId: string, channelId?: string) =>
    apiFetch<{
      generated_at: string;
      workspace_id: string;
      channel_id_filter: string | null;
      summary: {
        channels_count: number;
        phase1_audits_total: number;
        phase1_selected_count: number;
        phase2_outliers_total: number;
        phase2_valid_outliers: number;
        phase3_autopsies_count: number;
        phase4_mechanisms_count: number;
        experiment_batches_count: number;
        studio_runs_count: number;
        studio_terms_count: number;
        studio_outliers_count: number;
        google_trends_count: number;
        google_trends_sustainable_count: number;
        opportunities_count: number;
        opportunities_approved_count: number;
        briefs_count: number;
        briefs_approved_count: number;
        calendar_items_count: number;
      };
      channels: { id: string; display_name: string; handle: string | null; external_channel_id?: string | null; status: string }[];
      portfolio_analytics?: {
        channels: {
          channel_id: string;
          display_name: string;
          video_count: number;
          metrics: { metric_id: string; display_name: string; value_num: number | null }[];
        }[];
      };
      channel_videos?: { id: string; external_video_id: string; title: string; canonical_url: string; format: string }[];
      reverse_engineering: {
        audits: {
          id: string;
          display_name: string;
          approved: boolean;
          channel_mean_views: number;
          outlier_hits_count: number;
          max_outlier_ratio: number;
          ranking_score: number;
          failed_criteria_json?: string[];
          warnings_json?: string[];
        }[];
        viral_outliers: {
          id: string;
          channel_name: string;
          title: string;
          views: number;
          days_since_upload: number;
          views_per_day: number;
          outlier_ratio: number;
          pattern_key: string;
          confirmed_multi_channel: boolean;
          is_false_positive: boolean;
        }[];
        autopsies: {
          id: string;
          external_video_id: string;
          original_title: string;
          narrative_archetype: string;
          confidence: number;
          package_json?: {
            promise_structure?: string;
            central_tension?: string;
            visual_focus?: string;
            visual_question?: string;
          };
          script_retention_json?: {
            hook_0_15s?: string;
            value_15_30s?: string;
            open_loops?: string[];
          };
          comment_gaps_json?: {
            viewer_questions?: string[];
            follow_up_requests?: string[];
          };
        }[];
        mechanisms: {
          id: string;
          formula_theme: string;
          formula_angle: string;
          formula_emotion: string;
          formula_structure: string;
          formula_format?: string;
          synthesized_title: string;
          synthesized_thumb_concept: string;
          originality_blocked: boolean;
          originality_max_similarity: number;
        }[];
        batches: {
          id: string;
          title: string;
          status: string;
          impressions: number | null;
          ctr_pct: number | null;
          retention_30s_pct: number | null;
        }[];
      };
      studio_trends: {
        runs: { id: string; broad_topic: string; status: string; captured_via: string | null; created_at: string }[];
        terms: { id: string; term: string; block_type: string; audience_interest: string; is_hypothesis: boolean; gap_note: string }[];
        outliers: { id: string; title: string; canonical_url: string; outlier_ratio: number | null; outlier_tier: string; watched_by_my_viewers: boolean }[];
      };
      google_trends: {
        id: string;
        keyword: string;
        geo: string;
        gprop: string;
        direction_12m: string;
        durability_5y: string;
        peak_decay_pct?: number;
        verdict: string;
        summary: string;
        breakout_queries_json: { term: string; raw_label: string }[];
        rising_queries_json: { term: string; raw_label: string }[];
      }[];
      opportunities: {
        id: string;
        theme: string;
        angle: string;
        differentiation: string;
        score: number;
        score_version: string;
        confidence: number;
        status: string;
        insufficient_data: boolean;
        score_breakdown_json: Record<string, number>;
        limitations_json: string[];
        analyst_reports_json: {
          analyst: string;
          confidence: number;
          data_freshness: string;
          findings: string[];
          recommendations: string[];
          limitations: string[];
          evidence: { source_kind: string; snippet: string }[];
        }[];
      }[];
      briefs: { id: string; title: string; version: number; status: string; target_format: string; hook: string }[];
      calendar: { id: string; title: string; scheduled_for: string; status: string }[];
      diagnostics: {
        generated_at: string;
        environment_flags: Record<string, boolean>;
        redaction_applied: boolean;
        jobs_recent: { id: string; job_type: string; status: string; error_code: string | null }[];
      } | null;
    }>(`/api/v1/reports/overview${channelId ? `?channel_id=${channelId}` : ""}`, { token, workspaceId }),
  exportExecutiveMarkdown: async (token: string, workspaceId: string, channelId?: string): Promise<string> => {
    const res = await fetch(
      `${API_BASE}/api/v1/reports/executive.md${channelId ? `?channel_id=${channelId}` : ""}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Workspace-Id": workspaceId,
        },
      }
    );
    if (!res.ok) {
      throw new Error(`Falha ao exportar relatorio Markdown (${res.status}).`);
    }
    return res.text();
  },
  getStudioOverview: (token: string, workspaceId: string) =>
    apiFetch<StudioOverview>("/api/v1/studio/overview", { token, workspaceId }),
  getStudioSnapshot: (token: string, workspaceId: string, channelId: string, contentItemId?: string) =>
    apiFetch<StudioSnapshot>(
      `/api/v1/studio/channels/${channelId}/snapshot${contentItemId ? `?content_item_id=${encodeURIComponent(contentItemId)}` : ""}`,
      { token, workspaceId }
    ),
  getStudioEvents: (token: string, workspaceId: string, channelId: string, afterId = 0, limit = 100) =>
    apiFetch<{ events: StudioEvent[]; last_event_id: number }>(
      `/api/v1/studio/channels/${channelId}/events?after_id=${afterId}&limit=${limit}`,
      { token, workspaceId }
    ),
  getStudioRoomDetail: (token: string, workspaceId: string, channelId: string, roomKey: string) =>
    apiFetch<RoomDetailResponse>(`/api/v1/studio/channels/${channelId}/rooms/${roomKey}`, {
      token,
      workspaceId,
    }),
  getStudioAgentDetail: (token: string, workspaceId: string, channelId: string, agentKey: string) =>
    apiFetch<AgentDetailResponse>(`/api/v1/studio/channels/${channelId}/agents/${agentKey}`, {
      token,
      workspaceId,
    }),
  updateStudioChannelAgent: (
    token: string,
    workspaceId: string,
    channelId: string,
    agentKey: string,
    body: {
      enabled?: boolean;
      display_name?: string;
      avatar_key?: string;
      model_policy?: { mode: string; external_consent?: boolean };
      monthly_budget_cents?: number;
      clear_budget?: boolean;
    }
  ) =>
    apiFetch<{ agent: Record<string, unknown> }>(`/api/v1/studio/channels/${channelId}/agents/${agentKey}`, {
      method: "PATCH",
      token,
      workspaceId,
      body,
    }),
  createStudioContentItem: (
    token: string,
    workspaceId: string,
    channelId: string,
    body: { working_title: string; trigger_initial_agents?: boolean }
  ) =>
    apiFetch<{ content_item: ContentItemPipeline; deduplicated: boolean; enqueued_runs: AgentRunRecord[] }>(
      `/api/v1/studio/channels/${channelId}/content-items`,
      { method: "POST", token, workspaceId, body }
    ),
  runStudioAgent: (
    token: string,
    workspaceId: string,
    channelId: string,
    agentKey: string,
    body: { content_item_id?: string | null; reason?: string; idempotency_key?: string; topic?: string }
  ) =>
    apiFetch<{ run: AgentRunRecord; deduplicated: boolean }>(
      `/api/v1/studio/channels/${channelId}/agents/${agentKey}/run`,
      { method: "POST", token, workspaceId, body }
    ),
  cancelStudioRun: (token: string, workspaceId: string, runId: string) =>
    apiFetch<{ run: AgentRunRecord }>(`/api/v1/studio/runs/${runId}/cancel`, {
      method: "POST",
      token,
      workspaceId,
    }),
  retryStudioRun: (token: string, workspaceId: string, runId: string) =>
    apiFetch<{ run: AgentRunRecord }>(`/api/v1/studio/runs/${runId}/retry`, {
      method: "POST",
      token,
      workspaceId,
    }),
  submitStudioApproval: (
    token: string,
    workspaceId: string,
    channelId: string,
    body: {
      target_kind: "agent_output" | "opportunity" | "brief" | "publication_plan";
      target_id: string;
      target_version: number;
      decision: "approved" | "rejected" | "changes_requested";
      reason?: string;
      confirm_needs_review?: boolean;
      content_item_id?: string | null;
    }
  ) =>
    apiFetch<{ approval: Record<string, unknown>; enqueued_next_runs: AgentRunRecord[] }>(
      `/api/v1/studio/channels/${channelId}/approvals`,
      { method: "POST", token, workspaceId, body }
    ),
  reviseStudioOutput: (
    token: string,
    workspaceId: string,
    outputId: string,
    body: { action: "save_version" | "discard"; edited_content?: Record<string, unknown>; reason?: string }
  ) =>
    apiFetch<{ output: AgentOutput; action: string }>(`/api/v1/studio/outputs/${outputId}/revise`, {
      method: "POST",
      token,
      workspaceId,
      body,
    }),
  markStudioManualPublished: (
    token: string,
    workspaceId: string,
    contentItemId: string,
    publishedVideoUrl: string
  ) =>
    apiFetch<{ content_item: Record<string, unknown> }>(
      `/api/v1/studio/content-items/${contentItemId}/publish-manual`,
      { method: "POST", token, workspaceId, body: { published_video_url: publishedVideoUrl } }
    ),
};

export type ReportsOverviewDTO = Awaited<ReturnType<typeof api.getReportsOverview>>;
