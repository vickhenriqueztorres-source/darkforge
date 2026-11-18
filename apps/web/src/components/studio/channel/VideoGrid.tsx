"use client";

import { useMemo, useState } from "react";
import type { YouTubePublicVideo } from "@/lib/api";
import styles from "./channel.module.css";
import { formatAgeDays, formatCount, formatDuration, formatRatio } from "./format";

type FormatFilter = "all" | "long" | "short";
type SortKey = "recent" | "views" | "outlier";

const FORMAT_OPTIONS: { key: FormatFilter; label: string }[] = [
  { key: "all", label: "Todos" },
  { key: "long", label: "Longos" },
  { key: "short", label: "Shorts" },
];

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "recent", label: "Recentes" },
  { key: "views", label: "Mais vistos" },
  { key: "outlier", label: "Outliers" },
];

interface VideoGridProps {
  videos: YouTubePublicVideo[];
  bestVideoId: string | null;
}

export function VideoGrid({ videos, bestVideoId }: VideoGridProps) {
  const [formatFilter, setFormatFilter] = useState<FormatFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("recent");

  const visible = useMemo(() => {
    const filtered = formatFilter === "all" ? videos : videos.filter((v) => v.format === formatFilter);
    const sorted = filtered.slice();
    if (sortKey === "views") sorted.sort((a, b) => (b.views ?? -1) - (a.views ?? -1));
    if (sortKey === "outlier") sorted.sort((a, b) => (b.outlier_ratio ?? -1) - (a.outlier_ratio ?? -1));
    return sorted;
  }, [videos, formatFilter, sortKey]);

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="video-grid-title">
      <div className={styles.sectionHead}>
        <div>
          <h3 id="video-grid-title" className={styles.sectionTitle}>
            Vídeos recentes
          </h3>
          <span className={styles.sectionHint}>{videos.length} vídeos na amostra</span>
        </div>
        <div className={styles.controls}>
          <div className={styles.segmented} role="group" aria-label="Filtrar por formato">
            {FORMAT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                aria-pressed={formatFilter === opt.key}
                className={`${styles.segment} ${formatFilter === opt.key ? styles.segmentActive : ""}`}
                onClick={() => setFormatFilter(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className={styles.segmented} role="group" aria-label="Ordenar vídeos">
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                aria-pressed={sortKey === opt.key}
                className={`${styles.segment} ${sortKey === opt.key ? styles.segmentActive : ""}`}
                onClick={() => setSortKey(opt.key)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {visible.length === 0 ? (
        <p className={styles.empty}>Nenhum vídeo neste filtro.</p>
      ) : (
        <ul className={styles.grid} style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {visible.map((v) => (
            <li key={v.video_id}>
              <VideoCard video={v} isBest={v.video_id === bestVideoId} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function VideoCard({ video, isBest }: { video: YouTubePublicVideo; isBest: boolean }) {
  const ratio = (video.outlier_ratio ?? 0) >= 1.5 ? formatRatio(video.outlier_ratio) : null;
  const duration = formatDuration(video.duration_seconds);
  const cornerChip = video.live ? "AO VIVO" : video.format === "short" ? "SHORT" : duration;

  const [src, setSrc] = useState(video.thumbnail_url ?? video.thumbnail_fallback_url ?? null);
  const handleError = () => {
    if (video.thumbnail_fallback_url && src !== video.thumbnail_fallback_url) setSrc(video.thumbnail_fallback_url);
  };
  const isVertical = video.format === "short" && src === video.thumbnail_url;

  return (
    <a className={styles.card} href={video.url} target="_blank" rel="noreferrer">
      <div className={styles.thumb}>
        {src && isVertical && (
          // eslint-disable-next-line @next/next/no-img-element -- thumbnails remotas do YouTube sem config de domínio
          <img className={styles.thumbBackdrop} src={src} alt="" aria-hidden="true" loading="lazy" referrerPolicy="no-referrer" />
        )}
        {src && (
          // eslint-disable-next-line @next/next/no-img-element -- thumbnails remotas do YouTube sem config de domínio
          <img
            className={isVertical ? styles.thumbVertical : styles.thumbImg}
            src={src}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={handleError}
          />
        )}
        {ratio ? (
          <span className={`${styles.chip} ${styles.chipOutlier}`} title="Views em relação à mediana do mesmo formato">
            {ratio} mediana
          </span>
        ) : isBest ? (
          <span className={`${styles.chip} ${styles.chipBest}`}>Mais visto</span>
        ) : null}
        {cornerChip && <span className={`${styles.chip} ${styles.chipDuration}`}>{cornerChip}</span>}
      </div>
      <p className={styles.cardTitle}>{video.title}</p>
      <div className={styles.cardMeta}>
        <span>
          {formatCount(video.views)} {video.views === 1 ? "view" : "views"}
        </span>
        {video.likes !== null && (
          <>
            <span aria-hidden="true">·</span>
            <span>
              {formatCount(video.likes)} {video.likes === 1 ? "like" : "likes"}
            </span>
          </>
        )}
        <span aria-hidden="true">·</span>
        <span>{formatAgeDays(video.age_days)}</span>
      </div>
    </a>
  );
}
