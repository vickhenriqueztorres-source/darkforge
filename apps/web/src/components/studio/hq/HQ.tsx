"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { HQFilter, StudioOverview } from "@/lib/studio/hq-types";
import { studioLamp } from "@/lib/studio/hq-status";
import type { OverviewRealtimeStatus } from "@/lib/studio/useStudioOverview";
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
  realtimeStatus,
  focusedChannelId,
  initialFocus,
  onFocusChannel,
  onEnterChannel,
  onBackToOverview,
}: HQProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const anchors = useRef(new Map<string, HTMLElement>());
  const [visible, setVisible] = useState(true);
  const [hoveredChannelId, setHoveredChannelId] = useState<string | null>(null);
  const [filter] = useState<HQFilter>("all");
  const [perfSample, setPerfSample] = useState<PerfSnapshot | null>(null);
  const reducedMotion = usePrefersReducedMotion();

  const perfEnabled = useMemo(() => {
    if (process.env.NODE_ENV !== "development" || typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("perf") === "1";
  }, []);

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!focusedChannelId) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onBackToOverview();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [focusedChannelId, onBackToOverview]);

  const anchorRef = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) anchors.current.set(id, el);
      else anchors.current.delete(id);
    },
    []
  );

  const focusedChannel = useMemo(
    () => (focusedChannelId ? overview?.channels.find((c) => c.channel.id === focusedChannelId) ?? null : null),
    [focusedChannelId, overview]
  );

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
              : loading
                ? "Carregando canais da Sede…"
                : "Visão geral dos estúdios"}
          </p>
        </div>
        <div className={styles.headerRight}>
          <span className={`pill ${realtimeStatus === "connected" ? "ok" : "info"}`}>
            {realtimeStatus === "connected"
              ? "Realtime ativo"
              : realtimeStatus === "reconnecting"
                ? "Reconectando…"
                : "Polling 15s"}
          </span>
          {focusedChannel && (
            <>
              <button type="button" className="btn studio-btn-sm" onClick={onBackToOverview}>
                ← Voltar para a Sede
              </button>
              <button
                type="button"
                className="btn primary studio-btn-sm"
                onClick={() => onEnterChannel(focusedChannel.channel.id)}
              >
                Entrar no estúdio
              </button>
            </>
          )}
        </div>
      </header>

      <div
        ref={stageRef}
        className={styles.stage}
        role="group"
        aria-label="Maquete 3D da Sede DarkForge. Use a lista Estúdios dos canais para navegar por teclado."
      >
        {overview && overview.channels.length > 0 && (
          <>
            <HQScene
              overview={overview}
              filter={filter}
              searchHighlightId={null}
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
              onPerfSample={setPerfSample}
            />

            <div className={styles.overlay} aria-hidden="true">
              {overview.channels.slice(0, 24).map((ch) => {
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
            </div>
          </>
        )}

        {perfEnabled && perfSample && (
          <div className={styles.perfBadge} data-testid="hq-perf-probe">
            {perfSample.fps} FPS · {perfSample.drawCalls} draw calls · {perfSample.triangles} tris
          </div>
        )}
      </div>
    </section>
  );
}
