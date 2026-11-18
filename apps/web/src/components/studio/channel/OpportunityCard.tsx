"use client";

import { useState } from "react";
import type { AgentOutput, ContentItemPipeline } from "@/lib/studio/types";
import styles from "./channel.module.css";

const STATUS_LABEL: Partial<Record<AgentOutput["status"], string>> = {
  approved: "Aprovada",
  rejected: "Rejeitada",
  needs_review: "Revisar",
};

interface OpportunityCardProps {
  opportunity: AgentOutput | null;
  activeItem: ContentItemPipeline | null;
  busy: boolean;
  onGenerate: () => void;
  onDecide: (output: AgentOutput, decision: "approved" | "rejected") => void;
}

export function OpportunityCard({ opportunity, activeItem, busy, onGenerate, onDecide }: OpportunityCardProps) {
  const [showWhy, setShowWhy] = useState(false);

  const content = (opportunity?.content ?? {}) as Record<string, unknown>;
  const score = (content.score ?? null) as { value?: number; max?: number } | null;
  const labels = (content.labels ?? null) as { potencial?: string; concorrencia?: string } | null;
  const evidence = (content.evidence ?? []) as { text: string; source_id: string }[];
  const limitations = (content.limitations ?? []) as string[];
  const confidence = typeof content.confidence === "string" ? content.confidence : null;
  const topic = typeof content.topic === "string" ? content.topic : null;

  const scoreVal = typeof score?.value === "number" ? score.value : null;
  const scoreMax = typeof score?.max === "number" && score.max > 0 ? score.max : 100;
  const decided = opportunity?.status === "approved" || opportunity?.status === "rejected";

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="opp-title">
      <div className={styles.sectionHead}>
        <h3 id="opp-title" className={styles.sectionTitle}>
          Próxima oportunidade
        </h3>
        {opportunity ? (
          <span className={styles.sourceBadge}>{STATUS_LABEL[opportunity.status] ?? "Aguardando"}</span>
        ) : null}
      </div>

      {opportunity ? (
        <>
          <div className={styles.opp}>
            <div
              className={`${styles.score} ${scoreVal !== null ? styles.scoreFilled : ""}`}
              aria-label={`Score ${scoreVal ?? "indisponível"} de ${scoreMax}`}
            >
              <span className={styles.scoreValue}>{scoreVal ?? "—"}</span>
              <span className={styles.scoreMax}>/{scoreMax}</span>
            </div>
            <div className={styles.oppRows}>
              <div className={styles.oppRow}>
                <span>Potencial</span>
                <strong>{labels?.potencial ?? "—"}</strong>
              </div>
              <div className={styles.oppRow}>
                <span>Concorrência</span>
                <strong>{labels?.concorrencia ?? "—"}</strong>
              </div>
              <div className={styles.oppRow}>
                <span>Confiança</span>
                <strong>{confidence ?? "—"}</strong>
              </div>
            </div>
          </div>
          {topic && <p className={styles.oppTopic}>{topic}</p>}
          <div className={styles.oppActions}>
            <button type="button" className={styles.btn} aria-expanded={showWhy} onClick={() => setShowWhy((v) => !v)}>
              {showWhy ? "Ocultar evidências" : "Ver evidências"}
            </button>
            {!decided && (
              <>
                <button
                  type="button"
                  className={`${styles.btn} ${styles.btnPrimary}`}
                  disabled={busy}
                  onClick={() => onDecide(opportunity, "approved")}
                >
                  Aprovar
                </button>
                <button type="button" className={styles.btn} disabled={busy} onClick={() => onDecide(opportunity, "rejected")}>
                  Rejeitar
                </button>
              </>
            )}
          </div>
          {showWhy && (
            <ul className={styles.evidence}>
              {evidence.map((ev, i) => (
                <li key={i}>{ev.text}</li>
              ))}
              {limitations.length > 0 && <li>Limitações: {limitations.join(" · ")}</li>}
              {evidence.length === 0 && limitations.length === 0 && <li>Sem evidências registradas.</li>}
            </ul>
          )}
        </>
      ) : (
        <div>
          <p className={styles.sectionHint} style={{ margin: "0 0 12px", lineHeight: 1.5 }}>
            {activeItem
              ? `Aguardando análise para "${activeItem.working_title}".`
              : "O Estrategista cruza os dados do canal e a pesquisa para sugerir o próximo vídeo."}
          </p>
          <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={onGenerate} disabled={busy}>
            {busy ? "Gerando…" : "Gerar oportunidade"}
          </button>
        </div>
      )}
    </section>
  );
}
