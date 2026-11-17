"use client";

import { useCallback, useEffect, useMemo, useRef, type MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, OrthographicCamera } from "@react-three/drei";
import { Vector3, type Object3D } from "three";
import type { AgentKey, RoomKey, StudioAgentState } from "@/lib/studio/types";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import { AgentFigure } from "./AgentFigure";
import { OfficeRooms } from "./OfficeRooms";
import { AGENT_LABEL_HEIGHT, ROOM_ORDER, assignDesks, meetingSeat, roomLabelPosition } from "./layout3d";

const ISO_AZIMUTH = Math.PI / 4;
const APPROVAL_STATUSES = new Set(["waiting_approval", "needs_review", "waiting_input"]);

/** DOM label elements keyed by `room:<key>` or `agent:<key>`, positioned over the canvas every frame. */
export type OverlayAnchors = MutableRefObject<Map<string, HTMLElement>>;

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
  agentObjects: MutableRefObject<Map<AgentKey, Object3D>>;
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
        const obj = agentObjects.current.get(key as AgentKey);
        if (!obj) continue;
        v.set(obj.position.x, AGENT_LABEL_HEIGHT, obj.position.z);
      }
      v.project(camera);
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      const lift = kind === "agent" ? "-100%" : "-50%";
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, ${lift})`;
      el.style.visibility = "visible";
    }
  });
  return null;
}

export interface OfficeSceneProps {
  agents: StudioAgentState[];
  selectedAgent: AgentKey | null;
  hoveredAgent: AgentKey | null;
  active: boolean;
  reducedMotion: boolean;
  anchors: OverlayAnchors;
  onSelectAgent: (agentKey: AgentKey) => void;
  onHoverAgent: (agentKey: AgentKey | null) => void;
  onSelectRoom: (roomKey: RoomKey) => void;
}

export default function OfficeScene({
  agents,
  selectedAgent,
  hoveredAgent,
  active,
  reducedMotion,
  anchors,
  onSelectAgent,
  onHoverAgent,
  onSelectRoom,
}: OfficeSceneProps) {
  const seatingKey = agents.map((a) => `${a.agent_key}:${a.room_key}`).join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reassign desks only when the seating changes, not on every event
  const desks = useMemo(() => assignDesks(agents), [seatingKey]);
  const meetings = useMemo(() => PIPELINE_ORDER.map((_, i) => meetingSeat(i)), []);

  const agentObjects = useRef(new Map<AgentKey, Object3D>());
  const registerAnchor = useCallback((key: AgentKey, object: Object3D | null) => {
    if (object) agentObjects.current.set(key, object);
    else agentObjects.current.delete(key);
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
    </Canvas>
  );
}
