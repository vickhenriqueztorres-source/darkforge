import type { YouTubePublicVideo } from "@/lib/api";
import styles from "./channel.module.css";
import { formatAgeDays, formatCount, formatFullCount, formatRatio } from "./format";

interface ViewsBarChartProps {
  videos: YouTubePublicVideo[];
  median: number | null;
}

export function ViewsBarChart({ videos, median }: ViewsBarChartProps) {
  const chronological = videos.filter((v) => v.views !== null).slice().reverse();
  if (chronological.length < 2) {
    return <p className={styles.empty}>Poucos vídeos com views públicas para montar o gráfico.</p>;
  }

  const max = Math.max(...chronological.map((v) => v.views ?? 0), 1);
  const medianPct = median ? Math.min(100, (median / max) * 100) : null;
  const first = chronological[0];
  const last = chronological[chronological.length - 1];

  return (
    <div>
      <div className={styles.chart} role="group" aria-label="Views por vídeo, do mais antigo ao mais recente">
        {medianPct !== null && (
          <div className={styles.medianLine} style={{ bottom: `${medianPct}%` }} aria-hidden="true">
            <span className={styles.medianLabel}>mediana {formatCount(median)}</span>
          </div>
        )}
        {chronological.map((v) => {
          const pct = Math.max(2, ((v.views ?? 0) / max) * 100);
          const isOutlier = (v.outlier_ratio ?? 0) >= 2;
          const ratio = formatRatio(v.outlier_ratio);
          const label = `${v.title} — ${formatFullCount(v.views)} views${ratio ? `, ${ratio} a mediana` : ""}, ${formatAgeDays(v.age_days)}`;
          return (
            <a
              key={v.video_id}
              href={v.url}
              target="_blank"
              rel="noreferrer"
              title={label}
              aria-label={label}
              className={`${styles.bar} ${v.format === "short" ? styles.barShort : ""} ${isOutlier ? styles.barOutlier : ""}`}
              style={{ height: `${pct}%` }}
            />
          );
        })}
      </div>
      <div className={styles.chartAxis}>
        <span>{formatAgeDays(first.age_days)}</span>
        <span>{formatAgeDays(last.age_days)}</span>
      </div>
      <div className={styles.legend} style={{ marginTop: 10 }}>
        <span>
          <span className={styles.legendSwatch} style={{ background: "rgba(148,163,184,0.35)" }} aria-hidden="true" />
          Longo
        </span>
        <span>
          <span className={styles.legendSwatch} style={{ background: "rgba(148,163,184,0.18)" }} aria-hidden="true" />
          Short
        </span>
        <span>
          <span className={styles.legendSwatch} style={{ background: "var(--accent)" }} aria-hidden="true" />
          Outlier (2x+ a mediana do formato)
        </span>
      </div>
    </div>
  );
}
