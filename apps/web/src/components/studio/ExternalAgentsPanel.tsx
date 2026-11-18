"use client";

import React, { useEffect, useMemo, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import type {
  ExternalAgentDetailResponse,
  ExternalAgentState,
  ExternalAgentsSnapshot,
  ExternalExecutionStatus,
  ExternalGroupKey,
  ExternalIngestToken,
} from "@/lib/studio/external-types";
import styles from "./external-agents.module.css";

interface ExternalAgentsPanelProps {
  token: string;
  workspaceId: string;
  channelId: string;
  channelName: string;
  snapshot: ExternalAgentsSnapshot | null;
  loading: boolean;
  externalInspectKey?: string | null;
  onExternalInspectHandled?: () => void;
  onRefresh: () => void;
  onNotice?: (notice: { kind: "info" | "warn" | "err"; code: string; message: string }) => void;
}

const GROUP_TABS: Array<{ key: "all" | "active_only" | ExternalGroupKey; label: string }> = [
  { key: "all", label: "Todos" },
  { key: "active_only", label: "Com atividade" },
  { key: "standalone", label: "Bots Standalone" },
  { key: "hsl_editorial", label: "HSL Editorial & RAG" },
  { key: "hsl_cinematic", label: "HSL Cinema" },
  { key: "hsl_media", label: "HSL Mídia & Frames" },
  { key: "hsl_postprod", label: "HSL Pós & Pub" },
  { key: "shorts_cutter", label: "Shorts Cutter" },
];

function statusLabelPt(status: ExternalExecutionStatus): string {
  switch (status) {
    case "working":
      return "Trabalhando";
    case "queued":
      return "Na fila";
    case "waiting_input":
      return "Aguardando entrada";
    case "waiting_approval":
      return "Aguardando você";
    case "blocked":
      return "Bloqueado";
    case "no_signal":
      return "Sem sinal";
    case "done":
      return "Finalizado";
    case "gate_passed":
      return "Gate OK";
    case "gate_failed":
      return "Gate Reprovado";
    case "failed":
      return "Falhou";
    case "skipped":
      return "Ignorado";
    case "cancelled":
      return "Cancelado";
    default:
      return "Em espera";
  }
}

function pillClass(status: ExternalExecutionStatus): string {
  switch (status) {
    case "working":
      return styles.pillWork;
    case "done":
    case "gate_passed":
      return styles.pillOk;
    case "failed":
    case "gate_failed":
    case "blocked":
    case "no_signal":
      return styles.pillErr;
    case "queued":
    case "waiting_input":
    case "waiting_approval":
      return styles.pillInfo;
    default:
      return styles.pillIdle;
  }
}

function dotClass(status: ExternalExecutionStatus): string {
  switch (status) {
    case "working":
      return styles.dotWork;
    case "done":
    case "gate_passed":
      return styles.dotOk;
    case "failed":
    case "gate_failed":
    case "blocked":
    case "no_signal":
      return styles.dotErr;
    case "queued":
    case "waiting_input":
    case "waiting_approval":
      return styles.dotInfo;
    default:
      return styles.dotIdle;
  }
}

function formatDuration(ms: number | null | undefined): string | null {
  if (ms === null || ms === undefined) return null;
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const min = Math.floor(sec / 60);
  const rem = Math.round(sec % 60);
  return `${min}m ${rem}s`;
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function ExternalAgentsPanel({
  token,
  workspaceId,
  channelId,
  channelName,
  snapshot,
  loading,
  externalInspectKey,
  onExternalInspectHandled,
  onRefresh,
  onNotice,
}: ExternalAgentsPanelProps) {
  const [groupFilter, setGroupFilter] = useState<"all" | "active_only" | ExternalGroupKey>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Agent inspection modal
  const [inspectKey, setInspectKey] = useState<string | null>(null);
  const [agentDetail, setAgentDetail] = useState<ExternalAgentDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Connect external project modal
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [tokensList, setTokensList] = useState<ExternalIngestToken[]>([]);
  const [tokensLoading, setTokensLoading] = useState(false);
  const [newTokenLabel, setNewTokenLabel] = useState("Pipeline O Outro Lado");
  const [createdPlainToken, setCreatedPlainToken] = useState<string | null>(null);
  const [snippetTab, setSnippetTab] = useState<"python" | "typescript" | "supabase">("python");

  const agents = snapshot?.agents ?? [];
  const summary = snapshot?.summary ?? {
    total: agents.length,
    working: 0,
    queued: 0,
    waiting_human: 0,
    done: 0,
    failed: 0,
    idle: agents.length,
  };

  const workingNow = useMemo(() => agents.filter((a) => a.status === "working"), [agents]);

  const filteredAgents = useMemo(() => {
    const q = search.trim().toLowerCase();
    return agents.filter((ag) => {
      if (selectedRunId && ag.pipeline_run_id !== selectedRunId) {
        return false;
      }
      if (groupFilter === "active_only") {
        if (ag.status === "idle") return false;
      } else if (groupFilter !== "all" && ag.group_key !== groupFilter) {
        return false;
      }
      if (statusFilter === "working" && ag.status !== "working") return false;
      if (statusFilter === "done" && ag.status !== "done" && ag.status !== "gate_passed") return false;
      if (
        statusFilter === "failed" &&
        !["failed", "gate_failed", "blocked", "no_signal"].includes(ag.status)
      ) {
        return false;
      }
      if (statusFilter === "non_idle" && ag.status === "idle") return false;
      if (q) {
        const hay = `${ag.agent_key} ${ag.display_name} ${ag.sub_group} ${ag.stage_label ?? ""} ${ag.source_path}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [agents, groupFilter, statusFilter, search, selectedRunId]);

  const groupedAgents = useMemo(() => {
    const map = new Map<string, ExternalAgentState[]>();
    for (const ag of filteredAgents) {
      const list = map.get(ag.sub_group) ?? [];
      list.push(ag);
      map.set(ag.sub_group, list);
    }
    return Array.from(map.entries());
  }, [filteredAgents]);

  const openAgentDetail = async (agentKey: string) => {
    setInspectKey(agentKey);
    setAgentDetail(null);
    setDetailLoading(true);
    try {
      const res = await api.getExternalAgentDetail(token, workspaceId, channelId, agentKey);
      setAgentDetail(res);
    } catch (err) {
      onNotice?.({
        kind: "err",
        code: "EXT_DETAIL_ERR",
        message: err instanceof Error ? err.message : "Falha ao carregar detalhes do agente externo.",
      });
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!externalInspectKey) return;
    void openAgentDetail(externalInspectKey);
    onExternalInspectHandled?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalInspectKey]);

  const openConnectModal = async () => {
    setShowConnectModal(true);
    setCreatedPlainToken(null);
    setTokensLoading(true);
    try {
      const res = await api.listExternalIngestTokens(token, workspaceId, channelId);
      setTokensList(res.tokens);
    } catch (err) {
      onNotice?.({
        kind: "err",
        code: "EXT_TOKENS_ERR",
        message: err instanceof Error ? err.message : "Falha ao listar tokens de ingestão.",
      });
    } finally {
      setTokensLoading(false);
    }
  };

  const handleCreateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTokenLabel.trim()) return;
    try {
      const res = await api.createExternalIngestToken(token, workspaceId, channelId, newTokenLabel.trim());
      setCreatedPlainToken(res.token.token ?? null);
      setTokensList((prev) => [res.token, ...prev]);
      onNotice?.({
        kind: "info",
        code: "EXT_TOKEN_CREATED",
        message: "Token de ingestão criado. Copie e salve no projeto separado.",
      });
    } catch (err) {
      onNotice?.({
        kind: "err",
        code: "EXT_TOKEN_ERR",
        message: err instanceof Error ? err.message : "Erro ao gerar token.",
      });
    }
  };

  const handleRevokeToken = async (tokenId: string) => {
    try {
      await api.revokeExternalIngestToken(token, workspaceId, tokenId);
      setTokensList((prev) =>
        prev.map((t) => (t.id === tokenId ? { ...t, revoked_at: new Date().toISOString() } : t))
      );
    } catch (err) {
      onNotice?.({
        kind: "err",
        code: "EXT_TOKEN_REVOKE_ERR",
        message: err instanceof Error ? err.message : "Erro ao revogar token.",
      });
    }
  };

  const copyText = (txt: string, label: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(txt);
      onNotice?.({ kind: "info", code: "COPIED", message: `${label} copiado para a área de transferência.` });
    }
  };

  const sampleToken = createdPlainToken ?? "<SEU_X_INGEST_TOKEN>";

  const pythonSnippet = `import httpx

CENTRAL_API = "${API_BASE}/api/v1/external-agents/report"
INGEST_TOKEN = "${sampleToken}"
CHANNEL_ID = "${channelId}"

def report_agent(agent_key: str, status: str, *, run_id: str, stage: str = "", progress: float | None = None, model: str | None = None, metrics: dict | None = None):
    httpx.post(
        CENTRAL_API,
        headers={"X-Ingest-Token": INGEST_TOKEN},
        json={
            "channel_id": CHANNEL_ID,
            "agent_key": agent_key,          # ex: "firefly-worker", "agent_04_moment_miner", "NarrationVoiceAgent"
            "status": status,                # queued | working | done | gate_passed | gate_failed | failed
            "external_run_id": run_id,       # ex: "ep-2026-11-17-01"
            "pipeline_kind": "hsl_episode",  # hsl_episode | shorts_cutter | standalone_bot | firefly_batch
            "stage_label": stage,
            "progress": progress,
            "model_name": model,
            "metrics": metrics or {},
        },
        timeout=5.0,
    ).raise_for_status()`;

  const tsSnippet = `const CENTRAL_API = "${API_BASE}/api/v1/external-agents/report";
const INGEST_TOKEN = "${sampleToken}";
const CHANNEL_ID = "${channelId}";

export async function reportExternalAgent(params: {
  agentKey: string;
  status: "queued" | "working" | "done" | "gate_passed" | "gate_failed" | "failed";
  runId: string;
  pipelineKind?: "hsl_episode" | "shorts_cutter" | "standalone_bot" | "audio_factory";
  stageLabel?: string;
  progress?: number;
  modelName?: string;
  metrics?: Record<string, unknown>;
}) {
  await fetch(CENTRAL_API, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Ingest-Token": INGEST_TOKEN },
    body: JSON.stringify({
      channel_id: CHANNEL_ID,
      agent_key: params.agentKey,
      status: params.status,
      external_run_id: params.runId,
      pipeline_kind: params.pipelineKind ?? "hsl_episode",
      stage_label: params.stageLabel,
      progress: params.progress,
      model_name: params.modelName,
      metrics: params.metrics ?? {},
    }),
  });
}`;

  const supabaseRpcSnippet = `-- Chamada direta no Supabase Postgres (via service_role RPC):
SELECT public.ingest_external_agent_event(
  p_workspace_id    => '${workspaceId}'::uuid,
  p_channel_id      => '${channelId}'::uuid,
  p_agent_key       => 'NarrationVoiceAgent',
  p_status          => 'working',
  p_external_run_id => 'ep-2026-11-17-001',
  p_pipeline_kind   => 'hsl_episode',
  p_run_title       => 'Episodio #42 - O Outro Lado',
  p_stage_label     => 'Sintetizando voz ElevenLabs Chris (-16 LUFS)',
  p_progress        => 0.45,
  p_model_name      => 'ElevenLabs Chris'
);`;

  return (
    <section className={styles.wrapper} aria-labelledby="ext-agents-title">
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <span className={styles.eyebrow}>Observabilidade em Tempo Real · Projeto Separado</span>
          <h2 id="ext-agents-title" className={styles.title}>
            Central de Agentes Externos ({summary.total} agentes, bots &amp; gates)
          </h2>
          <p className={styles.subtitle}>
            Canal <strong>{channelName}</strong> · Mostra exatamente qual agente está trabalhando agora, quem já finalizou, gates aprovados/reprovados e logs ao vivo.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button type="button" className="btn studio-btn-sm" onClick={openConnectModal}>
            Conectar projeto separado (Token &amp; SDK)
          </button>
          <button type="button" className="btn studio-btn-sm" onClick={onRefresh} disabled={loading}>
            {loading ? "Atualizando…" : "Atualizar agentes"}
          </button>
        </div>
      </header>

      {/* Summary KPIs */}
      <div className={styles.summaryBar}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>
            <span className={`${styles.dot} ${workingNow.length > 0 ? styles.dotWork : styles.dotIdle}`} />
            Trabalhando agora
          </span>
          <span className={styles.statValue}>{summary.working}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>
            <span className={`${styles.dot} ${styles.dotOk}`} />
            Finalizados / Gate OK
          </span>
          <span className={styles.statValue}>{summary.done}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>
            <span className={`${styles.dot} ${styles.dotInfo}`} />
            Na fila / Aguardando
          </span>
          <span className={styles.statValue}>{summary.queued + summary.waiting_human}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>
            <span className={`${styles.dot} ${styles.dotErr}`} />
            Falhas / Gates Reprovados
          </span>
          <span className={styles.statValue}>{summary.failed}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>
            <span className={`${styles.dot} ${styles.dotIdle}`} />
            Em espera (idle)
          </span>
          <span className={styles.statValue}>{summary.idle}</span>
        </div>
      </div>

      {/* Highlight banner for agents currently working */}
      {workingNow.length > 0 && (
        <div className={styles.workingBanner} role="region" aria-label="Agentes trabalhando agora">
          <div className={styles.workingBannerTitle}>
            <span className={`${styles.dot} ${styles.dotWork}`} />
            {workingNow.length} agente(s) trabalhando agora neste canal
          </div>
          <div className={styles.workingGrid}>
            {workingNow.map((ag) => (
              <button
                key={ag.agent_key}
                type="button"
                className={styles.workingCard}
                onClick={() => void openAgentDetail(ag.agent_key)}
              >
                <div className={styles.agentCardTop}>
                  <span className={styles.agentName}>{ag.display_name}</span>
                  <span className={`${styles.statusPill} ${styles.pillWork}`}>
                    {typeof ag.progress === "number" ? `${Math.round(ag.progress * 100)}%` : "Ativo"}
                  </span>
                </div>
                <span className={styles.stageText}>{ag.stage_label ?? "Executando tarefa…"}</span>
                <div className={styles.agentMeta}>
                  <span>{ag.sub_group}</span>
                  {ag.model_name && <span>· {ag.model_name}</span>}
                  {ag.external_run_id && <span>· Run: {ag.external_run_id}</span>}
                </div>
                {typeof ag.progress === "number" && (
                  <div className={styles.progressTrack}>
                    <div
                      className={styles.progressFill}
                      style={{ width: `${Math.round(Math.max(0, Math.min(1, ag.progress)) * 100)}%` }}
                    />
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filter Tabs & Search */}
      <div className={styles.controlsRow}>
        <div className={styles.tabs} role="tablist" aria-label="Filtrar por squad">
          {GROUP_TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={groupFilter === t.key}
              className={`${styles.tabBtn} ${groupFilter === t.key ? styles.tabBtnActive : ""}`}
              onClick={() => setGroupFilter(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className={styles.filters}>
          <select
            aria-label="Filtrar por status"
            className={styles.selectInput}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Todos os status</option>
            <option value="non_idle">Somente com execução</option>
            <option value="working">Trabalhando agora</option>
            <option value="done">Finalizados / Gate OK</option>
            <option value="failed">Falhas / Bloqueados</option>
          </select>

          <input
            type="search"
            aria-label="Buscar agente externo"
            className={styles.searchInput}
            placeholder="Buscar agente, gate ou bot…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Main Split: Agent Matrix + Right Sidebar (Runs + Live Event Stream) */}
      <div className={styles.mainSplit}>
        <div className={styles.groupsList}>
          {groupedAgents.length === 0 ? (
            <div className={styles.groupBox}>
              <p className="muted" style={{ margin: 0 }}>
                Nenhum agente encontrado para os filtros selecionados.
              </p>
            </div>
          ) : (
            groupedAgents.map(([subGroup, items]) => {
              const workingCnt = items.filter((i) => i.status === "working").length;
              const doneCnt = items.filter((i) => i.status === "done" || i.status === "gate_passed").length;
              const failCnt = items.filter((i) =>
                ["failed", "gate_failed", "blocked", "no_signal"].includes(i.status)
              ).length;
              return (
                <div key={subGroup} className={styles.groupBox}>
                  <div className={styles.groupHeader}>
                    <h3 className={styles.groupTitle}>
                      {subGroup} ({items.length})
                    </h3>
                    <div className={styles.groupCounts}>
                      {workingCnt > 0 && <span style={{ color: "#fbbf24" }}>{workingCnt} ativo(s)</span>}
                      {doneCnt > 0 && <span style={{ color: "#4ade80" }}>{doneCnt} pronto(s)</span>}
                      {failCnt > 0 && <span style={{ color: "#f87171" }}>{failCnt} falha(s)</span>}
                    </div>
                  </div>

                  <div className={styles.agentGrid}>
                    {items.map((ag) => {
                      const dur = formatDuration(ag.duration_ms);
                      const cardCls = [
                        styles.agentCard,
                        ag.status === "working" ? styles.agentCardWorking : "",
                        ag.status === "done" || ag.status === "gate_passed" ? styles.agentCardDone : "",
                        ["failed", "gate_failed", "blocked", "no_signal"].includes(ag.status)
                          ? styles.agentCardFailed
                          : "",
                      ]
                        .filter(Boolean)
                        .join(" ");

                      return (
                        <button
                          key={ag.agent_key}
                          type="button"
                          className={cardCls}
                          onClick={() => void openAgentDetail(ag.agent_key)}
                        >
                          <div className={styles.agentCardTop}>
                            <span className={styles.agentName}>{ag.display_name}</span>
                            <span className={`${styles.statusPill} ${pillClass(ag.status)}`}>
                              <span className={`${styles.dot} ${dotClass(ag.status)}`} />
                              {statusLabelPt(ag.status)}
                            </span>
                          </div>

                          <div className={styles.agentMeta}>
                            <span className={styles.kindTag}>{ag.agent_kind}</span>
                            <span className={styles.kindTag}>{ag.runtime_lang === "python" ? "PY" : "TS"}</span>
                            {ag.model_name && <span>{ag.model_name}</span>}
                            {dur && <span>· {dur}</span>}
                          </div>

                          {ag.stage_label ? (
                            <span className={styles.stageText} title={ag.stage_label}>
                              {ag.stage_label}
                            </span>
                          ) : (
                            <span className={styles.stageText} style={{ color: "#64748b" }}>
                              {ag.source_path}
                            </span>
                          )}

                          {ag.status === "working" && typeof ag.progress === "number" && (
                            <div className={styles.progressTrack}>
                              <div
                                className={styles.progressFill}
                                style={{ width: `${Math.round(Math.max(0, Math.min(1, ag.progress)) * 100)}%` }}
                              />
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Sidebar: Pipeline Runs & Real-time Events */}
        <aside className={styles.sidebarCol} aria-label="Execuções de pipeline e logs ao vivo">
          <div className={styles.sideBox}>
            <div className={styles.sideTitle}>
              <span>Pipelines / Batches recentes</span>
              {selectedRunId && (
                <button
                  type="button"
                  className="btn studio-btn-sm"
                  onClick={() => setSelectedRunId(null)}
                >
                  Limpar filtro
                </button>
              )}
            </div>
            {!snapshot || snapshot.pipeline_runs.length === 0 ? (
              <p className="muted-tiny" style={{ margin: 0 }}>
                Nenhum run externo recebido ainda para este canal. Clique em &quot;Conectar projeto separado&quot; para enviar eventos.
              </p>
            ) : (
              <div className={styles.runsList}>
                {snapshot.pipeline_runs.map((run) => (
                  <button
                    key={run.id}
                    type="button"
                    className={`${styles.runItem} ${selectedRunId === run.id ? styles.runItemActive : ""}`}
                    onClick={() => setSelectedRunId((cur) => (cur === run.id ? null : run.id))}
                  >
                    <div className={styles.agentCardTop}>
                      <strong style={{ fontSize: 12 }}>{run.title}</strong>
                      <span className={`${styles.statusPill} ${run.status === "running" ? styles.pillWork : run.status === "completed" ? styles.pillOk : run.status === "failed" ? styles.pillErr : styles.pillInfo}`}>
                        {run.status}
                      </span>
                    </div>
                    <div className={styles.agentMeta}>
                      <span>{run.pipeline_kind}</span>
                      <span>· {run.completed_agents} concluídos</span>
                      {run.failed_agents > 0 && (
                        <span style={{ color: "#f87171" }}>· {run.failed_agents} falha(s)</span>
                      )}
                    </div>
                    {run.current_agent_key && (
                      <div className="muted-tiny">Atual: {run.current_agent_key}</div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className={styles.sideBox}>
            <div className={styles.sideTitle}>
              <span>Log em tempo real ({snapshot?.recent_events.length ?? 0})</span>
            </div>
            {!snapshot || snapshot.recent_events.length === 0 ? (
              <p className="muted-tiny" style={{ margin: 0 }}>
                Aguardando eventos dos agentes externos…
              </p>
            ) : (
              <div className={styles.eventFeed}>
                {snapshot.recent_events
                  .slice()
                  .reverse()
                  .slice(0, 40)
                  .map((evt) => (
                    <div key={evt.id} className={styles.eventRow}>
                      <div className={styles.eventTop}>
                        <span className={styles.eventAgent}>{evt.agent_key}</span>
                        <span>{formatTime(evt.created_at)}</span>
                      </div>
                      <span style={{ color: evt.level === "error" ? "#f87171" : "#e2e8f0" }}>
                        {evt.message}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </aside>
      </div>

      {/* Modal de Inspecao de Agente Externo */}
      {inspectKey && (
        <div className="studio-drawer-backdrop" onClick={() => setInspectKey(null)}>
          <div
            className="studio-modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Detalhes do agente ${inspectKey}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="studio-drawer-head">
              <div>
                <div className="studio-hud-eyebrow">Agente Externo · {inspectKey}</div>
                <h2 style={{ margin: 0 }}>{agentDetail?.agent.display_name ?? inspectKey}</h2>
              </div>
              <button type="button" className="btn" onClick={() => setInspectKey(null)}>
                Fechar
              </button>
            </div>

            {detailLoading || !agentDetail ? (
              <p className="muted">Carregando histórico e métricas…</p>
            ) : (
              <div className="studio-drawer-body">
                <p className="muted" style={{ marginTop: 0 }}>
                  {agentDetail.agent.description}
                </p>

                <section className="studio-drawer-box">
                  <div className="studio-drawer-item-top">
                    <strong>Estado Atual</strong>
                    <span className={`${styles.statusPill} ${pillClass(agentDetail.agent.status)}`}>
                      {statusLabelPt(agentDetail.agent.status)}
                    </span>
                  </div>
                  <div className="muted-tiny" style={{ marginTop: 6 }}>
                    Origem: <code>{agentDetail.agent.source_path}</code> · Sala 3D:{" "}
                    <strong>{agentDetail.agent.studio_room_key}</strong>
                  </div>
                  <div className="muted-tiny" style={{ marginTop: 4 }}>
                    Etapa atual: <strong>{agentDetail.agent.stage_label ?? "em espera"}</strong> · Modelo:{" "}
                    <strong>{agentDetail.agent.model_name ?? "—"}</strong> · Duração:{" "}
                    <strong>{formatDuration(agentDetail.agent.duration_ms) ?? "—"}</strong>
                  </div>
                  {agentDetail.agent.error_message && (
                    <div className="studio-hud-warning" style={{ marginTop: 8 }}>
                      Erro ({agentDetail.agent.error_code ?? "ERR"}): {agentDetail.agent.error_message}
                    </div>
                  )}
                </section>

                {agentDetail.executions.length > 0 && (
                  <section className="studio-drawer-box">
                    <strong>Execuções recentes ({agentDetail.executions.length})</strong>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                      {agentDetail.executions.slice(0, 6).map((ex) => (
                        <div key={ex.id} className="studio-drawer-item">
                          <div className="studio-drawer-item-top">
                            <span style={{ fontSize: 12, fontWeight: 600 }}>
                              {ex.pipeline_title ?? ex.external_execution_id}
                            </span>
                            <span className={`${styles.statusPill} ${pillClass(ex.status)}`}>
                              {statusLabelPt(ex.status)}
                            </span>
                          </div>
                          <div className="muted-tiny">
                            {ex.stage_label ?? "—"} · {formatDuration(ex.duration_ms) ?? "em curso"} ·{" "}
                            {formatTime(ex.updated_at)}
                          </div>
                          {ex.metrics && Object.keys(ex.metrics).length > 0 && (
                            <pre className={styles.codeBox} style={{ marginTop: 4 }}>
                              {JSON.stringify(ex.metrics, null, 2)}
                            </pre>
                          )}
                          {ex.artifacts && ex.artifacts.length > 0 && (
                            <pre className={styles.codeBox} style={{ marginTop: 4 }}>
                              {JSON.stringify(ex.artifacts, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                {agentDetail.events.length > 0 && (
                  <section className="studio-drawer-box">
                    <strong>Eventos deste agente ({agentDetail.events.length})</strong>
                    <div className={styles.eventFeed} style={{ marginTop: 8, maxHeight: 200 }}>
                      {agentDetail.events.map((ev) => (
                        <div key={ev.id} className={styles.eventRow}>
                          <div className={styles.eventTop}>
                            <span>{ev.event_type}</span>
                            <span>{formatTime(ev.created_at)}</span>
                          </div>
                          <span>{ev.message}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal Conectar Projeto Separado */}
      {showConnectModal && (
        <div className="studio-drawer-backdrop" onClick={() => setShowConnectModal(false)}>
          <div
            className="studio-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Conectar projeto separado"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="studio-drawer-head">
              <div>
                <div className="studio-hud-eyebrow">Integração Externa</div>
                <h2 style={{ margin: 0 }}>Conectar Projeto Separado ao Agente Central</h2>
              </div>
              <button type="button" className="btn" onClick={() => setShowConnectModal(false)}>
                Fechar
              </button>
            </div>

            <div className="studio-drawer-body">
              <section className="studio-drawer-box">
                <strong>Identificadores deste Canal</strong>
                <div className="muted-tiny" style={{ marginTop: 6 }}>
                  Workspace ID: <code>{workspaceId}</code>{" "}
                  <button type="button" className="btn studio-btn-sm" onClick={() => copyText(workspaceId, "Workspace ID")}>
                    Copiar
                  </button>
                </div>
                <div className="muted-tiny" style={{ marginTop: 6 }}>
                  Channel ID ({channelName}): <code>{channelId}</code>{" "}
                  <button type="button" className="btn studio-btn-sm" onClick={() => copyText(channelId, "Channel ID")}>
                    Copiar
                  </button>
                </div>
              </section>

              <section className="studio-drawer-box">
                <strong>Gerar Token de Ingestão (X-Ingest-Token)</strong>
                <form onSubmit={handleCreateToken} style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                  <input
                    className="input"
                    style={{ flex: 1, minWidth: 180 }}
                    value={newTokenLabel}
                    onChange={(e) => setNewTokenLabel(e.target.value)}
                    placeholder="Nome da integração (ex: HSL + Shorts PC)"
                  />
                  <button type="submit" className="btn primary studio-btn-sm">
                    Gerar Token
                  </button>
                </form>

                {createdPlainToken && (
                  <div className="studio-hud-warning" style={{ marginTop: 8 }}>
                    <div>
                      <strong>Copie agora (não será exibido novamente):</strong>
                    </div>
                    <code style={{ wordBreak: "break-all" }}>{createdPlainToken}</code>{" "}
                    <button
                      type="button"
                      className="btn studio-btn-sm"
                      onClick={() => copyText(createdPlainToken, "Token")}
                    >
                      Copiar token
                    </button>
                  </div>
                )}

                {tokensLoading ? (
                  <p className="muted-tiny">Carregando tokens…</p>
                ) : (
                  tokensList.length > 0 && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                      {tokensList.map((t) => (
                        <div key={t.id} className="studio-drawer-item">
                          <div className="studio-drawer-item-top">
                            <span style={{ fontSize: 12 }}>
                              <strong>{t.label}</strong> (<code>{t.token_prefix}…</code>)
                            </span>
                            {t.revoked_at ? (
                              <span className="muted-tiny">Revogado</span>
                            ) : (
                              <button
                                type="button"
                                className="btn studio-btn-sm"
                                onClick={() => void handleRevokeToken(t.id)}
                              >
                                Revogar
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )
                )}
              </section>

              <section className="studio-drawer-box">
                <div className="studio-drawer-item-top">
                  <strong>Código pronto para colar no projeto separado</strong>
                  <div className={styles.tabs}>
                    <button
                      type="button"
                      className={`${styles.tabBtn} ${snippetTab === "python" ? styles.tabBtnActive : ""}`}
                      onClick={() => setSnippetTab("python")}
                    >
                      Python
                    </button>
                    <button
                      type="button"
                      className={`${styles.tabBtn} ${snippetTab === "typescript" ? styles.tabBtnActive : ""}`}
                      onClick={() => setSnippetTab("typescript")}
                    >
                      TypeScript
                    </button>
                    <button
                      type="button"
                      className={`${styles.tabBtn} ${snippetTab === "supabase" ? styles.tabBtnActive : ""}`}
                      onClick={() => setSnippetTab("supabase")}
                    >
                      SQL / Supabase RPC
                    </button>
                  </div>
                </div>
                <pre className={styles.codeBox} style={{ marginTop: 8 }}>
                  {snippetTab === "python"
                    ? pythonSnippet
                    : snippetTab === "typescript"
                      ? tsSnippet
                      : supabaseRpcSnippet}
                </pre>
              </section>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
