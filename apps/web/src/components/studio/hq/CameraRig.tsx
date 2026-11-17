"use client";

import { type ComponentRef, useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, OrthographicCamera } from "@react-three/drei";
import type { StudioSlot } from "./layoutHQ";
import {
  HQ_ISO_AZIMUTH,
  clampPanTarget,
  easeInOutCubic,
  fitBuilding,
  focusSlotCamera,
  type BuildingBounds,
} from "./cameraMath";

export interface CameraRigProps {
  bounds: BuildingBounds;
  focusedSlot: StudioSlot | null;
  initialFocus: boolean;
  reducedMotion: boolean;
  onTransitionChange?: (animating: boolean) => void;
}

interface FlyTransition {
  active: boolean;
  elapsed: number;
  duration: number;
  fromTarget: [number, number, number];
  toTarget: [number, number, number];
  fromZoom: number;
  toZoom: number;
}

export function CameraRig({
  bounds,
  focusedSlot,
  initialFocus,
  reducedMotion,
  onTransitionChange,
}: CameraRigProps) {
  const { camera, size, invalidate } = useThree();
  const controlsRef = useRef<ComponentRef<typeof OrbitControls>>(null);

  const fit = useMemo(() => fitBuilding(bounds, { width: size.width, height: size.height }), [bounds, size.width, size.height]);

  const savedOverviewRef = useRef<{ target: [number, number, number]; zoom: number } | null>(null);
  const prevFocusedIdRef = useRef<string | null>(null);
  const initializedRef = useRef(false);

  const transitionRef = useRef<FlyTransition>({
    active: false,
    elapsed: 0,
    duration: 0.6,
    fromTarget: fit.target,
    toTarget: fit.target,
    fromZoom: fit.zoom,
    toZoom: fit.zoom,
  });

  // Initial mount & resize auto-fit when in overview
  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) return;

    if (!initializedRef.current) {
      initializedRef.current = true;
      if (focusedSlot && initialFocus) {
        const fc = focusSlotCamera(focusedSlot, bounds, size);
        controls.target.set(fc.target[0], fc.target[1], fc.target[2]);
        camera.zoom = fc.zoom;
        camera.updateProjectionMatrix();
        controls.update();
        savedOverviewRef.current = { target: fit.target, zoom: fit.zoom };
        prevFocusedIdRef.current = focusedSlot.channelId;
        invalidate();
        return;
      }
    }

    if (!focusedSlot && !transitionRef.current.active) {
      controls.target.set(fit.target[0], fit.target[1], fit.target[2]);
      camera.zoom = fit.zoom;
      camera.updateProjectionMatrix();
      controls.update();
      invalidate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only refit on camera/bounds/viewport resize
  }, [camera, fit.target[0], fit.target[2], fit.zoom]);

  // FlyTo / FlyBack transitions when focusedSlot changes
  useEffect(() => {
    const controls = controlsRef.current;
    if (!controls) return;
    const nextId = focusedSlot?.channelId ?? null;
    if (nextId === prevFocusedIdRef.current) return;

    const wasOverview = prevFocusedIdRef.current === null;
    prevFocusedIdRef.current = nextId;

    if (focusedSlot) {
      if (wasOverview) {
        savedOverviewRef.current = {
          target: [controls.target.x, controls.target.y, controls.target.z],
          zoom: camera.zoom,
        };
      }
      const fc = focusSlotCamera(focusedSlot, bounds, { width: size.width, height: size.height });
      if (reducedMotion) {
        controls.target.set(fc.target[0], fc.target[1], fc.target[2]);
        camera.zoom = fc.zoom;
        camera.updateProjectionMatrix();
        controls.update();
        onTransitionChange?.(false);
        invalidate();
        return;
      }
      transitionRef.current = {
        active: true,
        elapsed: 0,
        duration: 0.6,
        fromTarget: [controls.target.x, controls.target.y, controls.target.z],
        toTarget: fc.target,
        fromZoom: camera.zoom,
        toZoom: fc.zoom,
      };
      controls.enabled = false;
      onTransitionChange?.(true);
      invalidate();
    } else {
      const back = savedOverviewRef.current ?? { target: fit.target, zoom: fit.zoom };
      if (reducedMotion) {
        controls.target.set(back.target[0], back.target[1], back.target[2]);
        camera.zoom = back.zoom;
        camera.updateProjectionMatrix();
        controls.update();
        onTransitionChange?.(false);
        invalidate();
        return;
      }
      transitionRef.current = {
        active: true,
        elapsed: 0,
        duration: 0.6,
        fromTarget: [controls.target.x, controls.target.y, controls.target.z],
        toTarget: back.target,
        fromZoom: camera.zoom,
        toZoom: back.zoom,
      };
      controls.enabled = false;
      onTransitionChange?.(true);
      invalidate();
    }
  }, [focusedSlot, bounds, size.width, size.height, fit.target, fit.zoom, reducedMotion, camera, invalidate, onTransitionChange]);

  useFrame((_, delta) => {
    const tr = transitionRef.current;
    const controls = controlsRef.current;
    if (!tr.active || !controls) return;

    tr.elapsed += Math.min(delta, 0.05);
    const raw = Math.min(1, tr.elapsed / tr.duration);
    const k = easeInOutCubic(raw);

    const tx = tr.fromTarget[0] + (tr.toTarget[0] - tr.fromTarget[0]) * k;
    const ty = tr.fromTarget[1] + (tr.toTarget[1] - tr.fromTarget[1]) * k;
    const tz = tr.fromTarget[2] + (tr.toTarget[2] - tr.fromTarget[2]) * k;
    controls.target.set(tx, ty, tz);
    camera.zoom = tr.fromZoom + (tr.toZoom - tr.fromZoom) * k;
    camera.updateProjectionMatrix();
    controls.update();
    invalidate();

    if (raw >= 1) {
      tr.active = false;
      controls.enabled = true;
      onTransitionChange?.(false);
    }
  });

  const distance = 90;
  const cx = (bounds.x0 + bounds.x1) / 2;
  const cz = (bounds.z0 + bounds.z1) / 2;

  return (
    <>
      <OrthographicCamera
        makeDefault
        zoom={fit.zoom}
        position={[
          cx + Math.sin(HQ_ISO_AZIMUTH) * distance,
          distance * 0.82 + 0.7,
          cz + Math.cos(HQ_ISO_AZIMUTH) * distance,
        ]}
        near={0.1}
        far={400}
      />
      <OrbitControls
        ref={controlsRef}
        target={[cx, 0.7, cz]}
        enablePan
        enableZoom
        enableDamping
        minZoom={fit.minZoom}
        maxZoom={fit.maxZoom}
        minAzimuthAngle={HQ_ISO_AZIMUTH - 0.55}
        maxAzimuthAngle={HQ_ISO_AZIMUTH + 0.55}
        minPolarAngle={0.55}
        maxPolarAngle={1.05}
        onChange={() => {
          const controls = controlsRef.current;
          if (!controls) return;
          const [clampedX, clampedZ] = clampPanTarget(controls.target.x, controls.target.z, bounds);
          if (clampedX !== controls.target.x || clampedZ !== controls.target.z) {
            controls.target.set(clampedX, controls.target.y, clampedZ);
          }
          invalidate();
        }}
      />
    </>
  );
}
