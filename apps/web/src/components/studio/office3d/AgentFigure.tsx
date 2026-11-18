"use client";

import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import type { Group, Mesh, Object3D } from "three";
import type { AgentKey, AgentVisualStatus, RoomKey } from "@/lib/studio/types";
import { AGENT_LOOK, PALETTE, ROOM_STATIONS, coffeeSpot, route, type DeskSlot, type XZ } from "./layout3d";
import { FIGURE_PROPORTIONS } from "./figureProportions";

type Pose = "type" | "sit" | "alert" | "slump" | "present" | "stand";

export interface Stop {
  room: RoomKey;
  pos: XZ;
  facing: number;
  pose: Pose;
  dwell: [number, number];
}

export interface AgentFigureProps {
  agentKey: AgentKey;
  index: number;
  status: AgentVisualStatus;
  enabled: boolean;
  desk: DeskSlot & { facing?: number };
  meeting: { pos: XZ; facing: number };
  selected: boolean;
  hovered: boolean;
  reducedMotion: boolean;
  onSelect: (agentKey: AgentKey) => void;
  onHover: (agentKey: AgentKey | null) => void;
  registerAnchor: (agentKey: AgentKey, object: Object3D | null) => void;
  routeFn?: (fromRoom: RoomKey, fromPos: XZ, toRoom: RoomKey, toPos: XZ) => XZ[];
  allowIdleWander?: boolean;
  lookOverride?: { shirt: string; skin: string; hair: string };
  isExternalSpecialist?: boolean;
  customSchedule?: Stop[];
  onSelectCustom?: () => void;
  onHoverCustom?: (hovered: boolean) => void;
  registerCustomAnchor?: (object: Object3D | null) => void;
}

const WALK_SPEED = FIGURE_PROPORTIONS.walkSpeed;
const FACING_DESK = FIGURE_PROPORTIONS.facingDesk;

function buildSchedule(
  status: AgentVisualStatus,
  enabled: boolean,
  desk: DeskSlot & { facing?: number },
  meeting: { pos: XZ; facing: number },
  index: number,
  allowIdleWander: boolean,
  isExternalSpecialist: boolean
): Stop[] {
  const home = (pose: Pose, dwell: [number, number] = [Infinity, Infinity]): Stop => ({
    room: desk.room,
    pos: desk.seat,
    facing: desk.facing ?? FACING_DESK,
    pose,
    dwell,
  });
  if (!enabled || status === "disabled") return [home("slump")];
  if (!allowIdleWander) {
    switch (status) {
      case "working":
        return [home("type")];
      case "waiting_approval":
      case "needs_review":
      case "waiting_input":
        return [{ room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [Infinity, Infinity] }];
      case "failed":
      case "blocked":
      case "no_signal":
        return [home("alert")];
      default:
        return [home("sit")];
    }
  }

  const roomStations = ROOM_STATIONS[desk.room] ?? ROOM_STATIONS.mesa_agentes;
  const stationA = roomStations[index % roomStations.length];
  const stationB = roomStations[(index + 1) % roomStations.length];

  if (isExternalSpecialist) {
    switch (status) {
      case "working":
        return [
          { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "present", dwell: [2.2, 4.0] },
          { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [2.0, 3.6] },
          { room: stationB.room, pos: stationB.pos, facing: stationB.facing, pose: "stand", dwell: [2.0, 3.8] },
        ];
      case "waiting_approval":
      case "needs_review":
      case "waiting_input":
        return [
          { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [3.0, 5.0] },
          { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "present", dwell: [2.5, 4.0] },
        ];
      default:
        return [
          { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "stand", dwell: [2.5, 4.5] },
          { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [2.2, 4.0] },
          { room: "mesa_agentes", pos: coffeeSpot(index), facing: 0, pose: "stand", dwell: [2.0, 3.5] },
        ];
    }
  }

  switch (status) {
    case "working":
      return [
        home("type", [4.0, 7.0]),
        { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "present", dwell: [2.2, 3.8] },
        { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [2.0, 3.5] },
      ];
    case "waiting_approval":
    case "needs_review":
    case "waiting_input":
      return [
        { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [4.0, 6.5] },
        home("sit", [3.0, 5.0]),
      ];
    case "failed":
    case "blocked":
    case "no_signal":
      return [home("alert")];
    case "queued":
    case "done":
      return [
        home("type", [4.5, 8.0]),
        { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "stand", dwell: [2.5, 4.2] },
        { room: "mesa_agentes", pos: meeting.pos, facing: meeting.facing, pose: "present", dwell: [2.2, 3.8] },
      ];
    default:
      return [
        home("sit", [5.0, 9.0]),
        { room: stationA.room, pos: stationA.pos, facing: stationA.facing, pose: "stand", dwell: [2.5, 4.5] },
        { room: "mesa_agentes", pos: coffeeSpot(index), facing: 0, pose: "stand", dwell: [2.5, 4.5] },
      ];
  }
}

function randomBetween([min, max]: [number, number]) {
  if (!Number.isFinite(min)) return Infinity;
  return min + Math.random() * (max - min);
}

function lerpAngle(from: number, to: number, t: number) {
  let delta = ((to - from + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (delta < -Math.PI) delta += Math.PI * 2;
  return from + delta * t;
}

export function AgentFigure({
  agentKey,
  index,
  status,
  enabled,
  desk,
  meeting,
  selected,
  hovered,
  reducedMotion,
  onSelect,
  onHover,
  registerAnchor,
  routeFn = route,
  allowIdleWander = true,
  lookOverride,
  isExternalSpecialist = false,
  customSchedule,
  onSelectCustom,
  onHoverCustom,
  registerCustomAnchor,
}: AgentFigureProps) {
  const look = lookOverride ?? AGENT_LOOK[agentKey];

  const root = useRef<Group>(null);
  const body = useRef<Group>(null);
  const head = useRef<Group>(null);
  const legL = useRef<Group>(null);
  const legR = useRef<Group>(null);
  const armL = useRef<Group>(null);
  const armR = useRef<Group>(null);
  const folder = useRef<Mesh>(null);

  const motion = useRef({
    x: desk.seat[0],
    z: desk.seat[1],
    room: desk.room as RoomKey,
    facing: desk.facing ?? FACING_DESK,
    path: [] as XZ[],
    stopIndex: 0,
    dwellLeft: 0,
    walking: false,
    phase: Math.random() * 10,
  });

  useEffect(() => {
    if (registerCustomAnchor) {
      registerCustomAnchor(root.current);
      return () => registerCustomAnchor(null);
    }
    registerAnchor(agentKey, root.current);
    return () => registerAnchor(agentKey, null);
  }, [agentKey, registerAnchor, registerCustomAnchor]);

  const schedule = useMemo(
    () =>
      customSchedule ??
      buildSchedule(status, enabled, desk, meeting, index, allowIdleWander, isExternalSpecialist),
    [customSchedule, status, enabled, desk, meeting, index, allowIdleWander, isExternalSpecialist]
  );

  useEffect(() => {
    const m = motion.current;
    const first = schedule[0];
    m.stopIndex = 0;
    if (reducedMotion) {
      m.x = first.pos[0];
      m.z = first.pos[1];
      m.room = first.room;
      m.facing = first.facing;
      m.path = [];
      m.walking = false;
      m.dwellLeft = Infinity;
      return;
    }
    const atTarget = Math.hypot(m.x - first.pos[0], m.z - first.pos[1]) < 0.05;
    if (atTarget) {
      // Stagger initial departure so half the team is already walking on entry
      if (schedule.length > 1 && (isExternalSpecialist || index % 2 === 1)) {
        const nextIndex = 1 % schedule.length;
        const next = schedule[nextIndex];
        m.path = routeFn(first.room, [m.x, m.z], next.room, next.pos);
        m.stopIndex = nextIndex;
        m.walking = true;
      } else {
        m.walking = false;
        m.dwellLeft = 0.8 + (index % 4) * 0.9;
      }
    } else {
      m.path = routeFn(m.room, [m.x, m.z], first.room, first.pos);
      m.walking = true;
    }
  }, [schedule, reducedMotion, routeFn, isExternalSpecialist, index]);

  useFrame((state, delta) => {
    const m = motion.current;
    const dt = Math.min(delta, 0.05);
    const t = state.clock.elapsedTime + m.phase;
    const stop = schedule[m.stopIndex] ?? schedule[0];

    if (m.walking && !reducedMotion) {
      const target = m.path[0];
      if (!target) {
        m.walking = false;
        m.room = stop.room;
        m.dwellLeft = randomBetween(stop.dwell);
      } else {
        const dx = target[0] - m.x;
        const dz = target[1] - m.z;
        const dist = Math.hypot(dx, dz);
        const step = WALK_SPEED * dt;
        if (dist <= step) {
          m.x = target[0];
          m.z = target[1];
          m.path.shift();
        } else {
          m.x += (dx / dist) * step;
          m.z += (dz / dist) * step;
          m.facing = lerpAngle(m.facing, Math.atan2(dx, dz), Math.min(1, dt * 10));
        }
      }
    } else if (!reducedMotion) {
      m.facing = lerpAngle(m.facing, stop.facing, Math.min(1, dt * 6));
      if (schedule.length > 1) {
        m.dwellLeft -= dt;
        if (m.dwellLeft <= 0) {
          const nextIndex = (m.stopIndex + 1) % schedule.length;
          const next = schedule[nextIndex];
          m.path = routeFn(stop.room, [m.x, m.z], next.room, next.pos);
          m.stopIndex = nextIndex;
          m.walking = true;
        }
      }
    }

    const pose: Pose | "walk" = m.walking ? "walk" : stop.pose;
    const seated = pose === "type" || pose === "sit" || pose === "alert" || pose === "slump";
    const anim = reducedMotion ? 0 : 1;

    if (root.current) {
      root.current.position.set(m.x, 0, m.z);
      root.current.rotation.y = m.facing;
    }
    if (body.current) {
      const bob = pose === "walk" ? Math.abs(Math.sin(t * 9)) * 0.05 * anim : 0;
      body.current.position.y = (seated ? -0.06 : 0) + bob;
      body.current.rotation.x = pose === "slump" ? 0.35 : pose === "type" ? 0.08 : 0;
    }
    if (legL.current && legR.current) {
      if (seated) {
        legL.current.rotation.x = -1.45;
        legR.current.rotation.x = -1.45;
      } else if (pose === "walk") {
        legL.current.rotation.x = Math.sin(t * 9) * 0.6 * anim;
        legR.current.rotation.x = -Math.sin(t * 9) * 0.6 * anim;
      } else {
        legL.current.rotation.x = 0;
        legR.current.rotation.x = 0;
      }
    }
    if (armL.current && armR.current) {
      switch (pose) {
        case "walk":
          armL.current.rotation.x = -Math.sin(t * 9) * 0.5 * anim;
          armR.current.rotation.x = folderVisible(status, enabled) ? -1.1 : Math.sin(t * 9) * 0.5 * anim;
          break;
        case "type":
          armL.current.rotation.x = -1.15 + Math.sin(t * 22) * 0.12 * anim;
          armR.current.rotation.x = -1.15 + Math.cos(t * 19) * 0.12 * anim;
          break;
        case "alert":
          armL.current.rotation.x = -2.7 + Math.sin(t * 6) * 0.2 * anim;
          armR.current.rotation.x = -2.7 - Math.sin(t * 6) * 0.2 * anim;
          break;
        case "present":
          armL.current.rotation.x = -0.2;
          armR.current.rotation.x = -1.2 + Math.sin(t * 2) * 0.08 * anim;
          break;
        default:
          armL.current.rotation.x = -0.15;
          armR.current.rotation.x = -0.15;
      }
    }
    if (head.current) {
      head.current.rotation.y = pose === "alert" ? Math.sin(t * 7) * 0.4 * anim : pose === "stand" ? Math.sin(t * 0.8) * 0.3 * anim : 0;
      head.current.rotation.x = pose === "slump" ? 0.4 : pose === "type" ? 0.15 + Math.sin(t * 3) * 0.03 * anim : 0;
    }
    if (folder.current) {
      folder.current.visible = folderVisible(status, enabled) && (pose === "walk" || pose === "present");
    }
  });

  const dim = !enabled || status === "disabled" || status === "cancelled";
  const shirt = dim ? "#7c8288" : look.shirt;

  return (
    <group
      ref={root}
      onClick={(e) => {
        e.stopPropagation();
        if (onSelectCustom) onSelectCustom();
        else onSelect(agentKey);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        if (onHoverCustom) onHoverCustom(true);
        else onHover(agentKey);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        if (onHoverCustom) onHoverCustom(false);
        else onHover(null);
        document.body.style.cursor = "";
      }}
    >
      {(selected || hovered || isExternalSpecialist) && (
        <mesh rotation-x={-Math.PI / 2} position-y={0.03}>
          <ringGeometry args={[selected || hovered ? 0.38 : 0.31, selected || hovered ? 0.5 : 0.41, 32]} />
          <meshBasicMaterial
            color={selected || hovered ? PALETTE.accent : status === "working" ? "#00f0ff" : "#10b981"}
            transparent
            opacity={selected || hovered ? 0.92 : 0.65}
          />
        </mesh>
      )}

      <group ref={body}>
        <group ref={legL} position={[-0.1, 0.5, 0]}>
          <mesh position-y={-0.25} castShadow>
            <boxGeometry args={[0.14, 0.5, 0.15]} />
            <meshStandardMaterial color="#2c3440" roughness={0.8} />
          </mesh>
        </group>
        <group ref={legR} position={[0.1, 0.5, 0]}>
          <mesh position-y={-0.25} castShadow>
            <boxGeometry args={[0.14, 0.5, 0.15]} />
            <meshStandardMaterial color="#2c3440" roughness={0.8} />
          </mesh>
        </group>

        <RoundedBox args={[0.44, 0.52, 0.28]} radius={0.08} position-y={0.76} castShadow>
          <meshStandardMaterial color={shirt} roughness={0.7} />
        </RoundedBox>

        <group ref={armL} position={[-0.28, 0.98, 0]}>
          <mesh position-y={-0.2} castShadow>
            <capsuleGeometry args={[0.065, 0.28, 4, 8]} />
            <meshStandardMaterial color={shirt} roughness={0.7} />
          </mesh>
        </group>
        <group ref={armR} position={[0.28, 0.98, 0]}>
          <mesh position-y={-0.2} castShadow>
            <capsuleGeometry args={[0.065, 0.28, 4, 8]} />
            <meshStandardMaterial color={shirt} roughness={0.7} />
          </mesh>
          <mesh ref={folder} position={[0, -0.42, 0.06]} rotation-x={Math.PI / 2} visible={false} castShadow>
            <boxGeometry args={[0.26, 0.34, 0.03]} />
            <meshStandardMaterial color={PALETTE.paper} roughness={0.9} />
          </mesh>
        </group>

        <group ref={head} position-y={1.24}>
          <mesh castShadow>
            <sphereGeometry args={[0.19, 20, 16]} />
            <meshStandardMaterial color={look.skin} roughness={0.6} />
          </mesh>
          <mesh position={[0, 0.03, -0.02]} rotation-x={-0.35}>
            <sphereGeometry args={[0.205, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
            <meshStandardMaterial color={dim ? "#55595e" : look.hair} roughness={0.9} />
          </mesh>
          <mesh position={[-0.07, 0.01, 0.175]}>
            <sphereGeometry args={[0.025, 8, 8]} />
            <meshBasicMaterial color="#1a1a1a" />
          </mesh>
          <mesh position={[0.07, 0.01, 0.175]}>
            <sphereGeometry args={[0.025, 8, 8]} />
            <meshBasicMaterial color="#1a1a1a" />
          </mesh>
        </group>
      </group>

    </group>
  );
}

function folderVisible(status: AgentVisualStatus, enabled: boolean) {
  return (
    enabled &&
    (status === "working" ||
      status === "done" ||
      status === "waiting_approval" ||
      status === "needs_review" ||
      status === "waiting_input")
  );
}
