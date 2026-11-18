"use client";

import { Text } from "@react-three/drei";
import type { StudioOverview } from "@/lib/studio/hq-types";
import { PALETTE } from "@/components/studio/office3d/layout3d";
import { Box, Plant } from "@/components/studio/office3d/primitives";
import type { BuildingLayout } from "./layoutHQ";

function StaticReceptionist({ position }: { position: readonly [number, number] }) {
  return (
    <group position={[position[0], 0, position[1]]} rotation-y={Math.PI / 2}>
      <mesh position={[-0.09, 0.25, 0]} castShadow>
        <boxGeometry args={[0.13, 0.5, 0.14]} />
        <meshStandardMaterial color="#2c3440" roughness={0.85} />
      </mesh>
      <mesh position={[0.09, 0.25, 0]} castShadow>
        <boxGeometry args={[0.13, 0.5, 0.14]} />
        <meshStandardMaterial color="#2c3440" roughness={0.85} />
      </mesh>
      <mesh position={[0, 0.76, 0]} castShadow>
        <boxGeometry args={[0.42, 0.5, 0.26]} />
        <meshStandardMaterial color="#6b7280" roughness={0.75} />
      </mesh>
      <mesh position={[0, 1.22, 0]} castShadow>
        <sphereGeometry args={[0.18, 16, 12]} />
        <meshStandardMaterial color="#e0bca0" roughness={0.65} />
      </mesh>
      <mesh position={[0, 1.25, -0.02]} rotation-x={-0.35}>
        <sphereGeometry args={[0.195, 16, 10, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color="#25282e" roughness={0.9} />
      </mesh>
    </group>
  );
}

export interface LobbyProps {
  lobby: BuildingLayout["lobby"];
  totals: StudioOverview["totals"];
}

export function Lobby({ lobby, totals }: LobbyProps) {
  const wallX = lobby.x0 + 0.14;
  const centerZ = 0;

  return (
    <group>
      {/* Reception counter desk */}
      <group position={[lobby.desk[0], 0, lobby.desk[1]]}>
        <Box size={[0.72, 0.92, 2.0]} position={[0, 0.46, 0]} color={PALETTE.woodDark} />
        <Box size={[0.82, 0.07, 2.1]} position={[0, 0.95, 0]} color={PALETTE.wood} roughness={0.6} />
        <Box size={[0.38, 0.26, 0.44]} position={[0.1, 1.12, -0.35]} color="#1f262e" cast={false} />
      </group>

      <StaticReceptionist position={lobby.receptionist} />

      {lobby.plants.map((p, i) => (
        <Plant key={i} position={[p[0], 0, p[1]]} scale={0.95} />
      ))}

      {/* Relief DarkForge logo on the reception back wall */}
      <group position={[wallX, 2.08, centerZ]} rotation-y={Math.PI / 2}>
        <Box size={[2.2, 0.34, 0.05]} position={[0, 0, 0]} color="#212832" cast={false} />
        <Text
          position={[0, 0, 0.036]}
          font="/fonts/inter-700.woff"
          fontSize={0.21}
          letterSpacing={0.06}
          color="#f5a623"
          anchorX="center"
          anchorY="middle"
        >
          DarkForge
        </Text>
      </group>

      {/* Wall stats screen */}
      <group position={[wallX, 1.25, centerZ]} rotation-y={Math.PI / 2}>
        <Box size={[2.5, 0.95, 0.06]} position={[0, 0, 0]} color="#181f27" cast={false} />
        <mesh position={[0, 0, 0.034]}>
          <planeGeometry args={[2.36, 0.82]} />
          <meshStandardMaterial color="#11161c" emissive="#18222e" emissiveIntensity={0.45} roughness={0.4} />
        </mesh>

        <Text
          position={[-0.76, 0.1, 0.04]}
          font="/fonts/inter-700.woff"
          fontSize={0.26}
          color="#f5a623"
          anchorX="center"
          anchorY="middle"
        >
          {String(totals.working)}
        </Text>
        <Text
          position={[-0.76, -0.2, 0.04]}
          font="/fonts/inter-600.woff"
          fontSize={0.095}
          color="#cbd5e1"
          anchorX="center"
          anchorY="middle"
        >
          TRABALHANDO
        </Text>

        <Text
          position={[0, 0.1, 0.04]}
          font="/fonts/inter-700.woff"
          fontSize={0.26}
          color="#ff7a1a"
          anchorX="center"
          anchorY="middle"
        >
          {String(totals.awaiting_human)}
        </Text>
        <Text
          position={[0, -0.2, 0.04]}
          font="/fonts/inter-600.woff"
          fontSize={0.095}
          color="#cbd5e1"
          anchorX="center"
          anchorY="middle"
        >
          AGUARDANDO
        </Text>

        <Text
          position={[0.76, 0.1, 0.04]}
          font="/fonts/inter-700.woff"
          fontSize={0.26}
          color="#e0503f"
          anchorX="center"
          anchorY="middle"
        >
          {String(totals.problems)}
        </Text>
        <Text
          position={[0.76, -0.2, 0.04]}
          font="/fonts/inter-600.woff"
          fontSize={0.095}
          color="#cbd5e1"
          anchorX="center"
          anchorY="middle"
        >
          PROBLEMA
        </Text>
      </group>
    </group>
  );
}
