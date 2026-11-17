"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, ApiClientError, type ChannelYouTubeOverviewResponse } from "@/lib/api";
import type { ChannelMetricsPanel } from "@/lib/studio/types";
import styles from "./channel.module.css";
import { ChannelHeader } from "./ChannelHeader";
import { ChannelKpis } from "./ChannelKpis";
import { LinkYouTubeForm } from "./LinkYouTubeForm";
import { PrivateAnalyticsRow } from "./PrivateAnalyticsRow";
import { VideoGrid } from "./VideoGrid";
import { ViewsBarChart } from "./ViewsBarChart";

export function overviewKey(workspaceId: string, channelId: string) {
  return `yt-overview:${workspaceId}:${channelId}`;
}

interface ChannelOverviewProps {
  token: string;
  workspaceId: string;
  channelId: string;
  channelName: string;
  privateMetrics?: ChannelMetricsPanel | null;
}

export function ChannelOverview({ token, workspaceId, channelId, channelName, privateMetrics }: ChannelOverviewProps) {
  const [refreshing, setRefreshing] = useState(false);
  const [editingLink, setEditingLink] = useState(false);

  const { data, error, isLoading, mutate } = useSWR<ChannelYouTubeOverviewResponse, unknown>(
    token && workspaceId && channelId ? overviewKey(workspaceId, channelId) : null,
    () => api.getChannelYouTubeOverview(token, workspaceId, channelId),
    { revalidateOnFocus: false, dedupingInterval: 60_000, shouldRetryOnError: false }
  );

  const needsLink = error instanceof ApiClientError && error.status === 409;

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await mutate(api.getChannelYouTubeOverview(token, workspaceId, channelId, true), { revalidate: false });
    } finally {
      setRefreshing(false);
    }
  };

  const handleLink = async (channelRef: string) => {
    const res = await api.linkChannelYouTube(token, workspaceId, channelId, channelRef);
    await mutate(
      {
        channel_link: { handle: res.channel.handle, external_channel_id: res.channel.external_channel_id ?? null },
        has_api_key: res.has_api_key,
        overview: res.overview,
      },
      { revalidate: false }
    );
    setEditingLink(false);
  };

  if (needsLink || editingLink) {
    return (
      <LinkYouTubeForm
        channelName={channelName}
        initialValue={data?.channel_link.handle ?? ""}
        onSubmit={handleLink}
        onCancel={editingLink ? () => setEditingLink(false) : undefined}
      />
    );
  }

  if (isLoading && !data) {
    return <OverviewSkeleton />;
  }

  if (error && !data) {
    const message = error instanceof Error ? error.message : "Falha ao carregar dados do canal.";
    return (
      <section className={`${styles.panel} ${styles.panelPad}`} role="alert">
        <h2 className={styles.sectionTitle}>Não foi possível ler o canal no YouTube</h2>
        <p className={styles.sectionHint} style={{ margin: "6px 0 12px" }}>
          {message}
        </p>
        <button type="button" className={styles.btn} onClick={() => mutate()}>
          Tentar de novo
        </button>
      </section>
    );
  }

  if (!data) return null;
  const { overview } = data;

  return (
    <div className={styles.column}>
      <section className={styles.panel} aria-label={`Visão geral de ${overview.channel.title}`}>
        <ChannelHeader
          overview={overview}
          refreshing={refreshing}
          onRefresh={handleRefresh}
          onEditLink={() => setEditingLink(true)}
        />
        <ChannelKpis overview={overview} />
        {overview.warnings.length > 0 && <p className={styles.warnings}>{overview.warnings.join(" ")}</p>}
      </section>

      {privateMetrics && <PrivateAnalyticsRow metrics={privateMetrics} />}

      <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="views-chart-title">
        <div className={styles.sectionHead}>
          <h3 id="views-chart-title" className={styles.sectionTitle}>
            Views por vídeo
          </h3>
          <span className={styles.sectionHint}>Do mais antigo ao mais recente · clique numa barra para abrir</span>
        </div>
        <ViewsBarChart videos={overview.videos} median={overview.insights.views_median} />
      </section>

      <VideoGrid videos={overview.videos} bestVideoId={overview.insights.best_video_id} />
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className={styles.column} aria-busy="true" aria-label="Carregando dados do canal">
      <div className={styles.panel}>
        <div className={styles.skeleton} style={{ height: 132, borderRadius: "10px 10px 0 0" }} />
        <div style={{ display: "flex", gap: 14, padding: 18 }}>
          <div className={styles.skeleton} style={{ width: 80, height: 80, borderRadius: "50%" }} />
          <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
            <div className={styles.skeleton} style={{ height: 22, width: "40%" }} />
            <div className={styles.skeleton} style={{ height: 14, width: "25%" }} />
          </div>
        </div>
      </div>
      <div className={styles.grid}>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={styles.skeleton} style={{ aspectRatio: "16 / 9" }} />
        ))}
      </div>
    </div>
  );
}
