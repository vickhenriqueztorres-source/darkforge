"use client";

import React, { useState } from "react";
import { getStatusLabelPt, PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type {
  AgentKey,
  AgentOutput,
  ChannelMetricsPanel,
  ContentItemPipeline,
  StudioAgentState,
  StudioChannelInfo,
  StudioEvent,
} from "@/lib/studio/types";

function formatCompactNumber(val: number | null, unit: string): string {
  if (val === null || Number.isNaN(val)) return "indisponível";
  if (unit === "percent") {
    return `${val.toFixed(1).replace(".", ",")}%`;
  }
  if (unit === "seconds") {
    const mins = Math.floor(val / 60);
    const secs = Math.round(val % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  }
  if (val >= 1_000_000) {
    return `${(val / 1_000_000).toFixed(2).replace(".", ",")} mi`;
  }
  if (val >= 1_000) {
    return `${(val / 1_000).toFixed(1).replace(".", ",")} mil`;
  }
  return String(Math.round(val));
}

function formatRelativeAge(iso: string | null): string {
  if (!iso) return "sem sync";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "data desconhecida";
  const diffMin = Math.max(0, Math.round((Date.now() - dt.getTime()) / 60000));
  if (diffMin < 1) return "atualizado agora";
  if (diffMin < 60) return `atualizado há ${diffMin}m`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 48) return `atualizado há ${diffH}h`;
  const diffD = Math.round(diffH / 24);
  return `atualizado há ${diffD}d`;
}

interface ChannelPanelProps {
  channel: StudioChannelInfo;
  metrics: ChannelMetricsPanel;
  syncing: boolean;
  onSyncChannel: () => void;
}

export function StudioChannelPanel({
  channel,
  metrics,
  syncing,
  onSyncChannel,
}: ChannelPanelProps) {
  const series = metrics.series ?? [];
  const maxVal = series.length > 0 ? Math.max(...series.map((p) => p.value), 1) : 1;
  const minVal = series.length > 0 ? Math.min(...series.map((p) => p.value), 0) : 0;
  const span = Math.max(1, maxVal - minVal);

  const svgPoints =
    series.length > 1
      ? series
          .map((p, i) => {
            const x = (i / (series.length - 1)) * 280;
            const y = 32 - ((p.value - minVal) / span) * 24;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join(" ")
      : "";

  const areaPoints = svgPoints ? `0,36 ${svgPoints} 280,36` : "";

  return (
    <section className="studio-hud-panel holo-left" aria-label="Métricas do canal">
      <div className="studio-hud-header">
        <div className="studio-hud-title-group">
          <span className="studio-yt-badge" aria-hidden="true">▶</span>
          <div>
            <div className="studio-hud-title">Canal Principal</div>
            <h2 className="studio-hud-sub">{channel.display_name}</h2>
          </div>
        </div>
        <button
          type="button"
          className={`studio-freshness-btn ${metrics.stale ? "is-stale" : ""}`}
          onClick={onSyncChannel}
          disabled={syncing}
          title={
            metrics.stale
              ? "Dados desatualizados (stale) — clique para sincronizar"
              : "Sincronizar analytics (SP-03)"
          }
        >
          <span>
            {syncing
              ? "Sincronizando…"
              : metrics.stale
                ? `${formatRelativeAge(metrics.fetched_at)} • stale`
                : formatRelativeAge(metrics.fetched_at)}
          </span>
          <span aria-hidden="true">↻</span>
        </button>
      </div>

      <div className="studio-kpi-row">
        {metrics.cards.map((card) => {
          const isAvailable = card.availability === "available" && card.value !== null;
          return (
            <div key={card.key} className="studio-kpi-cell">
              <div className="studio-kpi-label">{card.label}</div>
              <div className={`studio-kpi-num ${!isAvailable ? "is-unknown" : ""}`}>
                {isAvailable ? formatCompactNumber(card.value, card.unit) : "indisponível"}
              </div>
              <div className="studio-kpi-sub">
                {card.delta_pct !== null && card.delta_pct !== undefined ? (
                  <span className={card.delta_pct >= 0 ? "delta-up" : "delta-down"}>
                    {card.delta_pct >= 0 ? "↑" : "↓"} {Math.abs(card.delta_pct).toFixed(1)}%
                  </span>
                ) : (
                  <span className="muted-tiny">
                    {card.availability === "unknown" ? "unknown" : card.availability}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="studio-sparkline-box" aria-label="Série de visualizações do período">
        <svg viewBox="0 0 280 36" className="studio-sparkline-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient id="sparkAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(245, 158, 11, 0.38)" />
              <stop offset="100%" stopColor="rgba(245, 158, 11, 0.0)" />
            </linearGradient>
          </defs>
          <line x1="0" y1="34" x2="280" y2="34" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
          {series.length > 1 ? (
            <>
              <polygon points={areaPoints} fill="url(#sparkAreaGrad)" />
              <polyline
                fill="none"
                stroke="#f59e0b"
                strokeWidth="2.2"
                points={svgPoints}
              />
            </>
          ) : (
            <line
              x1="0"
              y1="26"
              x2="280"
              y2="26"
              stroke="rgba(245, 158, 11, 0.28)"
              strokeDasharray="4 4"
              strokeWidth="1.5"
            />
          )}
        </svg>
        {series.length <= 1 && (
          <span className="studio-sparkline-caption muted-tiny">
            {metrics.stale ? "Dados stale — clique em atualizar" : "Série temporal ainda não sincronizada"}
          </span>
        )}
      </div>
    </section>
  );
}

interface OpportunityPanelProps {
  opportunity: AgentOutput | null;
  activeItem: ContentItemPipeline | null;
  busy: boolean;
  onGenerateOpportunity: () => void;
  onApproveOpportunity: (output: AgentOutput, decision: "approved" | "rejected" | "changes_requested") => void;
}

export function StudioOpportunityPanel({
  opportunity,
  activeItem,
  busy,
  onGenerateOpportunity,
  onApproveOpportunity,
}: OpportunityPanelProps) {
  const [showWhy, setShowWhy] = useState(false);

  const content = (opportunity?.content ?? {}) as Record<string, unknown>;
  const scoreObj = (content.score ?? null) as {
    value?: number;
    max?: number;
    version?: string;
    components?: { key: string; value: number }[];
  } | null;
  const labelsObj = (content.labels ?? null) as { potencial?: string; concorrencia?: string } | null;
  const evidenceArr = (content.evidence ?? []) as { text: string; source_id: string }[];
  const limitationsArr = (content.limitations ?? []) as string[];
  const confidenceStr = typeof content.confidence === "string" ? content.confidence : null;

  const scoreVal = typeof scoreObj?.value === "number" ? scoreObj.value : null;
  const scoreMax = typeof scoreObj?.max === "number" && scoreObj.max > 0 ? scoreObj.max : 100;
  const pct = scoreVal !== null ? Math.max(0, Math.min(1, scoreVal / scoreMax)) : 0;
  const circumference = 2 * Math.PI * 28;
  const strokeDashoffset = circumference * (1 - pct);

  return (
    <section className="studio-hud-panel holo-center" aria-label="Oportunidade de Vídeo">
      <div className="studio-hud-header">
        <div className="studio-hud-title-group">
          <span className="studio-hud-icon" aria-hidden="true">🎯</span>
          <h2 className="studio-hud-title">Oportunidade de Vídeo</h2>
        </div>
        {opportunity ? (
          <span className={`studio-pill-sm status-${opportunity.status}`}>
            {opportunity.status === "approved"
              ? "Aprovada"
              : opportunity.status === "rejected"
                ? "Rejeitada"
                : opportunity.status === "needs_review"
                  ? "Revisar"
                  : "Aguardando"}
          </span>
        ) : (
          <button
            type="button"
            className="btn primary studio-btn-xs"
            onClick={onGenerateOpportunity}
            disabled={busy}
          >
            {busy ? "Gerando…" : "Gerar oportunidade"}
          </button>
        )}
      </div>

      <div className="studio-opp-body">
        <div
          className="studio-score-ring-wrap"
          aria-label={`Score ${scoreVal ?? "indisponível"} de ${scoreMax}`}
        >
          <svg viewBox="0 0 68 68" className="studio-score-svg">
            <circle cx="34" cy="34" r="28" className="studio-ring-track" />
            {scoreVal !== null && (
              <circle
                cx="34"
                cy="34"
                r="28"
                className="studio-ring-fill"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
              />
            )}
          </svg>
          <div className="studio-score-center">
            <strong>{scoreVal !== null ? scoreVal : "—"}</strong>
            <span>/{scoreMax}</span>
          </div>
        </div>

        <div className="studio-opp-meta">
          <div className="studio-opp-row">
            <span>Potencial:</span>
            <strong className={labelsObj?.potencial ? "tone-ok-txt" : "muted-tiny"}>
              {labelsObj?.potencial ? labelsObj.potencial.toUpperCase() : "UNKNOWN"}
            </strong>
          </div>
          <div className="studio-opp-row">
            <span>Concorrência:</span>
            <strong className={labelsObj?.concorrencia ? "" : "muted-tiny"}>
              {labelsObj?.concorrencia ? labelsObj.concorrencia.toUpperCase() : "UNKNOWN"}
            </strong>
          </div>
          <div className="studio-opp-row">
            <span>Confiança:</span>
            <strong className={confidenceStr ? "tone-warn-txt" : "muted-tiny"}>
              {confidenceStr ? confidenceStr.toUpperCase() : "UNKNOWN"}
            </strong>
          </div>
          {opportunity ? (
            <div className="studio-opp-inline-links">
              <button
                type="button"
                className="studio-link-btn"
                aria-expanded={showWhy}
                onClick={() => setShowWhy((v) => !v)}
              >
                {showWhy ? "Ocultar evidências" : "Por quê?"}
              </button>
              {opportunity.status !== "approved" && opportunity.status !== "rejected" && (
                <>
                  <button
                    type="button"
                    className="studio-link-btn tone-ok-txt"
                    disabled={busy}
                    onClick={() => onApproveOpportunity(opportunity, "approved")}
                  >
                    Aprovar
                  </button>
                  <button
                    type="button"
                    className="studio-link-btn"
                    disabled={busy}
                    onClick={() => onApproveOpportunity(opportunity, "rejected")}
                  >
                    Rejeitar
                  </button>
                </>
              )}
            </div>
          ) : (
            <span className="muted-tiny">
              {activeItem
                ? `Aguardando análise para "${activeItem.working_title}"`
                : "Execute Pesquisa + Dados"}
            </span>
          )}
        </div>
      </div>

      {showWhy && opportunity && (
        <div className="studio-why-box">
          <div className="studio-why-topic">{String(content.topic ?? "")}</div>
          {evidenceArr.length > 0 && (
            <ul className="studio-why-list">
              {evidenceArr.map((ev, i) => (
                <li key={i}>
                  {ev.text} <span className="muted-tiny">({ev.source_id.slice(0, 8)})</span>
                </li>
              ))}
            </ul>
          )}
          {limitationsArr.length > 0 && (
            <div className="studio-why-limits">
              <strong>Limitações:</strong> {limitationsArr.join(" • ")}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

interface ActivityPanelProps {
  agents: StudioAgentState[];
  latestEventByAgent: Record<string, StudioEvent>;
  activeItem: ContentItemPipeline | null;
  onSelectAgent: (agentKey: AgentKey) => void;
}

function dotToneForAgent(status: StudioAgentState["status"]): string {
  switch (status) {
    case "done":
      return "dot-ok";
    case "working":
    case "needs_review":
    case "waiting_approval":
    case "waiting_input":
      return "dot-warn";
    case "failed":
    case "blocked":
    case "no_signal":
      return "dot-err";
    default:
      return "dot-muted";
  }
}

const SHORT_AGENT_LABELS: Record<AgentKey, string> = {
  dados: "Dados",
  pesquisa: "Pesquisa",
  estrategia: "Estratégia",
  titulos: "Títulos",
  roteiro: "Roteiro",
  thumbnail: "Thumbnail",
  edicao: "Produção",
  publicacao: "Publicação",
};

export function StudioActivityPanel({
  agents,
  latestEventByAgent,
  activeItem,
  onSelectAgent,
}: ActivityPanelProps) {
  const byKey = new Map(agents.map((a) => [a.agent_key, a]));
  const ordered = PIPELINE_ORDER.map((k) => byKey.get(k)).filter(Boolean) as StudioAgentState[];

  return (
    <section className="studio-hud-panel holo-right" aria-label="Atividade dos Agentes">
      <div className="studio-hud-header">
        <div className="studio-hud-title-group">
          <span className="studio-hud-icon" aria-hidden="true">❖</span>
          <div>
            <h2 className="studio-hud-title">Atividade dos Agentes</h2>
            {activeItem && (
              <div className="studio-hud-sub">
                {activeItem.working_title} ({activeItem.stage})
              </div>
            )}
          </div>
        </div>
      </div>

      <ul className="studio-activity-list">
        {ordered.map((agent) => {
          const evt = latestEventByAgent[agent.agent_key];
          const statusTxt = getStatusLabelPt(agent.status);
          const summaryTxt = evt?.summary ?? agent.stage_label ?? statusTxt;
          const shortName = SHORT_AGENT_LABELS[agent.agent_key] ?? agent.display_name;

          return (
            <li key={agent.agent_key}>
              <button
                type="button"
                className="studio-activity-row"
                title={`${agent.display_name} (${statusTxt}): ${summaryTxt}`}
                aria-label={`${agent.display_name}: ${summaryTxt} — ${statusTxt}`}
                onClick={() => onSelectAgent(agent.agent_key)}
              >
                <span className={`studio-dot ${dotToneForAgent(agent.status)}`} aria-hidden="true" />
                <span className="studio-activity-agent">{shortName}:</span>
                <span className="studio-activity-summary">{summaryTxt}</span>
                <span className="studio-activity-status-text">{statusTxt}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
