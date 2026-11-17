import assert from "node:assert/strict";
import { clampPanTarget, easeInOutCubic, fitBuilding } from "../cameraMath";
import { buildHQLayout } from "../layoutHQ";

export function runCameraMathTests(): number {
  let passed = 0;

  // 1. fitBuilding scales monotonically with channel count and viewport size
  const screens = [
    { width: 1280, height: 800 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ];

  for (const size of screens) {
    const f1 = fitBuilding(buildHQLayout(["c1"]).bounds, size);
    const f12 = fitBuilding(
      buildHQLayout(Array.from({ length: 12 }, (_, i) => `c${i}`)).bounds,
      size
    );
    const f24 = fitBuilding(
      buildHQLayout(Array.from({ length: 24 }, (_, i) => `c${i}`)).bounds,
      size
    );
    assert.ok(f1.zoom > f12.zoom, `1 channel zoom > 12 channel zoom at ${size.width}x${size.height}`);
    assert.ok(f12.zoom > f24.zoom, `12 channel zoom > 24 channel zoom at ${size.width}x${size.height}`);
    assert.ok(Math.abs(f24.minZoom - f24.zoom * 0.6) < 0.05);
    assert.ok(Math.abs(f24.maxZoom - f24.zoom * 2.5) < 0.05);
  }
  passed++;

  // 2. easeInOutCubic endpoints & midpoint
  assert.equal(easeInOutCubic(0), 0);
  assert.equal(easeInOutCubic(0.5), 0.5);
  assert.equal(easeInOutCubic(1), 1);

  // 3. clampPanTarget keeps target within building bounds + pad
  const b = { x0: -6, x1: 50, z0: -8.6, z1: 8.6 };
  const clamped = clampPanTarget(-100, 100, b);
  assert.equal(clamped[0], -7.5);
  assert.equal(clamped[1], 10.1);
  passed++;

  return passed;
}
