"use client";

import { useEffect, useRef, useState } from "react";
import type { StudioOverviewChannel } from "@/lib/studio/hq-types";
import { isChannelConnected, studioLamp, studioLampLabel } from "@/lib/studio/hq-status";
import { getStatusLabelPt, PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import { AGENT_LOOK } from "@/components/studio/office3d/layout3d";
import { channelInitials } from "./signText";
import styles from "./hq.module.css";

export interface HQFocusPanelProps {
  channel: StudioOverviewChannel;
  color: string;
  onEnter: (channelId: string) => void;
  onClose: () => void;
  onPrepareStudio: (channelId: string) => Promise<void>;
}

export function HQFocusPanel({
  channel,
  color,
  onEnter,
  onClose,
  onPrepareStudio,
}: HQFocusPanelProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);

  useEffect(() => {
    setPrepareError(null);
    panelRef.current?.focus();
  }, [channel.channel.id]);

  const lamp = studioLamp(channel);
  const connected = isChannelConnected(channel);

  const handlePrepare = async () => {
    setPreparing(true);
    setPrepareError(null);
    try {
      await onPrepareStudio(channel.channel.id);
    } catch (err) {
      setPrepareError(
        err instanceof Error ? err.message : "Não foi possível preparar o estúdio agora. Tente novamente."
      );
    } finally {
      setPreparing(false);
    }
  };

  return (
    <aside
      ref={panelRef}
      tabIndex={-1}
      className={styles.focusPanel}
      aria-label={`Detalhes do estúdio ${channel.channel.display_name}`}
    >
      <div className={styles.focusHeader}>
        <div className={styles.focusIdentity}>
          <span className={styles.cardAvatar} style={{ backgroundColor: color }} aria-hidden="true">
            {channel.channel.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={channel.channel.avatar_url} alt="" className={styles.cardAvatarImg} />
            ) : (
              channelInitials(channel.channel.display_name)
            )}
          </span>
          <div>
            <h3 className={styles.focusTitle}>{channel.channel.display_name}</h3>
            <p className={styles.focusMeta}>
              {channel.channel.handle ? `${channel.channel.handle} · ` : ""}
              {channel.channel.niche ?? "Sem nicho definido"}
            </p>
          </div>
        </div>
        <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Fechar painel do estúdio">
          ✕
        </button>
      </div>

      <div className={styles.focusStatusRow}>
        <span className={`${styles.lampBadge} ${styles[`lamp_${lamp}`]}`}>
          <span className={styles.lampDot} aria-hidden="true" />
          <span>{!connected ? "Desconectado" : !channel.provisioned ? "Em obras" : studioLampLabel(lamp)}</span>
        </span>
        {channel.active_item && (
          <span className={styles.focusStageChip}>
            Produzindo: {channel.active_item.working_title} ({channel.active_item.stage})
          </span>
        )}
      </div>

      {!channel.provisioned ? (
        <div className={styles.unprovBox}>
          <p className={styles.unprovText}>
            Este estúdio está em obras: os 8 agentes do canal ainda não foram provisionados.
          </p>
          {prepareError && (
            <p className={styles.prepareError} role="alert">
              {prepareError}
            </p>
          )}
          <button
            type="button"
            className="btn primary studio-btn-sm"
            onClick={handlePrepare}
            disabled={preparing}
          >
            {preparing ? "Preparando estúdio…" : "Preparar estúdio"}
          </button>
        </div>
      ) : (
        <ul className={styles.focusAgentList} aria-label="Equipe de 8 agentes">
          {PIPELINE_ORDER.map((agentKey) => {
            const look = AGENT_LOOK[agentKey];
            const agent = channel.agents.find((a) => a.agent_key === agentKey);
            const statusText = !agent
              ? "Indisponível"
              : !agent.enabled || agent.status === "disabled"
                ? "Desligado"
                : getStatusLabelPt(agent.status);
            return (
              <li key={agentKey} className={styles.focusAgentRow}>
                <span className={styles.agentColorDot} style={{ backgroundColor: look.shirt }} aria-hidden="true" />
                <span className={styles.focusAgentName}>{look.name}</span>
                <span className={styles.focusAgentStatus}>{statusText}</span>
              </li>
            );
          })}
        </ul>
      )}

      <div className={styles.focusActions}>
        <button type="button" className="btn studio-btn-sm" onClick={onClose}>
          ← Voltar
        </button>
        <button
          type="button"
          className="btn primary studio-btn-sm"
          onClick={() => onEnter(channel.channel.id)}
        >
          Entrar no estúdio
        </button>
      </div>
    </aside>
  );
}
