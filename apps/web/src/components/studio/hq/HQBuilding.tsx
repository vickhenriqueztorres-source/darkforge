"use client";

import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { ContactShadows, RoundedBox } from "@react-three/drei";
import {
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  CylinderGeometry,
  Float32BufferAttribute,
  IcosahedronGeometry,
  InstancedMesh,
  Matrix4,
  Object3D,
  PlaneGeometry,
  SRGBColorSpace,
} from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { StudioOverviewChannel } from "@/lib/studio/hq-types";
import { isChannelConnected, studioLamp } from "@/lib/studio/hq-status";
import { PIPELINE_ORDER } from "@/lib/studio/studio-layout";
import { PALETTE } from "@/components/studio/office3d/layout3d";
import {
  HQ_DOOR_WIDTH,
  HQ_OUTER_WALL_HEIGHT,
  HQ_PARTITION_HEIGHT,
  type BuildingLayout,
  type StudioSlot,
} from "./layoutHQ";
import { desaturateHex } from "./signText";

export interface StudioRenderEntry {
  slot: StudioSlot;
  channel: StudioOverviewChannel;
  color: string;
  connected: boolean;
  dimmed: boolean;
}

function paintGeometry(geo: BufferGeometry, hex: string): BufferGeometry {
  const nonIndexed = geo.index ? geo.toNonIndexed() : geo.clone();
  if (geo !== nonIndexed) geo.dispose();
  const count = nonIndexed.attributes.position.count;
  const col = new Color(hex);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    colors[i * 3] = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;
  }
  nonIndexed.setAttribute("color", new Float32BufferAttribute(colors, 3));
  if (!nonIndexed.attributes.uv) {
    nonIndexed.setAttribute("uv", new BufferAttribute(new Float32Array(count * 2), 2));
  }
  return nonIndexed;
}

function mergeColoredParts(parts: BufferGeometry[]): BufferGeometry {
  const merged = mergeGeometries(parts, false);
  for (const p of parts) p.dispose();
  if (!merged) {
    return new BoxGeometry(0.01, 0.01, 0.01);
  }
  return merged;
}

let cachedOnAirTexture: CanvasTexture | null = null;
function getOnAirTexture(): CanvasTexture | null {
  if (typeof document === "undefined") return null;
  if (cachedOnAirTexture) return cachedOnAirTexture;
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 48;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#2b1c0c";
    ctx.fillRect(0, 0, 256, 48);
    ctx.strokeStyle = "#f5a623";
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, 252, 44);
    ctx.fillStyle = "#fff3d6";
    ctx.font = "700 22px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("EM PRODUÇÃO", 128, 25);
  }
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  cachedOnAirTexture = tex;
  return tex;
}

function buildWallMeshes(layout: BuildingLayout, dimmedSet: Set<string>) {
  const t = 0.18;
  const opaqueWallGeos: BufferGeometry[] = [];
  const opaqueCapGeos: BufferGeometry[] = [];
  const dimmedWallGeos: BufferGeometry[] = [];
  const dimmedCapGeos: BufferGeometry[] = [];

  const slotAtX = (x: number, z: number) =>
    layout.slots.find((s) => x >= s.x0 - 0.05 && x <= s.x1 + 0.05 && Math.abs(s.door.wallZ - z) < 0.05);

  const slotsTouchingX = (x: number, midZ: number) =>
    layout.slots.filter((s) => (Math.abs(s.x0 - x) < 0.05 || Math.abs(s.x1 - x) < 0.05) && midZ >= s.z0 && midZ <= s.z1);

  for (const w of layout.walls) {
    const cuts = [w.from, ...w.gaps.flatMap((g) => [g - HQ_DOOR_WIDTH / 2, g + HQ_DOOR_WIDTH / 2]), w.to];
    for (let i = 0; i < cuts.length; i += 2) {
      const a = cuts[i];
      const b = cuts[i + 1];
      const len = b - a;
      if (len <= 0.01) continue;
      const mid = (a + b) / 2;

      let isDimmed = false;
      if (w.axis === "z" && w.gaps.length > 0) {
        const sl = slotAtX(mid, w.at);
        if (sl && dimmedSet.has(sl.channelId)) isDimmed = true;
      } else if (w.axis === "x" && w.height === HQ_PARTITION_HEIGHT) {
        const touching = slotsTouchingX(w.at, mid);
        if (touching.length > 0 && touching.every((s) => dimmedSet.has(s.channelId))) isDimmed = true;
      } else if (w.axis === "z" && w.height === HQ_PARTITION_HEIGHT) {
        const touching = layout.slots.filter(
          (s) => Math.abs(s.z1 - w.at) < 0.05 && mid >= s.x0 && mid <= s.x1
        );
        if (touching.length > 0 && touching.every((s) => dimmedSet.has(s.channelId))) isDimmed = true;
      }

      const sx = w.axis === "x" ? t : len;
      const sz = w.axis === "x" ? len : t;
      const px = w.axis === "x" ? w.at : mid;
      const pz = w.axis === "x" ? mid : w.at;

      const body = new BoxGeometry(sx, w.height, sz);
      body.translate(px, w.height / 2, pz);
      const cap = new BoxGeometry(sx + 0.04, 0.06, sz + 0.04);
      cap.translate(px, w.height + 0.03, pz);

      if (isDimmed) {
        dimmedWallGeos.push(body);
        dimmedCapGeos.push(cap);
      } else {
        opaqueWallGeos.push(body);
        opaqueCapGeos.push(cap);
      }
    }
  }

  const mergeOrNull = (list: BufferGeometry[]) => {
    if (list.length === 0) return null;
    const m = mergeGeometries(list, false);
    for (const g of list) g.dispose();
    return m;
  };

  return {
    opaqueWalls: mergeOrNull(opaqueWallGeos),
    opaqueCaps: mergeOrNull(opaqueCapGeos),
    dimmedWalls: mergeOrNull(dimmedWallGeos),
    dimmedCaps: mergeOrNull(dimmedCapGeos),
  };
}

function createSharedTemplates() {
  // Compact studio desk (centered at [0, 0, 0], facing -Z in local coords)
  const top = paintGeometry(new BoxGeometry(1.12, 0.06, 0.54).translate(0, 0.72, 0), PALETTE.wood);
  const legL = paintGeometry(new BoxGeometry(0.05, 0.69, 0.48).translate(-0.5, 0.345, 0), PALETTE.woodDark);
  const legR = paintGeometry(new BoxGeometry(0.05, 0.69, 0.48).translate(0.5, 0.345, 0), PALETTE.woodDark);
  const keyboard = paintGeometry(new BoxGeometry(0.42, 0.025, 0.14).translate(0, 0.76, 0.14), "#2a3038");
  const desk = mergeColoredParts([top, legL, legR, keyboard]);

  // Monitor body + stand (centered at desk [0, 0, 0])
  const stand = paintGeometry(new BoxGeometry(0.07, 0.24, 0.07).translate(0, 0.87, -0.1), PALETTE.metal);
  const bezel = paintGeometry(new BoxGeometry(0.78, 0.44, 0.045).translate(0, 1.18, -0.1), "#20262e");
  const monitorBody = mergeColoredParts([stand, bezel]);

  const monitorScreen = new PlaneGeometry(0.7, 0.36);
  monitorScreen.translate(0, 1.18, -0.074);

  // Chair (centered at seat [0, 0, 0], facing -Z)
  const seat = paintGeometry(new BoxGeometry(0.42, 0.06, 0.4).translate(0, 0.43, 0.02), "#323a44");
  const back = paintGeometry(new BoxGeometry(0.4, 0.44, 0.055).translate(0, 0.67, 0.22), "#323a44");
  const pole = paintGeometry(new BoxGeometry(0.055, 0.4, 0.055).translate(0, 0.2, 0.02), PALETTE.metal);
  const chair = mergeColoredParts([seat, back, pole]);

  // Door frame (centered at door [0, 0, 0])
  const frameL = new BoxGeometry(0.08, 1.56, 0.24).translate(-HQ_DOOR_WIDTH / 2 - 0.02, 0.78, 0);
  const frameR = new BoxGeometry(0.08, 1.56, 0.24).translate(HQ_DOOR_WIDTH / 2 + 0.02, 0.78, 0);
  const lintel = new BoxGeometry(HQ_DOOR_WIDTH + 0.12, 0.1, 0.26).translate(0, 1.56, 0);
  const doorFrame = mergeGeometries([frameL, frameR, lintel], false)!;
  frameL.dispose();
  frameR.dispose();
  lintel.dispose();

  // Meeting table
  const mtTop = paintGeometry(new CylinderGeometry(0.72, 0.72, 0.07, 28).translate(0, 0.72, 0), PALETTE.wood);
  const mtBase = paintGeometry(new CylinderGeometry(0.14, 0.24, 0.7, 14).translate(0, 0.35, 0), PALETTE.woodDark);
  const meetingTable = mergeColoredParts([mtTop, mtBase]);

  // Plant
  const pot = paintGeometry(new CylinderGeometry(0.2, 0.15, 0.4, 12).translate(0, 0.2, 0), "#c9b9a0");
  const leaf1 = paintGeometry(new IcosahedronGeometry(0.36, 1).translate(0, 0.64, 0), PALETTE.plant);
  const leaf2 = paintGeometry(new IcosahedronGeometry(0.22, 1).translate(0.14, 0.9, 0.04), "#5f8c58");
  const plant = mergeColoredParts([pot, leaf1, leaf2]);

  // Construction easel ("cavalete") for unprovisioned studios
  const legA = paintGeometry(new BoxGeometry(0.06, 0.92, 0.06).rotateX(0.22).translate(-0.32, 0.44, 0.1), PALETTE.wood);
  const legB = paintGeometry(new BoxGeometry(0.06, 0.92, 0.06).rotateX(0.22).translate(0.32, 0.44, 0.1), PALETTE.wood);
  const legC = paintGeometry(new BoxGeometry(0.06, 0.92, 0.06).rotateX(-0.22).translate(-0.32, 0.44, -0.1), PALETTE.woodDark);
  const legD = paintGeometry(new BoxGeometry(0.06, 0.92, 0.06).rotateX(-0.22).translate(0.32, 0.44, -0.1), PALETTE.woodDark);
  const board = paintGeometry(new BoxGeometry(0.92, 0.26, 0.05).translate(0, 0.66, 0.14), PALETTE.accent);
  const easel = mergeColoredParts([legA, legB, legC, legD, board]);

  // Sign housing (back body) & face & stripe & onAir plate
  const signHousing = new BoxGeometry(3.2, 0.6, 0.06).translate(0, 0, -0.005);
  const signFace = new BoxGeometry(3.14, 0.54, 0.016).translate(0, 0, 0.032);
  const signStripe = new BoxGeometry(0.08, 0.54, 0.018).translate(-1.53, 0, 0.038);
  const onAirPlate = new BoxGeometry(1.48, 0.22, 0.06);
  const tarp = new BoxGeometry(1.22, 0.22, 0.64);
  const floorPlane = new PlaneGeometry(8.38, 6.98);
  floorPlane.rotateX(-Math.PI / 2);
  const rugPlane = new PlaneGeometry(6.4, 3.35);
  rugPlane.rotateX(-Math.PI / 2);
  const spillPlane = new PlaneGeometry(1.7, 1.55);
  spillPlane.rotateX(-Math.PI / 2);

  return {
    desk,
    monitorBody,
    monitorScreen,
    chair,
    doorFrame,
    meetingTable,
    plant,
    easel,
    signHousing,
    signFace,
    signStripe,
    onAirPlate,
    tarp,
    floorPlane,
    rugPlane,
    spillPlane,
  };
}

interface BatchProps {
  entries: StudioRenderEntry[];
  templates: ReturnType<typeof createSharedTemplates>;
  opacity: number;
  transparent: boolean;
}

function StudioFurnitureBatch({ entries, templates, opacity, transparent }: BatchProps) {
  const floorRef = useRef<InstancedMesh>(null);
  const rugRef = useRef<InstancedMesh>(null);
  const doorRef = useRef<InstancedMesh>(null);
  const deskRef = useRef<InstancedMesh>(null);
  const monBodyRef = useRef<InstancedMesh>(null);
  const monScreenRef = useRef<InstancedMesh>(null);
  const chairRef = useRef<InstancedMesh>(null);
  const tableRef = useRef<InstancedMesh>(null);
  const plantRef = useRef<InstancedMesh>(null);
  const signHouseRef = useRef<InstancedMesh>(null);
  const signFaceLitRef = useRef<InstancedMesh>(null);
  const signFaceOffRef = useRef<InstancedMesh>(null);
  const signStripeRef = useRef<InstancedMesh>(null);
  const onAirRef = useRef<InstancedMesh>(null);
  const tarpRef = useRef<InstancedMesh>(null);
  const easelRef = useRef<InstancedMesh>(null);
  const spillRef = useRef<InstancedMesh>(null);

  const count = entries.length;
  const deskCount = count * 8;
  const litSigns = useMemo(() => entries.filter((e) => e.connected), [entries]);
  const offSigns = useMemo(() => entries.filter((e) => !e.connected), [entries]);
  const onAirEntries = useMemo(() => entries.filter((e) => e.channel.active_item !== null && e.connected), [entries]);
  const unprovEntries = useMemo(() => entries.filter((e) => !e.channel.provisioned), [entries]);
  const spillEntries = useMemo(() => entries.filter((e) => e.connected && e.channel.provisioned), [entries]);
  const onAirTexture = useMemo(() => getOnAirTexture(), []);

  useLayoutEffect(() => {
    const dummy = new Object3D();
    const col = new Color();

    for (let i = 0; i < count; i++) {
      const { slot, channel, color, connected } = entries[i];
      const cx = (slot.x0 + slot.x1) / 2;
      const cz = (slot.z0 + slot.z1) / 2;
      const effColor = connected ? color : desaturateHex(color, 0.4);
      const lamp = studioLamp(channel);

      // Floor
      dummy.position.set(cx, 0.01, cz);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      floorRef.current?.setMatrixAt(i, dummy.matrix);
      col.set(!channel.provisioned ? "#1c222a" : connected ? "#27303b" : "#282c31");
      floorRef.current?.setColorAt(i, col);

      // Rug
      dummy.position.set((slot.rug.x0 + slot.rug.x1) / 2, 0.02, (slot.rug.z0 + slot.rug.z1) / 2);
      dummy.updateMatrix();
      rugRef.current?.setMatrixAt(i, dummy.matrix);
      col.set(effColor);
      rugRef.current?.setColorAt(i, col);

      // Door frame
      dummy.position.set(slot.door.centerX, 0, slot.door.wallZ);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      doorRef.current?.setMatrixAt(i, dummy.matrix);
      doorRef.current?.setColorAt(i, col);

      // Meeting table
      dummy.position.set(slot.meetingTable.x, 0, slot.meetingTable.z);
      dummy.updateMatrix();
      tableRef.current?.setMatrixAt(i, dummy.matrix);

      // Plant
      dummy.position.set(slot.plant[0], 0, slot.plant[1]);
      dummy.updateMatrix();
      plantRef.current?.setMatrixAt(i, dummy.matrix);

      // Sign housing + stripe
      dummy.position.set(slot.sign.pos[0], slot.sign.pos[1], slot.sign.pos[2]);
      dummy.rotation.set(0, slot.sign.rotationY, 0);
      dummy.updateMatrix();
      signHouseRef.current?.setMatrixAt(i, dummy.matrix);
      signStripeRef.current?.setMatrixAt(i, dummy.matrix);
      signStripeRef.current?.setColorAt(i, col);

      // 8 desks + monitors + chairs
      for (let j = 0; j < 8; j++) {
        const dIdx = i * 8 + j;
        const dSlot = slot.desks[j];
        const agentKey = PIPELINE_ORDER[j];
        const agent = channel.agents.find((a) => a.agent_key === agentKey);

        dummy.position.set(dSlot.desk[0], 0, dSlot.desk[1]);
        dummy.rotation.set(0, dSlot.facing === 0 ? Math.PI : 0, 0);
        dummy.updateMatrix();
        deskRef.current?.setMatrixAt(dIdx, dummy.matrix);
        monBodyRef.current?.setMatrixAt(dIdx, dummy.matrix);
        monScreenRef.current?.setMatrixAt(dIdx, dummy.matrix);

        if (!channel.provisioned || !connected) {
          col.set(PALETTE.screenOff);
        } else if (!agent || !agent.enabled || agent.status === "disabled") {
          col.set(PALETTE.screenOff);
        } else if (agent.status === "failed" || agent.status === "blocked" || agent.status === "no_signal") {
          col.set(PALETTE.err);
        } else if (agent.status === "working") {
          col.set(PALETTE.screenWork);
        } else {
          col.set(PALETTE.screenIdle);
        }
        monScreenRef.current?.setColorAt(dIdx, col);

        dummy.position.set(dSlot.seat[0], 0, dSlot.seat[1]);
        dummy.rotation.set(0, dSlot.facing === 0 ? Math.PI : 0, 0);
        dummy.updateMatrix();
        chairRef.current?.setMatrixAt(dIdx, dummy.matrix);
      }
      void lamp;
    }

    litSigns.forEach((entry, idx) => {
      dummy.position.set(entry.slot.sign.pos[0], entry.slot.sign.pos[1], entry.slot.sign.pos[2]);
      dummy.rotation.set(0, entry.slot.sign.rotationY, 0);
      dummy.updateMatrix();
      signFaceLitRef.current?.setMatrixAt(idx, dummy.matrix);
    });

    offSigns.forEach((entry, idx) => {
      dummy.position.set(entry.slot.sign.pos[0], entry.slot.sign.pos[1], entry.slot.sign.pos[2]);
      dummy.rotation.set(0, entry.slot.sign.rotationY, 0);
      dummy.updateMatrix();
      signFaceOffRef.current?.setMatrixAt(idx, dummy.matrix);
    });

    onAirEntries.forEach((entry, idx) => {
      dummy.position.set(entry.slot.onAir[0], entry.slot.onAir[1], entry.slot.onAir[2]);
      dummy.rotation.set(0, entry.slot.sign.rotationY, 0);
      dummy.updateMatrix();
      onAirRef.current?.setMatrixAt(idx, dummy.matrix);
    });

    unprovEntries.forEach((entry, sIdx) => {
      for (let j = 0; j < 8; j++) {
        const dSlot = entry.slot.desks[j];
        dummy.position.set(dSlot.desk[0], 0.8, dSlot.desk[1]);
        dummy.rotation.set(0, 0, 0);
        dummy.updateMatrix();
        tarpRef.current?.setMatrixAt(sIdx * 8 + j, dummy.matrix);
      }
      dummy.position.set(entry.slot.door.outer[0], 0, entry.slot.door.outer[1]);
      dummy.rotation.set(0, entry.slot.sign.rotationY, 0);
      dummy.updateMatrix();
      easelRef.current?.setMatrixAt(sIdx, dummy.matrix);
    });

    spillEntries.forEach((entry, idx) => {
      const dirOut = entry.slot.side === "north" ? 1 : -1;
      dummy.position.set(entry.slot.door.centerX, 0.015, entry.slot.door.wallZ + dirOut * 0.85);
      dummy.rotation.set(0, 0, 0);
      dummy.updateMatrix();
      spillRef.current?.setMatrixAt(idx, dummy.matrix);
    });

    const allMeshes = [
      floorRef.current,
      rugRef.current,
      doorRef.current,
      deskRef.current,
      monBodyRef.current,
      monScreenRef.current,
      chairRef.current,
      tableRef.current,
      plantRef.current,
      signHouseRef.current,
      signFaceLitRef.current,
      signFaceOffRef.current,
      signStripeRef.current,
      onAirRef.current,
      tarpRef.current,
      easelRef.current,
      spillRef.current,
    ];
    for (const m of allMeshes) {
      if (!m) continue;
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
    }
  }, [entries, count, litSigns, offSigns, onAirEntries, unprovEntries, spillEntries]);

  if (count === 0) return null;

  return (
    <group>
      <instancedMesh key={`fl-${count}`} ref={floorRef} args={[templates.floorPlane, undefined, count]} receiveShadow>
        <meshStandardMaterial color="#ffffff" roughness={0.85} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`rg-${count}`} ref={rugRef} args={[templates.rugPlane, undefined, count]} receiveShadow>
        <meshStandardMaterial color="#ffffff" roughness={0.95} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`dr-${count}`} ref={doorRef} args={[templates.doorFrame, undefined, count]}>
        <meshStandardMaterial color="#ffffff" roughness={0.65} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`dk-${deskCount}`} ref={deskRef} args={[templates.desk, undefined, deskCount]} receiveShadow>
        <meshStandardMaterial vertexColors roughness={0.7} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`mb-${deskCount}`} ref={monBodyRef} args={[templates.monitorBody, undefined, deskCount]}>
        <meshStandardMaterial vertexColors roughness={0.6} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`ms-${deskCount}`} ref={monScreenRef} args={[templates.monitorScreen, undefined, deskCount]}>
        <meshBasicMaterial color="#ffffff" transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`ch-${deskCount}`} ref={chairRef} args={[templates.chair, undefined, deskCount]}>
        <meshStandardMaterial vertexColors roughness={0.8} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`mt-${count}`} ref={tableRef} args={[templates.meetingTable, undefined, count]} receiveShadow>
        <meshStandardMaterial vertexColors roughness={0.6} transparent={transparent} opacity={opacity} />
      </instancedMesh>
      <instancedMesh key={`pl-${count}`} ref={plantRef} args={[templates.plant, undefined, count]}>
        <meshStandardMaterial vertexColors roughness={0.9} flatShading transparent={transparent} opacity={opacity} />
      </instancedMesh>

      {/* Sign lightbox housings + faces + stripes */}
      <instancedMesh key={`sh-${count}`} ref={signHouseRef} args={[templates.signHousing, undefined, count]}>
        <meshStandardMaterial color="#1f262e" roughness={0.7} transparent={transparent} opacity={transparent ? 0.6 : 1} />
      </instancedMesh>
      {litSigns.length > 0 && (
        <instancedMesh key={`sfl-${litSigns.length}`} ref={signFaceLitRef} args={[templates.signFace, undefined, litSigns.length]}>
          <meshStandardMaterial
            color="#f4efe6"
            emissive="#f4efe6"
            emissiveIntensity={0.35}
            roughness={0.5}
            transparent={transparent}
            opacity={transparent ? 0.6 : 1}
          />
        </instancedMesh>
      )}
      {offSigns.length > 0 && (
        <instancedMesh key={`sfo-${offSigns.length}`} ref={signFaceOffRef} args={[templates.signFace, undefined, offSigns.length]}>
          <meshStandardMaterial
            color="#8f949a"
            roughness={0.75}
            transparent={transparent}
            opacity={transparent ? 0.6 : 1}
          />
        </instancedMesh>
      )}
      <instancedMesh key={`ss-${count}`} ref={signStripeRef} args={[templates.signStripe, undefined, count]}>
        <meshStandardMaterial color="#ffffff" roughness={0.6} transparent={transparent} opacity={transparent ? 0.6 : 1} />
      </instancedMesh>

      {onAirEntries.length > 0 && onAirTexture && (
        <instancedMesh key={`oa-${onAirEntries.length}`} ref={onAirRef} args={[templates.onAirPlate, undefined, onAirEntries.length]}>
          <meshStandardMaterial
            map={onAirTexture}
            emissive="#f5a623"
            emissiveMap={onAirTexture}
            emissiveIntensity={0.7}
            roughness={0.45}
            transparent={transparent}
            opacity={transparent ? 0.6 : 1}
          />
        </instancedMesh>
      )}

      {unprovEntries.length > 0 && (
        <>
          <instancedMesh key={`tp-${unprovEntries.length}`} ref={tarpRef} args={[templates.tarp, undefined, unprovEntries.length * 8]}>
            <meshStandardMaterial color="#5d6570" roughness={0.95} transparent={transparent} opacity={opacity} />
          </instancedMesh>
          <instancedMesh key={`es-${unprovEntries.length}`} ref={easelRef} args={[templates.easel, undefined, unprovEntries.length]}>
            <meshStandardMaterial vertexColors roughness={0.8} transparent={transparent} opacity={opacity} />
          </instancedMesh>
        </>
      )}

      {spillEntries.length > 0 && (
        <instancedMesh key={`sp-${spillEntries.length}`} ref={spillRef} args={[templates.spillPlane, undefined, spillEntries.length]}>
          <meshBasicMaterial color="#ffcf87" transparent opacity={transparent ? 0.04 : 0.13} depthWrite={false} />
        </instancedMesh>
      )}
    </group>
  );
}

export interface HQBuildingProps {
  layout: BuildingLayout;
  entries: StudioRenderEntry[];
}

export function HQBuilding({ layout, entries }: HQBuildingProps) {
  const templates = useMemo(() => createSharedTemplates(), []);
  useEffect(() => {
    return () => {
      Object.values(templates).forEach((g) => g.dispose());
    };
  }, [templates]);

  const dimmedSet = useMemo(
    () => new Set(entries.filter((e) => e.dimmed).map((e) => e.slot.channelId)),
    [entries]
  );

  const wallGeos = useMemo(() => buildWallMeshes(layout, dimmedSet), [layout, dimmedSet]);
  useEffect(() => {
    return () => {
      wallGeos.opaqueWalls?.dispose();
      wallGeos.opaqueCaps?.dispose();
      wallGeos.dimmedWalls?.dispose();
      wallGeos.dimmedCaps?.dispose();
    };
  }, [wallGeos]);

  const corridorGeo = useMemo(() => {
    const geos = layout.corridors.map((c) => {
      const p = new PlaneGeometry(c.x1 - c.x0, c.z1 - c.z0);
      p.rotateX(-Math.PI / 2);
      p.translate((c.x0 + c.x1) / 2, 0.008, (c.z0 + c.z1) / 2);
      return p;
    });
    const merged = mergeGeometries(geos, false)!;
    geos.forEach((g) => g.dispose());
    return merged;
  }, [layout.corridors]);
  useEffect(() => () => corridorGeo.dispose(), [corridorGeo]);

  const normalEntries = useMemo(() => entries.filter((e) => !e.dimmed), [entries]);
  const dimmedEntries = useMemo(() => entries.filter((e) => e.dimmed), [entries]);

  const width = layout.bounds.x1 - layout.bounds.x0;
  const depth = layout.bounds.z1 - layout.bounds.z0;
  const cx = (layout.bounds.x0 + layout.bounds.x1) / 2;
  const cz = (layout.bounds.z0 + layout.bounds.z1) / 2;

  return (
    <group>
      {/* Chamfered maquette base plate + lighter bevel trim */}
      <RoundedBox args={[width + 1.6, 0.44, depth + 1.6]} radius={0.15} smoothness={2} position={[cx, -0.22, cz]} receiveShadow>
        <meshStandardMaterial color="#11161c" roughness={0.85} />
      </RoundedBox>
      <RoundedBox args={[width + 1.72, 0.14, depth + 1.72]} radius={0.08} smoothness={2} position={[cx, -0.38, cz]}>
        <meshStandardMaterial color="#1d2530" roughness={0.75} />
      </RoundedBox>

      {/* Contact shadow under the maquette */}
      <ContactShadows
        position={[cx, -0.45, cz]}
        opacity={0.35}
        scale={Math.max(width, depth) * 1.35}
        blur={2.2}
        far={3}
        frames={1}
      />

      {/* Corridor floor */}
      <mesh geometry={corridorGeo} receiveShadow>
        <meshStandardMaterial color="#1b2129" roughness={0.55} />
      </mesh>

      {/* Building walls (merged) */}
      {wallGeos.opaqueWalls && (
        <mesh geometry={wallGeos.opaqueWalls} castShadow receiveShadow>
          <meshStandardMaterial color={PALETTE.wall} roughness={0.85} />
        </mesh>
      )}
      {wallGeos.opaqueCaps && (
        <mesh geometry={wallGeos.opaqueCaps}>
          <meshStandardMaterial color={PALETTE.wallCap} roughness={0.75} />
        </mesh>
      )}
      {wallGeos.dimmedWalls && (
        <mesh geometry={wallGeos.dimmedWalls}>
          <meshStandardMaterial color={PALETTE.wall} roughness={0.85} transparent opacity={0.25} />
        </mesh>
      )}
      {wallGeos.dimmedCaps && (
        <mesh geometry={wallGeos.dimmedCaps}>
          <meshStandardMaterial color={PALETTE.wallCap} roughness={0.75} transparent opacity={0.25} />
        </mesh>
      )}

      <StudioFurnitureBatch entries={normalEntries} templates={templates} opacity={1} transparent={false} />
      {dimmedEntries.length > 0 && (
        <StudioFurnitureBatch entries={dimmedEntries} templates={templates} opacity={0.25} transparent />
      )}
    </group>
  );
}
