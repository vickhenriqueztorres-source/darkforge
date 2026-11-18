import type { HQFilter, StudioLamp, StudioOverviewChannel } from "./hq-types";
import type { AgentVisualStatus } from "./types";

const PROBLEM_STATUSES = new Set<AgentVisualStatus>(["failed", "blocked", "no_signal"]);
const AWAITING_STATUSES = new Set<AgentVisualStatus>(["waiting_approval", "needs_review", "waiting_input"]);

export function isChannelConnected(channel: StudioOverviewChannel): boolean {
  return channel.channel.status === "active";
}

export function studioWorkingCount(channel: StudioOverviewChannel): number {
  if (channel.agents.length > 0) {
    return channel.agents.filter((a) => a.enabled && a.status === "working").length;
  }
  return channel.counts.working;
}

export function studioAwaitingCount(channel: StudioOverviewChannel): number {
  if (channel.agents.length > 0) {
    return channel.agents.filter((a) => a.enabled && AWAITING_STATUSES.has(a.status)).length;
  }
  return channel.counts.awaiting_human;
}

export function studioProblemCount(channel: StudioOverviewChannel): number {
  if (channel.agents.length > 0) {
    return channel.agents.filter((a) => a.enabled && PROBLEM_STATUSES.has(a.status)).length;
  }
  return channel.counts.failed + channel.counts.blocked;
}

/**
 * Pure status lamp priority for a studio module:
 * off (unprovisioned or disconnected) > problem (failed/blocked/no_signal)
 * > awaiting (waiting_approval/needs_review/waiting_input) > working > ok.
 */
export function studioLamp(channel: StudioOverviewChannel): StudioLamp {
  if (!channel.provisioned || channel.agents.length === 0 || !isChannelConnected(channel)) {
    return "off";
  }
  const enabled = channel.agents.filter((a) => a.enabled && a.status !== "disabled");
  if (enabled.some((a) => PROBLEM_STATUSES.has(a.status)) || channel.counts.failed + channel.counts.blocked > 0) {
    return "problem";
  }
  if (enabled.some((a) => AWAITING_STATUSES.has(a.status)) || channel.counts.awaiting_human > 0) {
    return "awaiting";
  }
  if (enabled.some((a) => a.status === "working") || channel.counts.working > 0) {
    return "working";
  }
  return "ok";
}

export function studioLampLabel(lamp: StudioLamp): string {
  switch (lamp) {
    case "problem":
      return "Com problema";
    case "awaiting":
      return "Aguardando você";
    case "working":
      return "Trabalhando";
    case "ok":
      return "Tudo ok";
    case "off":
      return "Desligado";
  }
}

export function matchesFilter(channel: StudioOverviewChannel, filter: HQFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "unprovisioned":
      return !channel.provisioned || channel.agents.length === 0;
    case "working":
      return channel.provisioned && isChannelConnected(channel) && studioWorkingCount(channel) > 0;
    case "awaiting":
      return channel.provisioned && isChannelConnected(channel) && studioAwaitingCount(channel) > 0;
    case "problem":
      return channel.provisioned && isChannelConnected(channel) && studioProblemCount(channel) > 0;
  }
}

export function studioSummaryText(channel: StudioOverviewChannel): string {
  const name = channel.channel.display_name;
  if (!isChannelConnected(channel)) {
    return `${name}, desconectado`;
  }
  if (!channel.provisioned || channel.agents.length === 0) {
    return `${name}, em obras (sem agentes)`;
  }
  const working = studioWorkingCount(channel);
  const awaiting = studioAwaitingCount(channel);
  const problems = studioProblemCount(channel);
  const parts: string[] = [];
  if (working > 0) parts.push(`${working} trabalhando`);
  if (awaiting > 0) parts.push(`${awaiting} aguardando você`);
  if (problems > 0) parts.push(`${problems} com problema`);
  if (parts.length === 0) {
    return `${name}, tudo ok`;
  }
  return `${name}, ${parts.join(", ")}`;
}
