"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { buildHQSearchString, parseHQRoute } from "./hq-navigation";

export interface UseHQNavigationOptions {
  availableChannelIds: string[];
  channelsLoaded: boolean;
  activeChannelId: string;
  onSelectChannel: (channelId: string) => void;
  onChannelNotFound?: (channelId: string) => void;
}

export interface UseHQNavigationResult {
  viewMode: "sede" | "channel";
  focusedChannelId: string | null;
  isInitialFocus: boolean;
  focusChannel: (channelId: string) => void;
  enterChannel: (channelId: string) => void;
  goToOverview: () => void;
  goBackOneStep: () => void;
  setViewMode: (mode: "sede" | "channel") => void;
}

const URL_SYNC_EVENT = "darkforge:hq-url-sync";

export function notifyHQUrlSync() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(URL_SYNC_EVENT));
  }
}

export function useHQNavigation({
  availableChannelIds,
  channelsLoaded,
  activeChannelId,
  onSelectChannel,
  onChannelNotFound,
}: UseHQNavigationOptions): UseHQNavigationResult {
  const pathname = usePathname();

  const [viewMode, setViewModeState] = useState<"sede" | "channel">(() => {
    if (typeof window === "undefined") return "sede";
    return parseHQRoute(new URLSearchParams(window.location.search)).viewMode;
  });
  const [focusedChannelId, setFocusedChannelId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return parseHQRoute(new URLSearchParams(window.location.search)).focusedChannelId;
  });
  const isInitialFocusRef = useRef<boolean>(Boolean(focusedChannelId));

  const syncFromLocation = useCallback(() => {
    if (typeof window === "undefined") return;
    const parsed = parseHQRoute(new URLSearchParams(window.location.search));
    setViewModeState(parsed.viewMode);
    setFocusedChannelId(parsed.focusedChannelId);
    if (parsed.viewMode === "channel" && parsed.channelId && parsed.channelId !== activeChannelId) {
      onSelectChannel(parsed.channelId);
    }
  }, [activeChannelId, onSelectChannel]);

  useEffect(() => {
    window.addEventListener("popstate", syncFromLocation);
    window.addEventListener(URL_SYNC_EVENT, syncFromLocation);
    return () => {
      window.removeEventListener("popstate", syncFromLocation);
      window.removeEventListener(URL_SYNC_EVENT, syncFromLocation);
    };
  }, [syncFromLocation]);

  // Validate ?focus=<id> once channels are loaded
  useEffect(() => {
    if (!channelsLoaded || !focusedChannelId) return;
    if (!availableChannelIds.includes(focusedChannelId)) {
      const missingId = focusedChannelId;
      setFocusedChannelId(null);
      isInitialFocusRef.current = false;
      const qs = buildHQSearchString(window.location.search, { type: "overview" });
      window.history.replaceState(null, "", `${pathname}${qs}`);
      onChannelNotFound?.(missingId);
    }
  }, [channelsLoaded, focusedChannelId, availableChannelIds, pathname, onChannelNotFound]);

  const goToOverview = useCallback(() => {
    isInitialFocusRef.current = false;
    setViewModeState("sede");
    setFocusedChannelId(null);
    if (typeof window !== "undefined") {
      const qs = buildHQSearchString(window.location.search, { type: "overview" });
      window.history.replaceState(null, "", `${pathname}${qs}`);
    }
  }, [pathname]);

  const focusChannel = useCallback(
    (channelId: string) => {
      isInitialFocusRef.current = false;
      setViewModeState("sede");
      setFocusedChannelId(channelId);
      if (typeof window !== "undefined") {
        const qs = buildHQSearchString(window.location.search, { type: "focus", channelId });
        window.history.replaceState(null, "", `${pathname}${qs}`);
      }
    },
    [pathname]
  );

  const enterChannel = useCallback(
    (channelId: string) => {
      isInitialFocusRef.current = false;
      onSelectChannel(channelId);
      setViewModeState("channel");
      setFocusedChannelId(null);
      if (typeof window !== "undefined") {
        const qs = buildHQSearchString(window.location.search, { type: "enter", channelId });
        window.history.pushState(null, "", `${pathname}${qs}`);
      }
    },
    [onSelectChannel, pathname]
  );

  const goBackOneStep = useCallback(() => {
    if (viewMode === "channel") {
      const targetFocus = activeChannelId;
      if (targetFocus && availableChannelIds.includes(targetFocus)) {
        focusChannel(targetFocus);
      } else {
        goToOverview();
      }
      return;
    }
    if (focusedChannelId) {
      goToOverview();
    }
  }, [viewMode, activeChannelId, availableChannelIds, focusedChannelId, focusChannel, goToOverview]);

  const setViewMode = useCallback(
    (mode: "sede" | "channel") => {
      if (mode === "sede") {
        isInitialFocusRef.current = false;
        setViewModeState("sede");
        setFocusedChannelId(null);
        if (typeof window !== "undefined") {
          const qs = buildHQSearchString(window.location.search, { type: "overview" });
          window.history.pushState(null, "", `${pathname}${qs}`);
        }
      } else {
        const target = activeChannelId || availableChannelIds[0] || "";
        if (target) enterChannel(target);
      }
    },
    [activeChannelId, availableChannelIds, enterChannel, pathname]
  );

  return {
    viewMode,
    focusedChannelId,
    isInitialFocus: isInitialFocusRef.current,
    focusChannel,
    enterChannel,
    goToOverview,
    goBackOneStep,
    setViewMode,
  };
}
