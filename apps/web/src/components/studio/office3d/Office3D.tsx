"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { AgentKey, ContentItemPipeline, RoomKey, StudioAgentState, StudioRoomState } from "@/lib/studio/types";
import { AGENT_LOOK, ROOMS, ROOM_ORDER, agentBubble } from "./layout3d";
import styles from "./office3d.module.css";

const OfficeScene = dynamic(() => import("./OfficeScene"), {
  ssr: false,
  loading: () => <div className={styles.loading}>Montando o escritório…</div>,
});

const APPROVAL = new Set(["waiting_approval", "needs_review", "waiting_input"]);
const PROBLEM = new Set(["failed", "blocked", "no_signal"]);

export interface Office3DProps {
  agents: StudioAgentState[];
  rooms: StudioRoomState[];
  activeItem: ContentItemPipeline | null;
  selectedAgent: AgentKey | null;
  loading: boolean;
  onSelectAgent: (agentKey: AgentKey) => void;
  onSelectRoom: (roomKey: RoomKey) => void;
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export function Office3D({ agents, rooms, activeItem, selectedAgent, loading, onSelectAgent, onSelectRoom }: Office3DProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLElement>());
  const [visible, setVisible] = useState(true);
  const [hoveredAgent, setHoveredAgent] = useState<AgentKey | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const anchorRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) anchors.current.set(id, el);
      else anchors.current.delete(id);
    },
    []
  );

  const enabled = agents.filter((a) => a.enabled);
  const working = enabled.filter((a) => a.status === "working").length;
  const waiting = enabled.filter((a) => APPROVAL.has(a.status)).length;
  const problems = enabled.filter((a) => PROBLEM.has(a.status)).length;
  const roomState = new Map(rooms.map((r) => [r.room_key, r]));
  const orderedAgents = PIPELINE_ORDER.map((k) => agents.find((a) => a.agent_key === k)).filter(
    (a): a is StudioAgentState => Boolean(a)
  );

  return (
    <section className={styles.section} aria-labelledby="office-title">
      <header className={styles.header}>
        <div>
          <h2 id="office-title" className={styles.title}>
            Escritório dos agentes
          </h2>
          <p className={styles.hint}>
            {activeItem ? `Produzindo: ${activeItem.working_title}` : "Nenhum vídeo em produção agora"}
            {" · "}clique numa sala ou num agente · arraste para girar
          </p>
        </div>
        <ul className={styles.stats} aria-label="Resumo da equipe">
          <li>
            <span className={`${styles.dot} ${styles.dotWork}`} aria-hidden="true" />
            {working} trabalhando
          </li>
          <li>
            <span className={`${styles.dot} ${styles.dotWarn}`} aria-hidden="true" />
            {waiting} aguardando você
          </li>
          <li>
            <span className={`${styles.dot} ${styles.dotErr}`} aria-hidden="true" />
            {problems} com problema
          </li>
        </ul>
      </header>

      <div
        ref={stageRef}
        className={styles.stage}
        role="group"
        aria-label="Maquete 3D do escritório. A lista Equipe de agentes ao lado tem as mesmas ações acessíveis por teclado."
      >
        <OfficeScene
          agents={agents}
          selectedAgent={selectedAgent}
          hoveredAgent={hoveredAgent}
          active={visible}
          reducedMotion={reducedMotion}
          anchors={anchors}
          onSelectAgent={onSelectAgent}
          onHoverAgent={setHoveredAgent}
          onSelectRoom={onSelectRoom}
        />

        <div className={styles.overlay}>
          {ROOM_ORDER.map((key) => {
            const state = roomState.get(key);
            const label = state?.room_label ?? ROOMS[key].label;
            const busy = state?.working ?? 0;
            const pending = state ? state.awaiting_human + state.failed + state.blocked : 0;
            const description = [label, busy ? `${busy} trabalhando` : null, pending ? `${pending} pendências` : null]
              .filter(Boolean)
              .join(", ");
            return (
              <div key={key} ref={anchorRef(`room:${key}`)} className={styles.anchor}>
                <button
                  type="button"
                  className={styles.roomLabel}
                  onClick={() => onSelectRoom(key)}
                  aria-label={`Abrir ${description}`}
                >
                  <span>{label}</span>
                  {busy > 0 && <span className={`${styles.count} ${styles.countWork}`}>{busy}</span>}
                  {pending > 0 && <span className={`${styles.count} ${styles.countWarn}`}>{pending}</span>}
                </button>
              </div>
            );
          })}

          {orderedAgents.map((agent) => {
            const bubble = agentBubble(agent.status, agent.enabled, agent.progress);
            const showName = hoveredAgent === agent.agent_key || selectedAgent === agent.agent_key;
            if (!bubble && !showName) return null;
            return (
              <div key={agent.agent_key} ref={anchorRef(`agent:${agent.agent_key}`)} className={styles.anchor} aria-hidden="true">
                <div className={styles.bubbleWrap}>
                  {showName && <span className={styles.nameTag}>{AGENT_LOOK[agent.agent_key].name}</span>}
                  {bubble && <span className={`${styles.bubble} ${styles[`tone_${bubble.tone}`]}`}>{bubble.text}</span>}
                </div>
              </div>
            );
          })}
        </div>

        {agents.length === 0 && !loading && (
          <p className={styles.overlayNote}>Os agentes deste canal ainda não foram provisionados.</p>
        )}
      </div>
    </section>
  );
}
