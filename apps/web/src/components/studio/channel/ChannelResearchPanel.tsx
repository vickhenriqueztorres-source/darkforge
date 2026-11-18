"use client";

import { useState } from "react";
import type { AgentOutput, StudioAgentState } from "@/lib/studio/types";
import styles from "./channel.module.css";

interface ResearchCandidate {
  reference_id?: string;
  url?: string;
  why_similar?: string;
  observed_at?: string;
}

interface EpisodeSuggestion {
  title: string;
  alternative_title?: string | null;
  theme: string;
  angle: string;
  thumbnail_structure?: {
    hero_object?: string;
    shock_text?: string;
    visual_composition?: string;
  };
  opening_hook?: string;
  why_now?: string;
}

const VALIDATION_LABEL: Record<string, string> = {
  validado: "Tema validado",
  fraco: "Evidência fraca",
  sem_evidencia: "Sem evidência",
};

function extractYouTubeId(url?: string): string | null {
  if (!url) return null;
  const m = url.match(/(?:[?&]v=|\/shorts\/|youtu\.be\/)([\w-]{11})/);
  return m ? m[1] : null;
}

interface ChannelResearchPanelProps {
  research: AgentOutput | null;
  pesquisaAgent: StudioAgentState | null;
  busy?: boolean;
  onRunResearch?: (topic?: string) => void;
  onCreateEpisode?: (title: string) => void;
}

export function ChannelResearchPanel({
  research,
  pesquisaAgent,
  busy = false,
  onRunResearch,
  onCreateEpisode,
}: ChannelResearchPanelProps) {
  const [topic, setTopic] = useState("");
  const isRunning = pesquisaAgent?.status === "queued" || pesquisaAgent?.status === "working";

  const content = (research?.content ?? {}) as Record<string, unknown>;
  const tv = (content.topic_validation ?? null) as { topic?: string; status?: string; reason?: string } | null;
  const candidates = Array.isArray(content.candidates) ? (content.candidates as ResearchCandidate[]) : [];
  const suggestions = Array.isArray(content.episode_suggestions)
    ? (content.episode_suggestions as EpisodeSuggestion[])
    : [];
  const limitations = Array.isArray(content.limitations) ? (content.limitations as string[]) : [];
  const badgeText = isRunning
    ? "Pesquisando…"
    : (tv?.status && VALIDATION_LABEL[tv.status]) || (research ? "Concluída" : "Aguardando");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!onRunResearch || busy) return;
    onRunResearch(topic.trim() || undefined);
  };

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="channel-research-title">
      <div className={styles.sectionHead}>
        <div>
          <h3 id="channel-research-title" className={styles.sectionTitle}>
            Pesquisa do canal
          </h3>
          <span className={styles.sectionHint}>
            {tv?.topic
              ? `Tema: ${tv.topic}${tv.reason ? ` · ${tv.reason}` : ""}`
              : "Sugestões de episódios com estrutura de thumbnail e referências do YouTube"}
          </span>
        </div>
        <span className={styles.sourceBadge}>{badgeText}</span>
      </div>

      {onRunResearch && (
        <form className={styles.linkRow} onSubmit={handleSubmit} style={{ marginBottom: 14 }}>
          <label htmlFor="channel-research-topic" className="sr-only">
            Tema ou palavra-chave para pesquisar no YouTube
          </label>
          <input
            id="channel-research-topic"
            className={styles.input}
            placeholder="Pesquisar tema ou palavra-chave (opcional — vazio usa identidade do canal)…"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            maxLength={200}
          />
          <button
            type="submit"
            className={`${styles.btn} ${styles.btnPrimary}`}
            disabled={busy || isRunning || (pesquisaAgent ? !pesquisaAgent.enabled : false)}
          >
            {isRunning ? "Pesquisando…" : "Pesquisar"}
          </button>
        </form>
      )}

      {suggestions.length > 0 && (
        <div>
          <h4 className={styles.epSectionTitle}>Sugestões de novos episódios ({suggestions.length})</h4>
          <div className={styles.epList}>
            {suggestions.map((ep, idx) => (
              <article key={`${ep.title}-${idx}`} className={styles.epCard}>
                <h5 className={styles.epTitle}>{ep.title}</h5>
                {ep.alternative_title && (
                  <div className={styles.epAltTitle}>Teste A/B: {ep.alternative_title}</div>
                )}
                <div className={styles.epMeta}>
                  <strong>Tema:</strong> {ep.theme}
                  <br />
                  <strong>Ângulo:</strong> {ep.angle}
                </div>
                {ep.thumbnail_structure && (
                  <div className={styles.epThumbBox}>
                    {ep.thumbnail_structure.shock_text && (
                      <span className={styles.epShockTag}>{ep.thumbnail_structure.shock_text}</span>
                    )}
                    {ep.thumbnail_structure.hero_object && (
                      <div>
                        <strong>Thumbnail Hero:</strong> {ep.thumbnail_structure.hero_object}
                      </div>
                    )}
                    {ep.thumbnail_structure.visual_composition && (
                      <div style={{ color: "var(--muted)" }}>{ep.thumbnail_structure.visual_composition}</div>
                    )}
                  </div>
                )}
                {ep.opening_hook && (
                  <div className={styles.epMeta}>
                    <strong>Hook (0–30s):</strong> {ep.opening_hook}
                  </div>
                )}
                {ep.why_now && (
                  <div className={styles.epMeta}>
                    <strong>Por que agora:</strong> {ep.why_now}
                  </div>
                )}
                {onCreateEpisode && (
                  <div style={{ marginTop: "auto", paddingTop: 4 }}>
                    <button
                      type="button"
                      className={styles.btn}
                      disabled={busy}
                      onClick={() => onCreateEpisode(ep.title)}
                    >
                      Iniciar este episódio
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        </div>
      )}

      {candidates.length === 0 ? (
        <p className={styles.empty}>
          {isRunning
            ? "Pesquisando referências públicas e gerando sugestões com IA…"
            : "Nenhuma referência pesquisada ainda. Clique em Pesquisar para buscar referências e sugerir novos episódios."}
        </p>
      ) : (
        <>
          <h4 className={styles.epSectionTitle}>Referências analisadas no YouTube ({candidates.length})</h4>
          <ul className={styles.grid} style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {candidates.map((c, idx) => {
              const vid = extractYouTubeId(c.url);
              const thumb = vid ? `https://i.ytimg.com/vi/${vid}/hq720.jpg` : null;
              const fallback = vid ? `https://i.ytimg.com/vi/${vid}/hqdefault.jpg` : null;
              const parts = (c.why_similar ?? "").split(" — ");
              const metaLine = parts.length > 1 ? parts[0] : "";
              const titleLine = parts.length > 1 ? parts.slice(1).join(" — ") : (c.why_similar ?? c.url ?? "Referência");

              return (
                <li key={c.reference_id ?? idx}>
                  <a
                    href={c.url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.card}
                  >
                    {thumb && (
                      <div className={styles.thumb}>
                        <img
                          src={thumb}
                          alt=""
                          loading="lazy"
                          className={styles.thumbImg}
                          onLoad={(e) => {
                            const img = e.currentTarget;
                            if (img.naturalWidth > 0 && img.naturalWidth <= 120 && fallback && img.src !== fallback) {
                              img.src = fallback;
                            }
                          }}
                          onError={(e) => {
                            const img = e.currentTarget;
                            if (fallback && img.src !== fallback) img.src = fallback;
                          }}
                        />
                      </div>
                    )}
                    <span className={styles.cardTitle}>{titleLine}</span>
                    {metaLine && <span className={styles.cardMeta}>{metaLine}</span>}
                  </a>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {limitations.length > 0 && (
        <p className={styles.warnings} style={{ marginTop: 12 }}>
          {limitations[0]}
        </p>
      )}
    </section>
  );
}
