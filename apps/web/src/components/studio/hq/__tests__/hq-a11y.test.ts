import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ApiClientError } from "@/lib/api";
import { HQ_OVERVIEW_FIXTURES } from "@/lib/studio/__fixtures__/hq-overview";
import { studioSummaryText } from "@/lib/studio/hq-status";
import { transitionHQNav, type HQNavState } from "@/lib/studio/hq-navigation";
import { StudioCardList } from "../StudioCardList";
import { HQFocusPanel } from "../HQFocusPanel";
import { formatMinutesAgo, HQ } from "../HQ";

export function runHqA11yTests(): number {
  let passed = 0;

  // 1. StudioCardList renders all channels from fixtures with aria-label & text statuses
  const seven = HQ_OVERVIEW_FIXTURES.seven;
  const htmlList = renderToStaticMarkup(
    React.createElement(StudioCardList, {
      channels: seven.channels,
      filter: "all",
      searchQuery: "",
      focusedChannelId: null,
      mode: "sidebar",
      onFocusOrEnter: () => {},
      onEnterChannel: () => {},
    })
  );
  for (const ch of seven.channels) {
    const htmlName = ch.channel.display_name.replace(/&/g, "&amp;");
    assert.ok(htmlList.includes(htmlName), `missing channel name ${ch.channel.display_name}`);
    const summary = studioSummaryText(ch).replace(/&/g, "&amp;");
    assert.ok(htmlList.includes(summary), `missing aria-label ${summary}`);
  }
  assert.ok(htmlList.includes("Trabalhando"));
  assert.ok(htmlList.includes("Aguardando você"));
  assert.ok(htmlList.includes("Com problema"));
  assert.ok(htmlList.includes("Em obras"));
  assert.ok(htmlList.includes("Desconectado"));
  passed++;

  // 2. Focus panel shows 8 agents + enter button (and Prepare Studio for unprovisioned)
  const workingHtml = renderToStaticMarkup(
    React.createElement(HQFocusPanel, {
      channel: seven.channels[0],
      color: "#3f8f8a",
      onEnter: () => {},
      onClose: () => {},
      onPrepareStudio: async () => {},
    })
  );
  assert.ok(workingHtml.includes("Analista de Dados"));
  assert.ok(workingHtml.includes("Roteirista"));
  assert.ok(workingHtml.includes("Entrar no estúdio"));

  const unprovHtml = renderToStaticMarkup(
    React.createElement(HQFocusPanel, {
      channel: seven.channels[3],
      color: "#4f6f9a",
      onEnter: () => {},
      onClose: () => {},
      onPrepareStudio: async () => {},
    })
  );
  assert.ok(unprovHtml.includes("Preparar estúdio"));
  passed++;

  // 3. Loading, Error (with ApiClientError code), and Empty states render cleanly
  const loadingHtml = renderToStaticMarkup(
    React.createElement(HQ, {
      overview: undefined,
      loading: true,
      error: null,
      realtimeStatus: "polling",
      focusedChannelId: null,
      initialFocus: false,
      onFocusChannel: () => {},
      onEnterChannel: () => {},
      onBackToOverview: () => {},
      onPrepareStudio: async () => {},
      onRetry: () => {},
    })
  );
  assert.ok(loadingHtml.includes("Carregando estúdios"));

  const errHtml = renderToStaticMarkup(
    React.createElement(HQ, {
      overview: undefined,
      loading: false,
      error: new ApiClientError(503, { code: "SUPABASE_UNAVAILABLE", message: "Banco fora do ar", retryable: true }),
      realtimeStatus: "polling",
      focusedChannelId: null,
      initialFocus: false,
      onFocusChannel: () => {},
      onEnterChannel: () => {},
      onBackToOverview: () => {},
      onPrepareStudio: async () => {},
      onRetry: () => {},
    })
  );
  assert.ok(errHtml.includes("SUPABASE_UNAVAILABLE"));
  assert.ok(errHtml.includes("Tentar de novo"));

  const emptyHtml = renderToStaticMarkup(
    React.createElement(HQ, {
      overview: HQ_OVERVIEW_FIXTURES.empty,
      loading: false,
      error: null,
      realtimeStatus: "connected",
      focusedChannelId: null,
      initialFocus: false,
      onFocusChannel: () => {},
      onEnterChannel: () => {},
      onBackToOverview: () => {},
      onPrepareStudio: async () => {},
      onRetry: () => {},
      onNavigateChannels: () => {},
    })
  );
  assert.ok(emptyHtml.includes("Conectar canal"));
  passed++;

  // 4. Keyboard flow (Enter -> Enter -> Esc) and formatMinutesAgo
  let navState: HQNavState = { mode: "overview", focusedChannelId: null };
  navState = transitionHQNav(navState, { type: "focus", channelId: "ch-1" });
  assert.equal(navState.mode, "focus");
  navState = transitionHQNav(navState, { type: "focus", channelId: "ch-1" });
  assert.equal(navState.mode, "enter");
  navState = transitionHQNav(navState, { type: "back" });
  assert.equal(navState.mode, "focus");
  navState = transitionHQNav(navState, { type: "back" });
  assert.equal(navState.mode, "overview");
  assert.equal(formatMinutesAgo("2026-11-17T17:05:00Z", Date.parse("2026-11-17T17:15:00Z")), "Última atividade há 10 min");
  passed++;

  return passed;
}
