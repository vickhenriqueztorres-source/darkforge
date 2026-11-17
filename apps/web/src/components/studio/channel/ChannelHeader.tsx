import type { YouTubePublicOverview } from "@/lib/api";
import styles from "./channel.module.css";
import { formatRelativeIso } from "./format";

interface ChannelHeaderProps {
  overview: YouTubePublicOverview;
  refreshing: boolean;
  onRefresh: () => void;
  onEditLink: () => void;
}

export function ChannelHeader({ overview, refreshing, onRefresh, onEditLink }: ChannelHeaderProps) {
  const { channel, source } = overview;
  const exact = source === "youtube_data_api_v3";

  return (
    <>
      <div className={styles.banner}>
        {channel.banner_url && (
          // eslint-disable-next-line @next/next/no-img-element -- imagens remotas do YouTube sem config de domínio
          <img className={styles.bannerImg} src={channel.banner_url} alt="" referrerPolicy="no-referrer" />
        )}
        <div className={styles.bannerFade} aria-hidden="true" />
      </div>
      <div className={styles.headerBody}>
        <div className={styles.identity}>
          {channel.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- imagens remotas do YouTube sem config de domínio
            <img
              className={styles.avatar}
              src={channel.avatar_url}
              alt={`Avatar do canal ${channel.title}`}
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className={styles.avatar} aria-hidden="true" />
          )}
          <div>
            <h2 className={styles.channelName}>{channel.title || "Canal sem nome"}</h2>
            <div className={styles.channelMeta}>
              {channel.handle && <span>{channel.handle}</span>}
              <span
                className={`${styles.sourceBadge} ${exact ? styles.sourceBadgeExact : ""}`}
                title={
                  exact
                    ? "Números exatos via YouTube Data API v3"
                    : "Página pública + RSS: inscritos arredondados, 15 vídeos mais recentes"
                }
              >
                {exact ? "Data API v3 · exato" : "Página pública + RSS"}
              </span>
              <span>Atualizado {formatRelativeIso(overview.fetched_at)}</span>
            </div>
          </div>
        </div>
        <div className={styles.headerActions}>
          <button type="button" className={styles.btn} onClick={onEditLink}>
            Trocar canal
          </button>
          <a className={styles.btn} href={channel.url} target="_blank" rel="noreferrer">
            Abrir no YouTube
          </a>
          <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "Atualizando…" : "Atualizar dados"}
          </button>
        </div>
      </div>
    </>
  );
}
