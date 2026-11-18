import type { AgentVisualStatus } from "@/lib/studio/types";

export type CrowdLocation = "desk" | "meeting" | "hidden";

export interface FigurePoseState {
  visible: boolean;
  seated: boolean;
  yOffset: number;
  torsoScaleY: number;
  bodyTiltX: number;
  headTiltX: number;
  headYaw: number;
  typingPulse: number;
}

const APPROVAL_SET = new Set<AgentVisualStatus>(["waiting_approval", "needs_review", "waiting_input"]);
const PROBLEM_SET = new Set<AgentVisualStatus>(["failed", "blocked", "no_signal"]);

export function targetLocationForStatus(status: AgentVisualStatus, enabled: boolean): CrowdLocation {
  if (!enabled || status === "disabled") return "hidden";
  if (APPROVAL_SET.has(status)) return "meeting";
  return "desk";
}

export function hashPhase(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 0) % 1000) / 100;
}

/**
 * Pure deterministic pose calculation matching design-spec.md §6.
 */
export function figurePose(
  status: AgentVisualStatus,
  enabled: boolean,
  t: number,
  phase: number,
  reducedMotion: boolean,
  jumpAge = 1
): FigurePoseState {
  if (!enabled || status === "disabled") {
    return {
      visible: false,
      seated: true,
      yOffset: 0,
      torsoScaleY: 1,
      bodyTiltX: 0,
      headTiltX: 0,
      headYaw: 0,
      typingPulse: 0,
    };
  }

  const time = t + phase;

  if (APPROVAL_SET.has(status)) {
    return {
      visible: true,
      seated: false,
      yOffset: 0,
      torsoScaleY: 1,
      bodyTiltX: 0,
      headTiltX: reducedMotion ? 0 : Math.sin(time * 2.1) * 0.05,
      headYaw: reducedMotion ? 0 : Math.sin(time * 1.1) * 0.12,
      typingPulse: 0,
    };
  }

  if (status === "working") {
    const typingPulse = reducedMotion ? 0 : Math.sin(time * ((Math.PI * 2) / 0.35)) * 0.04;
    return {
      visible: true,
      seated: true,
      yOffset: 0,
      torsoScaleY: 1 + typingPulse * 0.5,
      bodyTiltX: 0.1 + typingPulse,
      headTiltX: 0.15 + typingPulse * 0.5,
      headYaw: 0,
      typingPulse,
    };
  }

  if (status === "queued") {
    return {
      visible: true,
      seated: true,
      yOffset: 0,
      torsoScaleY: 1,
      bodyTiltX: 0,
      headTiltX: 0,
      headYaw: 0.45,
      typingPulse: 0,
    };
  }

  if (PROBLEM_SET.has(status)) {
    return {
      visible: true,
      seated: true,
      yOffset: 0,
      torsoScaleY: 1,
      bodyTiltX: 0.22,
      headTiltX: 0.42,
      headYaw: 0,
      typingPulse: 0,
    };
  }

  const breath = reducedMotion ? 1 : 1 + 0.015 * Math.sin(time * ((Math.PI * 2) / 3));
  const jump =
    status === "done" && !reducedMotion && jumpAge >= 0 && jumpAge < 0.7
      ? Math.sin((jumpAge / 0.7) * Math.PI) * 0.15
      : 0;

  return {
    visible: true,
    seated: true,
    yOffset: jump,
    torsoScaleY: breath,
    bodyTiltX: 0,
    headTiltX: 0,
    headYaw: 0,
    typingPulse: 0,
  };
}
