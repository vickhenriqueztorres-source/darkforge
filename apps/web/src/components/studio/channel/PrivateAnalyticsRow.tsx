import type { ChannelMetricsPanel, MetricCard } from "@/lib/studio/types";
import styles from "./channel.module.css";
import { formatCount, formatRelativeIso } from "./format";

function formatMetric(card: MetricCard): string {
  if (card.value === null) return "—";
  if (card.unit === "percent") return `${card.value.toFixed(1).replace(".", ",")}%`;
  if (card.unit === "seconds") {
    const m = Math.floor(card.value / 60);
    const s = Math.round(card.value % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  }
  return formatCount(card.value);
}

/** Métricas privadas do YouTube Analytics (OAuth). Só aparece quando há pelo menos um valor real. */
export function PrivateAnalyticsRow({ metrics }: { metrics: ChannelMetricsPanel }) {
  const available = metrics.cards.filter((c) => c.availability === "available" && c.value !== null);
  if (available.length === 0) return null;

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="private-analytics-title">
      <div className={styles.sectionHead} style={{ marginBottom: 10 }}>
        <h3 id="private-analytics-title" className={styles.sectionTitle}>
          YouTube Analytics · privado
        </h3>
        <span className={styles.sectionHint}>
          Via OAuth · {metrics.stale ? "desatualizado" : `sync ${formatRelativeIso(metrics.fetched_at)}`}
        </span>
      </div>
      <dl className={styles.privateRow} style={{ margin: 0 }}>
        {available.map((card) => (
          <div key={card.key} className={styles.privateItem}>
            <dt className={styles.kpiLabel}>{card.label}</dt>
            <dd className={styles.privateValue} style={{ margin: 0 }}>
              {formatMetric(card)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
