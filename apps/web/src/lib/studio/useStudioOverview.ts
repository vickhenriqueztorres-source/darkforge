"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";
import type { StudioOverview } from "./hq-types";
import { createOverviewRefetchScheduler } from "./overview-scheduler";

export type OverviewRealtimeStatus = "connected" | "reconnecting" | "polling";

export interface UseStudioOverviewResult {
  overview: StudioOverview | undefined;
  error: unknown;
  isLoading: boolean;
  isValidating: boolean;
  realtimeStatus: OverviewRealtimeStatus;
  mutate: () => Promise<StudioOverview | undefined>;
  prepareStudio: (channelId: string) => Promise<void>;
}

export function useStudioOverview(
  token: string,
  workspaceId: string,
  opts?: { enabled?: boolean }
): UseStudioOverviewResult {
  const enabled = (opts?.enabled ?? true) && Boolean(token && workspaceId);
  const [realtimeStatus, setRealtimeStatus] = useState<OverviewRealtimeStatus>("polling");

  const swr = useSWR<StudioOverview>(
    enabled ? ["studio-overview", workspaceId] : null,
    () => api.getStudioOverview(token, workspaceId),
    {
      revalidateOnFocus: true,
      refreshInterval: realtimeStatus === "polling" ? 15000 : 0,
      dedupingInterval: 500,
    }
  );

  const mutateRef = useRef(swr.mutate);
  mutateRef.current = swr.mutate;

  useEffect(() => {
    if (!enabled) {
      setRealtimeStatus("polling");
      return;
    }

    const scheduler = createOverviewRefetchScheduler(
      () => {
        void mutateRef.current();
      },
      { debounceMs: 400, minIntervalMs: 1000 }
    );

    let channelSub: ReturnType<ReturnType<typeof getSupabaseClient>["channel"]> | null = null;
    if (isSupabaseConfigured()) {
      try {
        const supa = getSupabaseClient();
        channelSub = supa
          .channel(`studio-overview-${workspaceId}`)
          .on(
            "postgres_changes",
            {
              event: "INSERT",
              schema: "public",
              table: "agent_events",
              filter: `workspace_id=eq.${workspaceId}`,
            },
            () => {
              scheduler.schedule();
            }
          )
          .subscribe((status) => {
            if (status === "SUBSCRIBED") {
              setRealtimeStatus("connected");
            } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
              setRealtimeStatus("reconnecting");
            }
          });
      } catch {
        setRealtimeStatus("polling");
      }
    } else {
      setRealtimeStatus("polling");
    }

    const onOnline = () => {
      setRealtimeStatus("reconnecting");
      scheduler.schedule();
    };
    window.addEventListener("online", onOnline);

    return () => {
      scheduler.cancel();
      window.removeEventListener("online", onOnline);
      if (channelSub) {
        try {
          getSupabaseClient().removeChannel(channelSub);
        } catch {
          // ignore cleanup failure
        }
      }
    };
  }, [enabled, workspaceId]);

  const prepareStudio = useCallback(
    async (channelId: string) => {
      if (!token || !workspaceId || !channelId) return;
      await api.getStudioSnapshot(token, workspaceId, channelId);
      await swr.mutate();
    },
    [token, workspaceId, swr]
  );

  const refresh = useCallback(() => swr.mutate(), [swr]);

  return {
    overview: swr.data,
    error: swr.error,
    isLoading: swr.isLoading,
    isValidating: swr.isValidating,
    realtimeStatus,
    mutate: refresh,
    prepareStudio,
  };
}
