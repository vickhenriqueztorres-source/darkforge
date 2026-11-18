"use client";

import React, { Component, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import { Text, useTexture } from "@react-three/drei";
import { CanvasTexture, SRGBColorSpace, type MeshStandardMaterial } from "three";
import type { StudioLamp } from "@/lib/studio/hq-types";
import { channelInitials, desaturateHex, fitSignText } from "./signText";

const monogramTextureCache = new Map<string, CanvasTexture>();

function getMonogramTexture(initials: string, bgColor: string): CanvasTexture {
  const key = `${initials}|${bgColor}`;
  const existing = monogramTextureCache.get(key);
  if (existing) return existing;

  if (typeof document === "undefined") {
    const empty = new CanvasTexture(null as unknown as HTMLCanvasElement);
    monogramTextureCache.set(key, empty);
    return empty;
  }

  const canvas = document.createElement("canvas");
  canvas.width = 96;
  canvas.height = 96;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, 96, 96);
    ctx.fillStyle = "#f4efe6";
    ctx.font = "700 40px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(initials, 48, 50);
  }
  const tex = new CanvasTexture(canvas);
  tex.colorSpace = SRGBColorSpace;
  tex.needsUpdate = true;
  monogramTextureCache.set(key, tex);
  return tex;
}

class AvatarErrorBoundary extends Component<
  { fallback: React.ReactNode; children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(prevProps: { children: React.ReactNode }) {
    if (prevProps.children !== this.props.children && this.state.failed) {
      this.setState({ failed: false });
    }
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function TextureAvatarDisc({ url, opacity }: { url: string; opacity: number }) {
  const texture = useTexture(url);
  useEffect(() => {
    texture.colorSpace = SRGBColorSpace;
    texture.needsUpdate = true;
  }, [texture]);
  return (
    <mesh position={[-1.22, 0, 0.048]}>
      <circleGeometry args={[0.22, 24]} />
      <meshBasicMaterial map={texture} transparent={opacity < 1} opacity={opacity} />
    </mesh>
  );
}

function MonogramDisc({ initials, bgColor, opacity }: { initials: string; bgColor: string; opacity: number }) {
  const [tex, setTex] = useState<CanvasTexture | null>(null);
  useEffect(() => {
    setTex(getMonogramTexture(initials, bgColor));
  }, [initials, bgColor]);
  return (
    <mesh position={[-1.22, 0, 0.048]}>
      <circleGeometry args={[0.22, 24]} />
      {tex ? (
        <meshBasicMaterial map={tex} transparent={opacity < 1} opacity={opacity} />
      ) : (
        <meshBasicMaterial color={bgColor} transparent={opacity < 1} opacity={opacity} />
      )}
    </mesh>
  );
}

const LAMP_COLORS: Record<StudioLamp, string> = {
  ok: "#3fae6a",
  working: "#f5a623",
  awaiting: "#ff7a1a",
  problem: "#e0503f",
  off: "#3b434d",
};

export interface ChannelSignProps {
  displayName: string;
  avatarUrl: string | null;
  channelColor: string;
  lamp: StudioLamp;
  position: readonly [number, number, number];
  rotationY: number;
  connected: boolean;
  dimmed: boolean;
  reducedMotion: boolean;
  withHousing?: boolean;
  onAir?: boolean;
}

export function ChannelSign({
  displayName,
  avatarUrl,
  channelColor,
  lamp,
  position,
  rotationY,
  connected,
  dimmed,
  reducedMotion,
  withHousing = false,
  onAir = false,
}: ChannelSignProps) {
  const lampMatRef = useRef<MeshStandardMaterial>(null);
  const fit = useMemo(() => fitSignText(displayName, 2.32), [displayName]);
  const initials = useMemo(() => channelInitials(displayName), [displayName]);
  const effectiveColor = connected ? channelColor : desaturateHex(channelColor, 0.4);
  const signOpacity = dimmed ? 0.6 : 1;
  const lampColor = LAMP_COLORS[lamp];

  useFrame((state) => {
    const mat = lampMatRef.current;
    if (!mat) return;
    if (lamp === "off") {
      mat.emissiveIntensity = 0;
      return;
    }
    if (reducedMotion || lamp === "ok" || lamp === "problem") {
      mat.emissiveIntensity = lamp === "problem" ? 1.45 : lamp === "awaiting" ? 1.45 : 1.1;
      return;
    }
    const t = state.clock.elapsedTime;
    if (lamp === "working") {
      const wave = 0.5 + 0.5 * Math.sin((t * Math.PI * 2) / 1.6);
      mat.emissiveIntensity = 0.55 + wave * 0.85;
      return;
    }
    // awaiting: double pulse inside 1.6s cycle
    const cyc = (t % 1.6) / 1.6;
    const p1 = Math.exp(-Math.pow((cyc - 0.16) / 0.07, 2));
    const p2 = Math.exp(-Math.pow((cyc - 0.38) / 0.07, 2));
    mat.emissiveIntensity = 0.45 + Math.max(p1, p2) * 1.35;
  });

  const monogram = <MonogramDisc initials={initials} bgColor={effectiveColor} opacity={signOpacity} />;

  return (
    <group position={[position[0], position[1], position[2]]} rotation-y={rotationY}>
      {withHousing && (
        <>
          <mesh position={[0, 0, -0.005]}>
            <boxGeometry args={[3.2, 0.6, 0.07]} />
            <meshStandardMaterial color="#1f262e" roughness={0.7} transparent={dimmed} opacity={signOpacity} />
          </mesh>
          <mesh position={[0, 0, 0.034]}>
            <boxGeometry args={[3.14, 0.54, 0.014]} />
            <meshStandardMaterial
              color={connected ? "#f4efe6" : "#8f949a"}
              emissive={connected ? "#f4efe6" : "#000000"}
              emissiveIntensity={connected ? 0.35 : 0}
              roughness={0.5}
              transparent={dimmed}
              opacity={signOpacity}
            />
          </mesh>
          <mesh position={[-1.53, 0, 0.043]}>
            <boxGeometry args={[0.08, 0.54, 0.012]} />
            <meshStandardMaterial color={effectiveColor} roughness={0.6} transparent={dimmed} opacity={signOpacity} />
          </mesh>
          {onAir && (
            <group position={[0, 0.44, 0]}>
              <mesh>
                <boxGeometry args={[1.45, 0.22, 0.06]} />
                <meshStandardMaterial color="#231a10" emissive="#f5a623" emissiveIntensity={0.75} roughness={0.5} />
              </mesh>
              <Text
                position={[0, 0, 0.036]}
                font="/fonts/inter-700.woff"
                fontSize={0.11}
                letterSpacing={0.08}
                color="#fff6e0"
                anchorX="center"
                anchorY="middle"
              >
                EM PRODUÇÃO
              </Text>
            </group>
          )}
        </>
      )}

      {avatarUrl ? (
        <AvatarErrorBoundary fallback={monogram}>
          <Suspense fallback={monogram}>
            <TextureAvatarDisc url={avatarUrl} opacity={signOpacity} />
          </Suspense>
        </AvatarErrorBoundary>
      ) : (
        monogram
      )}

      <Text
        position={[-0.9, 0, 0.05]}
        font="/fonts/inter-600.woff"
        fontSize={fit.fontSize}
        letterSpacing={0.01}
        color="#11161c"
        anchorX="left"
        anchorY="middle"
        maxWidth={2.38}
        fillOpacity={signOpacity}
      >
        {fit.text}
      </Text>

      {/* Status lamp to the right of the sign */}
      <mesh position={[1.85, 0, 0.02]}>
        <sphereGeometry args={[0.12, 16, 12]} />
        <meshStandardMaterial
          ref={lampMatRef}
          color={lampColor}
          emissive={lamp === "off" ? "#000000" : lampColor}
          emissiveIntensity={lamp === "off" ? 0 : 1.1}
          roughness={0.35}
          transparent={dimmed}
          opacity={dimmed ? 0.6 : 1}
        />
      </mesh>
    </group>
  );
}
