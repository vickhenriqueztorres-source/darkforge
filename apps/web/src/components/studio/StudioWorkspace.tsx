"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiClientError, type ChannelDTO } from "@/lib/api";
import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";
import { buildOverviewFixture } from "@/lib/studio/__fixtures__/hq-overview";
import { applyStudioEvent, detectEventGap } from "@/lib/studio/reducer";
import { useHQNavigation } from "@/lib/studio/useHQNavigation";
import { useStudioOverview } from "@/lib/studio/useStudioOverview";
import type {
  AgentDetailResponse,
  AgentKey,
  AgentOutput,
  RoomDetailResponse,
  RoomKey,
  StudioEvent,
  StudioSnapshot,
} from "@/lib/studio/types";
import { AgentModal } from "./AgentModal";
import { RoomDrawer } from "./RoomDrawer";
import { AgentPipeline } from "./channel/AgentPipeline";
import { ChannelOverview } from "./channel/ChannelOverview";
import { OpportunityCard } from "./channel/OpportunityCard";
import { HQ } from "./hq/HQ";
import { Office3D } from "./office3d/Office3D";
import layoutStyles from "./channel/channel.module.css";

export interface StudioWorkspaceProps {
  token: string;
  workspaceId: string;
  channels: ChannelDTO[];
  activeChannelId: string;
  onSelectChannel: (channelId: string) => void;
  onNotice?: (notice: { kind: "info" | "warn" | "err"; code: string; message: string }) => void;
  onNavigateChannels?: () => void;
}

export function StudioWorkspace({
  token,
  workspaceId,
  channels,
  activeChannelId,
  onSelectChannel,
  onNotice,
  onNavigateChannels,
}: StudioWorkspaceProps) {
  const [demoCount] = useState<number | null>(() => {
    if (process.env.NODE_ENV !== "development" || typeof window === "undefined") return null;
    const raw = new URLSearchParams(window.location.search).get("demo");
    if (!raw) return null;
    const n = Number(raw);
    return Number.isFinite(n) && n >= 0 ? n : null;
  });

  const overviewState = useStudioOverview(token, workspaceId, { enabled: demoCount === null });
  const effectiveOverview =
    demoCount !== null && process.env.NODE_ENV === "development"
      ? buildOverviewFixture(demoCount)
      : overviewState.overview;

  const availableChannelIds =
    effectiveOverview?.channels.map((c) => c.channel.id) ?? channels.map((c) => c.id);
  const channelsLoaded = Boolean(effectiveOverview) || channels.length > 0;

  const handleChannelNotFound = useCallback(() => {
    onNotice?.({
      kind: "warn",
      code: "CHANNEL_NOT_FOUND",
      message: "Canal não encontrado neste workspace",
    });
  }, [onNotice]);

  const nav = useHQNavigation({
    availableChannelIds,
    channelsLoaded,
    activeChannelId,
    onSelectChannel,
    onChannelNotFound: handleChannelNotFound,
  });

  const [snapshot, setSnapshot] = useState<StudioSnapshot | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncingChannel, setSyncingChannel] = useState(false);
  const [realtimeStatus, setRealtimeStatus] = useState<"connected" | "reconnecting" | "polling">("polling");

  // New video inline form
  const [showNewVideo, setShowNewVideo] = useState(false);
  const [newVideoTitle, setNewVideoTitle] = useState("");

  // Drawers / Modals
  const [selectedRoom, setSelectedRoom] = useState<RoomKey | null>(null);
  const [roomDetail, setRoomDetail] = useState<RoomDetailResponse | null>(null);
  const [roomLoading, setRoomLoading] = useState(false);
  const lastRoomTriggerRef = useRef<HTMLButtonElement | null>(null);

  const [selectedAgent, setSelectedAgent] = useState<AgentKey | null>(null);
  const [agentDetail, setAgentDetail] = useState<AgentDetailResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);

  const selectedAgentRef = useRef<AgentKey | null>(null);
  const selectedRoomRef = useRef<RoomKey | null>(null);
  selectedAgentRef.current = selectedAgent;
  selectedRoomRef.current = selectedRoom;

  const lastEventIdRef = useRef<number>(0);

  const notifyError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiClientError) {
        onNotice?.({ kind: "warn", code: err.envelope.code, message: err.envelope.message });
      } else {
        onNotice?.({
          kind: "err",
          code: "STUDIO_ERROR",
          message: err instanceof Error ? err.message : "Erro ao operar no Estúdio.",
        });
      }
    },
    [onNotice]
  );

  // Sync ?channel= and ?item= to URL without stale frame (only in channel view)
  const syncUrlParams = useCallback(
    (chId: string, itemId?: string) => {
      if (typeof window === "undefined" || nav.viewMode !== "channel") return;
      const url = new URL(window.location.href);
      url.searchParams.delete("view");
      url.searchParams.delete("focus");
      if (chId) url.searchParams.set("channel", chId);
      else url.searchParams.delete("channel");
      if (itemId) url.searchParams.set("item", itemId);
      else url.searchParams.delete("item");
      window.history.replaceState({}, "", url.toString());
    },
    [nav.viewMode]
  );

  const fetchSnapshot = useCallback(
    async (chId: string, itemId?: string, opts?: { silent?: boolean }) => {
      if (!token || !workspaceId || !chId) {
        setSnapshot(null);
        return;
      }
      if (!opts?.silent) setLoading(true);
      setError(null);
      try {
        const snap = await api.getStudioSnapshot(token, workspaceId, chId, itemId || undefined);
        setSnapshot(snap);
        lastEventIdRef.current = snap.last_event_id ?? 0;
        const resolvedItem = snap.active_content_item?.content_item_id ?? "";
        setSelectedItemId(resolvedItem);
        syncUrlParams(chId, resolvedItem || undefined);
      } catch (err) {
        if (!opts?.silent) {
          setError(err instanceof Error ? err.message : "Falha ao carregar snapshot do estúdio.");
          setSnapshot(null);
        }
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [token, workspaceId, syncUrlParams]
  );

  // Immediately wipe previous channel state when channel changes (UI-05-T06)
  useEffect(() => {
    setSnapshot(null);
    setSelectedRoom(null);
    setSelectedAgent(null);
    setRoomDetail(null);
    setAgentDetail(null);
    lastEventIdRef.current = 0;

    if (!activeChannelId || nav.viewMode !== "channel") return;
    const urlItem =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("item") ?? undefined
        : undefined;
    fetchSnapshot(activeChannelId, urlItem);
  }, [activeChannelId, workspaceId, nav.viewMode, fetchSnapshot]);

  // Esc in channel office view returns one step back when no drawer/modal is open
  useEffect(() => {
    if (nav.viewMode !== "channel" || selectedRoom || selectedAgent) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        nav.goBackOneStep();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nav, selectedRoom, selectedAgent]);

  const loadRoomDetail = useCallback(
    async (roomKey: RoomKey, opts?: { silent?: boolean }) => {
      if (!activeChannelId) return;
      if (!opts?.silent) setRoomLoading(true);
      try {
        const det = await api.getStudioRoomDetail(token, workspaceId, activeChannelId, roomKey);
        setRoomDetail(det);
      } catch (err) {
        if (!opts?.silent) notifyError(err);
      } finally {
        if (!opts?.silent) setRoomLoading(false);
      }
    },
    [token, workspaceId, activeChannelId, notifyError]
  );

  const loadAgentDetail = useCallback(
    async (agentKey: AgentKey, opts?: { silent?: boolean }) => {
      if (!activeChannelId) return;
      if (!opts?.silent) setAgentLoading(true);
      try {
        const det = await api.getStudioAgentDetail(token, workspaceId, activeChannelId, agentKey);
        setAgentDetail(det);
      } catch (err) {
        if (!opts?.silent) notifyError(err);
      } finally {
        if (!opts?.silent) setAgentLoading(false);
      }
    },
    [token, workspaceId, activeChannelId, notifyError]
  );

  // Cursor catch-up helper (UI-03-T02 / UI-03-T03)
  const catchUpEvents = useCallback(async () => {
    if (!token || !workspaceId || !activeChannelId) return;
    try {
      const res = await api.getStudioEvents(
        token,
        workspaceId,
        activeChannelId,
        lastEventIdRef.current,
        100
      );
      if (res.events.length > 0) {
        setSnapshot((prev) => {
          if (!prev || prev.channel.id !== activeChannelId) return prev;
          let next = prev;
          for (const evt of res.events) {
            next = applyStudioEvent(next, evt);
          }
          lastEventIdRef.current = next.last_event_id;
          return next;
        });
        if (selectedAgentRef.current) {
          void loadAgentDetail(selectedAgentRef.current, { silent: true });
        }
        if (selectedRoomRef.current) {
          void loadRoomDetail(selectedRoomRef.current, { silent: true });
        }
        if (res.events.some((e) => e.event_type === "completed" || e.event_type === "output_validated")) {
          void fetchSnapshot(activeChannelId, selectedItemId || undefined, { silent: true });
        }
      }
    } catch {
      // Silent retry on next tick
    }
  }, [token, workspaceId, activeChannelId, selectedItemId, fetchSnapshot, loadAgentDetail, loadRoomDetail]);

  // Realtime + Polling fallback + online reconnect replay
  useEffect(() => {
    if (!activeChannelId || !token || !workspaceId) return;

    let channelSub: ReturnType<ReturnType<typeof getSupabaseClient>["channel"]> | null = null;
    if (isSupabaseConfigured()) {
      try {
        const supa = getSupabaseClient();
        channelSub = supa
          .channel(`studio-events-${activeChannelId}`)
          .on(
            "postgres_changes",
            {
              event: "INSERT",
              schema: "public",
              table: "agent_events",
              filter: `channel_id=eq.${activeChannelId}`,
            },
            (payload) => {
              const evt = payload.new as StudioEvent;
              if (!evt || typeof evt.id !== "number") return;
              if (detectEventGap(lastEventIdRef.current, evt.id)) {
                catchUpEvents();
                return;
              }
              setSnapshot((prev) => {
                if (!prev || prev.channel.id !== activeChannelId) return prev;
                const next = applyStudioEvent(prev, evt);
                lastEventIdRef.current = next.last_event_id;
                return next;
              });
              if (selectedAgentRef.current === evt.agent_key) {
                void loadAgentDetail(selectedAgentRef.current, { silent: true });
              }
              if (selectedRoomRef.current) {
                void loadRoomDetail(selectedRoomRef.current, { silent: true });
              }
              if (evt.event_type === "completed" || evt.event_type === "output_validated") {
                void fetchSnapshot(activeChannelId, selectedItemId || undefined, { silent: true });
              }
            }
          )
          .subscribe((status) => {
            if (status === "SUBSCRIBED") {
              setRealtimeStatus("connected");
              catchUpEvents();
            } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
              setRealtimeStatus("reconnecting");
            }
          });
      } catch {
        setRealtimeStatus("polling");
      }
    }

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        catchUpEvents();
      }
    }, 4000);

    const onOnline = () => {
      setRealtimeStatus("reconnecting");
      catchUpEvents();
    };
    window.addEventListener("online", onOnline);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", onOnline);
      if (channelSub) {
        try {
          getSupabaseClient().removeChannel(channelSub);
        } catch {
          // ignore
        }
      }
    };
  }, [activeChannelId, selectedItemId, token, workspaceId, catchUpEvents, fetchSnapshot, loadAgentDetail, loadRoomDetail]);

  // Enquanto o modal do agente estiver aberto e em execucao/fila, atualiza estado e outputs a cada 2s
  const openAgentStatus = agentDetail?.agent?.status;
  useEffect(() => {
    if (!selectedAgent || (openAgentStatus !== "queued" && openAgentStatus !== "working")) return;
    const poll = window.setInterval(() => {
      void loadAgentDetail(selectedAgent, { silent: true });
    }, 2000);
    return () => window.clearInterval(poll);
  }, [selectedAgent, openAgentStatus, loadAgentDetail]);

  const handleSelectRoom = (roomKey: RoomKey, triggerEl?: HTMLButtonElement | null) => {
    if (triggerEl) lastRoomTriggerRef.current = triggerEl;
    setSelectedRoom(roomKey);
    loadRoomDetail(roomKey);
  };

  const handleCloseRoom = useCallback(() => {
    setSelectedRoom(null);
    setRoomDetail(null);
    window.setTimeout(() => lastRoomTriggerRef.current?.focus(), 0);
  }, []);

  const handleSelectAgent = (agentKey: AgentKey) => {
    setSelectedAgent(agentKey);
    loadAgentDetail(agentKey);
  };

  const handleSelectContentItem = (itemId: string) => {
    setSelectedItemId(itemId);
    fetchSnapshot(activeChannelId, itemId || undefined);
  };

  const handleCreateVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeChannelId || !newVideoTitle.trim()) return;
    setBusy(true);
    try {
      const res = await api.createStudioContentItem(token, workspaceId, activeChannelId, {
        working_title: newVideoTitle.trim(),
        trigger_initial_agents: true,
      });
      setNewVideoTitle("");
      setShowNewVideo(false);
      await fetchSnapshot(activeChannelId, res.content_item.content_item_id ?? (res.content_item as unknown as { id: string }).id);
      onNotice?.({
        kind: "info",
        code: res.deduplicated ? "CONTENT_ITEM_DEDUP" : "CONTENT_ITEM_CREATED",
        message: res.deduplicated
          ? "Vídeo já existente selecionado."
          : `Vídeo criado e ${res.enqueued_runs.length} agentes iniciais enfileirados.`,
      });
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleSyncChannel = async () => {
    if (!activeChannelId) return;
    setSyncingChannel(true);
    try {
      await api.syncChannel(token, workspaceId, activeChannelId);
      onNotice?.({
        kind: "info",
        code: "SYNC_QUEUED",
        message: "Sincronização do canal enfileirada no Job Manager.",
      });
      await fetchSnapshot(activeChannelId, selectedItemId);
    } catch (err) {
      notifyError(err);
    } finally {
      setSyncingChannel(false);
    }
  };

  const handleRunAgent = async (agentKey: AgentKey, options?: { topic?: string }) => {
    if (!activeChannelId) return;
    setBusy(true);
    try {
      await api.runStudioAgent(token, workspaceId, activeChannelId, agentKey, {
        content_item_id: selectedItemId || null,
        reason: "manual_ui",
        topic: options?.topic?.trim() || undefined,
      });
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedRoom) await loadRoomDetail(selectedRoom, { silent: true });
      if (selectedAgent) await loadAgentDetail(selectedAgent, { silent: true });
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleCancelRun = async (runId: string) => {
    setBusy(true);
    try {
      await api.cancelStudioRun(token, workspaceId, runId);
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedAgent) await loadAgentDetail(selectedAgent);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleRetryRun = async (runId: string) => {
    setBusy(true);
    try {
      await api.retryStudioRun(token, workspaceId, runId);
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedAgent) await loadAgentDetail(selectedAgent);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleUpdateAgentConfig = async (
    agentKey: AgentKey,
    patch: {
      enabled?: boolean;
      display_name?: string;
      model_policy?: { mode: string; external_consent?: boolean };
      monthly_budget_cents?: number;
      clear_budget?: boolean;
    }
  ) => {
    if (!activeChannelId) return;
    setBusy(true);
    try {
      await api.updateStudioChannelAgent(token, workspaceId, activeChannelId, agentKey, patch);
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedAgent) await loadAgentDetail(selectedAgent);
      onNotice?.({ kind: "info", code: "AGENT_UPDATED", message: `Configuração de ${agentKey} salva.` });
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleSubmitApproval = async (
    targetKind: "agent_output" | "opportunity" | "brief" | "publication_plan",
    targetId: string,
    targetVersion: number,
    decision: "approved" | "rejected" | "changes_requested",
    reason?: string,
    confirmNeedsReview?: boolean
  ) => {
    if (!activeChannelId) return;
    setBusy(true);
    try {
      await api.submitStudioApproval(token, workspaceId, activeChannelId, {
        target_kind: targetKind,
        target_id: targetId,
        target_version: targetVersion,
        decision,
        reason,
        confirm_needs_review: confirmNeedsReview,
        content_item_id: selectedItemId || null,
      });
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedRoom) await loadRoomDetail(selectedRoom);
      onNotice?.({
        kind: "info",
        code: "APPROVAL_RECORDED",
        message: `Decisão "${decision}" registrada para ${targetKind} v${targetVersion}.`,
      });
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleReviseOutput = async (
    outputId: string,
    action: "save_version" | "discard",
    editedContent?: Record<string, unknown>,
    reason?: string
  ) => {
    setBusy(true);
    try {
      await api.reviseStudioOutput(token, workspaceId, outputId, {
        action,
        edited_content: editedContent,
        reason,
      });
      await fetchSnapshot(activeChannelId, selectedItemId);
      if (selectedRoom) await loadRoomDetail(selectedRoom);
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const handleMarkManualPublished = async (contentItemId: string, url: string) => {
    setBusy(true);
    try {
      await api.markStudioManualPublished(token, workspaceId, contentItemId, url);
      await fetchSnapshot(activeChannelId, contentItemId);
      if (selectedRoom) await loadRoomDetail(selectedRoom);
      onNotice?.({
        kind: "info",
        code: "PUBLISHED_MANUAL",
        message: "Vídeo marcado como publicado manualmente com URL validada.",
      });
    } catch (err) {
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const activeChannel = channels.find((c) => c.id === activeChannelId);

  if (nav.viewMode === "channel" && !activeChannelId && channels.length === 0) {
    return (
      <section className="card">
        <h2>Estúdio de Conteúdo</h2>
        <p className="muted">
          Crie ou selecione um canal na aba &quot;Canais &amp; Perfil&quot; para abrir o escritório 3D com a equipe de 8 agentes.
        </p>
      </section>
    );
  }

  return (
    <div className="studio-workspace">
      {/* Barra superior de controle do Studio */}
      <div className="studio-toolbar" aria-label="Controles do estúdio">
        <div className="studio-toolbar-left">
          <div className="studio-view-segmented" role="group" aria-label="Modo de visualização do estúdio">
            <button
              type="button"
              className={`studio-seg-btn ${nav.viewMode === "sede" ? "active" : ""}`}
              aria-pressed={nav.viewMode === "sede"}
              onClick={() => nav.setViewMode("sede")}
            >
              Sede
            </button>
            <button
              type="button"
              className={`studio-seg-btn ${nav.viewMode === "channel" ? "active" : ""}`}
              aria-pressed={nav.viewMode === "channel"}
              disabled={!activeChannelId && channels.length === 0}
              onClick={() => nav.setViewMode("channel")}
            >
              Estúdio do canal
            </button>
          </div>

          {nav.viewMode === "channel" && (
            <>
              <div className="studio-select-group">
                <label htmlFor="studio-channel-select" className="muted-tiny">Canal</label>
                <select
                  id="studio-channel-select"
                  className="input studio-select"
                  value={activeChannelId}
                  onChange={(e) => nav.enterChannel(e.target.value)}
                >
                  {channels.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.display_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="studio-select-group">
                <label htmlFor="studio-item-select" className="muted-tiny">Vídeo em produção</label>
                <select
                  id="studio-item-select"
                  className="input studio-select"
                  value={selectedItemId}
                  onChange={(e) => handleSelectContentItem(e.target.value)}
                  disabled={!snapshot || snapshot.content_items.length === 0}
                >
                  {!snapshot || snapshot.content_items.length === 0 ? (
                    <option value="">Nenhum vídeo ativo</option>
                  ) : (
                    snapshot.content_items.map((ci) => (
                      <option key={ci.content_item_id} value={ci.content_item_id}>
                        {ci.working_title} ({ci.stage})
                      </option>
                    ))
                  )}
                </select>
              </div>

              <button
                type="button"
                className="btn primary studio-btn-sm"
                onClick={() => setShowNewVideo((v) => !v)}
              >
                + Novo vídeo
              </button>
            </>
          )}
        </div>

        <div className="studio-toolbar-right">
          {nav.viewMode === "channel" && (
            <>
              <span className={`pill ${realtimeStatus === "connected" ? "ok" : "info"}`}>
                {realtimeStatus === "connected"
                  ? "Realtime ativo"
                  : realtimeStatus === "reconnecting"
                    ? "Reconectando…"
                    : "Sincronização cursor"}
              </span>
              <button
                type="button"
                className="btn studio-btn-sm"
                onClick={() => fetchSnapshot(activeChannelId, selectedItemId)}
                disabled={loading}
              >
                Atualizar
              </button>
            </>
          )}
          <Link href="/studio" className="btn studio-btn-sm" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}>
            Tela cheia
          </Link>
        </div>
      </div>

      {nav.viewMode === "sede" ? (
        <HQ
          overview={effectiveOverview}
          loading={demoCount === null ? overviewState.isLoading : false}
          error={demoCount === null ? overviewState.error : null}
          realtimeStatus={overviewState.realtimeStatus}
          focusedChannelId={nav.focusedChannelId}
          initialFocus={nav.isInitialFocus}
          onFocusChannel={nav.focusChannel}
          onEnterChannel={nav.enterChannel}
          onBackToOverview={nav.goToOverview}
          onPrepareStudio={overviewState.prepareStudio}
          onRetry={() => void overviewState.mutate()}
          onNavigateChannels={onNavigateChannels}
        />
      ) : (
        <>
          {showNewVideo && (
            <form className="studio-new-video-bar" onSubmit={handleCreateVideo}>
              <label htmlFor="new-video-title" className="sr-only">Título de trabalho do vídeo</label>
              <input
                id="new-video-title"
                className="input"
                required
                minLength={2}
                placeholder="Título de trabalho do novo vídeo (dispara Dados + Pesquisa)…"
                value={newVideoTitle}
                onChange={(e) => setNewVideoTitle(e.target.value)}
              />
              <button type="submit" className="btn primary studio-btn-sm" disabled={busy}>
                {busy ? "Criando…" : "Iniciar no Estúdio"}
              </button>
              <button type="button" className="btn studio-btn-sm" onClick={() => setShowNewVideo(false)}>
                Cancelar
              </button>
            </form>
          )}

          <Office3D
            agents={snapshot?.agents ?? []}
            rooms={snapshot?.rooms ?? []}
            activeItem={snapshot?.active_content_item ?? null}
            selectedAgent={selectedAgent}
            loading={loading}
            onSelectAgent={handleSelectAgent}
            onSelectRoom={(roomKey) => handleSelectRoom(roomKey)}
            onBackToHQ={nav.goToOverview}
          />

          <div className={layoutStyles.layout}>
            <ChannelOverview
              key={activeChannelId}
              token={token}
              workspaceId={workspaceId}
              channelId={activeChannelId}
              channelName={activeChannel?.display_name ?? "Canal"}
              privateMetrics={snapshot?.metrics_panel ?? null}
              latestResearch={snapshot?.latest_research ?? null}
              pesquisaAgent={snapshot?.agents.find((a) => a.agent_key === "pesquisa") ?? null}
              researchBusy={busy}
              onRunResearch={(topic) => handleRunAgent("pesquisa", topic ? { topic } : undefined)}
            />

            <aside className={layoutStyles.column} aria-label="Produção do canal">
              <OpportunityCard
                opportunity={snapshot?.latest_opportunity ?? null}
                activeItem={snapshot?.active_content_item ?? null}
                busy={busy}
                onGenerate={() => handleRunAgent("estrategia")}
                onDecide={(out, dec) =>
                  handleSubmitApproval("opportunity", out.id, out.version, dec, undefined, out.status === "needs_review")
                }
              />
              <AgentPipeline
                agents={snapshot?.agents ?? []}
                rooms={snapshot?.rooms ?? []}
                latestEventByAgent={snapshot?.latest_event_by_agent ?? {}}
                activeItem={snapshot?.active_content_item ?? null}
                loading={loading}
                error={error}
                onRetry={() => fetchSnapshot(activeChannelId, selectedItemId)}
                onSelectAgent={handleSelectAgent}
                onSelectRoom={handleSelectRoom}
              />
              <button
                type="button"
                className={layoutStyles.btn}
                onClick={handleSyncChannel}
                disabled={syncingChannel}
                title="Enfileira o sync OAuth (YouTube Analytics privado: retenção, tempo médio etc.)"
              >
                {syncingChannel ? "Enfileirando…" : "Sincronizar analytics privado (OAuth)"}
              </button>
            </aside>
          </div>
        </>
      )}

      <RoomDrawer
        roomKey={selectedRoom}
        detail={roomDetail}
        loading={roomLoading}
        activeItem={snapshot?.active_content_item ?? null}
        busy={busy}
        onClose={handleCloseRoom}
        onSelectAgent={handleSelectAgent}
        onRunAgent={handleRunAgent}
        onSubmitApproval={handleSubmitApproval}
        onReviseOutput={handleReviseOutput}
        onMarkManualPublished={handleMarkManualPublished}
      />

      <AgentModal
        agentKey={selectedAgent}
        detail={agentDetail}
        loading={agentLoading}
        busy={busy}
        onClose={() => setSelectedAgent(null)}
        onRunNow={handleRunAgent}
        onCancelRun={handleCancelRun}
        onRetryRun={handleRetryRun}
        onUpdateAgentConfig={handleUpdateAgentConfig}
      />
    </div>
  );
}
