/**
 * Drop-in Telemetry Client (TypeScript) para o projeto separado O Outro Lado
 * (pipeline HSL, sound-agent, sfx-agent, music-agent, packaging-agent).
 * Zero dependencias externas (usa fetch nativo do Node 18+ / Deno / Bun).
 */

export type ExternalAgentStatus =
  | "idle"
  | "queued"
  | "working"
  | "waiting_input"
  | "waiting_approval"
  | "blocked"
  | "done"
  | "gate_passed"
  | "gate_failed"
  | "failed"
  | "skipped"
  | "cancelled";

export type ExternalPipelineKind =
  | "hsl_episode"
  | "shorts_cutter"
  | "standalone_bot"
  | "firefly_batch"
  | "audio_factory"
  | "custom";

export interface ReportAgentParams {
  agentKey: string;
  status: ExternalAgentStatus;
  externalRunId: string;
  pipelineKind?: ExternalPipelineKind;
  runTitle?: string;
  externalExecutionId?: string;
  stageLabel?: string;
  progress?: number;
  modelName?: string;
  eventType?:
    | "queued"
    | "started"
    | "progress"
    | "stage_changed"
    | "heartbeat"
    | "artifact_created"
    | "gate_passed"
    | "gate_failed"
    | "waiting_human"
    | "completed"
    | "failed"
    | "cancelled"
    | "log";
  level?: "debug" | "info" | "warn" | "error";
  message?: string;
  inputSummary?: Record<string, unknown>;
  outputSummary?: Record<string, unknown>;
  artifacts?: Array<Record<string, unknown>>;
  metrics?: Record<string, unknown>;
  errorCode?: string;
  errorMessage?: string;
  attempt?: number;
  metadata?: Record<string, unknown>;
}

export interface CentralTelemetryConfig {
  apiBaseUrl?: string;
  ingestToken?: string;
  channelId?: string;
  supabaseUrl?: string;
  supabaseServiceRoleKey?: string;
  workspaceId?: string;
  sourceRepo?: string;
  failOpen?: boolean;
}

export class CentralTelemetryClient {
  private readonly apiBaseUrl: string;
  private readonly ingestToken: string;
  private readonly channelId: string;
  private readonly supabaseUrl: string;
  private readonly supabaseKey: string;
  private readonly workspaceId: string;
  private readonly sourceRepo: string;
  private readonly failOpen: boolean;

  constructor(cfg: CentralTelemetryConfig = {}) {
    this.apiBaseUrl = (cfg.apiBaseUrl ?? process.env.MANAGET_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    this.ingestToken = cfg.ingestToken ?? process.env.MANAGET_INGEST_TOKEN ?? "";
    this.channelId = cfg.channelId ?? process.env.MANAGET_CHANNEL_ID ?? "";
    this.supabaseUrl = (cfg.supabaseUrl ?? process.env.SUPABASE_URL ?? "").replace(/\/$/, "");
    this.supabaseKey = cfg.supabaseServiceRoleKey ?? process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";
    this.workspaceId = cfg.workspaceId ?? process.env.MANAGET_WORKSPACE_ID ?? "";
    this.sourceRepo = cfg.sourceRepo ?? "O-OUTRO-LADO";
    this.failOpen = cfg.failOpen ?? true;
  }

  async report(params: ReportAgentParams): Promise<void> {
    try {
      if (this.ingestToken) {
        const res = await fetch(`${this.apiBaseUrl}/api/v1/external-agents/report`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Ingest-Token": this.ingestToken,
          },
          body: JSON.stringify({
            channel_id: this.channelId || undefined,
            agent_key: params.agentKey,
            status: params.status,
            external_run_id: params.externalRunId,
            pipeline_kind: params.pipelineKind ?? "hsl_episode",
            run_title: params.runTitle,
            external_execution_id: params.externalExecutionId,
            stage_label: params.stageLabel,
            progress: params.progress,
            model_name: params.modelName,
            event_type: params.eventType,
            level: params.level ?? "info",
            message: params.message,
            input_summary: params.inputSummary ?? {},
            output_summary: params.outputSummary ?? {},
            artifacts: params.artifacts ?? [],
            metrics: params.metrics ?? {},
            error_code: params.errorCode,
            error_message: params.errorMessage,
            source_repo: this.sourceRepo,
            attempt: params.attempt ?? 1,
            metadata: params.metadata ?? {},
          }),
        });
        if (!res.ok && !this.failOpen) {
          throw new Error(`Central telemetry HTTP ${res.status}`);
        }
        return;
      }

      if (this.supabaseUrl && this.supabaseKey) {
        const res = await fetch(`${this.supabaseUrl}/rest/v1/rpc/ingest_external_agent_event`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            apikey: this.supabaseKey,
            Authorization: `Bearer ${this.supabaseKey}`,
          },
          body: JSON.stringify({
            p_workspace_id: this.workspaceId,
            p_channel_id: this.channelId,
            p_agent_key: params.agentKey,
            p_status: params.status,
            p_external_run_id: params.externalRunId,
            p_pipeline_kind: params.pipelineKind ?? "hsl_episode",
            p_run_title: params.runTitle ?? null,
            p_external_execution_id: params.externalExecutionId ?? null,
            p_stage_label: params.stageLabel ?? null,
            p_progress: params.progress ?? null,
            p_model_name: params.modelName ?? null,
            p_event_type: params.eventType ?? null,
            p_level: params.level ?? "info",
            p_message: params.message ?? null,
            p_input_summary: params.inputSummary ?? {},
            p_output_summary: params.outputSummary ?? {},
            p_artifacts: params.artifacts ?? [],
            p_metrics: params.metrics ?? {},
            p_error_code: params.errorCode ?? null,
            p_error_message: params.errorMessage ?? null,
            p_source_repo: this.sourceRepo,
            p_attempt: params.attempt ?? 1,
            p_metadata: params.metadata ?? {},
          }),
        });
        if (!res.ok && !this.failOpen) {
          throw new Error(`Supabase RPC HTTP ${res.status}`);
        }
      }
    } catch (err) {
      if (!this.failOpen) throw err;
    }
  }

  async track<T>(
    opts: {
      agentKey: string;
      externalRunId: string;
      pipelineKind?: ExternalPipelineKind;
      runTitle?: string;
      stageLabel?: string;
      modelName?: string;
      isGate?: boolean;
    },
    fn: () => Promise<T>
  ): Promise<T> {
    await this.report({
      agentKey: opts.agentKey,
      status: "working",
      externalRunId: opts.externalRunId,
      pipelineKind: opts.pipelineKind ?? "hsl_episode",
      runTitle: opts.runTitle,
      stageLabel: opts.stageLabel ?? "Executando",
      progress: 0.1,
      modelName: opts.modelName,
    });
    try {
      const result = await fn();
      await this.report({
        agentKey: opts.agentKey,
        status: opts.isGate ? "gate_passed" : "done",
        externalRunId: opts.externalRunId,
        pipelineKind: opts.pipelineKind ?? "hsl_episode",
        runTitle: opts.runTitle,
        stageLabel: "Concluído",
        progress: 1,
        modelName: opts.modelName,
      });
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await this.report({
        agentKey: opts.agentKey,
        status: opts.isGate ? "gate_failed" : "failed",
        externalRunId: opts.externalRunId,
        pipelineKind: opts.pipelineKind ?? "hsl_episode",
        runTitle: opts.runTitle,
        stageLabel: `Erro: ${msg.slice(0, 180)}`,
        modelName: opts.modelName,
        errorCode: err instanceof Error ? err.name : "Error",
        errorMessage: msg.slice(0, 1500),
      });
      throw err;
    }
  }
}
