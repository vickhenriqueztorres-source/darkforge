import { getStatusLabelPt, PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type {
  AgentKey,
  ContentItemPipeline,
  RoomKey,
  StudioAgentState,
  StudioEvent,
  StudioRoomState,
} from "@/lib/studio/types";
import styles from "./channel.module.css";

const AGENT_LABELS: Record<AgentKey, string> = {
  dados: "Analista de Dados",
  pesquisa: "Pesquisador",
  estrategia: "Estrategista",
  titulos: "Títulos",
  roteiro: "Roteirista",
  thumbnail: "Designer de Capa",
  edicao: "Produção",
  publicacao: "Publicação",
};

function dotClass(agent: StudioAgentState): string {
  if (!agent.enabled) return styles.dot;
  switch (agent.status) {
    case "done":
      return `${styles.dot} ${styles.dotOk}`;
    case "working":
      return `${styles.dot} ${styles.dotWarn} ${styles.dotPulse}`;
    case "queued":
    case "needs_review":
    case "waiting_approval":
    case "waiting_input":
      return `${styles.dot} ${styles.dotWarn}`;
    case "failed":
    case "blocked":
    case "no_signal":
      return `${styles.dot} ${styles.dotErr}`;
    default:
      return styles.dot;
  }
}

interface AgentPipelineProps {
  agents: StudioAgentState[];
  rooms: StudioRoomState[];
  latestEventByAgent: Record<string, StudioEvent>;
  activeItem: ContentItemPipeline | null;
  externalActiveTitle?: string | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectAgent: (agentKey: AgentKey) => void;
  onSelectRoom: (roomKey: RoomKey, trigger: HTMLButtonElement) => void;
}

export function AgentPipeline({
  agents,
  rooms,
  latestEventByAgent,
  activeItem,
  externalActiveTitle = null,
  loading,
  error,
  onRetry,
  onSelectAgent,
  onSelectRoom,
}: AgentPipelineProps) {
  const sortedRooms = rooms.slice().sort((a, b) => a.sort_order - b.sort_order);
  const byKey = new Map(agents.map((a) => [a.agent_key, a]));
  const ordered = PIPELINE_ORDER.map((k) => byKey.get(k)).filter((a): a is StudioAgentState => Boolean(a));

  return (
    <section className={`${styles.panel} ${styles.panelPad}`} aria-labelledby="agents-title">
      <div className={styles.sectionHead} style={{ marginBottom: 6 }}>
        <div>
          <h3 id="agents-title" className={styles.sectionTitle}>
            Equipe de agentes
          </h3>
          <span className={styles.sectionHint}>
            {activeItem
              ? `Vídeo: ${activeItem.working_title}`
              : externalActiveTitle
                ? `Conectado: ${externalActiveTitle}`
                : "Equipe conectada em campo"}
          </span>
        </div>
      </div>

      {error ? (
        <div role="alert">
          <p className={styles.errorText} style={{ marginBottom: 10 }}>
            {error}
          </p>
          <button type="button" className={styles.btn} onClick={onRetry}>
            Tentar de novo
          </button>
        </div>
      ) : loading && ordered.length === 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }} aria-busy="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={styles.skeleton} style={{ height: 34 }} />
          ))}
        </div>
      ) : ordered.length === 0 ? (
        <p className={styles.empty}>Os agentes deste canal ainda não foram provisionados.</p>
      ) : (
        <ol className={styles.pipeline}>
          {ordered.map((agent, i) => {
            const status = agent.enabled ? getStatusLabelPt(agent.status) : "Desativado";
            const summary = latestEventByAgent[agent.agent_key]?.summary ?? agent.stage_label ?? agent.description;
            const name = AGENT_LABELS[agent.agent_key] ?? agent.display_name;
            return (
              <li key={agent.agent_key} className={styles.step}>
                <button
                  type="button"
                  className={styles.stepBtn}
                  onClick={() => onSelectAgent(agent.agent_key)}
                  aria-label={`${name}: ${status}. ${summary ?? ""}`}
                >
                  <span className={styles.stepIndex} aria-hidden="true">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className={styles.stepName}>{name}</span>
                  <span className={styles.stepStatus}>
                    <span className={dotClass(agent)} aria-hidden="true" />
                    {status}
                  </span>
                  {summary && <span className={styles.stepSummary}>{summary}</span>}
                  {agent.status === "working" && typeof agent.progress === "number" && (
                    <span className={styles.progress} aria-hidden="true">
                      <span
                        className={styles.progressFill}
                        style={{ display: "block", width: `${Math.round(Math.max(0, Math.min(1, agent.progress)) * 100)}%` }}
                      />
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {sortedRooms.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div className={styles.kpiLabel} style={{ marginBottom: 8 }}>
            Salas · aprovações e entregas
          </div>
          <div className={styles.controls}>
            {sortedRooms.map((room) => {
              const pending = room.awaiting_human + room.failed + room.blocked;
              return (
                <button
                  key={room.room_key}
                  type="button"
                  className={styles.btn}
                  onClick={(e) => onSelectRoom(room.room_key, e.currentTarget)}
                  aria-label={`${room.room_label}${pending ? `, ${pending} pendências` : ""}`}
                >
                  {room.room_label}
                  {pending > 0 && (
                    <span className={`${styles.chip} ${styles.chipOutlier}`} style={{ position: "static" }}>
                      {pending}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
