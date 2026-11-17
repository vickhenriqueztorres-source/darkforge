"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import {
  BoxGeometry,
  Color,
  InstancedMesh,
  Object3D,
  SphereGeometry,
} from "three";
import type { StudioOverviewChannel } from "@/lib/studio/hq-types";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import type { AgentKey, AgentVisualStatus, RoomKey } from "@/lib/studio/types";
import { AgentFigure } from "@/components/studio/office3d/AgentFigure";
import { FIGURE_PROPORTIONS } from "@/components/studio/office3d/figureProportions";
import { AGENT_LOOK, type XZ } from "@/components/studio/office3d/layout3d";
import { desaturateHex } from "./signText";
import { deskForAgent, routeInStudio, type StudioSlot } from "./layoutHQ";
import { figurePose, hashPhase, targetLocationForStatus } from "./crowdPose";

interface CrowdInstance {
  studioIndex: number;
  channelId: string;
  agentKey: AgentKey;
  agentIndex: number;
  slot: StudioSlot;
  status: AgentVisualStatus;
  enabled: boolean;
  provisioned: boolean;
  connected: boolean;
  dimmed: boolean;
  phase: number;
  deskPos: XZ;
  deskFacing: number;
  meetingPos: XZ;
  meetingFacing: number;
}

interface MotionState {
  x: number;
  z: number;
  facing: number;
  path: XZ[];
  walking: boolean;
  prevLocation: string;
  prevStatus: AgentVisualStatus;
  jumpAge: number;
}

export interface CrowdFiguresProps {
  slots: StudioSlot[];
  channelsById: Map<string, StudioOverviewChannel>;
  dimmedIds: Set<string>;
  focusedChannelId: string | null;
  reducedMotion: boolean;
  onSelectAgent?: (agentKey: AgentKey) => void;
  registerAgentAnchor?: (agentKey: AgentKey, object: Object3D | null) => void;
}

function lerpAngle(from: number, to: number, t: number) {
  let delta = ((to - from + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (delta < -Math.PI) delta += Math.PI * 2;
  return from + delta * t;
}

export function CrowdFigures({
  slots,
  channelsById,
  dimmedIds,
  focusedChannelId,
  reducedMotion,
  onSelectAgent,
  registerAgentAnchor,
}: CrowdFiguresProps) {
  const legsRef = useRef<InstancedMesh>(null);
  const torsoRef = useRef<InstancedMesh>(null);
  const headRef = useRef<InstancedMesh>(null);
  const hairRef = useRef<InstancedMesh>(null);

  const [selectedAgent, setSelectedAgent] = useState<AgentKey | null>(null);
  const [hoveredAgent, setHoveredAgent] = useState<AgentKey | null>(null);

  useEffect(() => {
    setSelectedAgent(null);
    setHoveredAgent(null);
  }, [focusedChannelId]);

  const instances = useMemo<CrowdInstance[]>(() => {
    const out: CrowdInstance[] = [];
    slots.forEach((slot, studioIndex) => {
      const ch = channelsById.get(slot.channelId);
      const connected = ch ? ch.channel.status === "active" : false;
      const provisioned = ch ? ch.provisioned : false;
      const dimmed = dimmedIds.has(slot.channelId);

      PIPELINE_ORDER.forEach((agentKey, agentIndex) => {
        const agent = ch?.agents.find((a) => a.agent_key === agentKey);
        const desk = deskForAgent(slot, agentKey);
        const meeting = slot.meeting[agentIndex];
        out.push({
          studioIndex,
          channelId: slot.channelId,
          agentKey,
          agentIndex,
          slot,
          status: agent?.status ?? "idle",
          enabled: provisioned && Boolean(agent?.enabled),
          provisioned,
          connected,
          dimmed,
          phase: hashPhase(`${slot.channelId}:${agentKey}`),
          deskPos: desk.seat,
          deskFacing: desk.facing,
          meetingPos: meeting.pos,
          meetingFacing: meeting.facing,
        });
      });
    });
    return out;
  }, [slots, channelsById, dimmedIds]);

  const geometries = useMemo(() => {
    const p = FIGURE_PROPORTIONS;
    // Combined lower body block matching the two legs width
    const legs = new BoxGeometry(0.34, p.legSize[1], p.legSize[2]);
    const torso = new BoxGeometry(p.torsoSize[0], p.torsoSize[1], p.torsoSize[2]);
    const head = new SphereGeometry(p.headRadius, 12, 10);
    const hair = new SphereGeometry(p.hairRadius, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    return { legs, torso, head, hair };
  }, []);

  useEffect(() => {
    return () => {
      Object.values(geometries).forEach((g) => g.dispose());
    };
  }, [geometries]);

  const motionMapRef = useRef(new Map<string, MotionState>());
  const dirtyRef = useRef(true);

  useEffect(() => {
    dirtyRef.current = true;
    const map = motionMapRef.current;
    for (const inst of instances) {
      const key = `${inst.channelId}:${inst.agentKey}`;
      const loc = targetLocationForStatus(inst.status, inst.enabled);
      const targetPos = loc === "meeting" ? inst.meetingPos : inst.deskPos;
      const targetFacing = loc === "meeting" ? inst.meetingFacing : inst.deskFacing;
      const existing = map.get(key);
      if (!existing) {
        map.set(key, {
          x: targetPos[0],
          z: targetPos[1],
          facing: targetFacing,
          path: [],
          walking: false,
          prevLocation: loc,
          prevStatus: inst.status,
          jumpAge: inst.status === "done" ? 0 : 1,
        });
      } else {
        if (inst.status === "done" && existing.prevStatus !== "done") {
          existing.jumpAge = 0;
        }
        existing.prevStatus = inst.status;
        if (reducedMotion || loc === "hidden" || existing.prevLocation === "hidden") {
          existing.x = targetPos[0];
          existing.z = targetPos[1];
          existing.facing = targetFacing;
          existing.path = [];
          existing.walking = false;
        } else if (loc !== existing.prevLocation) {
          existing.path = routeInStudio(inst.slot, [existing.x, existing.z], targetPos);
          existing.walking = existing.path.length > 0;
        }
        existing.prevLocation = loc;
      }
    }
  }, [instances, reducedMotion]);

  useLayoutEffect(() => {
    const col = new Color();
    instances.forEach((inst, i) => {
      const look = AGENT_LOOK[inst.agentKey];
      const baseShirt = inst.status === "cancelled" ? "#7c8288" : look.shirt;
      const shirtHex = inst.connected ? baseShirt : desaturateHex(baseShirt, 0.4);
      const skinHex = inst.connected ? look.skin : desaturateHex(look.skin, 0.4);
      const hairHex = inst.connected ? look.hair : desaturateHex(look.hair, 0.4);
      const legHex = inst.connected ? "#2c3440" : "#3a3f45";

      col.set(legHex);
      legsRef.current?.setColorAt(i, col);
      col.set(shirtHex);
      torsoRef.current?.setColorAt(i, col);
      col.set(skinHex);
      headRef.current?.setColorAt(i, col);
      col.set(hairHex);
      hairRef.current?.setColorAt(i, col);
    });
    for (const m of [legsRef.current, torsoRef.current, headRef.current, hairRef.current]) {
      if (m?.instanceColor) m.instanceColor.needsUpdate = true;
    }
    dirtyRef.current = true;
  }, [instances]);

  const dummyRef = useRef(new Object3D());

  // Single useFrame driving all 192 instanced figures
  useFrame((state, delta) => {
    const count = instances.length;
    if (count === 0) return;

    const dt = Math.min(delta, 0.05);
    const t = state.clock.elapsedTime;
    const p = FIGURE_PROPORTIONS;
    const dummy = dummyRef.current;

    let anyAnimated = dirtyRef.current;

    for (let i = 0; i < count; i++) {
      const inst = instances[i];
      const key = `${inst.channelId}:${inst.agentKey}`;
      const m = motionMapRef.current.get(key);
      if (!m) continue;

      const isFocusedStudio = focusedChannelId === inst.channelId;
      const loc = targetLocationForStatus(inst.status, inst.enabled);
      if (isFocusedStudio || loc === "hidden" || !inst.provisioned) {
        if (dirtyRef.current) {
          dummy.position.set(0, -10, 0);
          dummy.scale.set(0, 0, 0);
          dummy.rotation.set(0, 0, 0);
          dummy.updateMatrix();
          legsRef.current?.setMatrixAt(i, dummy.matrix);
          torsoRef.current?.setMatrixAt(i, dummy.matrix);
          headRef.current?.setMatrixAt(i, dummy.matrix);
          hairRef.current?.setMatrixAt(i, dummy.matrix);
        }
        continue;
      }

      if (m.walking && !reducedMotion) {
        anyAnimated = true;
        const target = m.path[0];
        if (!target) {
          m.walking = false;
        } else {
          const dx = target[0] - m.x;
          const dz = target[1] - m.z;
          const dist = Math.hypot(dx, dz);
          const step = p.walkSpeed * dt;
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
      } else {
        const targetFacing = loc === "meeting" ? inst.meetingFacing : inst.deskFacing;
        if (Math.abs(m.facing - targetFacing) > 0.01 && !reducedMotion) {
          m.facing = lerpAngle(m.facing, targetFacing, Math.min(1, dt * 8));
          anyAnimated = true;
        } else {
          m.facing = targetFacing;
        }
      }

      if (inst.status === "done" && m.jumpAge < 0.7 && !reducedMotion) {
        m.jumpAge += dt;
        anyAnimated = true;
      }

      if (!reducedMotion && (inst.status === "working" || inst.status === "idle" || inst.status === "waiting_approval" || inst.status === "needs_review" || inst.status === "waiting_input" || m.walking)) {
        anyAnimated = true;
      }

      if (!anyAnimated && !dirtyRef.current) continue;

      const pose = figurePose(inst.status, inst.enabled, t, inst.phase, reducedMotion, m.jumpAge);
      const seatedOffset = pose.seated && !m.walking ? p.seatedBodyOffsetY : 0;
      const walkBob = m.walking && !reducedMotion ? Math.abs(Math.sin((t + inst.phase) * 9)) * 0.05 : 0;
      const baseY = pose.yOffset + seatedOffset + walkBob;

      // Legs
      dummy.position.set(m.x, baseY + 0.25, m.z);
      dummy.rotation.set(pose.seated && !m.walking ? -0.45 : 0, m.facing, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      legsRef.current?.setMatrixAt(i, dummy.matrix);

      // Torso / shirt
      dummy.position.set(m.x, baseY + p.torsoY, m.z);
      dummy.rotation.set(pose.bodyTiltX, m.facing, 0);
      dummy.scale.set(1, pose.torsoScaleY, 1);
      dummy.updateMatrix();
      torsoRef.current?.setMatrixAt(i, dummy.matrix);

      // Head
      dummy.position.set(m.x, baseY + p.headY, m.z);
      dummy.rotation.set(pose.headTiltX, m.facing + pose.headYaw, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      headRef.current?.setMatrixAt(i, dummy.matrix);

      // Hair
      dummy.position.set(m.x, baseY + p.headY + p.hairOffset[1], m.z);
      dummy.rotation.set(pose.headTiltX + p.hairRotX, m.facing + pose.headYaw, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      hairRef.current?.setMatrixAt(i, dummy.matrix);
    }

    if (anyAnimated || dirtyRef.current) {
      if (legsRef.current) legsRef.current.instanceMatrix.needsUpdate = true;
      if (torsoRef.current) torsoRef.current.instanceMatrix.needsUpdate = true;
      if (headRef.current) headRef.current.instanceMatrix.needsUpdate = true;
      if (hairRef.current) hairRef.current.instanceMatrix.needsUpdate = true;
      dirtyRef.current = false;
    }
  });

  // LOD: full AgentFigure set for the currently focused studio
  const focusedSlot = useMemo(
    () => (focusedChannelId ? slots.find((s) => s.channelId === focusedChannelId) ?? null : null),
    [focusedChannelId, slots]
  );
  const focusedChannel = focusedSlot ? channelsById.get(focusedSlot.channelId) : undefined;
  const noopRoute = useMemo(
    () =>
      focusedSlot
        ? (_fr: RoomKey, fromPos: XZ, _tr: RoomKey, toPos: XZ) => routeInStudio(focusedSlot, fromPos, toPos)
        : undefined,
    [focusedSlot]
  );
  const noopAnchor = useMemo(() => () => {}, []);

  const count = instances.length;

  return (
    <group>
      {count > 0 && (
        <>
          <instancedMesh key={`cl-${count}`} ref={legsRef} args={[geometries.legs, undefined, count]} castShadow>
            <meshStandardMaterial color="#ffffff" roughness={0.8} />
          </instancedMesh>
          <instancedMesh key={`ct-${count}`} ref={torsoRef} args={[geometries.torso, undefined, count]} castShadow>
            <meshStandardMaterial color="#ffffff" roughness={0.7} />
          </instancedMesh>
          <instancedMesh key={`ch-${count}`} ref={headRef} args={[geometries.head, undefined, count]} castShadow>
            <meshStandardMaterial color="#ffffff" roughness={0.6} />
          </instancedMesh>
          <instancedMesh key={`chr-${count}`} ref={hairRef} args={[geometries.hair, undefined, count]}>
            <meshStandardMaterial color="#ffffff" roughness={0.9} />
          </instancedMesh>
        </>
      )}

      {focusedSlot && focusedChannel && focusedChannel.provisioned && (
        <group>
          {PIPELINE_ORDER.map((agentKey, i) => {
            const agent = focusedChannel.agents.find((a) => a.agent_key === agentKey);
            if (!agent) return null;
            const d = deskForAgent(focusedSlot, agentKey);
            return (
              <AgentFigure
                key={`${focusedSlot.channelId}:${agentKey}`}
                agentKey={agentKey}
                index={i}
                status={agent.status}
                enabled={agent.enabled}
                desk={{ room: "mesa_agentes", desk: d.desk, seat: d.seat, facing: d.facing }}
                meeting={focusedSlot.meeting[i]}
                selected={selectedAgent === agentKey}
                hovered={hoveredAgent === agentKey}
                reducedMotion={reducedMotion}
                onSelect={(k) => {
                  setSelectedAgent(k);
                  onSelectAgent?.(k);
                }}
                onHover={setHoveredAgent}
                registerAnchor={registerAgentAnchor ?? noopAnchor}
                routeFn={noopRoute}
                allowIdleWander={false}
              />
            );
          })}
        </group>
      )}
    </group>
  );
}
