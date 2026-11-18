import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { AgentKey } from "@/lib/studio/types";

export type XZ = readonly [number, number];
export type XYZ = readonly [number, number, number];

export const MODULE = { w: 8.4, d: 7 } as const;
export const CORRIDOR_W = 3.2;
export const LOBBY_D = 6;
export const WING_GAP = 4;
export const MAX_PER_SIDE = 6;
export const MAX_PER_WING = MAX_PER_SIDE * 2;
export const MAX_CHANNELS = 24;

export const HQ_OUTER_WALL_HEIGHT = 2.4;
export const HQ_CORRIDOR_WALL_HEIGHT = 1.6;
export const HQ_PARTITION_HEIGHT = 0.95;
export const HQ_DOOR_WIDTH = 1.3;
export const HQ_MEETING_RADIUS = 0.72;

export interface HQDeskSlot {
  index: number;
  desk: XZ;
  seat: XZ;
  facing: number;
}

export interface StudioSlot {
  channelId: string;
  index: number;
  wing: 0 | 1;
  col: number;
  side: "north" | "south";
  x0: number;
  x1: number;
  z0: number;
  z1: number;
  door: { inner: XZ; outer: XZ; centerX: number; wallZ: number };
  sign: { pos: XYZ; rotationY: number };
  lamp: XYZ;
  onAir: XYZ;
  desks: HQDeskSlot[];
  meetingTable: { x: number; z: number; radius: number };
  meeting: Array<{ pos: XZ; facing: number }>;
  plant: XZ;
  rug: { x0: number; x1: number; z0: number; z1: number };
}

export interface BuildingWall {
  axis: "x" | "z";
  at: number;
  from: number;
  to: number;
  height: number;
  gaps: number[];
}

export interface BuildingLayout {
  slots: StudioSlot[];
  overflow: number;
  wings: number;
  lobby: {
    x0: number;
    x1: number;
    z0: number;
    z1: number;
    desk: XZ;
    screen: XYZ;
    logoPos: XYZ;
    receptionist: XZ;
    plants: XZ[];
  };
  corridors: Array<{ x0: number; x1: number; z0: number; z1: number }>;
  bounds: { x0: number; x1: number; z0: number; z1: number };
  walls: BuildingWall[];
}

const DESK_X_OFFSETS = [1.55, 3.3, 5.1, 6.85] as const;
const ROW_SEAT_DEPTHS = [1.45, 3.25] as const;
const ROW_DESK_DEPTHS = [2.05, 3.85] as const;
const MEETING_DEPTH = 5.55;

function buildStudioSlot(channelId: string, index: number): StudioSlot {
  const wing: 0 | 1 = index < MAX_PER_WING ? 0 : 1;
  const localIdx = wing === 0 ? index : index - MAX_PER_WING;
  const side: "north" | "south" = localIdx % 2 === 0 ? "north" : "south";
  const col = Math.floor(localIdx / 2);

  const corridorCenterZ = wing === 0 ? 0 : (MODULE.d * 2 + CORRIDOR_W + WING_GAP);
  const corridorHalf = CORRIDOR_W / 2;

  const x0 = col * MODULE.w;
  const x1 = x0 + MODULE.w;
  const z0 = side === "north" ? corridorCenterZ - corridorHalf - MODULE.d : corridorCenterZ + corridorHalf;
  const z1 = z0 + MODULE.d;

  const doorX = (x0 + x1) / 2;
  const wallZ = side === "north" ? z1 : z0;
  const dirIntoStudio = side === "north" ? -1 : 1;

  const depthToZ = (d: number) => wallZ + dirIntoStudio * d;
  const facing = side === "north" ? Math.PI : 0;

  const desks: HQDeskSlot[] = [];
  for (let row = 0; row < 2; row++) {
    for (let c = 0; c < 4; c++) {
      const idx = row * 4 + c;
      const x = x0 + DESK_X_OFFSETS[c];
      desks.push({
        index: idx,
        desk: [x, depthToZ(ROW_DESK_DEPTHS[row])],
        seat: [x, depthToZ(ROW_SEAT_DEPTHS[row])],
        facing,
      });
    }
  }

  const mtX = doorX;
  const mtZ = depthToZ(MEETING_DEPTH);
  const meetingRadius = HQ_MEETING_RADIUS;
  const meeting = PIPELINE_ORDER.map((_, i) => {
    const angle = (i / PIPELINE_ORDER.length) * Math.PI * 2 + Math.PI / 8;
    const r = meetingRadius + 0.42;
    const mx = mtX + Math.sin(angle) * r;
    const mz = mtZ + Math.cos(angle) * r;
    return {
      pos: [mx, mz] as XZ,
      facing: Math.atan2(mtX - mx, mtZ - mz),
    };
  });

  // Sign mounted on the corridor face of the corridor wall, centered above the door
  const signOffsetZ = side === "north" ? 0.14 : -0.14;
  const signRotationY = side === "north" ? 0 : Math.PI;
  const rightSignDir = side === "north" ? 1 : -1;

  const signPos: XYZ = [doorX, 1.38, wallZ + signOffsetZ];
  const lampPos: XYZ = [doorX + rightSignDir * 1.85, 1.38, wallZ + signOffsetZ];
  const onAirPos: XYZ = [doorX, 1.82, wallZ + signOffsetZ];

  const rugZ1 = depthToZ(1.0);
  const rugZ2 = depthToZ(4.35);

  return {
    channelId,
    index,
    wing,
    col,
    side,
    x0,
    x1,
    z0,
    z1,
    door: {
      inner: [doorX, depthToZ(0.85)],
      outer: [doorX, wallZ - dirIntoStudio * 0.7],
      centerX: doorX,
      wallZ,
    },
    sign: {
      pos: signPos,
      rotationY: signRotationY,
    },
    lamp: lampPos,
    onAir: onAirPos,
    desks,
    meetingTable: { x: mtX, z: mtZ, radius: meetingRadius },
    meeting,
    plant: [x0 + 0.65, depthToZ(6.35)],
    rug: {
      x0: x0 + 1.0,
      x1: x1 - 1.0,
      z0: Math.min(rugZ1, rugZ2),
      z1: Math.max(rugZ1, rugZ2),
    },
  };
}

export function deskForAgent(slot: StudioSlot, agentKey: AgentKey): HQDeskSlot {
  const idx = PIPELINE_ORDER.indexOf(agentKey);
  return slot.desks[idx >= 0 ? idx : 0];
}

function avoidRoundTable(
  a: XZ,
  b: XZ,
  table: { x: number; z: number; radius: number },
  depth = 0
): XZ[] {
  const clearance = table.radius + 0.32;
  const dx = b[0] - a[0];
  const dz = b[1] - a[1];
  const lenSq = dx * dx + dz * dz || 1;
  const t = Math.max(0, Math.min(1, ((table.x - a[0]) * dx + (table.z - a[1]) * dz) / lenSq));
  const px = a[0] + dx * t;
  const pz = a[1] + dz * t;
  const dist = Math.hypot(px - table.x, pz - table.z);
  if (dist >= clearance || depth > 2 || t <= 0 || t >= 1) return [b];
  let nx = px - table.x;
  let nz = pz - table.z;
  if (dist < 1e-3) {
    nx = -dz;
    nz = dx;
  }
  const n = Math.hypot(nx, nz) || 1;
  const detour: XZ = [table.x + (nx / n) * (table.radius + 0.5), table.z + (nz / n) * (table.radius + 0.5)];
  return [...avoidRoundTable(a, detour, table, depth + 1), ...avoidRoundTable(detour, b, table, depth + 1)];
}

/** Simple collision-free route inside a studio module (desk <-> meeting table). */
export function routeInStudio(slot: StudioSlot, from: XZ, to: XZ): XZ[] {
  const aisleX = slot.door.centerX;
  const raw: XZ[] = [];
  if (Math.abs(from[0] - to[0]) > 1.2 && Math.abs(from[1] - to[1]) > 1.2) {
    raw.push([aisleX, from[1]], [aisleX, to[1]]);
  }
  raw.push(to);

  const path: XZ[] = [];
  let cursor = from;
  for (const pt of raw) {
    path.push(...avoidRoundTable(cursor, pt, slot.meetingTable));
    cursor = pt;
  }
  return path;
}

export function buildHQLayout(channelIds: readonly string[]): BuildingLayout {
  const count = Math.min(channelIds.length, MAX_CHANNELS);
  const overflow = Math.max(0, channelIds.length - MAX_CHANNELS);
  const slots = channelIds.slice(0, count).map((id, i) => buildStudioSlot(id, i));
  const wings = count > MAX_PER_WING ? 2 : 1;

  const wing0Slots = slots.filter((s) => s.wing === 0);
  const wing1Slots = slots.filter((s) => s.wing === 1);

  const wing0Cols = Math.max(1, Math.ceil(wing0Slots.length / 2));
  const wing1Cols = wing1Slots.length > 0 ? Math.ceil(wing1Slots.length / 2) : 0;
  const maxCols = Math.max(wing0Cols, wing1Cols);

  const lobbyX0 = -LOBBY_D;
  const lobbyX1 = 0;
  const wing0CorridorZ0 = -CORRIDOR_W / 2;
  const wing0CorridorZ1 = CORRIDOR_W / 2;

  const wing1CenterZ = MODULE.d * 2 + CORRIDOR_W + WING_GAP;
  const wing1CorridorZ0 = wing1CenterZ - CORRIDOR_W / 2;
  const wing1CorridorZ1 = wing1CenterZ + CORRIDOR_W / 2;

  const corridors: Array<{ x0: number; x1: number; z0: number; z1: number }> = [
    { x0: lobbyX0, x1: wing0Cols * MODULE.w, z0: wing0CorridorZ0, z1: wing0CorridorZ1 },
  ];
  if (wings === 2) {
    corridors.push({
      x0: lobbyX0,
      x1: wing1Cols * MODULE.w,
      z0: wing1CorridorZ0,
      z1: wing1CorridorZ1,
    });
    // Connecting hall along the reception side linking both corridors
    corridors.push({
      x0: lobbyX0,
      x1: lobbyX1,
      z0: wing0CorridorZ1,
      z1: wing1CorridorZ0,
    });
  }

  const hasWing0North = wing0Slots.some((s) => s.side === "north");
  const hasWing0South = wing0Slots.some((s) => s.side === "south");
  const hasWing1North = wing1Slots.some((s) => s.side === "north");
  const hasWing1South = wing1Slots.some((s) => s.side === "south");

  const minZ = hasWing0North ? -CORRIDOR_W / 2 - MODULE.d : wing0CorridorZ0;
  const maxZ =
    wings === 2
      ? hasWing1South
        ? wing1CorridorZ1 + MODULE.d
        : wing1CorridorZ1
      : hasWing0South
        ? CORRIDOR_W / 2 + MODULE.d
        : wing0CorridorZ1;

  const bounds = {
    x0: lobbyX0,
    x1: Math.max(lobbyX1, maxCols * MODULE.w),
    z0: minZ,
    z1: maxZ,
  };

  const walls: BuildingWall[] = [];

  // Lobby back wall (-X)
  const lobbyBackZ1 = wings === 2 ? wing1CorridorZ1 : wing0CorridorZ1;
  walls.push({
    axis: "x",
    at: lobbyX0,
    from: wing0CorridorZ0,
    to: lobbyBackZ1,
    height: HQ_OUTER_WALL_HEIGHT,
    gaps: [],
  });
  // Lobby north side wall
  walls.push({
    axis: "z",
    at: wing0CorridorZ0,
    from: lobbyX0,
    to: lobbyX1,
    height: HQ_OUTER_WALL_HEIGHT,
    gaps: [],
  });
  if (wings === 1) {
    walls.push({
      axis: "z",
      at: wing0CorridorZ1,
      from: lobbyX0,
      to: lobbyX1,
      height: HQ_PARTITION_HEIGHT,
      gaps: [],
    });
  } else {
    walls.push({
      axis: "z",
      at: wing1CorridorZ1,
      from: lobbyX0,
      to: lobbyX1,
      height: HQ_PARTITION_HEIGHT,
      gaps: [],
    });
    // Inner hall wall facing studios at x = 0 between wing0 south and wing1 north
    walls.push({
      axis: "x",
      at: 0,
      from: wing0CorridorZ1,
      to: wing1CorridorZ0,
      height: HQ_PARTITION_HEIGHT,
      gaps: [],
    });
  }

  // Per-wing studio walls
  for (const w of [0, 1] as const) {
    const wSlots = slots.filter((s) => s.wing === w);
    if (wSlots.length === 0) continue;
    const cZ0 = w === 0 ? wing0CorridorZ0 : wing1CorridorZ0;
    const cZ1 = w === 0 ? wing0CorridorZ1 : wing1CorridorZ1;

    for (const side of ["north", "south"] as const) {
      const sideSlots = wSlots.filter((s) => s.side === side);
      if (sideSlots.length === 0) continue;
      const sideMinX = 0;
      const sideMaxX = Math.max(...sideSlots.map((s) => s.x1));
      const corridorWallZ = side === "north" ? cZ0 : cZ1;
      const outerWallZ = side === "north" ? cZ0 - MODULE.d : cZ1 + MODULE.d;

      // Corridor wall with door gaps
      walls.push({
        axis: "z",
        at: corridorWallZ,
        from: sideMinX,
        to: sideMaxX,
        height: HQ_CORRIDOR_WALL_HEIGHT,
        gaps: sideSlots.map((s) => s.door.centerX),
      });

      // Outer back wall of this row
      walls.push({
        axis: "z",
        at: outerWallZ,
        from: sideMinX,
        to: sideMaxX,
        height: side === "north" ? HQ_OUTER_WALL_HEIGHT : HQ_PARTITION_HEIGHT,
        gaps: [],
      });

      // Side partitions at col boundaries (x = 0, 8.4, ...)
      const sZ0 = Math.min(corridorWallZ, outerWallZ);
      const sZ1 = Math.max(corridorWallZ, outerWallZ);
      const colBoundaries = new Set<number>();
      for (const s of sideSlots) {
        colBoundaries.add(s.x0);
        colBoundaries.add(s.x1);
      }
      for (const xAt of Array.from(colBoundaries).sort((a, b) => a - b)) {
        walls.push({
          axis: "x",
          at: xAt,
          from: sZ0,
          to: sZ1,
          height: xAt === 0 && w === 0 ? HQ_OUTER_WALL_HEIGHT : HQ_PARTITION_HEIGHT,
          gaps: [],
        });
      }
    }
  }

  return {
    slots,
    overflow,
    wings,
    lobby: {
      x0: lobbyX0,
      x1: lobbyX1,
      z0: wing0CorridorZ0,
      z1: wings === 2 ? wing1CorridorZ1 : wing0CorridorZ1,
      desk: [-2.8, 0.0],
      screen: [lobbyX0 + 0.14, 1.5, 0.0],
      logoPos: [lobbyX0 + 0.12, 2.25, 0.0],
      receptionist: [-3.4, 0.0],
      plants: [
        [-5.2, -1.15],
        [-5.2, 1.15],
      ],
    },
    corridors,
    bounds,
    walls,
  };
}
