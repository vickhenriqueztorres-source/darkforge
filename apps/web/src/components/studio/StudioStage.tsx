"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  getStatusLabelPt,
  polygonToSvgPoints,
  resolveAgentPosition,
  STUDIO_LAYOUT,
  STUDIO_VIEWBOX,
} from "@/lib/studio/studio-layout";
import type { AgentKey, RoomKey, StudioAgentState, StudioRoomState } from "@/lib/studio/types";

interface StudioStageProps {
  channelName?: string;
  rooms: StudioRoomState[];
  agents: StudioAgentState[];
  selectedRoom: RoomKey | null;
  selectedAgent: AgentKey | null;
  loading: boolean;
  error: string | null;
  hudOverlay?: React.ReactNode;
  onSelectRoom: (roomKey: RoomKey, triggerEl?: HTMLButtonElement | null) => void;
  onSelectAgent: (agentKey: AgentKey) => void;
  onRetryLoad?: () => void;
}

function AgentSvgIcon({ agentKey }: { agentKey: AgentKey }) {
  switch (agentKey) {
    case "dados":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M3 16V10M8 16V4M13 16V8M18 16V6" strokeLinecap="round" />
        </svg>
      );
    case "pesquisa":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="8.5" cy="8.5" r="5" />
          <path d="M12.5 12.5L17 17" strokeLinecap="round" />
        </svg>
      );
    case "estrategia":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M3 15L8 10L12 13L17 6" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M13 6H17V10" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "titulos":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M3 9V4H8L16 12L11 17L3 9Z" strokeLinejoin="round" />
          <circle cx="6.5" cy="6.5" r="1" fill="currentColor" />
        </svg>
      );
    case "roteiro":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="4" y="3" width="12" height="14" rx="2" />
          <path d="M7 7H13M7 10H13M7 13H10" strokeLinecap="round" />
        </svg>
      );
    case "thumbnail":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="3" y="4" width="14" height="12" rx="2" />
          <circle cx="7.5" cy="8" r="1.4" />
          <path d="M4 15L8.5 10.5L12 14L14.5 11.5L17 14" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "edicao":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="3" y="5" width="14" height="11" rx="2" />
          <path d="M8.5 8.5L13 10.5L8.5 12.5V8.5Z" fill="currentColor" />
        </svg>
      );
    case "publicacao":
      return (
        <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <rect x="3" y="4" width="14" height="13" rx="2" />
          <path d="M3 8H17M7 2.5V5.5M13 2.5V5.5" strokeLinecap="round" />
        </svg>
      );
  }
}

function statusTone(status: StudioAgentState["status"]): "ok" | "warn" | "err" | "muted" {
  switch (status) {
    case "done":
      return "ok";
    case "working":
    case "needs_review":
    case "waiting_approval":
    case "waiting_input":
      return "warn";
    case "failed":
    case "blocked":
    case "no_signal":
      return "err";
    default:
      return "muted";
  }
}

function statusBadgeIcon(badge: ReturnType<typeof resolveAgentPosition>["badge"]): string {
  switch (badge) {
    case "working":
      return "⚡";
    case "clock":
      return "⏳";
    case "amber_bubble":
      return "!";
    case "approval":
      return "✋";
    case "lock":
      return "🔒";
    case "no_signal":
      return "📡";
    case "red_alert":
      return "!";
    case "check":
      return "✓";
    case "disabled":
      return "×";
    default:
      return "";
  }
}

const MIN_ZOOM = 1;
const MAX_ZOOM = 2.6;

export function StudioStage({
  channelName,
  rooms,
  agents,
  selectedRoom,
  selectedAgent,
  loading,
  error,
  hudOverlay,
  onSelectRoom,
  onSelectAgent,
  onRetryLoad,
}: StudioStageProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragOriginRef = useRef<{ clientX: number; clientY: number; panX: number; panY: number } | null>(null);

  const roomStateByKey = new Map(rooms.map((r) => [r.room_key, r]));
  const roomOrder: RoomKey[] = [
    "sala_dados",
    "pesquisa",
    "mesa_agentes",
    "gravacao",
    "design_thumbnail",
    "estrategia_publicacao",
  ];

  const clampPan = useCallback((nextX: number, nextY: number, z: number) => {
    const el = canvasRef.current;
    if (!el || z <= 1) return { x: 0, y: 0 };
    const maxX = ((z - 1) * el.clientWidth) / 2;
    const maxY = ((z - 1) * el.clientHeight) / 2;
    return {
      x: Math.max(-maxX, Math.min(maxX, nextX)),
      y: Math.max(-maxY, Math.min(maxY, nextY)),
    };
  }, []);

  const applyZoom = useCallback(
    (nextZoomRaw: number) => {
      const nextZoom = Number(Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, nextZoomRaw)).toFixed(2));
      setZoom(nextZoom);
      setPan((prev) => clampPan(prev.x, prev.y, nextZoom));
    },
    [clampPan]
  );

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Native wheel listener with passive: false so mouse wheel zooms smoothly over the diorama
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      // Allow normal scroll if user is zooming out at 1x already
      if (e.deltaY > 0 && zoom <= 1) return;
      // Ignore wheel inside HUD panels if scrolling text
      if ((e.target as HTMLElement | null)?.closest(".studio-hud-panel")) return;
      e.preventDefault();
      const step = e.deltaY < 0 ? 0.2 : -0.2;
      applyZoom(zoom + step);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoom, applyZoom]);

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (zoom <= 1) return;
    if ((e.target as HTMLElement).closest("button")) return;
    setDragging(true);
    dragOriginRef.current = {
      clientX: e.clientX,
      clientY: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging || !dragOriginRef.current) return;
    const dx = e.clientX - dragOriginRef.current.clientX;
    const dy = e.clientY - dragOriginRef.current.clientY;
    setPan(clampPan(dragOriginRef.current.panX + dx, dragOriginRef.current.panY + dy, zoom));
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    setDragging(false);
    dragOriginRef.current = null;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }
  };

  const roomSlotCounter: Record<string, number> = {};
  const gravacaoState = roomStateByKey.get("gravacao");
  const isRecordingActive = Boolean(gravacaoState && gravacaoState.working > 0);

  return (
    <div className="studio-stage-shell">
      {/* Desktop / Tablet Zoomable Interactive Stage */}
      <div
        className="studio-diorama-wrap"
        aria-label="Maquete interativa do Estúdio de Conteúdo"
      >
        <div
          ref={canvasRef}
          className={`studio-diorama-canvas ${zoom > 1 ? "is-zoomed" : ""} ${dragging ? "is-dragging" : ""}`}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        >
          {/* Floating HUD Cards stay pinned cleanly at 100% scale above the studio roof */}
          {hudOverlay && (
            <div className={`studio-hud-floating-layer ${zoom > 1.35 ? "is-dimmed-for-zoom" : ""}`}>
              {hudOverlay}
            </div>
          )}

          {/* Zoom + Pan Layer: Clean Plate + SVG Polygons + Plaques + Agents scale together */}
          <div
            className="studio-zoom-layer"
            style={{
              transform: `translate3d(${pan.x}px, ${pan.y}px, 0) scale(${zoom})`,
            }}
          >
            {/* Clean Plate 2560x1429 (WebP high-quality prioritized for sharp edges) */}
            <picture className="studio-clean-plate-pic">
              <source srcSet="/studio/studio-clean-plate.webp" type="image/webp" />
              <source srcSet="/studio/studio-clean-plate.avif" type="image/avif" />
              <img
                src="/studio/studio-clean-plate.jpg"
                alt="Maquete arquitetônica do estúdio de conteúdo com 6 salas"
                width={2560}
                height={1429}
                fetchPriority="high"
                className="studio-clean-plate-img"
                draggable={false}
              />
            </picture>

            {/* Atmospheric Vignette & Hologram Glow */}
            <div className="studio-vignette" aria-hidden="true" />
            <div className="studio-holo-beams" aria-hidden="true" />

            {/* SVG Room Polygons & Conduit Paths */}
            <svg
              className="studio-svg-overlay"
              viewBox={`0 0 ${STUDIO_VIEWBOX.width} ${STUDIO_VIEWBOX.height}`}
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <linearGradient id="selectedRoomFill" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="rgba(245, 178, 72, 0.24)" />
                  <stop offset="100%" stopColor="rgba(245, 178, 72, 0.04)" />
                </linearGradient>
              </defs>

              <g className="studio-circuit-group">
                <path d="M 350 205 L 430 245" className="studio-circuit-line" />
                <path d="M 320 315 L 415 295" className="studio-circuit-line" />
                <path d="M 605 255 L 680 215" className="studio-circuit-line" />
                <path d="M 615 285 L 675 295" className="studio-circuit-line" />
                <path d="M 600 330 L 665 385" className="studio-circuit-line" />
              </g>

              {roomOrder.map((rKey) => {
                const layout = STUDIO_LAYOUT[rKey];
                const state = roomStateByKey.get(rKey);
                const isSelected = selectedRoom === rKey;
                const isUnavailable = Boolean(state && state.agents === 0 && state.disabled_agents > 0);
                const hasAlert = Boolean(state && (state.failed > 0 || state.blocked > 0));
                const hasWorking = Boolean(state && state.working > 0);

                return (
                  <polygon
                    key={rKey}
                    points={polygonToSvgPoints(layout.polygon)}
                    className={[
                      "studio-room-poly",
                      isSelected ? "is-selected" : "",
                      isUnavailable ? "is-disabled" : "",
                      hasAlert ? "is-alert" : "",
                      hasWorking ? "is-working" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  />
                );
              })}
            </svg>

            {/* Architectural Central Monolith Signage & ON AIR Lamp */}
            <div className="studio-central-monolith-sign" aria-hidden="true">
              <span className="studio-monolith-yt">▶</span>
              <span className="studio-monolith-title">CENTRAL DE CONTEÚDO</span>
              <span className="studio-monolith-sub">{channelName || "CANAL PRINCIPAL"}</span>
            </div>

            <div
              className={`studio-on-air-lamp ${isRecordingActive ? "is-live" : ""}`}
              aria-hidden="true"
            >
              ON AIR
            </div>

            {/* Accessible Keyboard Architectural Room Plaques */}
            {roomOrder.map((rKey) => {
              const layout = STUDIO_LAYOUT[rKey];
              const state = roomStateByKey.get(rKey);
              const isSelected = selectedRoom === rKey;
              const isUnavailable = Boolean(state && state.agents === 0 && state.disabled_agents > 0);

              const statusParts: string[] = [];
              if (state) {
                statusParts.push(`${state.agents} agentes ativos`);
                if (state.working > 0) statusParts.push(`${state.working} trabalhando`);
                if (state.awaiting_human > 0) statusParts.push(`${state.awaiting_human} aguardando humano`);
                if (state.blocked > 0) statusParts.push(`${state.blocked} bloqueados`);
                if (state.failed > 0) statusParts.push(`${state.failed} com falha`);
                if (isUnavailable) statusParts.push("módulo indisponível");
              }

              return (
                <button
                  key={rKey}
                  type="button"
                  data-room-key={rKey}
                  className={[
                    "studio-room-hotspot",
                    `room-${rKey}`,
                    isSelected ? "is-selected" : "",
                    isUnavailable ? "is-disabled" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  style={{
                    left: `${layout.labelAnchor.x * 100}%`,
                    top: `${layout.labelAnchor.y * 100}%`,
                  }}
                  aria-label={`${layout.label}${statusParts.length ? ` — ${statusParts.join(", ")}` : ""}`}
                  aria-expanded={isSelected}
                  onClick={(e) => onSelectRoom(rKey, e.currentTarget)}
                >
                  <span className="studio-room-title">{layout.label.toUpperCase()}</span>
                  {state && (
                    <span className="studio-room-badges">
                      {isUnavailable ? (
                        <span className="studio-badge muted">OFF</span>
                      ) : (
                        <>
                          {state.working > 0 && (
                            <span className="studio-badge warn" title="Trabalhando">
                              ● {state.working}
                            </span>
                          )}
                          {state.awaiting_human > 0 && (
                            <span className="studio-badge info" title="Aguardando decisão humana">
                              ✋ {state.awaiting_human}
                            </span>
                          )}
                          {(state.blocked > 0 || state.failed > 0) && (
                            <span className="studio-badge err" title="Bloqueio ou falha">
                              ! {state.blocked + state.failed}
                            </span>
                          )}
                        </>
                      )}
                    </span>
                  )}
                </button>
              );
            })}

            {/* 3D Miniature Specialist Pedestals + Floating Glass Pill Tags */}
            {agents.map((agent, idx) => {
              const slotIdx = roomSlotCounter[agent.room_key] ?? 0;
              roomSlotCounter[agent.room_key] = slotIdx + 1;
              const pos = resolveAgentPosition(agent, STUDIO_LAYOUT, slotIdx, idx);
              const tone = statusTone(agent.status);
              const icon = statusBadgeIcon(pos.badge);
              const isSelected = selectedAgent === agent.agent_key;

              return (
                <button
                  key={agent.channel_agent_id}
                  type="button"
                  data-agent-key={agent.agent_key}
                  data-agent-status={agent.status}
                  className={[
                    "studio-agent-sprite",
                    `tone-${tone}`,
                    pos.animated ? "is-working" : "",
                    !agent.enabled ? "is-disabled" : "",
                    isSelected ? "is-selected" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  style={{
                    left: "0%",
                    top: "0%",
                    transform: `translate3d(calc(${pos.x * 100}cqw - 50%), calc(${pos.y * 100}cqh - 50%), 0)`,
                  }}
                  aria-label={`${agent.display_name} (${agent.agent_key}): ${getStatusLabelPt(agent.status)}`}
                  onClick={() => onSelectAgent(agent.agent_key)}
                >
                  <span className="studio-agent-figure" aria-hidden="true">
                    <span className="studio-agent-pedestal-ring" />
                    <span className="studio-agent-avatar-3d">
                      <span className="studio-mini-head" />
                      <span className="studio-mini-shoulders" />
                    </span>
                  </span>

                  <span className="studio-agent-pill">
                    <span className="studio-agent-pill-icon">
                      <AgentSvgIcon agentKey={agent.agent_key} />
                    </span>
                    <span className="studio-agent-name">{agent.display_name}</span>
                    {agent.status === "working" && agent.progress !== null && (
                      <span className="studio-agent-pct">{Math.round(agent.progress * 100)}%</span>
                    )}
                    {icon && (
                      <span className={`studio-agent-state-icon tone-${tone}`} aria-hidden="true">
                        {icon}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}

            {/* Architectural Plinth Footer */}
            <div className="studio-plinth-caption" aria-hidden="true">
              <span className="studio-plinth-yt">▶</span>
              <div className="studio-plinth-texts">
                <span className="studio-plinth-brand">ESTÚDIO DE CONTEÚDO</span>
                <span className="studio-plinth-sub">PESQUISA • ROTEIRO • PRODUÇÃO • PUBLICAÇÃO • CRESCIMENTO</span>
              </div>
            </div>
          </div>

          {/* Zoom Controls (Bottom-Right Corner) */}
          <div className="studio-zoom-controls" role="group" aria-label="Controles de zoom da maquete">
            <button
              type="button"
              className="studio-zoom-btn"
              onClick={() => applyZoom(zoom - 0.25)}
              disabled={zoom <= MIN_ZOOM}
              aria-label="Diminuir zoom"
              title="Diminuir zoom"
            >
              −
            </button>
            <button
              type="button"
              className="studio-zoom-btn studio-zoom-readout"
              onClick={resetView}
              aria-label={`Zoom atual ${Math.round(zoom * 100)}%, clique para resetar`}
              title="Resetar zoom e posição (100%)"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              type="button"
              className="studio-zoom-btn"
              onClick={() => applyZoom(zoom + 0.25)}
              disabled={zoom >= MAX_ZOOM}
              aria-label="Aumentar zoom"
              title="Aumentar zoom (ou use o scroll do mouse)"
            >
              +
            </button>
          </div>

          {loading && (
            <div className="studio-stage-overlay-msg" role="status" aria-live="polite">
              <div className="studio-skeleton-bar" />
              <span>Carregando estado real do estúdio…</span>
            </div>
          )}

          {!loading && error && (
            <div className="studio-stage-overlay-msg is-error" role="alert">
              <strong>Falha ao carregar o estúdio</strong>
              <span>{error}</span>
              {onRetryLoad && (
                <button type="button" className="btn primary" onClick={onRetryLoad}>
                  Tentar novamente
                </button>
              )}
            </div>
          )}

          {!loading && !error && agents.length === 0 && (
            <div className="studio-stage-overlay-msg" role="status">
              <span>Nenhum agente configurado neste canal ainda.</span>
            </div>
          )}
        </div>
      </div>

      {/* Mobile Accessible Room + Agent List (< 768px) */}
      <div className="studio-mobile-list" aria-label="Lista de salas e agentes do estúdio">
        {roomOrder.map((rKey) => {
          const layout = STUDIO_LAYOUT[rKey];
          const state = roomStateByKey.get(rKey);
          const roomAgents = agents.filter((a) => a.room_key === rKey);
          const isUnavailable = Boolean(state && state.agents === 0 && state.disabled_agents > 0);

          return (
            <section key={rKey} className="studio-mobile-room-card">
              <div className="studio-mobile-room-head">
                <button
                  type="button"
                  className="studio-mobile-room-btn"
                  onClick={(e) => onSelectRoom(rKey, e.currentTarget)}
                >
                  <strong>{layout.label}</strong>
                  <span className="muted">
                    {isUnavailable ? "Módulo indisponível" : `${roomAgents.filter((a) => a.enabled).length} agentes`}
                  </span>
                </button>
              </div>
              <div className="studio-mobile-agents">
                {roomAgents.length === 0 ? (
                  <span className="muted">Sem agentes nesta sala</span>
                ) : (
                  roomAgents.map((agent) => (
                    <button
                      key={agent.channel_agent_id}
                      type="button"
                      className={`studio-mobile-agent-chip tone-${statusTone(agent.status)}`}
                      onClick={() => onSelectAgent(agent.agent_key)}
                    >
                      <AgentSvgIcon agentKey={agent.agent_key} />
                      <span>{agent.display_name}</span>
                      <span className="studio-chip-status">{getStatusLabelPt(agent.status)}</span>
                    </button>
                  ))
                )}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
