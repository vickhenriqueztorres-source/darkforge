"use client";

import { PALETTE } from "./layout3d";

export function Box({
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

export function Plant({ position, scale = 1 }: { position: [number, number, number]; scale?: number }) {
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
