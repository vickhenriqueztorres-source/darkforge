export interface OverviewScheduler {
  schedule: () => void;
  cancel: () => void;
}

export interface SchedulerTimers {
  now: () => number;
  setTimeout: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
  clearTimeout: (id: ReturnType<typeof setTimeout>) => void;
}

const DEFAULT_TIMERS: SchedulerTimers = {
  now: () => Date.now(),
  setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms),
  clearTimeout: (id) => globalThis.clearTimeout(id),
};

/**
 * Coalesces bursts with a 400ms trailing debounce and enforces at most
 * 1 execution per 1000ms (max 1 refetch/s).
 */
export function createOverviewRefetchScheduler(
  onTrigger: () => void,
  opts?: {
    debounceMs?: number;
    minIntervalMs?: number;
    timers?: SchedulerTimers;
  }
): OverviewScheduler {
  const debounceMs = opts?.debounceMs ?? 400;
  const minIntervalMs = opts?.minIntervalMs ?? 1000;
  const timers = opts?.timers ?? DEFAULT_TIMERS;

  let debounceTimer: ReturnType<typeof setTimeout> | null = null;
  let throttleTimer: ReturnType<typeof setTimeout> | null = null;
  let lastTriggeredAt = -Infinity;
  let pendingAfterThrottle = false;

  const fire = () => {
    lastTriggeredAt = timers.now();
    pendingAfterThrottle = false;
    onTrigger();
  };

  const flush = () => {
    debounceTimer = null;
    const elapsed = timers.now() - lastTriggeredAt;
    if (elapsed >= minIntervalMs) {
      if (throttleTimer !== null) {
        timers.clearTimeout(throttleTimer);
        throttleTimer = null;
      }
      fire();
      return;
    }
    pendingAfterThrottle = true;
    if (throttleTimer === null) {
      const wait = Math.max(0, minIntervalMs - elapsed);
      throttleTimer = timers.setTimeout(() => {
        throttleTimer = null;
        if (pendingAfterThrottle) {
          fire();
        }
      }, wait);
    }
  };

  return {
    schedule() {
      if (debounceTimer !== null) {
        timers.clearTimeout(debounceTimer);
      }
      debounceTimer = timers.setTimeout(flush, debounceMs);
    },
    cancel() {
      if (debounceTimer !== null) {
        timers.clearTimeout(debounceTimer);
        debounceTimer = null;
      }
      if (throttleTimer !== null) {
        timers.clearTimeout(throttleTimer);
        throttleTimer = null;
      }
      pendingAfterThrottle = false;
    },
  };
}
