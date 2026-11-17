import type { StudioSlot } from "./layoutHQ";

export const HQ_ISO_AZIMUTH = Math.PI / 4;

export interface BuildingBounds {
  x0: number;
  x1: number;
  z0: number;
  z1: number;
}

export interface ViewportSize {
  width: number;
  height: number;
}

export interface CameraFitResult {
  zoom: number;
  target: [number, number, number];
  minZoom: number;
  maxZoom: number;
}

export function easeInOutCubic(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  return clamped < 0.5 ? 4 * clamped * clamped * clamped : 1 - Math.pow(-2 * clamped + 2, 3) / 2;
}

/**
 * Computes isometric orthographic zoom with 6% margin around the building bounds.
 */
export function fitBuilding(bounds: BuildingBounds, size: ViewportSize): CameraFitResult {
  const safeW = Math.max(320, size.width);
  const safeH = Math.max(240, size.height);
  const bWidth = Math.max(10, bounds.x1 - bounds.x0 + 2);
  const bDepth = Math.max(10, bounds.z1 - bounds.z0 + 2);

  // Projected isometric span at 45 deg azimuth and ~39 deg elevation
  const projW = (bWidth + bDepth) * Math.SQRT1_2;
  const projH = (bWidth + bDepth) * Math.SQRT1_2 * 0.62 + 2.8;

  const margin = 0.94; // 6% margin (design-spec.md §7)
  const zoomX = (safeW * margin) / projW;
  const zoomY = (safeH * margin) / projH;
  const zoom = Math.max(4, Math.round(Math.min(zoomX, zoomY) * 100) / 100);

  return {
    zoom,
    target: [(bounds.x0 + bounds.x1) / 2, 0.7, (bounds.z0 + bounds.z1) / 2],
    minZoom: Math.max(2, Math.round(zoom * 0.6 * 100) / 100),
    maxZoom: Math.round(zoom * 2.5 * 100) / 100,
  };
}

export function focusSlotCamera(
  slot: StudioSlot,
  bounds: BuildingBounds,
  size: ViewportSize
): { target: [number, number, number]; zoom: number } {
  const fit = fitBuilding(bounds, size);
  const projSlotW = (10.5 + 9.5) * Math.SQRT1_2;
  const projSlotH = projSlotW * 0.62 + 2.4;
  const idealZoom = Math.min((size.width * 0.72) / projSlotW, (size.height * 0.72) / projSlotH);
  const zoom = Math.max(fit.minZoom, Math.min(fit.maxZoom, idealZoom));
  return {
    target: [(slot.x0 + slot.x1) / 2, 0.7, (slot.z0 + slot.z1) / 2],
    zoom,
  };
}

export function clampPanTarget(
  x: number,
  z: number,
  bounds: BuildingBounds
): [number, number] {
  const pad = 1.5;
  return [
    Math.max(bounds.x0 - pad, Math.min(bounds.x1 + pad, x)),
    Math.max(bounds.z0 - pad, Math.min(bounds.z1 + pad, z)),
  ];
}
