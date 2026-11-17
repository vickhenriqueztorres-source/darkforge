"use client";

import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";

export interface PerfSnapshot {
  fps: number;
  drawCalls: number;
  triangles: number;
}

/**
 * Dev-only FPS & draw-call probe enabled with ?perf=1 when NODE_ENV=development.
 */
export function PerfProbe({ onSample }: { onSample: (sample: PerfSnapshot) => void }) {
  const { gl } = useThree();
  const framesRef = useRef(0);
  const lastSampleRef = useRef(performance.now());
  const onSampleRef = useRef(onSample);
  onSampleRef.current = onSample;

  useEffect(() => {
    lastSampleRef.current = performance.now();
    framesRef.current = 0;
  }, []);

  useFrame(() => {
    framesRef.current += 1;
    const now = performance.now();
    const elapsed = now - lastSampleRef.current;
    if (elapsed >= 500) {
      const fps = Math.round((framesRef.current * 1000) / elapsed);
      const sample: PerfSnapshot = {
        fps,
        drawCalls: gl.info.render.calls,
        triangles: gl.info.render.triangles,
      };
      framesRef.current = 0;
      lastSampleRef.current = now;
      if (typeof window !== "undefined") {
        (window as unknown as { __DARKFORGE_HQ_PERF__?: PerfSnapshot }).__DARKFORGE_HQ_PERF__ = sample;
      }
      onSampleRef.current(sample);
    }
  });

  return null;
}
