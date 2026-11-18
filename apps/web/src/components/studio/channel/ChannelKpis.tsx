import type { YouTubePublicOverview } from "@/lib/api";
import styles from "./channel.module.css";
import { formatAgeDays, formatCount, formatFullCount } from "./format";

interface Kpi {
  label: string;
  value: string;
  hint: string;
  muted?: boolean;
  title?: string;
}

export function ChannelKpis({ overview }: { overview: YouTubePublicOverview }) {
  const { stats, insights } = overview;
  const exact = overview.source === "youtube_data_api_v3";
  const longMedian = insights.median_by_format.long;
  const shortMedian = insights.median_by_format.short;

  const kpis: Kpi[] = [
    {
      label: "Inscritos",
      value: stats.subscribers_hidden ? "Oculto" : formatCount(stats.subscribers),
      hint: stats.subscribers_hidden ? "O canal oculta a contagem" : exact ? "Arredondado pelo YouTube" : "Valor público arredondado",
      muted: stats.subscribers_hidden,
      title: formatFullCount(stats.subscribers),
    },
    stats.total_views !== null
      ? { label: "Views totais", value: formatCount(stats.total_views), hint: "Desde a criação", title: formatFullCount(stats.total_views) }
      : {
          label: `Views (últimos ${insights.sample_size})`,
          value: formatCount(insights.views_sum),
          hint: "Total exige YOUTUBE_API_KEY",
          title: formatFullCount(insights.views_sum),
        },
    {
      label: "Vídeos",
      value: formatFullCount(stats.video_count),
      hint: `${insights.longs_count} longos · ${insights.shorts_count} shorts recentes`,
    },
    {
      label: "Mediana · longos",
      value: formatCount(longMedian ?? null),
      hint: shortMedian !== undefined ? `Shorts: ${formatCount(shortMedian)}` : "Sem shorts na amostra",
      muted: longMedian === undefined,
    },
    {
      label: "Uploads em 30 dias",
      value: formatFullCount(insights.uploads_last_30d),
      hint:
        insights.avg_days_between_uploads !== null
          ? `1 a cada ${insights.avg_days_between_uploads.toString().replace(".", ",")} dias`
          : "Cadência indisponível",
    },
    {
      label: "Último upload",
      value: formatAgeDays(insights.days_since_last_upload),
      hint:
        insights.engagement_rate_avg !== null
          ? `Engajamento médio ${insights.engagement_rate_avg.toString().replace(".", ",")}%`
          : "Engajamento exige likes públicos",
      muted: insights.days_since_last_upload === null,
    },
  ];

  return (
    <dl className={styles.kpis}>
      {kpis.map((k) => (
        <div key={k.label} className={styles.kpi}>
          <dt className={styles.kpiLabel}>{k.label}</dt>
          <dd className={`${styles.kpiValue} ${k.muted ? styles.kpiValueMuted : ""}`} style={{ margin: 0 }} title={k.title}>
            {k.value}
          </dd>
          <dd className={styles.kpiHint} style={{ margin: 0 }}>
            {k.hint}
          </dd>
        </div>
      ))}
    </dl>
  );
}
