"use client";

import React, { useEffect, useRef, useState } from "react";
import { getStatusLabelPt } from "@/lib/studio/studio-layout";
import type { AgentDetailResponse, AgentKey } from "@/lib/studio/types";

interface AgentModalProps {
  agentKey: AgentKey | null;
  detail: AgentDetailResponse | null;
  loading: boolean;
  busy: boolean;
  onClose: () => void;
  onRunNow: (agentKey: AgentKey) => void;
  onCancelRun: (runId: string) => void;
  onRetryRun: (runId: string) => void;
  onUpdateAgentConfig: (
    agentKey: AgentKey,
    patch: {
      enabled?: boolean;
      display_name?: string;
      model_policy?: { mode: string; external_consent?: boolean };
      monthly_budget_cents?: number;
      clear_budget?: boolean;
    }
  ) => void;
}

export function AgentModal({
  agentKey,
  detail,
  loading,
  busy,
  onClose,
  onRunNow,
  onCancelRun,
  onRetryRun,
  onUpdateAgentConfig,
}: AgentModalProps) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [policyMode, setPolicyMode] = useState<"local_only" | "external_consented">("local_only");
  const [externalConsent, setExternalConsent] = useState(false);
  const [budgetReais, setBudgetReais] = useState("");
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    if (detail?.agent) {
      setDisplayName(detail.agent.display_name);
      setEnabled(detail.agent.enabled);
      const mode = detail.agent.model_policy?.mode === "external_consented" ? "external_consented" : "local_only";
      setPolicyMode(mode);
      setExternalConsent(Boolean(detail.agent.model_policy?.external_consent));
      setBudgetReais(
        detail.agent.monthly_budget_cents !== null && detail.agent.monthly_budget_cents !== undefined
          ? (detail.agent.monthly_budget_cents / 100).toFixed(2)
          : ""
      );
      setConfigError(null);
    }
  }, [detail]);

  useEffect(() => {
    if (!agentKey) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [agentKey, onClose]);

  if (!agentKey) return null;

  const ag = detail?.agent;
  const latestRun = detail?.runs[0] ?? null;
  const isNoSignal = ag?.status === "no_signal";

  const handleSaveConfig = (e: React.FormEvent) => {
    e.preventDefault();
    if (policyMode === "external_consented" && !externalConsent) {
      setConfigError("Política externa exige consentimento explícito marcado.");
      return;
    }
    setConfigError(null);
    const parsedBudget = budgetReais.trim() ? Math.round(Number(budgetReais.replace(",", ".")) * 100) : undefined;
    onUpdateAgentConfig(agentKey, {
      enabled,
      display_name: displayName,
      model_policy: { mode: policyMode, external_consent: policyMode === "external_consented" ? externalConsent : false },
      monthly_budget_cents: parsedBudget,
      clear_budget: !budgetReais.trim(),
    });
  };

  return (
    <div className="studio-drawer-backdrop" onClick={onClose}>
      <div
        className="studio-modal"
        role="dialog"
        aria-modal="true"
        aria-label={ag ? `Agente ${ag.display_name}` : "Card do Agente"}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="studio-drawer-head">
          <div>
            <div className="studio-hud-eyebrow">Agente do Canal ({agentKey})</div>
            <h2 style={{ margin: 0 }}>{ag?.display_name ?? agentKey}</h2>
          </div>
          <button ref={closeRef} type="button" className="btn" onClick={onClose}>
            Fechar
          </button>
        </div>

        {loading || !ag ? (
          <p className="muted">Carregando histórico e política do agente…</p>
        ) : (
          <div className="studio-drawer-body">
            <p className="muted">{ag.description}</p>

            {/* Run atual */}
            <section className="studio-drawer-box">
              <div className="studio-drawer-item-top">
                <strong>Estado Atual</strong>
                <span className={`studio-pill-sm status-${ag.status}`}>
                  {getStatusLabelPt(ag.status)}
                </span>
              </div>

              {isNoSignal && (
                <div className="studio-hud-warning">
                  Heartbeat atrasado (&gt; 2 min). Exibindo &quot;sem sinal&quot; em vez de simular progresso.
                </div>
              )}

              <div className="muted-tiny" style={{ marginTop: 6 }}>
                Etapa: <strong>{ag.stage_label ?? "em espera"}</strong> • Progresso:{" "}
                <strong>
                  {ag.progress !== null && ag.progress !== undefined
                    ? `${Math.round(ag.progress * 100)}%`
                    : "indeterminado"}
                </strong>
              </div>
              <div className="muted-tiny">
                Heartbeat: {ag.heartbeat_at ? new Date(ag.heartbeat_at).toLocaleString("pt-BR") : "nenhum"}
              </div>
              {ag.error_message && <div className="studio-err-tiny">{ag.error_code}: {ag.error_message}</div>}

              <div className="studio-drawer-actions" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn primary studio-btn-sm"
                  disabled={!ag.enabled || busy}
                  onClick={() => onRunNow(agentKey)}
                >
                  Executar agora
                </button>
                {latestRun && (latestRun.status === "queued" || latestRun.status === "working") && (
                  <button
                    type="button"
                    className="btn studio-btn-sm"
                    disabled={busy}
                    onClick={() => onCancelRun(latestRun.id)}
                  >
                    Cancelar
                  </button>
                )}
                {latestRun && (latestRun.status === "failed" || latestRun.status === "blocked" || latestRun.status === "cancelled") && (
                  <button
                    type="button"
                    className="btn studio-btn-sm"
                    disabled={busy}
                    onClick={() => onRetryRun(latestRun.id)}
                  >
                    Tentar de novo
                  </button>
                )}
              </div>
            </section>

            {/* Política & Configuração por Canal (UI-06-T05) */}
            <section className="studio-drawer-box">
              <h3>Configuração da Equipe no Canal</h3>
              <form onSubmit={handleSaveConfig}>
                <div className="field">
                  <label htmlFor="ag-display-name">Nome de exibição</label>
                  <input
                    id="ag-display-name"
                    className="input"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </div>
                <div className="inline-grid-3">
                  <label className="studio-check-label">
                    <input
                      type="checkbox"
                      checked={enabled}
                      onChange={(e) => setEnabled(e.target.checked)}
                    />
                    <span>Agente ativo</span>
                  </label>
                  <div className="field">
                    <label htmlFor="ag-policy">Política de modelo</label>
                    <select
                      id="ag-policy"
                      className="input"
                      value={policyMode}
                      onChange={(e) => setPolicyMode(e.target.value as "local_only" | "external_consented")}
                    >
                      <option value="local_only">Local apenas (CPU/Determinístico)</option>
                      <option value="external_consented">Externo com consentimento</option>
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="ag-budget">Orçamento mensal (R$)</label>
                    <input
                      id="ag-budget"
                      className="input"
                      placeholder="Ilimitado"
                      value={budgetReais}
                      onChange={(e) => setBudgetReais(e.target.value)}
                    />
                  </div>
                </div>
                {policyMode === "external_consented" && (
                  <label className="studio-check-label" style={{ marginBottom: 8 }}>
                    <input
                      type="checkbox"
                      checked={externalConsent}
                      onChange={(e) => setExternalConsent(e.target.checked)}
                    />
                    <span>Autorizo envio de contexto curado para provedor externo (sem credenciais)</span>
                  </label>
                )}
                {configError && <div className="studio-err-tiny">{configError}</div>}
                <button type="submit" className="btn studio-btn-sm" disabled={busy}>
                  Salvar política do agente
                </button>
              </form>
            </section>

            {/* Histórico de outputs */}
            <section>
              <h3>Outputs produzidos ({detail.outputs.length})</h3>
              {detail.outputs.length === 0 ? (
                <p className="muted-tiny">Nenhum output produzido ainda.</p>
              ) : (
                <div className="studio-drawer-list">
                  {detail.outputs.slice(0, 6).map((o) => (
                    <div key={o.id} className="studio-drawer-item compact">
                      <div className="studio-drawer-item-top">
                        <strong>{o.output_type} v{o.version}</strong>
                        <span className={`studio-pill-sm status-${o.status}`}>{o.status}</span>
                      </div>
                      <div className="muted-tiny">{String(o.content?.summary ?? "")}</div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
