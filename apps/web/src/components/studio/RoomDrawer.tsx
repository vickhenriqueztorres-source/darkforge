"use client";

import React, { useEffect, useRef, useState } from "react";
import { getStatusLabelPt } from "@/lib/studio/studio-layout";
import type {
  AgentKey,
  AgentOutput,
  ContentItemPipeline,
  RoomDetailResponse,
  RoomKey,
} from "@/lib/studio/types";

interface RoomDrawerProps {
  roomKey: RoomKey | null;
  detail: RoomDetailResponse | null;
  loading: boolean;
  activeItem: ContentItemPipeline | null;
  busy: boolean;
  onClose: () => void;
  onSelectAgent: (agentKey: AgentKey) => void;
  onRunAgent: (agentKey: AgentKey) => void;
  onSubmitApproval: (
    targetKind: "agent_output" | "opportunity" | "brief" | "publication_plan",
    targetId: string,
    targetVersion: number,
    decision: "approved" | "rejected" | "changes_requested",
    reason?: string,
    confirmNeedsReview?: boolean
  ) => void;
  onReviseOutput: (
    outputId: string,
    action: "save_version" | "discard",
    editedContent?: Record<string, unknown>,
    reason?: string
  ) => void;
  onMarkManualPublished: (contentItemId: string, url: string) => void;
}

export function RoomDrawer({
  roomKey,
  detail,
  loading,
  activeItem,
  busy,
  onClose,
  onSelectAgent,
  onRunAgent,
  onSubmitApproval,
  onReviseOutput,
  onMarkManualPublished,
}: RoomDrawerProps) {
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const [editingOutputId, setEditingOutputId] = useState<string | null>(null);
  const [editedJsonText, setEditedJsonText] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [manualUrl, setManualUrl] = useState("");
  const [approvalReason, setApprovalReason] = useState("");

  useEffect(() => {
    if (!roomKey) return;
    closeBtnRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [roomKey, onClose]);

  if (!roomKey) return null;

  const startRevision = (out: AgentOutput) => {
    setEditingOutputId(out.id);
    setEditedJsonText(JSON.stringify(out.content, null, 2));
    setEditError(null);
  };

  const handleSaveRevision = (outId: string) => {
    try {
      const parsed = JSON.parse(editedJsonText) as Record<string, unknown>;
      setEditError(null);
      onReviseOutput(outId, "save_version", parsed, "Revisão manual no Estúdio");
      setEditingOutputId(null);
    } catch {
      setEditError("JSON inválido. Corrija a sintaxe antes de salvar nova versão.");
    }
  };

  const latestPubPlan = detail?.recent_outputs.find(
    (o) => o.output_type === "publication_plan" && o.content_item_id === activeItem?.content_item_id
  );

  return (
    <div className="studio-drawer-backdrop" onClick={onClose}>
      <aside
        className="studio-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={detail?.room.label ?? "Detalhes da Sala"}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="studio-drawer-head">
          <div>
            <div className="studio-hud-eyebrow">Sala do Estúdio</div>
            <h2 style={{ margin: 0 }}>{detail?.room.label ?? roomKey}</h2>
          </div>
          <button
            ref={closeBtnRef}
            type="button"
            className="btn"
            onClick={onClose}
            aria-label="Fechar gaveta da sala"
          >
            Fechar (Esc)
          </button>
        </div>

        {loading || !detail ? (
          <p className="muted">Carregando dados reais da sala…</p>
        ) : (
          <div className="studio-drawer-body">
            {/* Agentes da sala */}
            <section>
              <h3>Agentes nesta sala ({detail.agents.length})</h3>
              <div className="studio-drawer-list">
                {detail.agents.map((ag) => (
                  <div key={ag.channel_agent_id} className="studio-drawer-item">
                    <div className="studio-drawer-item-top">
                      <div>
                        <strong>{ag.display_name}</strong>{" "}
                        <span className="muted-tiny">({ag.agent_key})</span>
                        <div className="muted-tiny">{ag.description}</div>
                      </div>
                      <span className={`studio-pill-sm status-${ag.status}`}>
                        {getStatusLabelPt(ag.status)}
                      </span>
                    </div>
                    {!ag.enabled && (
                      <div className="studio-hud-warning">
                        Módulo desabilitado neste canal{" "}
                        {typeof ag.config?.unavailable_reason === "string"
                          ? `(${ag.config.unavailable_reason})`
                          : ""}
                      </div>
                    )}
                    <div className="studio-drawer-actions">
                      <button
                        type="button"
                        className="btn studio-btn-sm"
                        onClick={() => onSelectAgent(ag.agent_key)}
                      >
                        Abrir card
                      </button>
                      <button
                        type="button"
                        className="btn primary studio-btn-sm"
                        disabled={!ag.enabled || busy}
                        onClick={() => onRunAgent(ag.agent_key)}
                      >
                        Executar agora
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Aprovação de Brief consolidado na sala mesa_agentes / gravacao */}
            {activeItem && (roomKey === "mesa_agentes" || roomKey === "gravacao") && (
              <section className="studio-drawer-box">
                <h3>Gate do Brief — {activeItem.working_title}</h3>
                <p className="muted-tiny">
                  Estágio atual: <strong>{activeItem.stage}</strong> ({activeItem.status})
                </p>
                <div className="field">
                  <label htmlFor="brief-approval-reason">Justificativa (opcional)</label>
                  <input
                    id="brief-approval-reason"
                    className="input"
                    value={approvalReason}
                    onChange={(e) => setApprovalReason(e.target.value)}
                    placeholder="Ex.: Brief alinhado aos pilares e originalidade validada"
                  />
                </div>
                <div className="studio-drawer-actions">
                  <button
                    type="button"
                    className="btn primary studio-btn-sm"
                    disabled={busy}
                    onClick={() =>
                      onSubmitApproval(
                        "brief",
                        activeItem.content_item_id,
                        (activeItem.brief_version ?? 0) + 1,
                        "approved",
                        approvalReason || "Brief aprovado para produção"
                      )
                    }
                  >
                    Aprovar Brief e Liberar Produção
                  </button>
                </div>
              </section>
            )}

            {/* Publicação Manual (UI-06-T06) */}
            {roomKey === "estrategia_publicacao" && activeItem && (
              <section className="studio-drawer-box">
                <h3>Publicação Manual no YouTube</h3>
                <p className="muted-tiny">
                  Nenhum agente publica automaticamente. Após publicar no YouTube Studio, registre a URL oficial abaixo.
                </p>
                {activeItem.stage === "publicado_manual" && activeItem.published_video_url ? (
                  <div className="pill ok">
                    Publicado manualmente: {activeItem.published_video_url}
                  </div>
                ) : (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      onMarkManualPublished(activeItem.content_item_id, manualUrl);
                    }}
                  >
                    <div className="field">
                      <label htmlFor="manual-yt-url">URL do vídeo publicado no YouTube</label>
                      <input
                        id="manual-yt-url"
                        className="input"
                        type="url"
                        required
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={manualUrl}
                        onChange={(e) => setManualUrl(e.target.value)}
                      />
                    </div>
                    <button type="submit" className="btn primary studio-btn-sm" disabled={busy}>
                      Marcar como publicado
                    </button>
                  </form>
                )}

                {latestPubPlan && latestPubPlan.status !== "approved" && (
                  <div style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="btn primary studio-btn-sm"
                      disabled={busy}
                      onClick={() =>
                        onSubmitApproval(
                          "publication_plan",
                          latestPubPlan.id,
                          latestPubPlan.version,
                          "approved",
                          "Plano de publicação aprovado"
                        )
                      }
                    >
                      Aprovar Plano v{latestPubPlan.version}
                    </button>
                  </div>
                )}
              </section>
            )}

            {/* Runs recentes */}
            <section>
              <h3>Execuções recentes ({detail.recent_runs.length})</h3>
              {detail.recent_runs.length === 0 ? (
                <p className="muted-tiny">Nenhuma execução registrada nesta sala.</p>
              ) : (
                <div className="studio-drawer-list">
                  {detail.recent_runs.slice(0, 8).map((r) => (
                    <div key={r.id} className="studio-drawer-item compact">
                      <div className="studio-drawer-item-top">
                        <span>
                          <strong>{r.agent_key}</strong> • tentativa #{r.attempt}
                        </span>
                        <span className={`studio-pill-sm status-${r.status}`}>
                          {getStatusLabelPt(r.status)}
                        </span>
                      </div>
                      <div className="muted-tiny">
                        Etapa: {r.stage_label ?? "—"} • Progresso:{" "}
                        {r.progress !== null && r.progress !== undefined
                          ? `${Math.round(r.progress * 100)}%`
                          : "indeterminado"}{" "}
                        • Custo:{" "}
                        {r.cost_estimate_cents !== null && r.cost_estimate_cents !== undefined
                          ? `R$ ${(r.cost_estimate_cents / 100).toFixed(2)}`
                          : "R$ 0,00"}
                      </div>
                      {r.error_message && <div className="studio-err-tiny">{r.error_message}</div>}
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Outputs recentes com fontes e revisão humana */}
            <section>
              <h3>Últimos outputs ({detail.recent_outputs.length})</h3>
              {detail.recent_outputs.length === 0 ? (
                <p className="muted-tiny">Nenhum output persistido ainda.</p>
              ) : (
                <div className="studio-drawer-list">
                  {detail.recent_outputs.slice(0, 8).map((out) => (
                    <div key={out.id} className="studio-drawer-item">
                      <div className="studio-drawer-item-top">
                        <strong>
                          {out.output_type} v{out.version} ({out.author_kind})
                        </strong>
                        <span className={`studio-pill-sm status-${out.status}`}>{out.status}</span>
                      </div>
                      <div className="muted-tiny">
                        {String(out.content?.summary ?? "")}
                      </div>
                      {out.validation?.review_reasons && out.validation.review_reasons.length > 0 && (
                        <div className="studio-hud-warning">
                          Motivo da revisão: {out.validation.review_reasons.join(", ")}
                        </div>
                      )}
                      {out.sources && out.sources.length > 0 && (
                        <div className="muted-tiny">
                          Fontes ({out.sources.length}):{" "}
                          {out.sources.map((s) => `${s.source_kind}:${s.source_id.slice(0, 8)}`).join(", ")}
                        </div>
                      )}

                      {out.status === "needs_review" && editingOutputId !== out.id && (
                        <div className="studio-drawer-actions">
                          <button
                            type="button"
                            className="btn primary studio-btn-sm"
                            onClick={() => startRevision(out)}
                          >
                            Editar nova versão
                          </button>
                          <button
                            type="button"
                            className="btn studio-btn-sm"
                            disabled={busy}
                            onClick={() => onReviseOutput(out.id, "discard")}
                          >
                            Descartar
                          </button>
                        </div>
                      )}

                      {editingOutputId === out.id && (
                        <div className="studio-revise-box">
                          <textarea
                            className="input"
                            rows={6}
                            value={editedJsonText}
                            onChange={(e) => setEditedJsonText(e.target.value)}
                          />
                          {editError && <div className="studio-err-tiny">{editError}</div>}
                          <div className="studio-drawer-actions">
                            <button
                              type="button"
                              className="btn primary studio-btn-sm"
                              disabled={busy}
                              onClick={() => handleSaveRevision(out.id)}
                            >
                              Salvar v{out.version + 1}
                            </button>
                            <button
                              type="button"
                              className="btn studio-btn-sm"
                              onClick={() => setEditingOutputId(null)}
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </aside>
    </div>
  );
}
