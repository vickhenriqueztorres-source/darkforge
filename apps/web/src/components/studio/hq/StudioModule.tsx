"use client";

import type { StudioLamp, StudioOverviewChannel } from "@/lib/studio/hq-types";
import { PALETTE } from "@/components/studio/office3d/layout3d";
import { ChannelSign } from "./ChannelSign";
import { HQ_DOOR_WIDTH, MODULE, type StudioSlot } from "./layoutHQ";

export interface StudioModuleProps {
  slot: StudioSlot;
  channel: StudioOverviewChannel;
  color: string;
  lamp: StudioLamp;
  connected: boolean;
  dimmed: boolean;
  focused: boolean;
  hovered: boolean;
  reducedMotion: boolean;
  allowPointLight: boolean;
  onSelect: (channelId: string) => void;
  onHover: (channelId: string | null) => void;
}

export function StudioModule({
  slot,
  channel,
  color,
  lamp,
  connected,
  dimmed,
  focused,
  hovered,
  reducedMotion,
  allowPointLight,
  onSelect,
  onHover,
}: StudioModuleProps) {
  const cx = (slot.x0 + slot.x1) / 2;
  const cz = (slot.z0 + slot.z1) / 2;
  const highlight = hovered || focused;

  return (
    <group>
      {/* Invisible pointer hitbox for zero extra draw calls */}
      <mesh
        position={[cx, 0.85, cz]}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(channel.channel.id);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(channel.channel.id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={(e) => {
          e.stopPropagation();
          onHover(null);
          document.body.style.cursor = "";
        }}
      >
        <boxGeometry args={[MODULE.w - 0.1, 1.7, MODULE.d - 0.1]} />
        <meshBasicMaterial visible={false} />
      </mesh>

      {/* Warm door spill light for up to 12 active studios */}
      {allowPointLight && connected && channel.provisioned && !dimmed && (
        <pointLight
          position={[slot.door.inner[0], 1.5, slot.door.inner[1]]}
          color="#ffd8a6"
          intensity={1.3}
          distance={5.5}
          decay={2}
        />
      )}

      {/* Hover / Focus accent outline on door frame and studio top */}
      {highlight && (
        <group>
          <mesh position={[slot.door.centerX, 1.62, slot.door.wallZ]}>
            <boxGeometry args={[HQ_DOOR_WIDTH + 0.24, 0.08, 0.3]} />
            <meshBasicMaterial color={PALETTE.accent} />
          </mesh>
          <mesh position={[cx, 0.03, cz]} rotation-x={-Math.PI / 2}>
            <planeGeometry args={[MODULE.w - 0.2, MODULE.d - 0.2]} />
            <meshBasicMaterial color={focused ? PALETTE.accent : color} transparent opacity={0.14} depthWrite={false} />
          </mesh>
        </group>
      )}

      <ChannelSign
        displayName={channel.channel.display_name}
        avatarUrl={channel.channel.avatar_url}
        channelColor={color}
        lamp={lamp}
        position={slot.sign.pos}
        rotationY={slot.sign.rotationY}
        connected={connected}
        dimmed={dimmed}
        reducedMotion={reducedMotion}
        withHousing={false}
        onAir={channel.active_item !== null}
      />
    </group>
  );
}
