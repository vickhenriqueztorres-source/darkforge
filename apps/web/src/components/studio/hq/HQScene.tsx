"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Vector3, type Object3D } from "three";
import type { HQFilter, StudioOverview, StudioOverviewChannel } from "@/lib/studio/hq-types";
import { isChannelConnected, matchesFilter, studioLamp } from "@/lib/studio/hq-status";
import type { AgentKey } from "@/lib/studio/types";
import { AGENT_LABEL_HEIGHT } from "@/components/studio/office3d/layout3d";
import { assignChannelColors } from "./hqColors";
import { buildHQLayout, type StudioSlot } from "./layoutHQ";
import { HQBuilding, type StudioRenderEntry } from "./HQBuilding";
import { StudioModule } from "./StudioModule";
import { Lobby } from "./Lobby";
import { CrowdFigures } from "./CrowdFigures";
import { CameraRig } from "./CameraRig";
import { PerfProbe, type PerfSnapshot } from "./PerfProbe";

export type HQOverlayAnchors = MutableRefObject<Map<string, HTMLElement>>;

function HQOverlaySync({
  anchors,
  slots,
  agentObjects,
}: {
  anchors: HQOverlayAnchors;
  slots: StudioSlot[];
  agentObjects: MutableRefObject<Map<AgentKey, Object3D>>;
}) {
  const { camera, size } = useThree();
  const studioPoints = useMemo(() => {
    const map = new Map<string, Vector3>();
    for (const s of slots) {
      map.set(`studio:${s.channelId}`, new Vector3((s.x0 + s.x1) / 2, 1.95, (s.z0 + s.z1) / 2));
      map.set(`hover:${s.channelId}`, new Vector3(s.sign.pos[0], s.sign.pos[1] + 0.55, s.sign.pos[2]));
    }
    return map;
  }, [slots]);
  const v = useMemo(() => new Vector3(), []);

  useFrame(() => {
    for (const [id, el] of anchors.current) {
      if (id.startsWith("agent:")) {
        const agentKey = id.slice(6) as AgentKey;
        const obj = agentObjects.current.get(agentKey);
        if (!obj) {
          el.style.visibility = "hidden";
          continue;
        }
        v.set(obj.position.x, AGENT_LABEL_HEIGHT, obj.position.z);
        v.project(camera);
        const x = (v.x * 0.5 + 0.5) * size.width;
        const y = (-v.y * 0.5 + 0.5) * size.height;
        el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -100%)`;
        el.style.visibility = "visible";
        continue;
      }

      const pt = studioPoints.get(id);
      if (!pt) continue;
      v.copy(pt);
      v.project(camera);
      const x = (v.x * 0.5 + 0.5) * size.width;
      const y = (-v.y * 0.5 + 0.5) * size.height;
      el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -100%)`;
      el.style.visibility = "visible";
    }
  });

  return null;
}

function InvalidateOnChange({ triggerKey }: { triggerKey: string }) {
  const { invalidate } = useThree();
  useEffect(() => {
    invalidate();
  }, [triggerKey, invalidate]);
  return null;
}

export interface HQSceneProps {
  overview: StudioOverview;
  pageOffset?: number;
  filter: HQFilter;
  searchHighlightId: string | null;
  focusedChannelId: string | null;
  hoveredChannelId: string | null;
  initialFocus: boolean;
  active: boolean;
  reducedMotion: boolean;
  perfEnabled?: boolean;
  anchors: HQOverlayAnchors;
  onFocusChannel: (channelId: string) => void;
  onEnterChannel: (channelId: string) => void;
  onHoverChannel: (channelId: string | null) => void;
  onSelectAgent?: (agentKey: AgentKey) => void;
  onPerfSample?: (sample: PerfSnapshot) => void;
}

export default function HQScene({
  overview,
  pageOffset = 0,
  filter,
  searchHighlightId,
  focusedChannelId,
  hoveredChannelId,
  initialFocus,
  active,
  reducedMotion,
  perfEnabled = false,
  anchors,
  onFocusChannel,
  onEnterChannel,
  onHoverChannel,
  onSelectAgent,
  onPerfSample,
}: HQSceneProps) {
  const [cameraAnimating, setCameraAnimating] = useState(false);

  const visibleChannels = useMemo(
    () => overview.channels.slice(pageOffset, pageOffset + 24),
    [overview.channels, pageOffset]
  );
  const channelIds = useMemo(() => visibleChannels.map((c) => c.channel.id), [visibleChannels]);
  const layout = useMemo(() => buildHQLayout(channelIds), [channelIds]);
  const colors = useMemo(() => assignChannelColors(channelIds), [channelIds]);
  const channelsById = useMemo(
    () => new Map<string, StudioOverviewChannel>(visibleChannels.map((c) => [c.channel.id, c])),
    [visibleChannels]
  );

  const entries = useMemo<StudioRenderEntry[]>(() => {
    return layout.slots
      .map((slot) => {
        const ch = channelsById.get(slot.channelId);
        if (!ch) return null;
        const connected = isChannelConnected(ch);
        const matches = matchesFilter(ch, filter);
        const searchMismatch = Boolean(searchHighlightId && searchHighlightId !== slot.channelId && filter === "all");
        return {
          slot,
          channel: ch,
          color: colors.get(slot.channelId) ?? "#3f8f8a",
          connected,
          dimmed: !matches || searchMismatch,
        };
      })
      .filter((e): e is StudioRenderEntry => e !== null);
  }, [layout.slots, channelsById, colors, filter, searchHighlightId]);

  const dimmedIds = useMemo(
    () => new Set(entries.filter((e) => e.dimmed).map((e) => e.slot.channelId)),
    [entries]
  );

  const agentObjects = useRef(new Map<AgentKey, Object3D>());
  const registerAgentAnchor = useCallback((key: AgentKey, obj: Object3D | null) => {
    if (obj) agentObjects.current.set(key, obj);
    else agentObjects.current.delete(key);
  }, []);

  const hasContinuousWork = useMemo(() => {
    if (reducedMotion) return false;
    return visibleChannels.some(
      (c) =>
        c.counts.working > 0 ||
        c.agents.some((a) => a.enabled && (a.status === "working" || a.status === "waiting_approval" || a.status === "needs_review" || a.status === "waiting_input"))
    );
  }, [visibleChannels, reducedMotion]);

  const frameloop = !active
    ? "never"
    : hasContinuousWork || cameraAnimating || focusedChannelId !== null
      ? "always"
      : "demand";

  const cx = (layout.bounds.x0 + layout.bounds.x1) / 2;
  const cz = (layout.bounds.z0 + layout.bounds.z1) / 2;
  const maxSpan = Math.max(layout.bounds.x1 - layout.bounds.x0, layout.bounds.z1 - layout.bounds.z0);
  const shadowExtent = Math.max(24, maxSpan * 0.72);

  let pointLightCount = 0;

  return (
    <Canvas
      shadows="percentage"
      dpr={[1, 2]}
      frameloop={frameloop}
      gl={{ antialias: true }}
      fallback={<p>Seu navegador não suporta WebGL, então a Sede 3D não pode ser exibida.</p>}
      onPointerMissed={() => {
        document.body.style.cursor = "";
        onHoverChannel(null);
      }}
    >
      <CameraRig
        bounds={layout.bounds}
        focusedSlot={focusedChannelId ? layout.slots.find((s) => s.channelId === focusedChannelId) ?? null : null}
        initialFocus={initialFocus}
        reducedMotion={reducedMotion}
        onTransitionChange={setCameraAnimating}
      />

      <InvalidateOnChange
        triggerKey={`${overview.snapshot_at}|${filter}|${focusedChannelId ?? ""}|${hoveredChannelId ?? ""}|${searchHighlightId ?? ""}`}
      />

      <HQOverlaySync anchors={anchors} slots={layout.slots} agentObjects={agentObjects} />

      {/* Night maquette lighting (design-spec.md §7) */}
      <hemisphereLight args={["#9db4cc", "#151a22", 0.55]} />
      <ambientLight intensity={0.18} />
      <directionalLight
        position={[cx + 18, 30, cz + 14]}
        intensity={1.55}
        color="#ffeed6"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-shadowExtent}
        shadow-camera-right={shadowExtent}
        shadow-camera-top={shadowExtent}
        shadow-camera-bottom={-shadowExtent}
        shadow-camera-near={1}
        shadow-camera-far={90}
        shadow-bias={-0.0006}
      />

      <HQBuilding layout={layout} entries={entries} />
      <Lobby lobby={layout.lobby} totals={overview.totals} />

      {entries.map((entry) => {
        const allowPointLight =
          entry.connected && entry.channel.provisioned && !entry.dimmed && pointLightCount < 12;
        if (allowPointLight) pointLightCount++;
        const isSelected = focusedChannelId === entry.slot.channelId;
        const isHovered = hoveredChannelId === entry.slot.channelId || searchHighlightId === entry.slot.channelId;

        return (
          <StudioModule
            key={entry.slot.channelId}
            slot={entry.slot}
            channel={entry.channel}
            color={entry.color}
            lamp={studioLamp(entry.channel)}
            connected={entry.connected}
            dimmed={entry.dimmed}
            focused={isSelected}
            hovered={isHovered}
            reducedMotion={reducedMotion}
            allowPointLight={allowPointLight}
            onSelect={(id) => {
              if (focusedChannelId === id) {
                onEnterChannel(id);
              } else {
                onFocusChannel(id);
              }
            }}
            onHover={onHoverChannel}
          />
        );
      })}

      <CrowdFigures
        slots={layout.slots}
        channelsById={channelsById}
        dimmedIds={dimmedIds}
        focusedChannelId={focusedChannelId}
        reducedMotion={reducedMotion}
        onSelectAgent={onSelectAgent}
        registerAgentAnchor={registerAgentAnchor}
      />

      {perfEnabled && process.env.NODE_ENV === "development" && onPerfSample && (
        <PerfProbe onSample={onPerfSample} />
      )}
    </Canvas>
  );
}
