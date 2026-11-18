"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { AgentKey, ContentItemPipeline, RoomKey, StudioAgentState, StudioRoomState } from "@/lib/studio/types";
import type { ExternalAgentState, ExternalRoomRollup } from "@/lib/studio/external-types";
import { AGENT_LOOK, EXTERNAL_GROUP_LOOK, ROOMS, ROOM_ORDER, agentBubble } from "./layout3d";
import styles from "./office3d.module.css";

const OfficeScene = dynamic(() => import("./OfficeScene"), {
  ssr: false,
  loading: () => <div className={styles.loading}>Montando o escritório…</div>,
});

const APPROVAL = new Set(["waiting_approval", "needs_review", "waiting_input"]);
const PROBLEM = new Set(["failed", "blocked", "no_signal"]);

const FEATURED_EXTERNAL_KEYS = [
  "firefly-worker",
  "RemotionChoreographyAgent",
  "DocumentaryEditorAgent",
  "packaging-agent",
  "HumanSelectionGate",
  "RemotionAssemblyAgent",
  "NarrationVoiceAgent",
  "ThumbnailRenderAgent",
  "agent_10_video_cutter",
  "SystemsResearchAgent",
  "firefly-jobstore",
] as const;

function shortExternalName(ag: ExternalAgentState): string {
  const map: Record<string, string> = {
    "firefly-worker": "Firefly Worker",
    "firefly-jobstore": "Firefly JobStore",
    "packaging-agent": "Packaging Squad",
    RemotionChoreographyAgent: "Remotion Choreo",
    DocumentaryEditorAgent: "Doc Editor",
    HumanSelectionGate: "Human Gate A/B/C",
    RemotionAssemblyAgent: "Remotion Master",
    NarrationVoiceAgent: "ElevenLabs Chris",
    ThumbnailRenderAgent: "Thumb Render 4K",
    agent_10_video_cutter: "Shorts Cutter #10",
    SystemsResearchAgent: "Systems Research",
  };
  return map[ag.agent_key] ?? ag.display_name.replace(/Agent$|Gate$/, "");
}

function extToneClass(status: ExternalAgentState["status"]): string {
  if (status === "working") return styles.tone_work;
  if (status === "waiting_approval" || status === "waiting_input") return styles.tone_warn;
  if (status === "failed" || status === "gate_failed" || status === "blocked") return styles.tone_err;
  if (status === "done" || status === "gate_passed") return styles.tone_ok;
  return styles.tone_neutral;
}

function extStatusShortPt(ag: ExternalAgentState): string {
  if (ag.status === "working") {
    const pct = typeof ag.progress === "number" ? ` ${Math.round(ag.progress * 100)}%` : "";
    return `Ativo${pct}`;
  }
  if (ag.status === "waiting_approval" || ag.status === "waiting_input") return "Aguardando A/B/C";
  if (ag.status === "gate_passed") return "Gate OK";
  if (ag.status === "done") return "Entregue";
  if (ag.status === "failed" || ag.status === "gate_failed") return "Falha";
  return "Pronto";
}

export interface Office3DProps {
  agents: StudioAgentState[];
  rooms: StudioRoomState[];
  externalAgents?: ExternalAgentState[];
  externalRollups?: ExternalRoomRollup[];
  externalActiveTitle?: string | null;
  activeItem: ContentItemPipeline | null;
  selectedAgent: AgentKey | null;
  loading: boolean;
  syncingExternal?: boolean;
  onSelectAgent: (agentKey: AgentKey) => void;
  onSelectRoom: (roomKey: RoomKey) => void;
  onInspectExternalAgent?: (agentKey: string) => void;
  onSyncExternal?: () => void;
  onBackToHQ?: () => void;
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

export function Office3D({
  agents,
  rooms,
  externalAgents = [],
  externalRollups = [],
  externalActiveTitle = null,
  activeItem,
  selectedAgent,
  loading,
  syncingExternal = false,
  onSelectAgent,
  onSelectRoom,
  onInspectExternalAgent,
  onSyncExternal,
  onBackToHQ,
}: Office3DProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLElement>());
  const [visible, setVisible] = useState(true);
  const [hoveredAgent, setHoveredAgent] = useState<AgentKey | null>(null);
  const [hoveredExternalKey, setHoveredExternalKey] = useState<string | null>(null);
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

  const featuredExternal = useMemo(() => {
    if (externalAgents.length === 0) return [];
    const byKey = new Map(externalAgents.map((a) => [a.agent_key, a]));
    const picked: ExternalAgentState[] = [];
    for (const k of FEATURED_EXTERNAL_KEYS) {
      const found = byKey.get(k);
      if (found) picked.push(found);
    }
    if (picked.length < 10) {
      for (const ag of externalAgents) {
        if (picked.length >= 10) break;
        if (!picked.some((p) => p.agent_key === ag.agent_key) && ag.status !== "idle") {
          picked.push(ag);
        }
      }
    }
    return picked;
  }, [externalAgents]);

  const enabled = agents.filter((a) => a.enabled);
  const extRollupMap = new Map(externalRollups.map((r) => [r.room_key, r]));
  const extWorking = externalRollups.reduce((acc, r) => acc + r.working, 0);
  const extDone = externalRollups.reduce((acc, r) => acc + r.done, 0);
  const extWaiting = externalRollups.reduce((acc, r) => acc + r.awaiting_human, 0);
  const extProblems = externalRollups.reduce((acc, r) => acc + r.failed, 0);
  const working = Math.max(enabled.filter((a) => a.status === "working").length, extWorking);
  const waiting = Math.max(enabled.filter((a) => APPROVAL.has(a.status)).length, extWaiting);
  const problems = enabled.filter((a) => PROBLEM.has(a.status)).length + extProblems;
  const roomState = new Map(rooms.map((r) => [r.room_key, r]));
  const orderedAgents = PIPELINE_ORDER.map((k) => agents.find((a) => a.agent_key === k)).filter(
    (a): a is StudioAgentState => Boolean(a)
  );

  return (
    <section className={styles.section} aria-labelledby="office-title">
      <header className={styles.header}>
        <div className={styles.titleRow}>
          {onBackToHQ && (
            <button type="button" className={styles.backToHqBtn} onClick={onBackToHQ}>
              ← Sede
            </button>
          )}
          <div>
            <div className={styles.titleLine}>
              <h2 id="office-title" className={styles.title}>
                Escritório dos agentes
              </h2>
              {externalAgents.length > 0 && (
                <span className={styles.connectedBadge}>
                  <span className={styles.pulseDot} aria-hidden="true" />
                  CONECTADO · AUTOMACAO - O OUTRO LADO ({externalAgents.length} agentes)
                </span>
              )}
            </div>
            <p className={styles.hint}>
              {activeItem
                ? `Produzindo: ${activeItem.working_title}`
                : externalActiveTitle
                  ? `Pipeline em campo: ${externalActiveTitle}`
                  : "Equipe pronta em campo"}
              {" · "}clique numa sala ou num agente 3D · arraste para girar
            </p>
          </div>
        </div>
        <div className={styles.headerRight}>
          <ul className={styles.stats} aria-label="Resumo da equipe">
            <li>
              <span className={`${styles.dot} ${styles.dotWork}`} aria-hidden="true" />
              {working} trabalhando agora
            </li>
            {extDone > 0 && (
              <li>
                <span className={`${styles.dot} ${styles.dotOk}`} aria-hidden="true" />
                {extDone} entregas / gates OK
              </li>
            )}
            <li>
              <span className={`${styles.dot} ${styles.dotWarn}`} aria-hidden="true" />
              {waiting} aguardando você
            </li>
            <li>
              <span className={`${styles.dot} ${styles.dotErr}`} aria-hidden="true" />
              {problems} com problema
            </li>
          </ul>
          {onSyncExternal && (
            <button
              type="button"
              className={styles.syncRepoBtn}
              onClick={onSyncExternal}
              disabled={syncingExternal}
              title="Sincroniza todos os agentes, takes, áudios, master MP4 e shorts da pasta AUTOMACAO - O OUTRO LADO"
            >
              {syncingExternal ? "Sincronizando…" : "↻ Sincronizar pasta conectada"}
            </button>
          )}
        </div>
      </header>

      <div
        ref={stageRef}
        className={styles.stage}
        role="group"
        aria-label="Maquete 3D do escritório com agentes internos e especialistas conectados da outra pasta caminhando e trabalhando."
      >
        <OfficeScene
          agents={agents}
          externalSpecialists={featuredExternal}
          selectedAgent={selectedAgent}
          hoveredAgent={hoveredAgent}
          hoveredExternalKey={hoveredExternalKey}
          active={visible}
          reducedMotion={reducedMotion}
          anchors={anchors}
          onSelectAgent={onSelectAgent}
          onHoverAgent={setHoveredAgent}
          onSelectExternalAgent={onInspectExternalAgent}
          onHoverExternalAgent={setHoveredExternalKey}
          onSelectRoom={onSelectRoom}
        />

        <div className={styles.overlay}>
          {ROOM_ORDER.map((key) => {
            const state = roomState.get(key);
            const ext = extRollupMap.get(key);
            const label = state?.room_label ?? ROOMS[key].label;
            const busy = (state?.working ?? 0) + (ext?.working ?? 0);
            const doneCount = ext?.done ?? 0;
            const pending = (state ? state.awaiting_human + state.failed + state.blocked : 0) + (ext ? ext.awaiting_human + ext.failed : 0);
            const description = [
              label,
              busy ? `${busy} trabalhando` : null,
              doneCount ? `${doneCount} prontos` : null,
              pending ? `${pending} pendências` : null,
            ]
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
                  {doneCount > 0 && <span className={`${styles.count} ${styles.countOk}`}>{doneCount}✓</span>}
                  {pending > 0 && <span className={`${styles.count} ${styles.countWarn}`}>{pending}</span>}
                </button>
              </div>
            );
          })}

          {orderedAgents.map((agent) => {
            const bubble = agentBubble(agent.status, agent.enabled, agent.progress);
            const showName = hoveredAgent === agent.agent_key || selectedAgent === agent.agent_key || agent.status === "working" || APPROVAL.has(agent.status);
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

          {featuredExternal.map((ext) => {
            const isHovered = hoveredExternalKey === ext.agent_key;
            const look = EXTERNAL_GROUP_LOOK[ext.group_key] ?? EXTERNAL_GROUP_LOOK.standalone;
            return (
              <div key={`ext:${ext.agent_key}`} ref={anchorRef(`ext:${ext.agent_key}`)} className={styles.anchor}>
                <button
                  type="button"
                  className={`${styles.extBadgeBtn} ${isHovered ? styles.extBadgeHover : ""}`}
                  onClick={() => onInspectExternalAgent?.(ext.agent_key)}
                  onMouseEnter={() => setHoveredExternalKey(ext.agent_key)}
                  onMouseLeave={() => setHoveredExternalKey(null)}
                  title={`${ext.display_name} (${look.badge}) — ${ext.stage_label ?? ""}`}
                >
                  <span className={styles.extSquadDot} style={{ background: look.shirt }} aria-hidden="true" />
                  <span className={styles.extBadgeName}>{shortExternalName(ext)}</span>
                  <span className={`${styles.extBadgeStatus} ${extToneClass(ext.status)}`}>
                    {extStatusShortPt(ext)}
                  </span>
                </button>
              </div>
            );
          })}
        </div>

        {agents.length === 0 && !loading && (
          <p className={styles.overlayNote}>Os agentes deste canal ainda não foram provisionados.</p>
        )}
      </div>

      {featuredExternal.length > 0 && (
        <div className={styles.squadStrip} aria-label="Especialistas da outra pasta caminhando e operando no escritório 3D">
          <div className={styles.squadStripHeader}>
            <span className={styles.squadStripTitle}>
              Agentes da Outra Pasta em Campo no 3D ({featuredExternal.length} especialistas caminhando · {externalAgents.length} conectados no total)
            </span>
            <span className={styles.squadStripHint}>
              Clique num especialista abaixo ou no boneco 3D para inspecionar logs, modelo e artefatos
            </span>
          </div>
          <div className={styles.squadStripList}>
            {featuredExternal.map((ext) => {
              const look = EXTERNAL_GROUP_LOOK[ext.group_key] ?? EXTERNAL_GROUP_LOOK.standalone;
              const roomName = ROOMS[ext.studio_room_key]?.label ?? ext.studio_room_key;
              return (
                <button
                  key={ext.agent_key}
                  type="button"
                  className={`${styles.squadCard} ${hoveredExternalKey === ext.agent_key ? styles.squadCardActive : ""}`}
                  onMouseEnter={() => setHoveredExternalKey(ext.agent_key)}
                  onMouseLeave={() => setHoveredExternalKey(null)}
                  onClick={() => onInspectExternalAgent?.(ext.agent_key)}
                >
                  <div className={styles.squadCardTop}>
                    <span className={styles.extSquadDot} style={{ background: look.shirt }} aria-hidden="true" />
                    <strong className={styles.squadCardName}>{shortExternalName(ext)}</strong>
                    <span className={`${styles.extBadgeStatus} ${extToneClass(ext.status)}`}>
                      {extStatusShortPt(ext)}
                    </span>
                  </div>
                  <div className={styles.squadCardStage}>
                    {ext.stage_label ?? ext.description}
                  </div>
                  <div className={styles.squadCardMeta}>
                    <span>{look.badge}</span>
                    <span>·</span>
                    <span>{roomName}</span>
                    {ext.model_name && (
                      <>
                        <span>·</span>
                        <span>{ext.model_name}</span>
                      </>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
