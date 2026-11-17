import type { AgentVisualStatus, StudioEvent, StudioEventType, StudioRoomState, StudioSnapshot } from "./types";

function eventToStatus(eventType: StudioEventType, prevStatus: AgentVisualStatus, payload: Record<string, unknown>): AgentVisualStatus {
  switch (eventType) {
    case "run_queued":
      return "queued";
    case "run_started":
    case "stage_changed":
    case "progress":
      return "working";
    case "output_saved":
      return prevStatus;
    case "output_validated":
      return prevStatus === "waiting_approval" ? "waiting_approval" : "done";
    case "needs_review":
      return "needs_review";
    case "handoff_created":
      return prevStatus;
    case "blocked":
      return "blocked";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
    case "completed":
      return (payload?.status as AgentVisualStatus | undefined) ?? "done";
    default:
      return prevStatus;
  }
}

function recomputeRooms(
  rooms: StudioRoomState[],
  agents: StudioSnapshot["agents"]
): StudioRoomState[] {
  return rooms.map((room) => {
    const inRoom = agents.filter((a) => a.room_key === room.room_key);
    return {
      ...room,
      working: inRoom.filter((a) => a.enabled && a.status === "working").length,
      awaiting_human: inRoom.filter(
        (a) => a.enabled && (a.status === "needs_review" || a.status === "waiting_approval")
      ).length,
      blocked: inRoom.filter((a) => a.enabled && (a.status === "blocked" || a.status === "no_signal")).length,
      failed: inRoom.filter((a) => a.enabled && a.status === "failed").length,
      agents: inRoom.filter((a) => a.enabled).length,
      disabled_agents: inRoom.filter((a) => !a.enabled).length,
    };
  });
}

export function applyStudioEvent(state: StudioSnapshot, event: StudioEvent): StudioSnapshot {
  if (event.channel_id !== state.channel.id) {
    return state;
  }
  if (event.id <= state.last_event_id && state.recent_events.some((e) => e.id === event.id)) {
    return state;
  }

  // Ignora evento fora de ordem por seq dentro do mesmo run
  const existingRunEvents = state.recent_events.filter((e) => e.run_id === event.run_id);
  const maxSeq = existingRunEvents.reduce((acc, e) => Math.max(acc, e.seq), 0);
  if (existingRunEvents.length > 0 && event.seq <= maxSeq) {
    return state;
  }

  const nextAgents = state.agents.map((agent) => {
    if (agent.agent_key !== event.agent_key) return agent;
    if (!agent.enabled) return agent;

    const nextStatus = eventToStatus(event.event_type, agent.status, event.payload);
    const nextProgress =
      typeof event.payload?.progress === "number"
        ? event.payload.progress
        : event.event_type === "completed"
          ? 1
          : agent.progress;
    const nextStageLabel =
      typeof event.payload?.stage_label === "string"
        ? event.payload.stage_label
        : event.summary;

    return {
      ...agent,
      run_id: event.run_id,
      content_item_id: event.content_item_id ?? agent.content_item_id,
      status: nextStatus,
      stage_label: nextStageLabel,
      progress: nextProgress,
      heartbeat_at: event.created_at,
    };
  });

  const nextEvents = [...state.recent_events, event].slice(-80);
  const nextLatestByAgent = {
    ...state.latest_event_by_agent,
    [event.agent_key]: event,
  };

  return {
    ...state,
    agents: nextAgents,
    rooms: recomputeRooms(state.rooms, nextAgents),
    recent_events: nextEvents,
    latest_event_by_agent: nextLatestByAgent,
    last_event_id: Math.max(state.last_event_id, event.id),
  };
}

export function detectEventGap(lastEventId: number, incomingEventId: number): boolean {
  return incomingEventId > lastEventId + 1;
}
