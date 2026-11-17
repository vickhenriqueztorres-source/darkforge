import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { AgentKey, RoomKey, StudioAgentState } from "@/lib/studio/types";

export type XZ = readonly [number, number];

export interface Room3D {
  key: RoomKey;
  label: string;
  x0: number;
  x1: number;
  z0: number;
  z1: number;
  floor: string;
  door: { inner: XZ; outer: XZ } | null;
  deskRange?: readonly [number, number];
}

export const PALETTE = {
  base: "#1b2129",
  wall: "#e7e0d3",
  wallCap: "#7a5236",
  wood: "#8a5f3f",
  woodDark: "#5b3d28",
  metal: "#3b434d",
  screenOff: "#1d2833",
  screenIdle: "#4b7a99",
  screenWork: "#f5a623",
  accent: "#f5a623",
  ok: "#3fae6a",
  warn: "#f5a623",
  err: "#e0503f",
  paper: "#f4efe6",
  plant: "#4f7a4c",
} as const;

export const BUILDING = { x0: -11.5, x1: 11.5, z0: -6.5, z1: 6.5 } as const;
export const OUTER_WALL_HEIGHT = 2.4;
export const PARTITION_HEIGHT = 0.95;

export const ROOMS: Record<RoomKey, Room3D> = {
  sala_dados: {
    key: "sala_dados",
    label: "Sala de Dados",
    x0: -11.5,
    x1: -4.25,
    z0: -6.5,
    z1: 0,
    floor: "#3a4654",
    door: { inner: [-5.1, -2.2], outer: [-3.4, -2.2] },
    deskRange: [-9.6, -5.7],
  },
  pesquisa: {
    key: "pesquisa",
    label: "Pesquisa",
    x0: -11.5,
    x1: -4.25,
    z0: 0,
    z1: 6.5,
    floor: "#9c7a52",
    door: { inner: [-5.1, 4.0], outer: [-3.4, 4.0] },
  },
  mesa_agentes: {
    key: "mesa_agentes",
    label: "Sala de Pauta",
    x0: -4.25,
    x1: 4.25,
    z0: -6.5,
    z1: 6.5,
    floor: "#6e4c34",
    door: null,
  },
  gravacao: {
    key: "gravacao",
    label: "Gravação e Edição",
    x0: 4.25,
    x1: 11.5,
    z0: -6.5,
    z1: -2.17,
    floor: "#2e3036",
    door: { inner: [5.1, -3.2], outer: [3.4, -3.2] },
    deskRange: [5.7, 8.4],
  },
  design_thumbnail: {
    key: "design_thumbnail",
    label: "Design de Capa",
    x0: 4.25,
    x1: 11.5,
    z0: -2.17,
    z1: 2.17,
    floor: "#d6cfc1",
    door: { inner: [5.1, 0.9], outer: [3.4, 0.9] },
  },
  estrategia_publicacao: {
    key: "estrategia_publicacao",
    label: "Estratégia e Publicação",
    x0: 4.25,
    x1: 11.5,
    z0: 2.17,
    z1: 6.5,
    floor: "#4b5a52",
    door: { inner: [5.1, 5.3], outer: [3.4, 5.3] },
  },
};

export const ROOM_ORDER: RoomKey[] = [
  "sala_dados",
  "pesquisa",
  "mesa_agentes",
  "gravacao",
  "design_thumbnail",
  "estrategia_publicacao",
];

/** Partitions with door gaps: [axis, fixed coordinate, from, to, gap centers]. */
export const PARTITIONS: Array<{ axis: "x" | "z"; at: number; from: number; to: number; gaps: number[] }> = [
  { axis: "x", at: -4.25, from: -6.5, to: 6.5, gaps: [-2.2, 4.0] },
  { axis: "x", at: 4.25, from: -6.5, to: 6.5, gaps: [-3.2, 0.9, 5.3] },
  { axis: "z", at: 0, from: -11.5, to: -4.25, gaps: [] },
  { axis: "z", at: -2.17, from: 4.25, to: 11.5, gaps: [] },
  { axis: "z", at: 2.17, from: 4.25, to: 11.5, gaps: [] },
];
export const DOOR_WIDTH = 1.3;

export const MEETING_TABLE = { x: 0, z: 1.4, radius: 1.2 } as const;
export const HUB: XZ = [0, -3.2];
export const COFFEE_BAR: XZ = [3.1, 6.0];

const DESK_Z_OFFSET = 1.1;
const SEAT_Z_OFFSET = 1.85;

export interface DeskSlot {
  room: RoomKey;
  desk: XZ;
  seat: XZ;
}

function deskXs(room: Room3D, count: number): number[] {
  const margin = 1.4;
  const [from, to] = room.deskRange ?? [room.x0 + margin, room.x1 - margin];
  if (count <= 1) return [(from + to) / 2];
  const step = (to - from) / (count - 1);
  return Array.from({ length: count }, (_, i) => from + step * i);
}

/** Desk per agent, grouped by the room each agent belongs to. */
export function assignDesks(agents: Pick<StudioAgentState, "agent_key" | "room_key">[]): Map<AgentKey, DeskSlot> {
  const byRoom = new Map<RoomKey, AgentKey[]>();
  const ordered = PIPELINE_ORDER.map((k) => agents.find((a) => a.agent_key === k)).filter(
    (a): a is Pick<StudioAgentState, "agent_key" | "room_key"> => Boolean(a)
  );
  for (const agent of ordered) {
    const roomKey = ROOMS[agent.room_key] ? agent.room_key : "mesa_agentes";
    const list = byRoom.get(roomKey) ?? [];
    list.push(agent.agent_key);
    byRoom.set(roomKey, list);
  }
  const result = new Map<AgentKey, DeskSlot>();
  for (const [roomKey, keys] of byRoom) {
    const room = ROOMS[roomKey];
    const xs = deskXs(room, keys.length);
    keys.forEach((key, i) => {
      result.set(key, {
        room: roomKey,
        desk: [xs[i], room.z0 + DESK_Z_OFFSET],
        seat: [xs[i], room.z0 + SEAT_Z_OFFSET],
      });
    });
  }
  return result;
}

export function meetingSeat(index: number, total = 8): { pos: XZ; facing: number } {
  const angle = (index / total) * Math.PI * 2 + Math.PI / 8;
  const r = MEETING_TABLE.radius + 0.7;
  const x = MEETING_TABLE.x + Math.sin(angle) * r;
  const z = MEETING_TABLE.z + Math.cos(angle) * r;
  return { pos: [x, z], facing: Math.atan2(MEETING_TABLE.x - x, MEETING_TABLE.z - z) };
}

export function coffeeSpot(index: number): XZ {
  return [COFFEE_BAR[0] - 0.8 - (index % 3) * 0.7, COFFEE_BAR[1] - 0.9 - Math.floor(index / 3) * 0.6];
}

function avoidTable(a: XZ, b: XZ, depth = 0): XZ[] {
  const { x: cx, z: cz, radius } = MEETING_TABLE;
  const clearance = radius + 0.45;
  const dx = b[0] - a[0];
  const dz = b[1] - a[1];
  const lenSq = dx * dx + dz * dz || 1;
  const t = Math.max(0, Math.min(1, ((cx - a[0]) * dx + (cz - a[1]) * dz) / lenSq));
  const px = a[0] + dx * t;
  const pz = a[1] + dz * t;
  const dist = Math.hypot(px - cx, pz - cz);
  if (dist >= clearance || depth > 2 || t <= 0 || t >= 1) return [b];
  let nx = px - cx;
  let nz = pz - cz;
  if (dist < 1e-3) {
    nx = -dz;
    nz = dx;
  }
  const n = Math.hypot(nx, nz) || 1;
  const detour: XZ = [cx + (nx / n) * (radius + 0.75), cz + (nz / n) * (radius + 0.75)];
  return [...avoidTable(a, detour, depth + 1), ...avoidTable(detour, b, depth + 1)];
}

/** Waypoints from one spot to another, passing through doors and around the meeting table. */
export function route(fromRoom: RoomKey, fromPos: XZ, toRoom: RoomKey, toPos: XZ): XZ[] {
  const raw: XZ[] = [];
  if (fromRoom !== toRoom) {
    const from = ROOMS[fromRoom].door;
    const to = ROOMS[toRoom].door;
    if (from) raw.push(from.inner, from.outer);
    if (from && to) raw.push(HUB);
    if (to) raw.push(to.outer, to.inner);
  }
  raw.push(toPos);

  const path: XZ[] = [];
  let cursor = fromPos;
  for (const point of raw) {
    path.push(...avoidTable(cursor, point));
    cursor = point;
  }
  return path;
}

export const AGENT_LOOK: Record<AgentKey, { shirt: string; skin: string; hair: string; name: string }> = {
  dados: { shirt: "#4f7cac", skin: "#e9c4a0", hair: "#2b1d14", name: "Analista de Dados" },
  pesquisa: { shirt: "#c9894b", skin: "#c68e62", hair: "#1c1c1c", name: "Pesquisador" },
  estrategia: { shirt: "#6f9677", skin: "#f1d2b6", hair: "#a0703c", name: "Estrategista" },
  titulos: { shirt: "#e0d2b4", skin: "#8d5a3b", hair: "#1c1c1c", name: "Títulos" },
  roteiro: { shirt: "#a35d4f", skin: "#e9c4a0", hair: "#5a3b22", name: "Roteirista" },
  thumbnail: { shirt: "#e0b04a", skin: "#c68e62", hair: "#2b1d14", name: "Designer de Capa" },
  edicao: { shirt: "#5c6b7a", skin: "#f1d2b6", hair: "#1c1c1c", name: "Produção" },
  publicacao: { shirt: "#7d8f5a", skin: "#8d5a3b", hair: "#5a3b22", name: "Publicação" },
};

export function roomLabelPosition(roomKey: RoomKey): [number, number, number] {
  const room = ROOMS[roomKey];
  const onBackWall = room.z0 === BUILDING.z0 && roomKey !== "mesa_agentes";
  return onBackWall ? [room.x0 + 1.9, OUTER_WALL_HEIGHT + 0.35, room.z0] : [room.x0 + 1.7, 0.05, room.z1 - 0.5];
}

export const AGENT_LABEL_HEIGHT = 1.82;

export type BubbleTone = "work" | "neutral" | "warn" | "err" | "ok";

export function agentBubble(
  status: StudioAgentState["status"],
  enabled: boolean,
  progress: number | null
): { tone: BubbleTone; text: string } | null {
  if (!enabled || status === "disabled") return null;
  switch (status) {
    case "working":
      return { tone: "work", text: typeof progress === "number" ? `Trabalhando ${Math.round(progress * 100)}%` : "Trabalhando" };
    case "queued":
      return { tone: "neutral", text: "Na fila" };
    case "waiting_approval":
    case "needs_review":
      return { tone: "warn", text: "Aguardando você" };
    case "waiting_input":
      return { tone: "warn", text: "Precisa de dados" };
    case "failed":
      return { tone: "err", text: "Falhou" };
    case "blocked":
      return { tone: "err", text: "Bloqueado" };
    case "no_signal":
      return { tone: "err", text: "Sem sinal" };
    case "done":
      return { tone: "ok", text: "Concluído" };
    default:
      return null;
  }
}
