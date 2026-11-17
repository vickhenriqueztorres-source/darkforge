"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiClientError } from "@/lib/api";
import type { HQFilter, StudioOverview, StudioOverviewChannel } from "@/lib/studio/hq-types";
import {
  isChannelConnected,
  matchesFilter,
  studioAwaitingCount,
  studioLamp,
  studioProblemCount,
  studioWorkingCount,
} from "@/lib/studio/hq-status";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { OverviewRealtimeStatus } from "@/lib/studio/useStudioOverview";
import { AGENT_LOOK, agentBubble } from "@/components/studio/office3d/layout3d";
import { assignChannelColors } from "./hqColors";
import { channelInitials } from "./signText";
import { StudioCardList } from "./StudioCardList";
import { HQFocusPanel } from "./HQFocusPanel";
import type { PerfSnapshot } from "./PerfProbe";
import styles from "./hq.module.css";

const HQScene = dynamic(() => import("./HQScene"), {
  ssr: false,
  loading: () => <div className={styles.loading}>Montando a Sede 3D…</div>,
});

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

function useIsMobileViewport() {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    setMobile(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setMobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return mobile;
}

function detectWebGL(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGLRenderingContext && (canvas.getContext("webgl2") || canvas.getContext("webgl")));
  } catch {
    return false;
  }
}

export function formatMinutesAgo(iso: string | null, nowMs = Date.now()): string | null {
  if (!iso) return null;
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return null;
  const diffMin = Math.max(0, Math.floor((nowMs - parsed) / 60000));
  if (diffMin < 1) return "Última atividade agora há pouco";
  if (diffMin < 60) return `Última atividade há ${diffMin} min`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `Última atividade há ${diffHours} h`;
  const diffDays = Math.floor(diffHours / 24);
  return `Última atividade há ${diffDays} d`;
}

const FILTER_DEFS: Array<{ id: HQFilter; label: string }> = [
  { id: "all", label: "Todos" },
  { id: "working", label: "Trabalhando" },
  { id: "awaiting", label: "Aguardando você" },
  { id: "problem", label: "Com problema" },
  { id: "unprovisioned", label: "Sem agentes" },
];

export interface HQProps {
  overview: StudioOverview | undefined;
  loading: boolean;
  error: unknown;
  realtimeStatus: OverviewRealtimeStatus;
  focusedChannelId: string | null;
  initialFocus: boolean;
  onFocusChannel: (channelId: string) => void;
  onEnterChannel: (channelId: string) => void;
  onBackToOverview: () => void;
  onPrepareStudio: (channelId: string) => Promise<void>;
  onRetry: () => void;
  onNavigateChannels?: () => void;
}

export function HQ({
  overview,
  loading,
  error,
  realtimeStatus,
  focusedChannelId,
  initialFocus,
  onFocusChannel,
  onEnterChannel,
  onBackToOverview,
  onPrepareStudio,
  onRetry,
  onNavigateChannels,
}: HQProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLElement>());
  const listButtonRefs = useRef(new Map<string, HTMLButtonElement>());
  const lastFocusedIdRef = useRef<string | null>(null);

  const [visible, setVisible] = useState(true);
  const [hoveredChannelId, setHoveredChannelId] = useState<string | null>(null);
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null);
  const [filter, setFilter] = useState<HQFilter>("all");
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [pageOffset, setPageOffset] = useState(0);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [webglAvailable, setWebglAvailable] = useState(true);
  const [perfSample, setPerfSample] = useState<PerfSnapshot | null>(null);

  const reducedMotion = usePrefersReducedMotion();
  const isMobile = useIsMobileViewport();

  useEffect(() => {
    setWebglAvailable(detectWebGL());
  }, []);

  const perfEnabled = useMemo(() => {
    if (process.env.NODE_ENV !== "development" || typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("perf") === "1";
  }, []);

  useEffect(() => {
    const el = stageRef.current;
    if (!el || isMobile || !webglAvailable) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(el);
    return () => observer.disconnect();
  }, [isMobile, webglAvailable]);

  // 150ms debounced search -> highlights & flies to matching studio
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const q = searchInput.trim().toLowerCase();
      setDebouncedSearch(q);
      if (q && overview) {
        const idx = overview.channels.findIndex(
          (c) =>
            c.channel.display_name.toLowerCase().includes(q) ||
            (c.channel.handle ?? "").toLowerCase().includes(q)
        );
        if (idx >= 0) {
          const targetPage = Math.floor(idx / 24) * 24;
          if (targetPage !== pageOffset) setPageOffset(targetPage);
          onFocusChannel(overview.channels[idx].channel.id);
        }
      }
    }, 150);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only trigger flyTo when query changes
  }, [searchInput]);

  const handleCloseFocus = useCallback(() => {
    const prevId = focusedChannelId ?? lastFocusedIdRef.current;
    onBackToOverview();
    if (prevId) {
      window.setTimeout(() => listButtonRefs.current.get(prevId)?.focus(), 0);
    }
  }, [focusedChannelId, onBackToOverview]);

  useEffect(() => {
    if (focusedChannelId) lastFocusedIdRef.current = focusedChannelId;
  }, [focusedChannelId]);

  useEffect(() => {
    if (!focusedChannelId) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleCloseFocus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [focusedChannelId, handleCloseFocus]);

  const anchorRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) anchors.current.set(id, el);
      else anchors.current.delete(id);
    },
    []
  );

  const channels = useMemo(() => overview?.channels ?? [], [overview]);
  const pagedChannels = useMemo(() => channels.slice(pageOffset, pageOffset + 24), [channels, pageOffset]);
  const colors = useMemo(() => assignChannelColors(pagedChannels.map((c) => c.channel.id)), [pagedChannels]);

  const filterCounts = useMemo(() => {
    const counts: Record<HQFilter, number> = {
      all: channels.length,
      working: 0,
      awaiting: 0,
      problem: 0,
      unprovisioned: 0,
    };
    for (const c of channels) {
      if (matchesFilter(c, "working")) counts.working++;
      if (matchesFilter(c, "awaiting")) counts.awaiting++;
      if (matchesFilter(c, "problem")) counts.problem++;
      if (matchesFilter(c, "unprovisioned")) counts.unprovisioned++;
    }
    return counts;
  }, [channels]);

  const searchHighlightId = useMemo(() => {
    if (!debouncedSearch) return null;
    const hit = pagedChannels.find(
      (c) =>
        c.channel.display_name.toLowerCase().includes(debouncedSearch) ||
        (c.channel.handle ?? "").toLowerCase().includes(debouncedSearch)
    );
    return hit?.channel.id ?? null;
  }, [debouncedSearch, pagedChannels]);

  const focusedChannel: StudioOverviewChannel | null = useMemo(
    () => (focusedChannelId ? channels.find((c) => c.channel.id === focusedChannelId) ?? null : null),
    [focusedChannelId, channels]
  );

  const hoveredChannel: StudioOverviewChannel | null = useMemo(
    () => (hoveredChannelId ? pagedChannels.find((c) => c.channel.id === hoveredChannelId) ?? null : null),
    [hoveredChannelId, pagedChannels]
  );

  const handleFocusOrEnter = useCallback(
    (id: string) => {
      if (focusedChannelId === id) {
        onEnterChannel(id);
      } else {
        onFocusChannel(id);
      }
    },
    [focusedChannelId, onEnterChannel, onFocusChannel]
  );

  const totalPages = Math.max(1, Math.ceil(channels.length / 24));
  const currentPage = Math.floor(pageOffset / 24);
  const show3DScene = !isMobile && webglAvailable;

  // Loading state
  if (loading && !overview) {
    return (
      <section className={styles.section} aria-labelledby="hq-title" aria-busy="true">
        <header className={styles.header}>
          <div>
            <h2 id="hq-title" className={styles.title}>Sede DarkForge</h2>
            <p className={styles.hint}>Carregando estúdios do workspace…</p>
          </div>
        </header>
        <div className={styles.skeletonLayout}>
          <div className={styles.skeletonList}>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className={styles.skeletonCard} />
            ))}
          </div>
          <div className={styles.skeletonBuilding}>
            <div className={styles.skeletonPlate} />
          </div>
        </div>
      </section>
    );
  }

  // Error state
  if (error && !overview) {
    const code = error instanceof ApiClientError ? error.envelope.code : "STUDIO_OVERVIEW_ERROR";
    const msg = error instanceof Error ? error.message : "Falha ao carregar a Sede dos canais.";
    return (
      <section className={styles.section} aria-labelledby="hq-title" role="alert">
        <header className={styles.header}>
          <div>
            <h2 id="hq-title" className={styles.title}>Sede DarkForge</h2>
          </div>
        </header>
        <div className={styles.stateBox}>
          <p className={styles.errorCode}>[{code}]</p>
          <p className={styles.stateMessage}>{msg}</p>
          <button type="button" className="btn primary studio-btn-sm" onClick={onRetry}>
            Tentar de novo
          </button>
        </div>
      </section>
    );
  }

  // Empty workspace (no channels)
  if (overview && overview.channels.length === 0) {
    return (
      <section className={styles.section} aria-labelledby="hq-title">
        <header className={styles.header}>
          <div>
            <h2 id="hq-title" className={styles.title}>Sede DarkForge</h2>
            <p className={styles.hint}>0 canais · 0 trabalhando · 0 aguardando você · 0 com problema</p>
          </div>
        </header>
        <div className={styles.emptyReception}>
          <svg width="180" height="104" viewBox="0 0 180 104" aria-hidden="true" className={styles.emptySvg}>
            <rect x="10" y="72" width="160" height="20" rx="6" fill="#1b2129" stroke="#334155" />
            <rect x="48" y="42" width="84" height="32" rx="4" fill="#5b3d28" stroke="#8a5f3f" />
            <rect x="52" y="16" width="76" height="18" rx="3" fill="#1f262e" stroke="#f5a623" />
            <text x="90" y="28" textAnchor="middle" fontSize="9" fontWeight="700" fill="#f5a623">DARKFORGE</text>
          </svg>
          <h3 className={styles.emptyTitle}>Recepção vazia — nenhum canal conectado</h3>
          <p className={styles.emptySub}>
            Conecte seu primeiro canal do YouTube para inaugurar o primeiro estúdio na Sede.
          </p>
          {onNavigateChannels && (
            <button type="button" className="btn primary studio-btn-sm" onClick={onNavigateChannels}>
              Conectar canal
            </button>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className={styles.section} aria-labelledby="hq-title">
      <header className={styles.header}>
        <div>
          <h2 id="hq-title" className={styles.title}>
            Sede DarkForge
          </h2>
          <p className={styles.hint}>
            {overview
              ? `${overview.totals.channels} canais · ${overview.totals.working} trabalhando · ${overview.totals.awaiting_human} aguardando você · ${overview.totals.problems} com problema`
              : "Visão geral dos estúdios"}
          </p>
        </div>

        <div className={styles.headerRight}>
          <label htmlFor="hq-channel-search" className="sr-only">Buscar canal</label>
          <input
            id="hq-channel-search"
            type="search"
            className={`input ${styles.searchInput}`}
            placeholder="Buscar canal…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          <span className={`pill ${realtimeStatus === "connected" ? "ok" : "info"}`}>
            {realtimeStatus === "connected"
              ? "Realtime ativo"
              : realtimeStatus === "reconnecting"
                ? "Reconectando…"
                : "Polling 15s"}
          </span>
        </div>
      </header>

      <div className={styles.filterBar} role="toolbar" aria-label="Filtrar estúdios por estado">
        <div className={styles.filterChips}>
          {FILTER_DEFS.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`${styles.filterChip} ${filter === f.id ? styles.filterChipActive : ""}`}
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
            >
              <span>{f.label}</span>
              <span className={styles.filterCount}>{filterCounts[f.id]}</span>
            </button>
          ))}
        </div>

        {totalPages > 1 && (
          <div className={styles.pagination} aria-label="Paginação de alas">
            {Array.from({ length: totalPages }).map((_, idx) => (
              <button
                key={idx}
                type="button"
                className={`${styles.pageBtn} ${currentPage === idx ? styles.pageBtnActive : ""}`}
                onClick={() => setPageOffset(idx * 24)}
              >
                Ala {idx + 1} ({idx * 24 + 1}–{Math.min((idx + 1) * 24, channels.length)})
              </button>
            ))}
          </div>
        )}
      </div>

      {!webglAvailable && !isMobile && (
        <p className={styles.webglNotice} role="status">
          WebGL indisponível neste navegador — exibindo a lista acessível dos estúdios.
        </p>
      )}

      <div className={show3DScene ? styles.workspaceGrid : styles.mobileStack}>
        <StudioCardList
          channels={pagedChannels}
          filter={filter}
          searchQuery={debouncedSearch}
          focusedChannelId={focusedChannelId}
          mode={show3DScene ? "sidebar" : "cards"}
          collapsed={show3DScene ? listCollapsed : false}
          onToggleCollapse={show3DScene ? () => setListCollapsed((v) => !v) : undefined}
          onFocusOrEnter={handleFocusOrEnter}
          onEnterChannel={onEnterChannel}
          onPrepareStudio={(id) => void onPrepareStudio(id)}
          buttonRefs={listButtonRefs}
        />

        {show3DScene && overview && (
          <div
            ref={stageRef}
            className={styles.stage}
            role="group"
            aria-label="Maquete 3D da Sede DarkForge. A lista Estúdios dos canais ao lado tem as mesmas ações acessíveis por teclado."
          >
            <HQScene
              overview={overview}
              pageOffset={pageOffset}
              filter={filter}
              searchHighlightId={searchHighlightId}
              focusedChannelId={focusedChannelId}
              hoveredChannelId={hoveredChannelId}
              initialFocus={initialFocus}
              active={visible}
              reducedMotion={reducedMotion}
              perfEnabled={perfEnabled}
              anchors={anchors}
              onFocusChannel={onFocusChannel}
              onEnterChannel={onEnterChannel}
              onHoverChannel={setHoveredChannelId}
              onHoverAgent={(k) => setHoveredAgent(k)}
              onPerfSample={setPerfSample}
            />

            <div className={styles.overlay} aria-hidden="true">
              {pagedChannels.map((ch) => {
                if (ch.channel.id === focusedChannelId) return null;
                const lamp = studioLamp(ch);
                if (lamp !== "awaiting" && lamp !== "problem") return null;
                return (
                  <div key={ch.channel.id} ref={anchorRef(`studio:${ch.channel.id}`)} className={styles.anchor}>
                    <span className={`${styles.bubble} ${lamp === "problem" ? styles.tone_problem : styles.tone_awaiting}`}>
                      {lamp === "problem" ? "Falhou" : "! Aguardando você"}
                    </span>
                  </div>
                );
              })}

              {focusedChannel &&
                focusedChannel.provisioned &&
                PIPELINE_ORDER.map((agentKey) => {
                  const agent = focusedChannel.agents.find((a) => a.agent_key === agentKey);
                  if (!agent) return null;
                  const bubble = agentBubble(agent.status, agent.enabled, agent.progress);
                  const showName = hoveredAgent === agentKey;
                  if (!bubble && !showName) return null;
                  return (
                    <div key={`agent:${agentKey}`} ref={anchorRef(`agent:${agentKey}`)} className={styles.anchor}>
                      <div className={styles.agentBubbleWrap}>
                        {showName && <span className={styles.agentNameTag}>{AGENT_LOOK[agentKey].name}</span>}
                        {bubble && <span className={`${styles.bubble} ${styles[`agentTone_${bubble.tone}`]}`}>{bubble.text}</span>}
                      </div>
                    </div>
                  );
                })}

              {hoveredChannel && (
                <div ref={anchorRef(`hover:${hoveredChannel.channel.id}`)} className={styles.anchor}>
                  <div className={styles.hoverCard}>
                    <div className={styles.hoverTop}>
                      <span
                        className={styles.cardAvatar}
                        style={{ backgroundColor: colors.get(hoveredChannel.channel.id) ?? "#3f8f8a" }}
                      >
                        {hoveredChannel.channel.avatar_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={hoveredChannel.channel.avatar_url} alt="" className={styles.cardAvatarImg} />
                        ) : (
                          channelInitials(hoveredChannel.channel.display_name)
                        )}
                      </span>
                      <div>
                        <div className={styles.hoverName}>{hoveredChannel.channel.display_name}</div>
                        {hoveredChannel.channel.handle && (
                          <div className={styles.hoverHandle}>{hoveredChannel.channel.handle}</div>
                        )}
                      </div>
                    </div>
                    <div className={styles.hoverCounts}>
                      {!isChannelConnected(hoveredChannel)
                        ? "Desconectado"
                        : !hoveredChannel.provisioned
                          ? "Em obras (sem agentes)"
                          : `${studioWorkingCount(hoveredChannel)} trabalhando · ${studioAwaitingCount(hoveredChannel)} aguardando você · ${studioProblemCount(hoveredChannel)} com problema`}
                    </div>
                    {hoveredChannel.active_item && (
                      <div className={styles.hoverActive}>
                        Produzindo: {hoveredChannel.active_item.working_title}
                      </div>
                    )}
                    {formatMinutesAgo(hoveredChannel.last_event_at) && (
                      <div className={styles.hoverTime}>{formatMinutesAgo(hoveredChannel.last_event_at)}</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {perfEnabled && perfSample && (
              <div className={styles.perfBadge} data-testid="hq-perf-probe">
                {perfSample.fps} FPS · {perfSample.drawCalls} draw calls · {perfSample.triangles} tris
              </div>
            )}
          </div>
        )}

        {focusedChannel && (
          <HQFocusPanel
            channel={focusedChannel}
            color={colors.get(focusedChannel.channel.id) ?? "#3f8f8a"}
            onEnter={onEnterChannel}
            onClose={handleCloseFocus}
            onPrepareStudio={onPrepareStudio}
          />
        )}
      </div>
    </section>
  );
}
