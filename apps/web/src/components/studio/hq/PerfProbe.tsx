"use client";

import { useEffect, useRef } from "react";
import { addAfterEffect, useThree } from "@react-three/fiber";

export interface PerfSnapshot {
  fps: number;
  drawCalls: number;
  triangles: number;
  renderer?: string;
}

/**
 * Dev-only FPS & draw-call probe enabled with ?perf=1 when NODE_ENV=development.
 */
export function PerfProbe({ onSample }: { onSample: (sample: PerfSnapshot) => void }) {
  const { gl } = useThree();
  const framesRef = useRef(0);
  const lastSampleRef = useRef(performance.now());
  const maxCallsRef = useRef(0);
  const maxTrisRef = useRef(0);
  const onSampleRef = useRef(onSample);
  onSampleRef.current = onSample;

  useEffect(() => {
    lastSampleRef.current = performance.now();
    framesRef.current = 0;

    let rendererName: string | undefined;
    try {
      const ctx = gl.getContext();
      const dbg = ctx.getExtension("WEBGL_debug_renderer_info");
      if (dbg) {
        rendererName = String(ctx.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
      }
    } catch {
      // ignore
    }

    const unsub = addAfterEffect(() => {
      framesRef.current += 1;
      maxCallsRef.current = Math.max(maxCallsRef.current, gl.info.render.calls);
      maxTrisRef.current = Math.max(maxTrisRef.current, gl.info.render.triangles);
      const now = performance.now();
      const elapsed = now - lastSampleRef.current;
      if (elapsed >= 500) {
        const fps = Math.round((framesRef.current * 1000) / elapsed);
        const sample: PerfSnapshot = {
          fps,
          drawCalls: maxCallsRef.current,
          triangles: maxTrisRef.current,
          renderer: rendererName,
        };
        framesRef.current = 0;
        maxCallsRef.current = 0;
        maxTrisRef.current = 0;
        lastSampleRef.current = now;
        if (typeof window !== "undefined") {
          (window as unknown as { __DARKFORGE_HQ_PERF__?: PerfSnapshot }).__DARKFORGE_HQ_PERF__ = sample;
        }
        onSampleRef.current(sample);
      }
    });
    return () => {
      unsub();
    };
  }, [gl]);

  return null;
}
