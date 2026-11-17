"use client";

import { useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import type { Mesh, MeshStandardMaterial } from "three";
import type { RoomKey } from "@/lib/studio/types";
import {
  BUILDING,
  COFFEE_BAR,
  DOOR_WIDTH,
  MEETING_TABLE,
  OUTER_WALL_HEIGHT,
  PALETTE,
  PARTITIONS,
  PARTITION_HEIGHT,
  ROOMS,
  ROOM_ORDER,
  meetingSeat,
  type DeskSlot,
} from "./layout3d";

function Box({
  size,
  position,
  color,
  emissive,
  emissiveIntensity = 0,
  roughness = 0.8,
  metalness = 0,
  cast = true,
}: {
  size: [number, number, number];
  position: [number, number, number];
  color: string;
  emissive?: string;
  emissiveIntensity?: number;
  roughness?: number;
  metalness?: number;
  cast?: boolean;
}) {
  return (
    <mesh position={position} castShadow={cast} receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial
        color={color}
        emissive={emissive ?? "#000000"}
        emissiveIntensity={emissiveIntensity}
        roughness={roughness}
        metalness={metalness}
      />
    </mesh>
  );
}

function Walls() {
  const t = 0.18;
  const segments: Array<{ size: [number, number, number]; position: [number, number, number] }> = [];

  for (const p of PARTITIONS) {
    const cuts = [p.from, ...p.gaps.flatMap((g) => [g - DOOR_WIDTH / 2, g + DOOR_WIDTH / 2]), p.to];
    for (let i = 0; i < cuts.length; i += 2) {
      const a = cuts[i];
      const b = cuts[i + 1];
      const len = b - a;
      if (len <= 0.01) continue;
      const mid = (a + b) / 2;
      segments.push(
        p.axis === "x"
          ? { size: [t, PARTITION_HEIGHT, len], position: [p.at, PARTITION_HEIGHT / 2, mid] }
          : { size: [len, PARTITION_HEIGHT, t], position: [mid, PARTITION_HEIGHT / 2, p.at] }
      );
    }
  }

  const width = BUILDING.x1 - BUILDING.x0;
  const depth = BUILDING.z1 - BUILDING.z0;

  return (
    <group>
      <Box
        size={[width + t, OUTER_WALL_HEIGHT, t]}
        position={[(BUILDING.x0 + BUILDING.x1) / 2, OUTER_WALL_HEIGHT / 2, BUILDING.z0 - t / 2]}
        color={PALETTE.wall}
      />
      <Box
        size={[t, OUTER_WALL_HEIGHT, depth]}
        position={[BUILDING.x0 - t / 2, OUTER_WALL_HEIGHT / 2, (BUILDING.z0 + BUILDING.z1) / 2]}
        color={PALETTE.wall}
      />
      {segments.map((s, i) => (
        <group key={i}>
          <Box size={s.size} position={s.position} color={PALETTE.wall} />
          <Box
            size={[s.size[0] + 0.04, 0.06, s.size[2] + 0.04]}
            position={[s.position[0], PARTITION_HEIGHT + 0.03, s.position[2]]}
            color={PALETTE.wallCap}
          />
        </group>
      ))}
    </group>
  );
}

function Monitor({ position, active, idle }: { position: [number, number, number]; active: boolean; idle: boolean }) {
  const screen = useRef<MeshStandardMaterial>(null);
  useFrame((state) => {
    if (!screen.current) return;
    screen.current.emissiveIntensity = active ? 0.9 + Math.sin(state.clock.elapsedTime * 3) * 0.25 : idle ? 0.35 : 0.05;
  });
  const color = active ? PALETTE.screenWork : idle ? PALETTE.screenIdle : PALETTE.screenOff;
  return (
    <group position={position}>
      <Box size={[0.08, 0.28, 0.08]} position={[0, 0.14, -0.05]} color={PALETTE.metal} />
      <Box size={[0.9, 0.52, 0.05]} position={[0, 0.5, -0.05]} color="#20262e" />
      <mesh position={[0, 0.5, -0.02]}>
        <planeGeometry args={[0.82, 0.44]} />
        <meshStandardMaterial ref={screen} color={color} emissive={color} emissiveIntensity={0.4} />
      </mesh>
    </group>
  );
}

function Desk({ slot, active, idle }: { slot: DeskSlot; active: boolean; idle: boolean }) {
  const [dx, dz] = slot.desk;
  const [sx, sz] = slot.seat;
  return (
    <group>
      <Box size={[1.3, 0.07, 0.62]} position={[dx, 0.74, dz]} color={PALETTE.wood} roughness={0.6} />
      {[-0.58, 0.58].map((ox) => (
        <Box key={ox} size={[0.06, 0.72, 0.56]} position={[dx + ox, 0.36, dz]} color={PALETTE.woodDark} />
      ))}
      <Monitor position={[dx, 0.78, dz - 0.08]} active={active} idle={idle} />
      <Box size={[0.5, 0.03, 0.16]} position={[dx, 0.79, dz + 0.16]} color="#2a3038" />
      <Box size={[0.08, 0.1, 0.08]} position={[dx + 0.5, 0.83, dz + 0.1]} color={PALETTE.paper} />
      <group position={[sx, 0, sz]}>
        <Box size={[0.48, 0.07, 0.46]} position={[0, 0.44, 0.02]} color="#323a44" />
        <Box size={[0.46, 0.5, 0.06]} position={[0, 0.72, 0.26]} color="#323a44" />
        <Box size={[0.06, 0.42, 0.06]} position={[0, 0.21, 0.02]} color={PALETTE.metal} />
      </group>
    </group>
  );
}

function Plant({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
  return (
    <group position={position} scale={scale}>
      <mesh position-y={0.22} castShadow>
        <cylinderGeometry args={[0.22, 0.17, 0.44, 16]} />
        <meshStandardMaterial color="#c9b9a0" roughness={0.9} />
      </mesh>
      <mesh position-y={0.72} castShadow>
        <icosahedronGeometry args={[0.42, 1]} />
        <meshStandardMaterial color={PALETTE.plant} roughness={0.9} flatShading />
      </mesh>
      <mesh position={[0.18, 1.02, 0.05]} castShadow>
        <icosahedronGeometry args={[0.26, 1]} />
        <meshStandardMaterial color="#5f8c58" roughness={0.9} flatShading />
      </mesh>
    </group>
  );
}

function ServerRack({ position }: { position: [number, number, number] }) {
  const leds = useRef<Mesh[]>([]);
  useFrame((state) => {
    leds.current.forEach((m, i) => {
      const mat = m.material as MeshStandardMaterial;
      mat.emissiveIntensity = Math.sin(state.clock.elapsedTime * (2 + i) + i) > 0.2 ? 1.6 : 0.2;
    });
  });
  return (
    <group position={position}>
      <Box size={[0.7, 1.9, 0.7]} position={[0, 0.95, 0]} color="#252b33" metalness={0.3} roughness={0.5} />
      {Array.from({ length: 6 }).map((_, i) => (
        <mesh
          key={i}
          ref={(m) => {
            if (m) leds.current[i] = m;
          }}
          position={[0.36, 0.35 + i * 0.25, -0.18 + (i % 2) * 0.12]}
        >
          <boxGeometry args={[0.02, 0.05, 0.12]} />
          <meshStandardMaterial color={i % 3 === 0 ? PALETTE.accent : PALETTE.ok} emissive={i % 3 === 0 ? PALETTE.accent : PALETTE.ok} />
        </mesh>
      ))}
    </group>
  );
}

function WallChart({ position, width = 2.4 }: { position: [number, number, number]; width?: number }) {
  const bars = [0.35, 0.6, 0.45, 0.8, 0.55, 1.0, 0.7];
  return (
    <group position={position}>
      <Box size={[width, 1.1, 0.06]} position={[0, 0, 0]} color="#1f2730" cast={false} />
      {bars.map((h, i) => (
        <mesh key={i} position={[-width / 2 + 0.3 + i * ((width - 0.6) / (bars.length - 1)), -0.42 + h * 0.4, 0.04]}>
          <planeGeometry args={[0.18, h * 0.8]} />
          <meshStandardMaterial
            color={i === 5 ? PALETTE.accent : PALETTE.screenIdle}
            emissive={i === 5 ? PALETTE.accent : PALETTE.screenIdle}
            emissiveIntensity={0.6}
          />
        </mesh>
      ))}
    </group>
  );
}

function Corkboard({ position }: { position: [number, number, number] }) {
  const notes = ["#e0b04a", "#f4efe6", "#c96b55", "#7fa8c9", "#f4efe6", "#e0b04a", "#9cc49a", "#f4efe6", "#c96b55"];
  return (
    <group position={position}>
      <Box size={[2.6, 1.0, 0.06]} position={[0, 0, 0]} color="#b48a5a" cast={false} />
      {notes.map((c, i) => (
        <mesh key={i} position={[-0.95 + (i % 5) * 0.48, 0.2 - Math.floor(i / 5) * 0.42, 0.04]} rotation-z={(i % 3) * 0.06 - 0.06}>
          <planeGeometry args={[0.36, 0.26]} />
          <meshStandardMaterial color={c} roughness={0.9} />
        </mesh>
      ))}
    </group>
  );
}

function Shelf({ position, rotationY = 0 }: { position: [number, number, number]; rotationY?: number }) {
  const books = ["#a35d4f", "#4f7cac", "#e0b04a", "#6f9677", "#e0d2b4", "#5c6b7a"];
  return (
    <group position={position} rotation-y={rotationY}>
      <Box size={[1.6, 1.6, 0.45]} position={[0, 0.8, 0]} color={PALETTE.woodDark} />
      {[0.45, 1.0].map((y) =>
        books.map((c, i) => (
          <Box key={`${y}-${i}`} size={[0.16, 0.38, 0.32]} position={[-0.6 + i * 0.22, y + 0.12, 0.06]} color={c} />
        ))
      )}
    </group>
  );
}

function RecordingSet({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <Box size={[2.2, 1.7, 0.08]} position={[0, 0.85, -0.6]} color="#3c5466" cast={false} />
      <mesh position={[0, 1.15, 0.9]} rotation-x={0}>
        <torusGeometry args={[0.32, 0.04, 12, 32]} />
        <meshStandardMaterial color="#ffffff" emissive="#fff4dd" emissiveIntensity={1.4} />
      </mesh>
      <Box size={[0.04, 1.1, 0.04]} position={[0, 0.55, 0.9]} color={PALETTE.metal} />
      <Box size={[0.3, 0.2, 0.36]} position={[0.6, 1.0, 1.0]} color="#1b1f24" />
      <Box size={[0.04, 0.95, 0.04]} position={[0.6, 0.48, 1.0]} color={PALETTE.metal} />
      <Box size={[0.5, 0.5, 0.5]} position={[0, 0.25, -0.1]} color="#8a5f3f" />
    </group>
  );
}

function ThumbnailWall({ position }: { position: [number, number, number] }) {
  const frames = ["#c96b55", "#e0b04a", "#4f7cac", "#6f9677", "#a35d4f", "#e0d2b4"];
  return (
    <group position={position}>
      {frames.map((c, i) => (
        <group key={i} position={[-1.6 + (i % 3) * 1.1, 0.25 - Math.floor(i / 3) * 0.62, 0]}>
          <Box size={[0.96, 0.56, 0.04]} position={[0, 0, 0]} color="#f4efe6" cast={false} />
          <mesh position={[0, 0, 0.03]}>
            <planeGeometry args={[0.86, 0.46]} />
            <meshStandardMaterial color={c} roughness={0.7} />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function Kanban({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <Box size={[3.0, 1.0, 0.05]} position={[0, 0, 0]} color={PALETTE.paper} cast={false} />
      {[0, 1, 2].map((col) =>
        Array.from({ length: 3 - col }).map((_, row) => (
          <mesh key={`${col}-${row}`} position={[-1.0 + col * 1.0, 0.25 - row * 0.28, 0.035]}>
            <planeGeometry args={[0.6, 0.2]} />
            <meshStandardMaterial color={col === 2 ? PALETTE.ok : col === 1 ? PALETTE.accent : "#7fa8c9"} roughness={0.9} />
          </mesh>
        ))
      )}
    </group>
  );
}

function MeetingTable({ highlight }: { highlight: boolean }) {
  return (
    <group position={[MEETING_TABLE.x, 0, MEETING_TABLE.z]}>
      <mesh position-y={0.74} castShadow receiveShadow>
        <cylinderGeometry args={[MEETING_TABLE.radius, MEETING_TABLE.radius, 0.08, 48]} />
        <meshStandardMaterial color={PALETTE.wood} roughness={0.5} />
      </mesh>
      <mesh position-y={0.37} castShadow>
        <cylinderGeometry args={[0.18, 0.3, 0.72, 16]} />
        <meshStandardMaterial color={PALETTE.woodDark} />
      </mesh>
      <mesh position-y={0.8}>
        <cylinderGeometry args={[0.35, 0.35, 0.02, 32]} />
        <meshStandardMaterial
          color={highlight ? PALETTE.accent : "#4b7a99"}
          emissive={highlight ? PALETTE.accent : "#4b7a99"}
          emissiveIntensity={highlight ? 1.1 : 0.4}
        />
      </mesh>
      {Array.from({ length: 8 }).map((_, i) => {
        const seat = meetingSeat(i);
        const ox = seat.pos[0] - MEETING_TABLE.x;
        const oz = seat.pos[1] - MEETING_TABLE.z;
        return (
          <mesh key={i} position={[ox * 1.18, 0.24, oz * 1.18]} castShadow>
            <cylinderGeometry args={[0.2, 0.2, 0.08, 16]} />
            <meshStandardMaterial color="#323a44" />
          </mesh>
        );
      })}
    </group>
  );
}

function CoffeeBar() {
  return (
    <group position={[COFFEE_BAR[0], 0, COFFEE_BAR[1]]}>
      <Box size={[1.6, 0.9, 0.6]} position={[0, 0.45, 0]} color={PALETTE.woodDark} />
      <Box size={[1.7, 0.06, 0.66]} position={[0, 0.93, 0]} color={PALETTE.paper} />
      <Box size={[0.36, 0.46, 0.34]} position={[-0.4, 1.19, 0]} color="#262b31" metalness={0.4} />
      <mesh position={[-0.4, 1.2, 0.18]}>
        <circleGeometry args={[0.05, 12]} />
        <meshStandardMaterial color={PALETTE.accent} emissive={PALETTE.accent} emissiveIntensity={1.5} />
      </mesh>
      {[0.2, 0.42].map((x) => (
        <mesh key={x} position={[x, 1.02, 0]} castShadow>
          <cylinderGeometry args={[0.06, 0.05, 0.13, 12]} />
          <meshStandardMaterial color={PALETTE.paper} />
        </mesh>
      ))}
    </group>
  );
}

function RoomFloor({
  roomKey,
  hovered,
  onHover,
  onSelect,
}: {
  roomKey: RoomKey;
  hovered: boolean;
  onHover: (key: RoomKey | null) => void;
  onSelect: (key: RoomKey) => void;
}) {
  const room = ROOMS[roomKey];
  const w = room.x1 - room.x0;
  const d = room.z1 - room.z0;
  return (
    <mesh
      position={[(room.x0 + room.x1) / 2, 0.01, (room.z0 + room.z1) / 2]}
      rotation-x={-Math.PI / 2}
      receiveShadow
      onClick={(e) => {
        e.stopPropagation();
        onSelect(roomKey);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        onHover(roomKey);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        onHover(null);
        document.body.style.cursor = "";
      }}
    >
      <planeGeometry args={[w - 0.02, d - 0.02]} />
      <meshStandardMaterial
        color={room.floor}
        roughness={0.85}
        emissive={PALETTE.accent}
        emissiveIntensity={hovered ? 0.12 : 0}
      />
    </mesh>
  );
}

export interface OfficeRoomsProps {
  desks: Array<{ slot: DeskSlot; active: boolean; idle: boolean }>;
  approvalsPending: boolean;
  onSelectRoom: (key: RoomKey) => void;
}

export function OfficeRooms({ desks, approvalsPending, onSelectRoom }: OfficeRoomsProps) {
  const [hoveredRoom, setHoveredRoom] = useState<RoomKey | null>(null);
  const width = BUILDING.x1 - BUILDING.x0;
  const depth = BUILDING.z1 - BUILDING.z0;

  return (
    <group>
      <Box
        size={[width + 1.2, 0.4, depth + 1.2]}
        position={[(BUILDING.x0 + BUILDING.x1) / 2, -0.2, (BUILDING.z0 + BUILDING.z1) / 2]}
        color={PALETTE.base}
        cast={false}
      />

      {ROOM_ORDER.map((key) => (
        <RoomFloor key={key} roomKey={key} hovered={hoveredRoom === key} onHover={setHoveredRoom} onSelect={onSelectRoom} />
      ))}

      <Walls />

      {desks.map((d, i) => (
        <Desk key={i} slot={d.slot} active={d.active} idle={d.idle} />
      ))}

      {/* Sala de Dados */}
      <ServerRack position={[-10.9, 0, -5.8]} />
      <ServerRack position={[-10.9, 0, -4.9]} />
      <WallChart position={[-7.4, 1.55, BUILDING.z0 + 0.05]} width={3.0} />
      <Plant position={[-10.8, 0, -0.7]} scale={0.8} />

      {/* Pesquisa */}
      <Corkboard position={[-7.8, 1.25, 0.12]} />
      <Shelf position={[-11.1, 0, 4.6]} rotationY={Math.PI / 2} />
      <Plant position={[-10.9, 0, 6.0]} scale={0.9} />

      {/* Sala de Pauta */}
      <WallChart position={[0, 1.55, BUILDING.z0 + 0.05]} width={3.6} />
      <MeetingTable highlight={approvalsPending} />
      <CoffeeBar />
      <Plant position={[-3.6, 0, 6.0]} />
      <Plant position={[-3.8, 0, -0.8]} scale={0.8} />

      {/* Gravação */}
      <RecordingSet position={[10.3, 0, -4.9]} />

      {/* Design de Capa */}
      <ThumbnailWall position={[8.3, 1.35, -2.06]} />

      {/* Estratégia e Publicação */}
      <Kanban position={[8.3, 1.4, 2.28]} />
      <Plant position={[11.0, 0, 6.1]} scale={0.8} />

    </group>
  );
}
