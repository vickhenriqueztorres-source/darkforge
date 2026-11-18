import assert from "node:assert/strict";
import { assignChannelColors, HQ_CHANNEL_COLORS } from "../hqColors";
import { buildHQLayout, deskForAgent, MAX_CHANNELS, MODULE, routeInStudio } from "../layoutHQ";

function overlap1D(a0: number, a1: number, b0: number, b1: number) {
  return Math.min(a1, b1) - Math.max(a0, b0) > 1e-6;
}

export function runLayoutHQTests(): number {
  let passed = 0;

  // 1. Counts n = 1, 2, 3, 7, 12, 13, 24, 30
  for (const n of [1, 2, 3, 7, 12, 13, 24, 30]) {
    const ids = Array.from({ length: n }, (_, i) => `ch-${i + 1}`);
    const layout = buildHQLayout(ids);

    assert.equal(layout.slots.length, Math.min(n, MAX_CHANNELS), `slots count for n=${n}`);
    assert.equal(layout.overflow, Math.max(0, n - MAX_CHANNELS), `overflow for n=${n}`);
    assert.equal(layout.wings, n > 12 ? 2 : 1, `wings for n=${n}`);

    // All slots inside bounds & no slot overlaps
    for (let i = 0; i < layout.slots.length; i++) {
      const a = layout.slots[i];
      assert.ok(a.x0 >= layout.bounds.x0 - 1e-6 && a.x1 <= layout.bounds.x1 + 1e-6);
      assert.ok(a.z0 >= layout.bounds.z0 - 1e-6 && a.z1 <= layout.bounds.z1 + 1e-6);
      assert.ok(Math.abs(a.x1 - a.x0 - MODULE.w) < 1e-6);
      assert.ok(Math.abs(a.z1 - a.z0 - MODULE.d) < 1e-6);

      // Door touches a corridor
      const touchesCorridor = layout.corridors.some((c) => {
        const inX = a.door.centerX >= c.x0 - 1e-6 && a.door.centerX <= c.x1 + 1e-6;
        const onZEdge = Math.abs(a.door.wallZ - c.z0) < 1e-6 || Math.abs(a.door.wallZ - c.z1) < 1e-6;
        return inX && onZEdge;
      });
      assert.ok(touchesCorridor, `door ${a.channelId} must touch corridor`);

      // Sign is on corridor side and faces corridor (0 for north/+Z, PI for south/-Z)
      const signInCorridor = layout.corridors.some(
        (c) => a.sign.pos[2] >= c.z0 - 0.01 && a.sign.pos[2] <= c.z1 + 0.01
      );
      assert.ok(signInCorridor, `sign ${a.channelId} must be on corridor side`);
      assert.equal(a.sign.rotationY, a.side === "north" ? 0 : Math.PI);

      // 8 desks inside studio without overlap
      assert.equal(a.desks.length, 8);
      for (let d1 = 0; d1 < a.desks.length; d1++) {
        const dk1 = a.desks[d1];
        assert.ok(dk1.desk[0] > a.x0 + 0.5 && dk1.desk[0] < a.x1 - 0.5);
        assert.ok(dk1.desk[1] > a.z0 + 0.3 && dk1.desk[1] < a.z1 - 0.3);
        assert.ok(dk1.seat[0] > a.x0 + 0.5 && dk1.seat[0] < a.x1 - 0.5);
        assert.ok(dk1.seat[1] > a.z0 + 0.3 && dk1.seat[1] < a.z1 - 0.3);
        for (let d2 = d1 + 1; d2 < a.desks.length; d2++) {
          const dk2 = a.desks[d2];
          const dist = Math.hypot(dk1.desk[0] - dk2.desk[0], dk1.desk[1] - dk2.desk[1]);
          assert.ok(dist >= 1.3, `desks ${d1} and ${d2} overlap`);
        }
      }

      // No studio overlaps another studio
      for (let j = i + 1; j < layout.slots.length; j++) {
        const b = layout.slots[j];
        const overlaps = overlap1D(a.x0, a.x1, b.x0, b.x1) && overlap1D(a.z0, a.z1, b.z0, b.z1);
        assert.equal(overlaps, false, `studios ${a.channelId} and ${b.channelId} overlap`);
      }
    }
  }
  passed++;

  // 2. Determinism and ID order invariance of geometry
  const idsA = ["ch-a", "ch-b", "ch-c", "ch-d"];
  const idsB = ["ch-d", "ch-c", "ch-b", "ch-a"];
  const layA1 = buildHQLayout(idsA);
  const layA2 = buildHQLayout(idsA);
  const layB = buildHQLayout(idsB);
  assert.deepEqual(layA1, layA2, "buildHQLayout must be deterministic");
  assert.deepEqual(layA1.bounds, layB.bounds, "reordering ids preserves building bounds");
  assert.equal(layA1.slots[0].x0, layB.slots[0].x0);
  assert.equal(layA1.slots[0].z0, layB.slots[0].z0);
  passed++;

  // 3. deskForAgent & routeInStudio
  const slot0 = layA1.slots[0];
  const dDados = deskForAgent(slot0, "dados");
  const dPub = deskForAgent(slot0, "publicacao");
  assert.equal(dDados.index, 0);
  assert.equal(dPub.index, 7);
  const path = routeInStudio(slot0, dDados.seat, slot0.meeting[0].pos);
  assert.ok(path.length >= 1);
  passed++;

  // 4. assignChannelColors never repeats color on adjacent studios of same side
  const collidingIds: string[] = [];
  let candidate = 0;
  while (collidingIds.length < 24) {
    const id = `channel-${candidate++}`;
    collidingIds.push(id);
  }
  const colors = assignChannelColors(collidingIds);
  assert.equal(colors.size, 24);
  for (const c of colors.values()) {
    assert.ok((HQ_CHANNEL_COLORS as readonly string[]).includes(c));
  }
  const forcedLayout = buildHQLayout(collidingIds);
  for (const wing of [0, 1] as const) {
    for (const side of ["north", "south"] as const) {
      const sideSlots = forcedLayout.slots
        .filter((s) => s.wing === wing && s.side === side)
        .sort((a, b) => a.col - b.col);
      for (let i = 1; i < sideSlots.length; i++) {
        assert.notEqual(
          colors.get(sideSlots[i - 1].channelId),
          colors.get(sideSlots[i].channelId),
          `adjacent same-side studios ${sideSlots[i - 1].channelId} and ${sideSlots[i].channelId} must not share color`
        );
      }
    }
  }
  passed++;

  return passed;
}
