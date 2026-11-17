import assert from "node:assert/strict";
import { createOverviewRefetchScheduler, type SchedulerTimers } from "../overview-scheduler";

function createFakeClock() {
  let currentMs = 10000;
  let nextId = 1;
  const tasks = new Map<number, { runAt: number; fn: () => void }>();

  const timers: SchedulerTimers = {
    now: () => currentMs,
    setTimeout(fn, ms) {
      const id = nextId++;
      tasks.set(id, { runAt: currentMs + ms, fn });
      return id as unknown as ReturnType<typeof setTimeout>;
    },
    clearTimeout(id) {
      tasks.delete(id as unknown as number);
    },
  };

  function advanceBy(ms: number) {
    const target = currentMs + ms;
    while (true) {
      let earliestId: number | null = null;
      let earliestTime = Infinity;
      for (const [id, task] of tasks) {
        if (task.runAt <= target && task.runAt < earliestTime) {
          earliestTime = task.runAt;
          earliestId = id;
        }
      }
      if (earliestId === null) break;
      const task = tasks.get(earliestId)!;
      tasks.delete(earliestId);
      currentMs = task.runAt;
      task.fn();
    }
    currentMs = target;
  }

  return { timers, advanceBy };
}

export function runHqOverviewHookTests(): number {
  let passed = 0;

  // 1. Burst within 400ms triggers only once after 400ms
  {
    const clock = createFakeClock();
    let calls = 0;
    const scheduler = createOverviewRefetchScheduler(() => {
      calls++;
    }, { debounceMs: 400, minIntervalMs: 1000, timers: clock.timers });

    scheduler.schedule();
    clock.advanceBy(150);
    scheduler.schedule();
    clock.advanceBy(150);
    scheduler.schedule();
    clock.advanceBy(399);
    assert.equal(calls, 0, "must debounce until 400ms after last event");
    clock.advanceBy(1);
    assert.equal(calls, 1, "must trigger once after 400ms quiet period");
  }
  passed++;

  // 2. Sustained events never trigger more than once per 1000ms
  {
    const clock = createFakeClock();
    let calls = 0;
    const scheduler = createOverviewRefetchScheduler(() => {
      calls++;
    }, { debounceMs: 400, minIntervalMs: 1000, timers: clock.timers });

    scheduler.schedule();
    clock.advanceBy(400); // fires #1 at t=10400
    assert.equal(calls, 1);

    scheduler.schedule();
    clock.advanceBy(400); // t=10800 -> throttled until t=11400
    assert.equal(calls, 1, "must throttle second refetch within 1000ms window");

    clock.advanceBy(599); // t=11399
    assert.equal(calls, 1);
    clock.advanceBy(1); // t=11400 -> fires #2
    assert.equal(calls, 2, "trailing refetch must fire at 1000ms mark");
  }
  passed++;

  // 3. Cancel prevents pending refetches
  {
    const clock = createFakeClock();
    let calls = 0;
    const scheduler = createOverviewRefetchScheduler(() => {
      calls++;
    }, { debounceMs: 400, minIntervalMs: 1000, timers: clock.timers });
    scheduler.schedule();
    clock.advanceBy(200);
    scheduler.cancel();
    clock.advanceBy(2000);
    assert.equal(calls, 0);
  }
  passed++;

  return passed;
}
