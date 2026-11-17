import type { AgentKey, AgentVisualStatus, RoomKey, StudioAgentState } from "./types";

export const STUDIO_LAYOUT_VERSION = "clean-plate-v2-2560x1429";
export const STUDIO_VIEWBOX = { width: 1000, height: 558 } as const;

export interface NormalizedPoint {
  x: number;
  y: number;
}

export interface RoomLayout {
  key: RoomKey;
  label: string;
  polygon: NormalizedPoint[];
  labelAnchor: NormalizedPoint;
  door: NormalizedPoint;
  desks: NormalizedPoint[];
  meeting?: NormalizedPoint[];
}

export const PIPELINE_ORDER: AgentKey[] = [
  "dados",
  "pesquisa",
  "estrategia",
  "titulos",
  "roteiro",
  "thumbnail",
  "edicao",
  "publicacao",
];

export const STUDIO_LAYOUT: Record<RoomKey, RoomLayout> = {
  sala_dados: {
    key: "sala_dados",
    label: "Sala de Dados",
    polygon: [
      { x: 0.12, y: 0.22 },
      { x: 0.37, y: 0.21 },
      { x: 0.36, y: 0.43 },
      { x: 0.10, y: 0.44 },
    ],
    labelAnchor: { x: 0.21, y: 0.30 },
    door: { x: 0.35, y: 0.36 },
    desks: [{ x: 0.30, y: 0.39 }],
  },
  pesquisa: {
    key: "pesquisa",
    label: "Pesquisa",
    polygon: [
      { x: 0.05, y: 0.45 },
      { x: 0.35, y: 0.43 },
      { x: 0.31, y: 0.69 },
      { x: 0.03, y: 0.67 },
    ],
    labelAnchor: { x: 0.17, y: 0.48 },
    door: { x: 0.32, y: 0.57 },
    desks: [
      { x: 0.19, y: 0.62 },
      { x: 0.13, y: 0.56 },
    ],
  },
  mesa_agentes: {
    key: "mesa_agentes",
    label: "Agentes de IA",
    polygon: [
      { x: 0.37, y: 0.35 },
      { x: 0.65, y: 0.35 },
      { x: 0.65, y: 0.72 },
      { x: 0.36, y: 0.72 },
    ],
    labelAnchor: { x: 0.51, y: 0.43 },
    door: { x: 0.50, y: 0.71 },
    desks: [
      { x: 0.42, y: 0.54 },
      { x: 0.60, y: 0.54 },
      { x: 0.51, y: 0.62 },
    ],
    meeting: [
      { x: 0.43, y: 0.49 },
      { x: 0.51, y: 0.47 },
      { x: 0.59, y: 0.49 },
      { x: 0.60, y: 0.55 },
      { x: 0.56, y: 0.61 },
      { x: 0.46, y: 0.61 },
      { x: 0.42, y: 0.55 },
      { x: 0.51, y: 0.63 },
    ],
  },
  gravacao: {
    key: "gravacao",
    label: "Gravação",
    polygon: [
      { x: 0.67, y: 0.25 },
      { x: 0.96, y: 0.28 },
      { x: 0.94, y: 0.46 },
      { x: 0.67, y: 0.43 },
    ],
    labelAnchor: { x: 0.80, y: 0.33 },
    door: { x: 0.68, y: 0.38 },
    desks: [{ x: 0.84, y: 0.42 }],
  },
  design_thumbnail: {
    key: "design_thumbnail",
    label: "Design – Thumbnail",
    polygon: [
      { x: 0.67, y: 0.44 },
      { x: 0.94, y: 0.46 },
      { x: 0.92, y: 0.61 },
      { x: 0.66, y: 0.58 },
    ],
    labelAnchor: { x: 0.80, y: 0.49 },
    door: { x: 0.67, y: 0.53 },
    desks: [{ x: 0.80, y: 0.56 }],
  },
  estrategia_publicacao: {
    key: "estrategia_publicacao",
    label: "Estratégia e Publicação",
    polygon: [
      { x: 0.66, y: 0.58 },
      { x: 0.92, y: 0.61 },
      { x: 0.90, y: 0.81 },
      { x: 0.65, y: 0.76 },
    ],
    labelAnchor: { x: 0.78, y: 0.64 },
    door: { x: 0.66, y: 0.70 },
    desks: [{ x: 0.78, y: 0.74 }],
  },
};

export interface AgentPositionResolution {
  x: number;
  y: number;
  targetRoom: RoomKey;
  anchorKind: "desk" | "door" | "meeting";
  animated: boolean;
  badge: "none" | "working" | "clock" | "amber_bubble" | "approval" | "lock" | "red_alert" | "no_signal" | "check" | "disabled";
}

export function resolveAgentPosition(
  agent: Pick<StudioAgentState, "agent_key" | "room_key" | "status" | "enabled">,
  layout: Record<RoomKey, RoomLayout> = STUDIO_LAYOUT,
  slotIndex = 0,
  agentIndex = 0
): AgentPositionResolution {
  const room = layout[agent.room_key] ?? layout.mesa_agentes;
  const desk = room.desks[slotIndex % room.desks.length] ?? room.labelAnchor;
  const status: AgentVisualStatus = !agent.enabled ? "disabled" : agent.status;

  if (status === "disabled") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "disabled" };
  }
  if (status === "queued") {
    return { x: room.door.x, y: room.door.y, targetRoom: room.key, anchorKind: "door", animated: false, badge: "none" };
  }
  if (status === "working") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: true, badge: "working" };
  }
  if (status === "waiting_input") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "clock" };
  }
  if (status === "needs_review") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "amber_bubble" };
  }
  if (status === "waiting_approval") {
    const meetingSeats = layout.mesa_agentes.meeting ?? layout.mesa_agentes.desks;
    const seat = meetingSeats[agentIndex % meetingSeats.length];
    return {
      x: seat.x,
      y: seat.y,
      targetRoom: "mesa_agentes",
      anchorKind: "meeting",
      animated: false,
      badge: "approval",
    };
  }
  if (status === "blocked") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "lock" };
  }
  if (status === "no_signal") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "no_signal" };
  }
  if (status === "failed") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "red_alert" };
  }
  if (status === "done") {
    return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "check" };
  }
  return { x: desk.x, y: desk.y, targetRoom: room.key, anchorKind: "desk", animated: false, badge: "none" };
}

export function polygonToSvgPoints(polygon: NormalizedPoint[]): string {
  return polygon
    .map((p) => `${Math.round(p.x * STUDIO_VIEWBOX.width)},${Math.round(p.y * STUDIO_VIEWBOX.height)}`)
    .join(" ");
}

export function getStatusLabelPt(status: AgentVisualStatus): string {
  const labels: Record<AgentVisualStatus, string> = {
    idle: "Em espera",
    queued: "Na fila",
    working: "Trabalhando",
    waiting_input: "Aguardando dado",
    needs_review: "Revisão humana",
    waiting_approval: "Aguardando aprovação",
    blocked: "Bloqueado",
    no_signal: "Sem sinal",
    failed: "Falhou",
    cancelled: "Cancelado",
    done: "Concluído",
    disabled: "Indisponível",
  };
  return labels[status] ?? status;
}
