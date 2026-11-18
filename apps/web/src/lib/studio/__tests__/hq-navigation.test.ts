import assert from "node:assert/strict";
import { buildHQSearchString, parseHQRoute, transitionHQNav, type HQNavState } from "../hq-navigation";

export function runHqNavigationTests(): number {
  let passed = 0;

  // 1. State machine transitions overview -> focus -> enter -> back -> back
  let s: HQNavState = { mode: "overview", focusedChannelId: null };
  s = transitionHQNav(s, { type: "focus", channelId: "ch-1" });
  assert.deepEqual(s, { mode: "focus", focusedChannelId: "ch-1" });

  // Focusing the already-focused channel enters it (double click / second Enter)
  s = transitionHQNav(s, { type: "focus", channelId: "ch-1" });
  assert.deepEqual(s, { mode: "enter", channelId: "ch-1" });

  // Back from enter returns to focus
  s = transitionHQNav(s, { type: "back" });
  assert.deepEqual(s, { mode: "focus", focusedChannelId: "ch-1" });

  // Back from focus returns to overview
  s = transitionHQNav(s, { type: "back" });
  assert.deepEqual(s, { mode: "overview", focusedChannelId: null });
  passed++;

  // 2. URL parsing & building
  assert.deepEqual(parseHQRoute(new URLSearchParams("?view=sede")), {
    viewMode: "sede",
    focusedChannelId: null,
    channelId: null,
  });
  assert.deepEqual(parseHQRoute(new URLSearchParams("?view=sede&focus=ch-9")), {
    viewMode: "sede",
    focusedChannelId: "ch-9",
    channelId: null,
  });
  assert.deepEqual(parseHQRoute(new URLSearchParams("?channel=ch-9")), {
    viewMode: "channel",
    focusedChannelId: null,
    channelId: "ch-9",
  });

  const qsFocus = buildHQSearchString("?view=sede", { type: "focus", channelId: "ch-2" });
  assert.equal(qsFocus, "?view=sede&focus=ch-2");

  const qsEnter = buildHQSearchString(qsFocus, { type: "enter", channelId: "ch-2" });
  assert.equal(qsEnter, "?channel=ch-2");

  const qsBack = buildHQSearchString(qsEnter, { type: "overview" });
  assert.equal(qsBack, "?channel=ch-2&view=sede");
  passed++;

  return passed;
}
