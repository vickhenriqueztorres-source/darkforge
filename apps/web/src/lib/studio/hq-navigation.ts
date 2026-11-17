export type HQNavState =
  | { mode: "overview"; focusedChannelId: null }
  | { mode: "focus"; focusedChannelId: string }
  | { mode: "enter"; channelId: string };

export interface HQRouteParsed {
  viewMode: "sede" | "channel";
  focusedChannelId: string | null;
  channelId: string | null;
}

export function parseHQRoute(params: URLSearchParams | { get(key: string): string | null }): HQRouteParsed {
  const view = params.get("view");
  const focus = params.get("focus");
  const channel = params.get("channel");

  if (view === "sede") {
    return {
      viewMode: "sede",
      focusedChannelId: focus && focus.trim() ? focus.trim() : null,
      channelId: channel && channel.trim() ? channel.trim() : null,
    };
  }
  if (channel && channel.trim()) {
    return {
      viewMode: "channel",
      focusedChannelId: null,
      channelId: channel.trim(),
    };
  }
  return {
    viewMode: "sede",
    focusedChannelId: null,
    channelId: null,
  };
}

export function buildHQSearchString(
  currentSearch: string,
  action:
    | { type: "overview" }
    | { type: "focus"; channelId: string }
    | { type: "enter"; channelId: string }
): string {
  const params = new URLSearchParams(currentSearch.startsWith("?") ? currentSearch.slice(1) : currentSearch);
  if (action.type === "overview") {
    params.set("view", "sede");
    params.delete("focus");
  } else if (action.type === "focus") {
    params.set("view", "sede");
    params.set("focus", action.channelId);
  } else {
    params.delete("view");
    params.delete("focus");
    params.set("channel", action.channelId);
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function transitionHQNav(
  state: HQNavState,
  event:
    | { type: "focus"; channelId: string }
    | { type: "enter"; channelId: string }
    | { type: "back" }
): HQNavState {
  if (event.type === "focus") {
    if (state.mode === "focus" && state.focusedChannelId === event.channelId) {
      return { mode: "enter", channelId: event.channelId };
    }
    return { mode: "focus", focusedChannelId: event.channelId };
  }
  if (event.type === "enter") {
    return { mode: "enter", channelId: event.channelId };
  }
  // back
  if (state.mode === "enter") {
    return { mode: "focus", focusedChannelId: state.channelId };
  }
  return { mode: "overview", focusedChannelId: null };
}
