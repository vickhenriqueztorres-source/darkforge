"use client";

import { useCallback, useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, OrthographicCamera } from "@react-three/drei";
import { Vector3, type Object3D } from "three";
import type { AgentKey, AgentVisualStatus, RoomKey, StudioAgentState } from "@/lib/studio/types";
import type { ExternalAgentState } from "@/lib/studio/external-types";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import { AgentFigure } from "./AgentFigure";
import { OfficeRooms } from "./OfficeRooms";
import {
  AGENT_LABEL_HEIGHT,
  EXTERNAL_GROUP_LOOK,
  ROOM_ORDER,
  ROOM_STATIONS,
  assignDesks,
  meetingSeat,
  roomLabelPosition,
} from "./layout3d";

const ISO_AZIMUTH = Math.PI / 4;
const APPROVAL_STATUSES = new Set(["waiting_approval", "needs_review", "waiting_input"]);

/** DOM label elements keyed by `room:<key>`, `agent:<key>` or `ext:<key>`, positioned over the canvas every frame. */
export type OverlayAnchors = MutableRefObject<Map<string, HTMLElement>>;

function mapExternalVisualStatus(status: ExternalAgentState["status"]): AgentVisualStatus {
  switch (status) {
    case "working":
      return "working";
    case "queued":
      return "queued";
    case "waiting_approval":
    case "waiting_input":
      return "waiting_approval";
    case "failed":
    case "gate_failed":
    case "blocked":
    case "no_signal":
      return "failed";
    case "done":
    case "gate_passed":
      return "done";
    default:
      return "idle";
  }
}

function FitCamera() {
  const { camera, size } = useThree();
  useEffect(() => {
    camera.zoom = Math.min(size.width / 28, size.height / 18.5);
    camera.updateProjectionMatrix();
  }, [camera, size.width, size.height]);
  return null;
}

function OverlaySync({
  anchors,
  agentObjects,
}: {
  anchors: OverlayAnchors;
  agentObjects: MutableRefObject<Map<string, Object3D>>;
}) {
  const { camera, size } = useThree();
  const roomPoints = useMemo(() => new Map(ROOM_ORDER.map((k) => [k, new Vector3(...roomLabelPosition(k))])), []);
  const v = useMemo(() => new Vector3(), []);

  useFrame(() => {
    for (const [id, el] of anchors.current) {
      const [kind, key] = id.split(":");
      if (kind === "room") {
        const point = roomPoints.get(key as RoomKey);
        if (!point) continue;
        v.copy(point);
      } else {
        const obj = agentObjects.current.get(id) ?? agentObjects.current.get(key);
        if (!obj) continue;
        v.set(obj.position.x, AGENT_LABEL_HEIGHT, obj.position.z);
      }
      v.project(camera);
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      const lift = kind === "room" ? "-50%" : "-100%";
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, ${lift})`;
      el.style.visibility = "visible";
    }
  });
  return null;
}

export interface OfficeSceneProps {
  agents: StudioAgentState[];
  externalSpecialists?: ExternalAgentState[];
  selectedAgent: AgentKey | null;
  hoveredAgent: AgentKey | null;
  hoveredExternalKey?: string | null;
  active: boolean;
  reducedMotion: boolean;
  anchors: OverlayAnchors;
  onSelectAgent: (agentKey: AgentKey) => void;
  onHoverAgent: (agentKey: AgentKey | null) => void;
  onSelectExternalAgent?: (agentKey: string) => void;
  onHoverExternalAgent?: (agentKey: string | null) => void;
  onSelectRoom: (roomKey: RoomKey) => void;
}

export default function OfficeScene({
  agents,
  externalSpecialists = [],
  selectedAgent,
  hoveredAgent,
  hoveredExternalKey = null,
  active,
  reducedMotion,
  anchors,
  onSelectAgent,
  onHoverAgent,
  onSelectExternalAgent,
  onHoverExternalAgent,
  onSelectRoom,
}: OfficeSceneProps) {
  const seatingKey = agents.map((a) => `${a.agent_key}:${a.room_key}`).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reassign desks only when the seating changes, not on every event
  const desks = useMemo(() => assignDesks(agents), [seatingKey]);
  const meetings = useMemo(() => PIPELINE_ORDER.map((_, i) => meetingSeat(i)), []);
  const extMeetings = useMemo(
    () => Array.from({ length: 16 }, (_, i) => meetingSeat(i, 16)),
    []
  );

  const agentObjects = useRef(new Map<string, Object3D>());
  const registerAnchor = useCallback((key: AgentKey, object: Object3D | null) => {
    if (object) {
      agentObjects.current.set(key, object);
      agentObjects.current.set(`agent:${key}`, object);
    } else {
      agentObjects.current.delete(key);
      agentObjects.current.delete(`agent:${key}`);
    }
  }, []);

  const registerExternalAnchor = useCallback((extKey: string, object: Object3D | null) => {
    if (object) agentObjects.current.set(`ext:${extKey}`, object);
    else agentObjects.current.delete(`ext:${extKey}`);
  }, []);

  const ordered = useMemo(
    () =>
      PIPELINE_ORDER.map((k) => agents.find((a) => a.agent_key === k)).filter(
        (a): a is StudioAgentState => Boolean(a)
      ),
    [agents]
  );

  const deskVisuals = ordered
    .map((agent) => {
      const slot = desks.get(agent.agent_key);
      if (!slot) return null;
      return {
        slot,
        active: agent.enabled && agent.status === "working",
        idle: agent.enabled && agent.status !== "disabled",
      };
    })
    .filter((d): d is NonNullable<typeof d> => d !== null);

  const approvalsPending = ordered.some((a) => a.enabled && APPROVAL_STATUSES.has(a.status));
  const distance = 40;

  return (
    <Canvas
      shadows="percentage"
      dpr={[1, 2]}
      frameloop={active ? "always" : "never"}
      gl={{ antialias: true }}
      fallback={<p>Seu navegador não suporta WebGL, então o escritório 3D não pode ser exibido.</p>}
      onPointerMissed={() => {
        document.body.style.cursor = "";
      }}
    >
      <OrthographicCamera
        makeDefault
        position={[Math.sin(ISO_AZIMUTH) * distance - 0.5, distance * 0.82 + 0.7, Math.cos(ISO_AZIMUTH) * distance - 0.5]}
        near={0.1}
        far={200}
      />
      <FitCamera />
      <OrbitControls
        target={[-0.5, 0.7, -0.5]}
        enablePan={false}
        enableZoom={false}
        enableDamping
        minAzimuthAngle={ISO_AZIMUTH - 0.55}
        maxAzimuthAngle={ISO_AZIMUTH + 0.55}
        minPolarAngle={0.55}
        maxPolarAngle={1.05}
      />
      <OverlaySync anchors={anchors} agentObjects={agentObjects} />

      <hemisphereLight args={["#fff6e8", "#3a3f47", 0.9]} />
      <ambientLight intensity={0.25} />
      <directionalLight
        position={[14, 22, 10]}
        intensity={1.6}
        color="#fff1dc"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-16}
        shadow-camera-right={16}
        shadow-camera-top={14}
        shadow-camera-bottom={-14}
        shadow-camera-near={1}
        shadow-camera-far={60}
        shadow-bias={-0.0006}
      />

      <OfficeRooms desks={deskVisuals} approvalsPending={approvalsPending} onSelectRoom={onSelectRoom} />

      {ordered.map((agent, i) => {
        const slot = desks.get(agent.agent_key);
        if (!slot) return null;
        return (
          <AgentFigure
            key={agent.agent_key}
            agentKey={agent.agent_key}
            index={i}
            status={agent.status}
            enabled={agent.enabled}
            desk={slot}
            meeting={meetings[i]}
            selected={selectedAgent === agent.agent_key}
            hovered={hoveredAgent === agent.agent_key}
            reducedMotion={reducedMotion}
            onSelect={onSelectAgent}
            onHover={onHoverAgent}
            registerAnchor={registerAnchor}
          />
        );
      })}

      {externalSpecialists.map((ext, idx) => {
        const roomKey = ROOM_STATIONS[ext.studio_room_key] ? ext.studio_room_key : "mesa_agentes";
        const stations = ROOM_STATIONS[roomKey];
        const homeStation = stations[idx % stations.length];
        const look = EXTERNAL_GROUP_LOOK[ext.group_key] ?? EXTERNAL_GROUP_LOOK.standalone;
        const visualStatus = mapExternalVisualStatus(ext.status);
        return (
          <AgentFigure
            key={`ext:${ext.agent_key}`}
            agentKey={ext.studio_agent_key}
            index={idx + 8}
            status={visualStatus}
            enabled={true}
            desk={{
              room: roomKey,
              desk: homeStation.pos,
              seat: homeStation.pos,
              facing: homeStation.facing,
            }}
            meeting={extMeetings[idx % extMeetings.length]}
            selected={false}
            hovered={hoveredExternalKey === ext.agent_key}
            reducedMotion={reducedMotion}
            onSelect={onSelectAgent}
            onHover={onHoverAgent}
            registerAnchor={registerAnchor}
            lookOverride={look}
            isExternalSpecialist={true}
            onSelectCustom={() => onSelectExternalAgent?.(ext.agent_key)}
            onHoverCustom={(h) => onHoverExternalAgent?.(h ? ext.agent_key : null)}
            registerCustomAnchor={(obj) => registerExternalAnchor(ext.agent_key, obj)}
          />
        );
      })}
    </Canvas>
  );
}
