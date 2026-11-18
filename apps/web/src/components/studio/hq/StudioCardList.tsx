"use client";

import type { MutableRefObject } from "react";
import type { HQFilter, StudioOverviewChannel } from "@/lib/studio/hq-types";
import {
  isChannelConnected,
  matchesFilter,
  studioAwaitingCount,
  studioLamp,
  studioLampLabel,
  studioProblemCount,
  studioSummaryText,
  studioWorkingCount,
} from "@/lib/studio/hq-status";
import { assignChannelColors } from "./hqColors";
import { channelInitials } from "./signText";
import styles from "./hq.module.css";

export interface StudioCardListProps {
  channels: StudioOverviewChannel[];
  filter: HQFilter;
  searchQuery: string;
  focusedChannelId: string | null;
  mode: "sidebar" | "cards";
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onFocusOrEnter: (channelId: string) => void;
  onEnterChannel: (channelId: string) => void;
  onPrepareStudio?: (channelId: string) => void;
  buttonRefs?: MutableRefObject<Map<string, HTMLButtonElement>>;
}

export function StudioCardList({
  channels,
  filter,
  searchQuery,
  focusedChannelId,
  mode,
  collapsed = false,
  onToggleCollapse,
  onFocusOrEnter,
  onEnterChannel,
  onPrepareStudio,
  buttonRefs,
}: StudioCardListProps) {
  const colors = assignChannelColors(channels.map((c) => c.channel.id));
  const normSearch = searchQuery.trim().toLowerCase();

  return (
    <aside
      className={mode === "cards" ? styles.cardListGridWrap : `${styles.cardListAside} ${collapsed ? styles.cardListCollapsed : ""}`}
      aria-label="Estúdios dos canais"
    >
      <div className={styles.cardListHeader}>
        <h3 className={styles.cardListTitle}>Estúdios dos canais ({channels.length})</h3>
        {mode === "sidebar" && onToggleCollapse && (
          <button
            type="button"
            className={styles.collapseBtn}
            onClick={onToggleCollapse}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expandir lista de estúdios" : "Recolher lista de estúdios"}
          >
            {collapsed ? "Abrir" : "Recolher"}
          </button>
        )}
      </div>

      {!collapsed && (
        <ul className={mode === "cards" ? styles.cardGrid : styles.cardList}>
          {channels.map((ch) => {
            const id = ch.channel.id;
            const lamp = studioLamp(ch);
            const lampText = studioLampLabel(lamp);
            const connected = isChannelConnected(ch);
            const color = colors.get(id) ?? "#3f8f8a";
            const working = studioWorkingCount(ch);
            const awaiting = studioAwaitingCount(ch);
            const problems = studioProblemCount(ch);
            const matches = matchesFilter(ch, filter);
            const searchMatch =
              !normSearch ||
              ch.channel.display_name.toLowerCase().includes(normSearch) ||
              (ch.channel.handle ?? "").toLowerCase().includes(normSearch);
            const dimmed = !matches || !searchMatch;
            const isFocused = focusedChannelId === id;

            return (
              <li key={id} className={styles.cardItem}>
                <button
                  ref={(el) => {
                    if (!buttonRefs) return;
                    if (el) buttonRefs.current.set(id, el);
                    else buttonRefs.current.delete(id);
                  }}
                  type="button"
                  className={`${styles.channelCardBtn} ${isFocused ? styles.channelCardFocused : ""} ${dimmed ? styles.channelCardDimmed : ""}`}
                  style={{ borderLeftColor: color }}
                  aria-label={studioSummaryText(ch)}
                  aria-pressed={isFocused}
                  onClick={() => onFocusOrEnter(id)}
                >
                  <div className={styles.cardTopRow}>
                    <span className={styles.cardAvatar} style={{ backgroundColor: color }} aria-hidden="true">
                      {ch.channel.avatar_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={ch.channel.avatar_url} alt="" className={styles.cardAvatarImg} />
                      ) : (
                        channelInitials(ch.channel.display_name)
                      )}
                    </span>
                    <div className={styles.cardNameBlock}>
                      <span className={styles.cardName}>{ch.channel.display_name}</span>
                      {ch.channel.handle && <span className={styles.cardHandle}>{ch.channel.handle}</span>}
                    </div>
                    <span className={`${styles.lampBadge} ${styles[`lamp_${lamp}`]}`}>
                      <span className={styles.lampDot} aria-hidden="true" />
                      <span>{!connected ? "Desconectado" : !ch.provisioned ? "Em obras" : lampText}</span>
                    </span>
                  </div>

                  <div className={styles.cardCountsRow}>
                    {!connected ? (
                      <span>Canal desconectado</span>
                    ) : !ch.provisioned ? (
                      <span>Sem agentes provisionados</span>
                    ) : (
                      <span>
                        {working} trabalhando · {awaiting} aguardando · {problems} com problema
                      </span>
                    )}
                  </div>

                  {ch.active_item && (
                    <div className={styles.cardActiveItem}>
                      Produzindo: {ch.active_item.working_title}
                    </div>
                  )}
                </button>

                {mode === "cards" && (
                  <div className={styles.mobileCardActions}>
                    {!ch.provisioned && onPrepareStudio && (
                      <button
                        type="button"
                        className="btn studio-btn-xs"
                        onClick={() => onPrepareStudio(id)}
                      >
                        Preparar estúdio
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn primary studio-btn-xs"
                      onClick={() => onEnterChannel(id)}
                    >
                      Entrar
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
