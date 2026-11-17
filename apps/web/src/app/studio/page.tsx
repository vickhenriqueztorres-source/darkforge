"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { api, type ChannelDTO, type WorkspaceListItem } from "@/lib/api";
import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";
import { StudioWorkspace } from "@/components/studio/StudioWorkspace";

export default function StudioRoutePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [workspaces, setWorkspaces] = useState<WorkspaceListItem[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState("");
  const [channels, setChannels] = useState<ChannelDTO[]>([]);
  const [activeChannelId, setActiveChannelId] = useState("");
  const [banner, setBanner] = useState<{ kind: string; code: string; message: string } | null>(null);

  useEffect(() => {
    if (!isSupabaseConfigured()) {
      setReady(true);
      return;
    }
    const supa = getSupabaseClient();
    supa.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setReady(true);
    });
    const { data: listener } = supa.auth.onAuthStateChange((_e, s) => setSession(s ?? null));
    return () => listener.subscription.unsubscribe();
  }, []);

  const loadContext = useCallback(async (tok: string) => {
    try {
      const wsRes = await api.listWorkspaces(tok);
      setWorkspaces(wsRes.items);
      const wsId = wsRes.items[0]?.workspace.id ?? "";
      setActiveWorkspaceId(wsId);
      if (wsId) {
        const chRes = await api.listChannels(tok, wsId);
        setChannels(chRes.items);
        const urlCh =
          typeof window !== "undefined"
            ? new URLSearchParams(window.location.search).get("channel")
            : null;
        const match = chRes.items.find((c) => c.id === urlCh) ?? chRes.items[0];
        setActiveChannelId(match?.id ?? "");
      }
    } catch {
      // handled by StudioWorkspace
    }
  }, []);

  useEffect(() => {
    if (session?.access_token) {
      loadContext(session.access_token);
    }
  }, [session?.access_token, loadContext]);

  return (
    <main className="main" style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <header className="topbar">
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <strong style={{ color: "var(--accent)" }}>DarkForge Estúdio de Conteúdo</strong>
          {workspaces.length > 1 && (
            <select
              className="input"
              style={{ width: "auto" }}
              value={activeWorkspaceId}
              onChange={(e) => {
                const ws = e.target.value;
                setActiveWorkspaceId(ws);
                if (session?.access_token && ws) {
                  api.listChannels(session.access_token, ws).then((r) => {
                    setChannels(r.items);
                    setActiveChannelId(r.items[0]?.id ?? "");
                  });
                }
              }}
            >
              {workspaces.map((w) => (
                <option key={w.workspace.id} value={w.workspace.id}>
                  {w.workspace.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <Link href="/" className="btn studio-btn-sm" style={{ textDecoration: "none" }}>
          Voltar ao Channel OS
        </Link>
      </header>

      {banner && (
        <div className={`banner ${banner.kind === "err" ? "err" : ""}`} role="alert">
          <strong>[{banner.code}]</strong> {banner.message}
        </div>
      )}

      {!ready ? (
        <section className="card"><p>Verificando sessão…</p></section>
      ) : !session ? (
        <section className="card">
          <p>Faça login na tela principal para acessar o Estúdio de Conteúdo.</p>
          <Link href="/" className="btn primary" style={{ textDecoration: "none" }}>
            Ir para Login
          </Link>
        </section>
      ) : (
        <StudioWorkspace
          token={session.access_token}
          workspaceId={activeWorkspaceId}
          channels={channels}
          activeChannelId={activeChannelId}
          onSelectChannel={setActiveChannelId}
          onNotice={setBanner}
        />
      )}
    </main>
  );
}
