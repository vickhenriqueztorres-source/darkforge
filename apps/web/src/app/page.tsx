"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import {
  api,
  ApiClientError,
  type ChannelDTO,
  type ChannelProfileVersionDTO,
  type ConnectionDTO,
  type EditorialThemeChangeDTO,
  type HealthDTO,
  type JobDTO,
  type JobEventDTO,
  type MetricFactDTO,
  type StorageReconcileDTO,
  type SyncCursorDTO,
  type VideoDTO,
  type WorkspaceListItem,
  type ReportsOverviewDTO,
} from "@/lib/api";
import { getSupabaseClient, isSupabaseConfigured } from "@/lib/supabase";
import { notifyHQUrlSync } from "@/lib/studio/useHQNavigation";
import { StudioWorkspace } from "@/components/studio/StudioWorkspace";

type NavSection =
  | "studio"
  | "dashboard"
  | "reports"
  | "channels"
  | "analytics"
  | "research"
  | "opportunities"
  | "calendar"
  | "briefs"
  | "knowledge"
  | "production"
  | "jobs"
  | "settings";

type ReportsTab =
  | "overview"
  | "channels_outliers"
  | "autopsies_mechanisms"
  | "trends_studio"
  | "opportunities_score";

type UiNotice = {
  kind: "info" | "warn" | "err";
  code: string;
  message: string;
  nextAction?: string;
};

const NAV_ITEMS: { id: NavSection; label: string; phase: string }[] = [
  { id: "studio", label: "Sede & Estúdios", phase: "UI" },
  { id: "dashboard", label: "Dashboard", phase: "SP-01" },
  { id: "reports", label: "Relatorios & Central", phase: "SP-24" },
  { id: "channels", label: "Canais & Perfil", phase: "SP-01" },
  { id: "analytics", label: "Analytics Center", phase: "SP-03" },
  { id: "research", label: "Pesquisa", phase: "SP-04" },
  { id: "opportunities", label: "Oportunidades", phase: "SP-07" },
  { id: "calendar", label: "Calendario", phase: "SP-07" },
  { id: "briefs", label: "Briefs e Geracoes", phase: "SP-07" },
  { id: "knowledge", label: "Knowledge / Copies", phase: "SP-06" },
  { id: "production", label: "Producao DarkForge", phase: "SP-08" },
  { id: "jobs", label: "Jobs e Qualidade", phase: "SP-02" },
  { id: "settings", label: "Configuracoes", phase: "SP-01" },
];

export default function HomePage() {
  const router = useRouter();
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [section, setSection] = useState<NavSection>("studio");
  const [session, setSession] = useState<Session | null>(null);
  const [authReady, setAuthReady] = useState(false);

  // Auth form
  const [email, setEmail] = useState("admin@managet.local");
  const [password, setPassword] = useState("Managet123!");
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");

  // Operational state
  const [health, setHealth] = useState<HealthDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<UiNotice | null>(null);

  // Workspaces & Channels
  const [workspaces, setWorkspaces] = useState<WorkspaceListItem[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string>("");
  const [wsName, setWsName] = useState("");
  const [wsSlug, setWsSlug] = useState("");

  const [channels, setChannels] = useState<ChannelDTO[]>([]);
  const [activeChannelId, setActiveChannelId] = useState<string>("");
  const [versions, setVersions] = useState<ChannelProfileVersionDTO[]>([]);
  const [themeChanges, setThemeChanges] = useState<EditorialThemeChangeDTO[]>([]);

  // Channel creation / profile form
  const [chDisplayName, setChDisplayName] = useState("");
  const [chHandle, setChHandle] = useState("");
  const [profName, setProfName] = useState("");
  const [profLang, setProfLang] = useState("pt-BR");
  const [profCountry, setProfCountry] = useState("BR");
  const [profTz, setProfTz] = useState("America/Sao_Paulo");
  const [profNiche, setProfNiche] = useState("");
  const [profPositioning, setProfPositioning] = useState("");
  const [profTheme, setProfTheme] = useState("");
  const [profPillars, setProfPillars] = useState("");
  const [profForbidden, setProfForbidden] = useState("");
  const [profSummary, setProfSummary] = useState("Atualizacao editorial");
  const [profThemeReason, setProfThemeReason] = useState("");

  // Jobs & Storage (SP-02)
  const [jobs, setJobs] = useState<JobDTO[]>([]);
  const [jobStatusFilter, setJobStatusFilter] = useState<string>("");
  const [selectedJob, setSelectedJob] = useState<{ job: JobDTO; events: JobEventDTO[] } | null>(null);
  const [reconcileReport, setReconcileReport] = useState<StorageReconcileDTO | null>(null);

  // YouTube & Analytics (SP-03)
  const [connections, setConnections] = useState<ConnectionDTO[]>([]);
  const [portfolio, setPortfolio] = useState<{
    period_start: string;
    period_end: string;
    channels: { channel_id: string; display_name: string; video_count: number; metrics: MetricFactDTO[]; cursors: SyncCursorDTO[] }[];
    quota: { daily_limit: number; own_sync_used: number; public_research_used: number };
  } | null>(null);
  const [channelAnalytics, setChannelAnalytics] = useState<{
    metrics: MetricFactDTO[];
    cursors: SyncCursorDTO[];
    videos: VideoDTO[];
  } | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<{ video: VideoDTO; metrics: MetricFactDTO[] } | null>(null);

  // Research & Title/Thumb (SP-04 / SP-05) & Studio Trends (SP-10..SP-14)
  const [refs, setRefs] = useState<{ channels: Record<string, unknown>[]; videos: Record<string, unknown>[] }>({ channels: [], videos: [] });
  const [titleInput, setTitleInput] = useState("");
  const [titleAnalysis, setTitleAnalysis] = useState<{ features_json: { features: string[] }; editorial_formula: string; limitations_json: string[] } | null>(null);
  const [titleTopic, setTitleTopic] = useState("");
  const [titleAlts, setTitleAlts] = useState<{ title: string; differentiation: string; originality: { approval_blocked: boolean; max_similarity: number } }[]>([]);
  const [studioTopic, setStudioTopic] = useState("");
  const [studioMinInterest, setStudioMinInterest] = useState("medium");
  const [studioWatchedOnly, setStudioWatchedOnly] = useState(true);
  const [studioDays, setStudioDays] = useState(28);
  const [studioMinOutlier, setStudioMinOutlier] = useState(3);
  const [studioSession, setStudioSession] = useState<{ authenticated: boolean; reason: string } | null>(null);
  const [studioTerms, setStudioTerms] = useState<{ id: string; term: string; block_type: string; audience_interest: string; is_hypothesis: boolean; gap_note: string }[]>([]);
  const [studioOutliers, setStudioOutliers] = useState<{ id: string; title: string; canonical_url: string; outlier_ratio: number | null; outlier_tier: string; watched_by_my_viewers: boolean; public_views: number | null }[]>([]);

  // Google Trends Sustainability (SP-15..SP-18)
  const [gtKeyword, setGtKeyword] = useState("");
  const [gtGeo, setGtGeo] = useState("BR");
  const [gtProp, setGtProp] = useState("youtube");
  const [gtCsv12m, setGtCsv12m] = useState("");
  const [gtCsv5y, setGtCsv5y] = useState("");
  const [gtCsvRel, setGtCsvRel] = useState("");
  const [gtItems, setGtItems] = useState<
    {
      id: string;
      keyword: string;
      geo: string;
      gprop: string;
      direction_12m: string;
      durability_5y: string;
      verdict: string;
      summary: string;
      points_12m_json: { value: number }[];
      points_5y_json: { value: number }[];
      breakout_queries_json: { term: string; raw_label: string }[];
      rising_queries_json: { term: string; raw_label: string }[];
    }[]
  >([]);

  // 4-Phase Reverse Engineering Lab (SP-19..SP-23)
  const [reVidId, setReVidId] = useState("");
  const [reVidTitle, setReVidTitle] = useState("");
  const [reTranscript, setReTranscript] = useState("");
  const [reComments, setReComments] = useState("");
  const [reOwnTopic, setReOwnTopic] = useState("");
  const [reNewAngle, setReNewAngle] = useState("");
  const [reP1Name, setReP1Name] = useState("");
  const [reP1Lang, setReP1Lang] = useState("pt-BR");
  const [reP1Country, setReP1Country] = useState("BR");
  const [reP1Format, setReP1Format] = useState("faceless_essay");
  const [reP1Tags, setReP1Tags] = useState("historia, documentario");
  const [reP1Views20, setReP1Views20] = useState("4500,4800,5100,4900,5000,4700,4600,5200,4400,5300,4950,5050,4800,4700,4600,5100,4900,5000,42000,68000");
  const [reP1Views90d, setReP1Views90d] = useState("42000,68000");
  const [reP1Celebrity, setReP1Celebrity] = useState(false);
  const [reP2ChannelName, setReP2ChannelName] = useState("Canal Referencia");
  const [reP2Title, setReP2Title] = useState("");
  const [reP2Views, setReP2Views] = useState("92000");
  const [reP2Days, setReP2Days] = useState("14");
  const [reP2BaselineViews, setReP2BaselineViews] = useState("4500");
  const [reP2SmallNiche, setReP2SmallNiche] = useState(false);
  const [reState, setReState] = useState<{
    audits: {
      id: string;
      external_channel_id?: string;
      display_name: string;
      approved: boolean;
      channel_mean_views?: number;
      outlier_hits_count?: number;
      max_outlier_ratio: number;
      ranking_score?: number;
    }[];
    viral_outliers: {
      id: string;
      external_video_id: string;
      channel_name: string;
      title: string;
      views: number;
      days_since_upload: number;
      views_per_day: number;
      outlier_ratio: number;
      pattern_key: string;
      confirmed_multi_channel: boolean;
      is_false_positive: boolean;
    }[];
    autopsies: { id: string; external_video_id?: string; original_title: string; narrative_archetype: string }[];
    mechanisms: {
      id: string;
      synthesized_title: string;
      synthesized_thumb_concept: string;
      formula_structure: string;
      originality_blocked: boolean;
      originality_max_similarity: number;
    }[];
    batches: { id: string; title: string; status: string; impressions: number | null; ctr_pct: number | null; retention_30s_pct: number | null }[];
  } | null>(null);

  // Relatorios & Central (SP-24 / SP-25)
  const [reportsTab, setReportsTab] = useState<ReportsTab>("overview");
  const [reportsOverview, setReportsOverview] = useState<ReportsOverviewDTO | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [executiveMd, setExecutiveMd] = useState("");

  // Knowledge/RAG (SP-06)
  const [knowSources, setKnowSources] = useState<{ id: string; title: string; source_type: string; curation_level: string; status: string; rights_status: string }[]>([]);
  const [knowTitle, setKnowTitle] = useState("");
  const [knowContent, setKnowContent] = useState("");
  const [knowQuery, setKnowQuery] = useState("");
  const [knowHits, setKnowHits] = useState<{ chunk_id: string; source_title: string; curation_level: string; chunk_text: string; hybrid_score: number }[]>([]);

  // Opportunities, Briefs & Calendar (SP-07)
  const [opps, setOpps] = useState<{ id: string; theme: string; angle: string; score: number; score_version: string; confidence: number; status: string; insufficient_data: boolean; limitations_json: string[] }[]>([]);
  const [oppTopic, setOppTopic] = useState("");
  const [briefs, setBriefs] = useState<{ id: string; brief_group_id: string; version: number; opportunity_id: string; title: string; hook: string; angle: string; status: string; content_sha256: string }[]>([]);
  const [briefExportText, setBriefExportText] = useState("");
  const [calItems, setCalItems] = useState<{ id: string; title: string; scheduled_for: string; status: string; auto_publish_enabled: boolean }[]>([]);
  const [calTitle, setCalTitle] = useState("");
  const [calDate, setCalDate] = useState("2026-11-20");

  // Production DarkForge (SP-08)
  const [prodHealth, setProdHealth] = useState<{ available: boolean; mode: string; reason: string | null } | null>(null);
  const [prodIntents, setProdIntents] = useState<{ id: string; brief_id: string; brief_version: number; status: string; manifest_validated: boolean; error_code: string | null; error_message: string | null }[]>([]);
  const [diagBundle, setDiagBundle] = useState("");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const mapErrorToNotice = useCallback((err: unknown): UiNotice => {
    if (err instanceof ApiClientError) {
      return {
        kind: err.envelope.code === "SUPABASE_UNAVAILABLE" || err.envelope.code === "WORKSPACE_FORBIDDEN" ? "err" : "warn",
        code: err.envelope.code,
        message: err.envelope.message,
        nextAction: err.envelope.details?.next_action,
      };
    }
    return {
      kind: "err",
      code: "UNEXPECTED_ERROR",
      message: err instanceof Error ? err.message : "Erro inesperado ao consultar dados.",
    };
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const h = await api.health();
      setHealth(h);
    } catch {
      setHealth({ status: "degraded", supabase_reachable: false, service: "darkforge-channel-os-api" });
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    if (!isSupabaseConfigured()) {
      setAuthReady(true);
      setNotice({
        kind: "err",
        code: "CONFIG_MISSING",
        message: "Variaveis NEXT_PUBLIC_SUPABASE_URL / PUBLISHABLE_KEY ausentes.",
      });
      return;
    }
    const supa = getSupabaseClient();
    supa.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setAuthReady(true);
    });
    const { data: listener } = supa.auth.onAuthStateChange((_evt, newSession) => {
      setSession(newSession ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, [refreshHealth]);

  const loadWorkspaces = useCallback(async (tok: string) => {
    setLoading(true);
    try {
      const res = await api.listWorkspaces(tok);
      setWorkspaces(res.items);
      if (res.items.length > 0) {
        setActiveWorkspaceId((prev) =>
          res.items.some((i) => i.workspace.id === prev) ? prev : res.items[0].workspace.id
        );
      } else {
        setActiveWorkspaceId("");
      }
      setNotice(null);
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    } finally {
      setLoading(false);
    }
  }, [mapErrorToNotice]);

  useEffect(() => {
    if (session?.access_token) {
      loadWorkspaces(session.access_token);
    } else {
      setWorkspaces([]);
      setChannels([]);
      setActiveWorkspaceId("");
      setActiveChannelId("");
    }
  }, [session?.access_token, loadWorkspaces]);

  const loadChannels = useCallback(async (tok: string, wsId: string) => {
    if (!wsId) return;
    setLoading(true);
    try {
      const res = await api.listChannels(tok, wsId);
      setChannels(res.items);
      if (res.items.length > 0) {
        const urlCh =
          typeof window !== "undefined"
            ? new URLSearchParams(window.location.search).get("channel")
            : null;
        const fromUrl = urlCh ? res.items.find((c) => c.id === urlCh) : undefined;
        const preferred = fromUrl ?? res.items.find((c) => c.external_channel_id) ?? res.items[0];
        setActiveChannelId((prev) =>
          fromUrl ? fromUrl.id : res.items.some((c) => c.id === prev) ? prev : preferred.id
        );
      } else {
        setActiveChannelId("");
      }
      setNotice(null);
    } catch (err) {
      setChannels([]);
      setNotice(mapErrorToNotice(err));
    } finally {
      setLoading(false);
    }
  }, [mapErrorToNotice]);

  useEffect(() => {
    if (session?.access_token && activeWorkspaceId) {
      loadChannels(session.access_token, activeWorkspaceId);
    }
  }, [session?.access_token, activeWorkspaceId, loadChannels]);

  const loadJobs = useCallback(async (tok: string, wsId: string, status?: string) => {
    if (!wsId) return;
    try {
      const res = await api.listJobs(tok, wsId, status || undefined);
      setJobs(res.items);
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }, [mapErrorToNotice]);

  useEffect(() => {
    if (session?.access_token && activeWorkspaceId && section === "jobs") {
      loadJobs(session.access_token, activeWorkspaceId, jobStatusFilter);
    }
  }, [session?.access_token, activeWorkspaceId, section, jobStatusFilter, loadJobs]);

  const loadAnalytics = useCallback(async (tok: string, wsId: string, chId?: string) => {
    if (!wsId) return;
    try {
      const [connRes, portRes] = await Promise.all([
        api.listConnections(tok, wsId),
        api.getPortfolioAnalytics(tok, wsId),
      ]);
      setConnections(connRes.items);
      setPortfolio(portRes);
      if (chId) {
        const chRes = await api.getChannelAnalytics(tok, wsId, chId);
        setChannelAnalytics(chRes);
      } else {
        setChannelAnalytics(null);
      }
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }, [mapErrorToNotice]);

  useEffect(() => {
    if (session?.access_token && activeWorkspaceId && (section === "analytics" || section === "settings")) {
      loadAnalytics(session.access_token, activeWorkspaceId, activeChannelId || undefined);
    }
  }, [session?.access_token, activeWorkspaceId, activeChannelId, section, loadAnalytics]);

  const loadReportsOverview = useCallback(
    async (tok: string, wsId: string, chId?: string) => {
      if (!wsId) return;
      setReportsLoading(true);
      try {
        const data = await api.getReportsOverview(tok, wsId, chId);
        setReportsOverview(data);
        setNotice(null);
      } catch (err) {
        setNotice(mapErrorToNotice(err));
      } finally {
        setReportsLoading(false);
      }
    },
    [mapErrorToNotice]
  );

  useEffect(() => {
    const tok = session?.access_token;
    if (!tok || !activeWorkspaceId) return;
    if (section === "reports") {
      loadReportsOverview(tok, activeWorkspaceId, activeChannelId || undefined);
      return;
    }
    if (section === "research" && activeChannelId) {
      Promise.all([
        api.listStudioRuns(tok, activeWorkspaceId, activeChannelId).then(async (r) => {
          if (r.items.length > 0) {
            const det = await api.getStudioRunDetail(tok, activeWorkspaceId, r.items[0].id);
            setStudioTerms(det.terms);
            setStudioOutliers(det.outliers);
          }
        }).catch(() => {}),
        api.listGoogleTrends(tok, activeWorkspaceId, activeChannelId).then((r) => setGtItems(r.items)).catch(() => {}),
        api.getReverseEngineeringState(tok, activeWorkspaceId, activeChannelId).then((st) => setReState(st)).catch(() => {}),
      ]);
    } else if (section === "opportunities" && activeChannelId) {
      api.listOpportunities(tok, activeWorkspaceId, activeChannelId).then((r) => setOpps(r.items)).catch((err) => setNotice(mapErrorToNotice(err)));
    } else if (section === "briefs" && activeChannelId) {
      Promise.all([
        api.listOpportunities(tok, activeWorkspaceId, activeChannelId).then((r) => setOpps(r.items)).catch(() => {}),
        api.listBriefs(tok, activeWorkspaceId).then((r) => setBriefs(r.items)).catch(() => {}),
      ]);
    } else if (section === "calendar") {
      api.listCalendar(tok, activeWorkspaceId).then((r) => setCalItems(r.items)).catch((err) => setNotice(mapErrorToNotice(err)));
    } else if (section === "knowledge") {
      api.listKnowledgeSources(tok, activeWorkspaceId).then((r) => setKnowSources(r.items)).catch((err) => setNotice(mapErrorToNotice(err)));
    } else if (section === "production") {
      Promise.all([
        api.getProductionHealth(tok, activeWorkspaceId).then((h) => setProdHealth(h)).catch(() => {}),
        api.listProductionIntents(tok, activeWorkspaceId).then((r) => setProdIntents(r.items)).catch(() => {}),
      ]);
    }
  }, [session?.access_token, activeWorkspaceId, activeChannelId, section, loadReportsOverview, mapErrorToNotice]);

  const loadChannelHistory = useCallback(
    async (tok: string, wsId: string, chId: string) => {
      if (!wsId || !chId) {
        setVersions([]);
        setThemeChanges([]);
        return;
      }
      try {
        const [vRes, tcRes] = await Promise.all([
          api.listProfileVersions(tok, wsId, chId),
          api.listThemeChanges(tok, wsId, chId),
        ]);
        setVersions(vRes.items);
        setThemeChanges(tcRes.items);
        if (vRes.items[0]) {
          const cur = vRes.items[0];
          setProfName(cur.name);
          setProfLang(cur.language);
          setProfCountry(cur.country);
          setProfTz(cur.timezone);
          setProfNiche(cur.niche);
          setProfPositioning(cur.positioning);
          setProfTheme(cur.editorial_theme);
          setProfPillars((cur.pillars_json ?? []).join(", "));
          const forb = (cur.restrictions_json?.forbidden_topics as string[] | undefined) ?? [];
          setProfForbidden(forb.join(", "));
        }
      } catch (err) {
        setNotice(mapErrorToNotice(err));
      }
    },
    [mapErrorToNotice]
  );

  useEffect(() => {
    if (session?.access_token && activeWorkspaceId && activeChannelId) {
      loadChannelHistory(session.access_token, activeWorkspaceId, activeChannelId);
    }
  }, [session?.access_token, activeWorkspaceId, activeChannelId, loadChannelHistory]);

  const activeWorkspace = useMemo(
    () => workspaces.find((w) => w.workspace.id === activeWorkspaceId) ?? null,
    [workspaces, activeWorkspaceId]
  );
  const activeChannel = useMemo(
    () => channels.find((c) => c.id === activeChannelId) ?? null,
    [channels, activeChannelId]
  );
  const activeVersion = versions[0] ?? null;

  async function handleAuthSubmit(e: React.FormEvent) {
    e.preventDefault();
    setNotice(null);
    try {
      const supa = getSupabaseClient();
      const result =
        authMode === "signin"
          ? await supa.auth.signInWithPassword({ email, password })
          : await supa.auth.signUp({ email, password });
      if (result.error) {
        setNotice({ kind: "err", code: "AUTH_ERROR", message: result.error.message });
      }
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }

  async function handleSignOut() {
    const supa = getSupabaseClient();
    await supa.auth.signOut();
    setNotice(null);
  }

  async function handleCreateWorkspace(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.access_token) return;
    try {
      const created = await api.createWorkspace(session.access_token, wsName, wsSlug);
      setWsName("");
      setWsSlug("");
      await loadWorkspaces(session.access_token);
      setActiveWorkspaceId(created.workspace.id);
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }

  function buildProfilePayload() {
    return {
      name: profName || chDisplayName,
      language: profLang,
      country: profCountry,
      timezone: profTz,
      niche: profNiche,
      positioning: profPositioning,
      editorial_theme: profTheme,
      pillars_json: profPillars.split(",").map((s) => s.trim()).filter(Boolean),
      restrictions_json: {
        forbidden_topics: profForbidden.split(",").map((s) => s.trim()).filter(Boolean),
      },
      change_summary: profSummary,
      theme_change_reason: profThemeReason,
    };
  }

  async function handleCreateChannel(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.access_token || !activeWorkspaceId) return;
    try {
      const created = await api.createChannel(session.access_token, activeWorkspaceId, {
        display_name: chDisplayName,
        handle: chHandle || null,
        profile: buildProfilePayload(),
      });
      setChDisplayName("");
      setChHandle("");
      await loadChannels(session.access_token, activeWorkspaceId);
      setActiveChannelId(created.channel.id);
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }

  async function handleUpdateProfile(e: React.FormEvent) {
    e.preventDefault();
    if (!session?.access_token || !activeWorkspaceId || !activeChannelId) return;
    try {
      await api.updateProfile(
        session.access_token,
        activeWorkspaceId,
        activeChannelId,
        buildProfilePayload()
      );
      await loadChannelHistory(session.access_token, activeWorkspaceId, activeChannelId);
      setNotice({ kind: "info", code: "PROFILE_VERSION_CREATED", message: "Nova versao editorial salva sem alterar o historico." });
    } catch (err) {
      setNotice(mapErrorToNotice(err));
    }
  }

  return (
    <div className="shell">
      <nav className="sidebar" aria-label="Navegacao principal">
        <div className="sidebar-brand">
          <div className="sidebar-logo-3d" aria-hidden="true">▶</div>
          <div>
            <strong className="sidebar-brand-title">DarkForge OS</strong>
            <div className="sidebar-brand-sub">Estúdio &amp; Inteligência 3D</div>
          </div>
        </div>

        <div className="sidebar-nav-list">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className="nav-btn"
              aria-current={section === item.id ? "page" : undefined}
              onClick={() => {
                setSection(item.id);
                if (item.id === "studio") {
                  router.push("/?view=sede", { scroll: false });
                  window.setTimeout(() => notifyHQUrlSync(), 0);
                }
              }}
            >
              <span className="nav-btn-label">{item.label}</span>
              <span className="nav-phase-badge">{item.phase}</span>
            </button>
          ))}
        </div>

        <div className="sidebar-footer">
          <button
            type="button"
            className="btn studio-btn-sm"
            style={{ width: "100%" }}
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          >
            Tema: {theme === "dark" ? "Escuro 3D" : "Claro"}
          </button>
        </div>
      </nav>

      <main className="main">
        <header className="topbar" aria-label="Contexto ativo do workspace">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
            <span className="pill info">
              Workspace: <strong>{activeWorkspace ? `${activeWorkspace.workspace.name} (${activeWorkspace.role})` : "Nenhum"}</strong>
            </span>
            <span className="pill">
              Canal: <strong>{activeChannel ? activeChannel.display_name : "Nenhum"}</strong>
            </span>
            <span className="pill">
              Perfil Editorial: <strong>{activeVersion ? `v${activeVersion.version_number}` : "N/A"}</strong>
            </span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span className={`pill ${health?.supabase_reachable ? "ok" : "err"}`}>
              Supabase: {health?.supabase_reachable ? "Conectado" : "Degradado / Offline"}
            </span>
            <button type="button" className="btn" onClick={refreshHealth}>Verificar</button>
            {session && (
              <button type="button" className="btn" onClick={handleSignOut}>Encerrar sessao</button>
            )}
          </div>
        </header>

        {health && !health.supabase_reachable && (
          <div className="banner err" role="alert">
            <strong>[MODO DEGRADADO — ADR-015]</strong> Supabase inacessivel. Escritas e conclusoes de jobs estao bloqueadas para evitar falso sucesso.
          </div>
        )}

        {notice && (
          <div className={`banner ${notice.kind === "err" ? "err" : ""}`} role="alert">
            <strong>[{notice.code}]</strong> {notice.message}
            {notice.nextAction && <div className="muted">Proxima acao: {notice.nextAction}</div>}
          </div>
        )}

        {!authReady ? (
          <section className="card"><p>Verificando sessao Supabase Auth...</p></section>
        ) : !session ? (
          <section className="card" style={{ maxWidth: 460 }}>
            <h2>Autenticacao no Produto (Supabase Auth)</h2>
            <p className="muted">
              A sessao do Channel OS e separada de qualquer conexao OAuth do YouTube (AUTH-004).
            </p>
            <form onSubmit={handleAuthSubmit}>
              <div className="field">
                <label htmlFor="auth-email">E-mail</label>
                <input id="auth-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="auth-pass">Senha</label>
                <input id="auth-pass" className="input" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="submit" className="btn primary">
                  {authMode === "signin" ? "Entrar" : "Criar conta"}
                </button>
                <button type="button" className="btn" onClick={() => setAuthMode((m) => (m === "signin" ? "signup" : "signin"))}>
                  {authMode === "signin" ? "Novo usuario" : "Ja tenho conta"}
                </button>
              </div>
            </form>
          </section>
        ) : (
          <>
            {section === "studio" && (
              <StudioWorkspace
                token={session.access_token}
                workspaceId={activeWorkspaceId}
                channels={channels}
                activeChannelId={activeChannelId}
                onSelectChannel={setActiveChannelId}
                onNotice={(n) => setNotice(n)}
                onNavigateChannels={() => setSection("channels")}
              />
            )}
            {(section === "dashboard" || section === "channels") && (
              <div className="grid-2">
                <section className="card">
                  <h2>Workspaces (Isolamento RLS)</h2>
                  {loading && <p className="muted">Carregando workspaces...</p>}
                  {!loading && workspaces.length === 0 && (
                    <p className="muted">Estado vazio legitimo: nenhum workspace vinculado ainda.</p>
                  )}
                  <div className="field">
                    <label htmlFor="ws-select">Selecionar workspace</label>
                    <select
                      id="ws-select"
                      className="input"
                      value={activeWorkspaceId}
                      onChange={(e) => setActiveWorkspaceId(e.target.value)}
                    >
                      <option value="">-- Selecione --</option>
                      {workspaces.map((w) => (
                        <option key={w.workspace.id} value={w.workspace.id}>
                          {w.workspace.name} ({w.role})
                        </option>
                      ))}
                    </select>
                  </div>
                  <form onSubmit={handleCreateWorkspace}>
                    <h3>Novo Workspace</h3>
                    <div className="field">
                      <label htmlFor="ws-name">Nome</label>
                      <input id="ws-name" className="input" required value={wsName} onChange={(e) => setWsName(e.target.value)} />
                    </div>
                    <div className="field">
                      <label htmlFor="ws-slug">Slug (minusculo, hifen)</label>
                      <input id="ws-slug" className="input" required value={wsSlug} onChange={(e) => setWsSlug(e.target.value)} placeholder="meu-workspace" />
                    </div>
                    <button type="submit" className="btn primary">Criar Workspace</button>
                  </form>
                </section>

                <section className="card">
                  <h2>Canais e Perfil Editorial Versionado</h2>
                  {!activeWorkspaceId ? (
                    <p className="muted">Selecione ou crie um workspace para gerenciar canais.</p>
                  ) : (
                    <>
                      <div className="field">
                        <label htmlFor="ch-select">Canal ativo ({channels.length})</label>
                        <select
                          id="ch-select"
                          className="input"
                          value={activeChannelId}
                          onChange={(e) => setActiveChannelId(e.target.value)}
                        >
                          <option value="">-- Novo ou selecione --</option>
                          {channels.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.display_name}{c.external_channel_id ? ` [${c.external_channel_id}]` : ""} ({c.status})
                            </option>
                          ))}
                        </select>
                      </div>
                      {channels.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
                          {channels.map((c) => (
                            <button
                              key={c.id}
                              type="button"
                              className={`btn ${activeChannelId === c.id ? "primary" : ""}`}
                              onClick={() => setActiveChannelId(c.id)}
                            >
                              {c.display_name}{c.external_channel_id ? ` (${c.external_channel_id})` : ""}
                            </button>
                          ))}
                        </div>
                      )}

                      {!activeChannelId ? (
                        <form onSubmit={handleCreateChannel}>
                          <h3>Cadastrar Canal + Perfil v1</h3>
                          <div className="field">
                            <label htmlFor="ch-name">Nome do canal</label>
                            <input id="ch-name" className="input" required value={chDisplayName} onChange={(e) => setChDisplayName(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ch-handle">Handle (@canal)</label>
                            <input id="ch-handle" className="input" value={chHandle} onChange={(e) => setChHandle(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="prof-niche">Nicho</label>
                            <input id="prof-niche" className="input" required value={profNiche} onChange={(e) => setProfNiche(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="prof-theme">Tema editorial inicial</label>
                            <input id="prof-theme" className="input" value={profTheme} onChange={(e) => setProfTheme(e.target.value)} />
                          </div>
                          <button type="submit" className="btn primary">Criar Canal e Perfil v1</button>
                        </form>
                      ) : (
                        <form onSubmit={handleUpdateProfile}>
                          <h3>Editar Perfil (gera nova versao imutavel)</h3>
                          <div className="field">
                            <label htmlFor="ed-niche">Nicho</label>
                            <input id="ed-niche" className="input" required value={profNiche} onChange={(e) => setProfNiche(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ed-pos">Posicionamento</label>
                            <textarea id="ed-pos" className="input" rows={2} value={profPositioning} onChange={(e) => setProfPositioning(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ed-theme">Tema editorial vigente</label>
                            <input id="ed-theme" className="input" value={profTheme} onChange={(e) => setProfTheme(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ed-pillars">Pilares (separados por virgula)</label>
                            <input id="ed-pillars" className="input" value={profPillars} onChange={(e) => setProfPillars(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ed-forb">Temas proibidos (separados por virgula)</label>
                            <input id="ed-forb" className="input" value={profForbidden} onChange={(e) => setProfForbidden(e.target.value)} />
                          </div>
                          <div className="field">
                            <label htmlFor="ed-reason">Motivo da mudanca de tema / resumo</label>
                            <input id="ed-reason" className="input" value={profThemeReason} onChange={(e) => { setProfThemeReason(e.target.value); setProfSummary(e.target.value || "Atualizacao editorial"); }} />
                          </div>
                          <button type="submit" className="btn primary">Salvar Nova Versao do Perfil</button>
                        </form>
                      )}
                    </>
                  )}
                </section>
              </div>
            )}

            {(section === "dashboard" || section === "channels") && activeChannelId && (
              <section className="card">
                <h3>Historico Imutavel de Versoes e Mudancas de Tema</h3>
                <div className="grid-2">
                  <div>
                    <h4>Versoes do Perfil ({versions.length})</h4>
                    <ul>
                      {versions.map((v) => (
                        <li key={v.id}>
                          <strong>v{v.version_number}</strong> — {v.editorial_theme || v.niche} ({v.change_summary})
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4>Mudancas de Tema ({themeChanges.length})</h4>
                    {themeChanges.length === 0 ? (
                      <p className="muted">Nenhuma mudanca de tema registrada apos v1.</p>
                    ) : (
                      <ul>
                        {themeChanges.map((tc) => (
                          <li key={tc.id}>
                            {tc.previous_theme || "(inicial)"} → <strong>{tc.new_theme}</strong> ({tc.reason || "sem motivo"})
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </section>
            )}

            {section === "jobs" && (
              <section className="card">
                <h2>Jobs, Recovery &amp; Qualidade (SP-02)</h2>
                {!activeWorkspaceId ? (
                  <p className="muted">Selecione um workspace para gerenciar jobs e Storage.</p>
                ) : (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                      <select
                        aria-label="Filtrar jobs por estado"
                        className="input"
                        value={jobStatusFilter}
                        onChange={(e) => setJobStatusFilter(e.target.value)}
                      >
                        <option value="">Todos os estados</option>
                        <option value="QUEUED">QUEUED</option>
                        <option value="RUNNING">RUNNING</option>
                        <option value="PAUSED">PAUSED</option>
                        <option value="BLOCKED">BLOCKED</option>
                        <option value="RECOVERABLE">RECOVERABLE</option>
                        <option value="FAILED">FAILED</option>
                        <option value="CANCELLED">CANCELLED</option>
                        <option value="SUCCEEDED">SUCCEEDED</option>
                      </select>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !activeWorkspaceId) return;
                          try {
                            const key = `diag-${crypto.randomUUID()}`;
                            await api.enqueueJob(
                              session.access_token,
                              activeWorkspaceId,
                              { job_type: "diagnostic.multi_step", payload: { steps: ["prepare", "process", "verify"] }, total_steps: 3 },
                              key
                            );
                            await loadJobs(session.access_token, activeWorkspaceId, jobStatusFilter);
                            setNotice({ kind: "info", code: "JOB_QUEUED", message: "Job diagnostico enfileirado na fila unica Postgres." });
                          } catch (err) {
                            setNotice(mapErrorToNotice(err));
                          }
                        }}
                      >
                        Enfileirar Job de Teste
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token || !activeWorkspaceId) return;
                          try {
                            const rep = await api.reconcileStorage(session.access_token, activeWorkspaceId, "exports");
                            setReconcileReport(rep.report);
                          } catch (err) {
                            setNotice(mapErrorToNotice(err));
                          }
                        }}
                      >
                        Reconciliar Storage (exports)
                      </button>
                    </div>

                    {reconcileReport && (
                      <div className="banner" style={{ marginBottom: 12 }}>
                        <strong>Reconciliacao bucket {reconcileReport.bucket}:</strong>{" "}
                        ausentes={reconcileReport.missing_in_storage.length}, orfaos={reconcileReport.orphaned_in_storage.length}, incompletos={reconcileReport.incomplete_uploads.length}
                      </div>
                    )}

                    {jobs.length === 0 ? (
                      <p className="muted">Nenhum job encontrado para este filtro.</p>
                    ) : (
                      <div className="grid-2">
                        <div>
                          {jobs.map((j) => (
                            <div key={j.id} className="card" style={{ marginBottom: 10 }}>
                              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                                <strong>{j.job_type}</strong>
                                <span className={`pill ${j.status === "SUCCEEDED" ? "ok" : j.status === "FAILED" || j.status === "BLOCKED" ? "err" : "warn"}`}>
                                  {j.status}
                                </span>
                              </div>
                              <p className="muted">
                                Etapa: <strong>{j.current_step}</strong> ({j.completed_steps}/{j.total_steps}) • Tentativa #{j.attempt_count}
                              </p>
                              {j.error_code && (
                                <p style={{ color: "var(--err)" }}>
                                  [{j.error_code}] {j.error_message} ({j.retryable ? "recuperavel" : "nao recuperavel"})
                                </p>
                              )}
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                <button
                                  type="button"
                                  className="btn"
                                  onClick={async () => {
                                    if (!session?.access_token) return;
                                    const d = await api.getJobDetail(session.access_token, activeWorkspaceId, j.id);
                                    setSelectedJob(d);
                                  }}
                                >
                                  Detalhes &amp; Logs
                                </button>
                                <button
                                  type="button"
                                  className="btn"
                                  onClick={async () => {
                                    if (!session?.access_token) return;
                                    try {
                                      const res = await api.pauseJob(session.access_token, activeWorkspaceId, j.id);
                                      setNotice({ kind: "info", code: "PAUSE_CONTROL", message: `Controle: ${res.control_result}` });
                                      await loadJobs(session.access_token, activeWorkspaceId, jobStatusFilter);
                                    } catch (err) { setNotice(mapErrorToNotice(err)); }
                                  }}
                                >
                                  Pausar
                                </button>
                                <button
                                  type="button"
                                  className="btn"
                                  onClick={async () => {
                                    if (!session?.access_token) return;
                                    try {
                                      await api.resumeJob(session.access_token, activeWorkspaceId, j.id);
                                      await loadJobs(session.access_token, activeWorkspaceId, jobStatusFilter);
                                    } catch (err) { setNotice(mapErrorToNotice(err)); }
                                  }}
                                >
                                  Retomar
                                </button>
                                <button
                                  type="button"
                                  className="btn"
                                  onClick={async () => {
                                    if (!session?.access_token) return;
                                    try {
                                      const res = await api.cancelJob(session.access_token, activeWorkspaceId, j.id);
                                      setNotice({ kind: "info", code: "CANCEL_CONTROL", message: `Controle: ${res.control_result}` });
                                      await loadJobs(session.access_token, activeWorkspaceId, jobStatusFilter);
                                    } catch (err) { setNotice(mapErrorToNotice(err)); }
                                  }}
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="card">
                          <h3>Eventos do Job</h3>
                          {!selectedJob ? (
                            <p className="muted">Selecione um job para inspecionar checkpoints e eventos SSE/replay.</p>
                          ) : (
                            <ul>
                              {selectedJob.events.map((ev) => (
                                <li key={ev.sequence_no}>
                                  <code>#{ev.sequence_no}</code> [{ev.status}] <strong>{ev.step_name}</strong>: {ev.message}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {section === "analytics" && (
              <section className="card">
                <h2>Analytics Center &amp; Conexao YouTube (SP-03)</h2>
                {!activeWorkspaceId ? (
                  <p className="muted">Selecione um workspace para consultar analytics.</p>
                ) : (
                  <>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                      {activeChannelId && (
                        <>
                          <button
                            type="button"
                            className="btn primary"
                            onClick={async () => {
                              if (!session?.access_token) return;
                              try {
                                const res = await api.authorizeYouTube(session.access_token, activeWorkspaceId, activeChannelId);
                                window.open(res.authorize_url, "_blank", "noopener,noreferrer");
                                setNotice({ kind: "info", code: "OAUTH_STARTED", message: "Fluxo OAuth oficial YouTube iniciado." });
                              } catch (err) {
                                setNotice(mapErrorToNotice(err));
                              }
                            }}
                          >
                            Conectar Canal via YouTube OAuth
                          </button>
                          <button
                            type="button"
                            className="btn"
                            onClick={async () => {
                              if (!session?.access_token) return;
                              try {
                                const res = await api.syncChannel(session.access_token, activeWorkspaceId, activeChannelId);
                                setNotice({ kind: "info", code: "SYNC_QUEUED", message: `Job de sync ${res.job_id} (${res.status}).` });
                              } catch (err) {
                                setNotice(mapErrorToNotice(err));
                              }
                            }}
                          >
                            Sincronizar Canal (Incremental)
                          </button>
                        </>
                      )}
                    </div>

                    {portfolio && (
                      <div className="card" style={{ marginBottom: 12 }}>
                        <h3>Portfolio ({portfolio.period_start} a {portfolio.period_end})</h3>
                        <p className="muted">
                          Quota API YouTube hoje: Sync proprio = {portfolio.quota.own_sync_used} | Pesquisa = {portfolio.quota.public_research_used} / {portfolio.quota.daily_limit}
                        </p>
                        {portfolio.channels.map((ch) => (
                          <div key={ch.channel_id} className="card" style={{ marginTop: 8 }}>
                            <strong>{ch.display_name}</strong> ({ch.video_count} videos) —{" "}
                            <span className="muted">
                              Frescor: {ch.cursors[0]?.freshness_status ?? "never_synced"}
                              {ch.cursors[0]?.last_successful_sync_at ? ` (${ch.cursors[0].last_successful_sync_at})` : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {channelAnalytics && (
                      <div className="grid-2">
                        <div className="card">
                          <h3>Metricas do Canal Ativo</h3>
                          {channelAnalytics.metrics.length === 0 ? (
                            <p className="muted">Nenhuma metrica sincronizada ainda (estado honesto sem zeros ficticios).</p>
                          ) : (
                            <ul>
                              {channelAnalytics.metrics.map((m) => (
                                <li key={m.id}>
                                  <strong>{m.display_name}:</strong>{" "}
                                  {m.availability === "available" ? m.value_num : <span className="pill warn">{m.availability.toUpperCase()}</span>}{" "}
                                  <span className="muted">({m.source} • rev.{m.source_revision} • {m.period_start}..{m.period_end})</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                        <div className="card">
                          <h3>Catalogo de Videos ({channelAnalytics.videos.length})</h3>
                          <ul>
                            {channelAnalytics.videos.map((v) => (
                              <li key={v.id} style={{ marginBottom: 6 }}>
                                <button
                                  type="button"
                                  className="btn"
                                  onClick={async () => {
                                    if (!session?.access_token) return;
                                    const d = await api.getVideoDetail(session.access_token, activeWorkspaceId, v.id);
                                    setSelectedVideo(d);
                                  }}
                                >
                                  {v.title} ({v.format})
                                </button>
                              </li>
                            ))}
                          </ul>
                          {selectedVideo && (
                            <div className="card" style={{ marginTop: 10 }}>
                              <h4>Ficha: {selectedVideo.video.title}</h4>
                              <p className="muted">Fonte: {selectedVideo.video.source}</p>
                              <ul>
                                {selectedVideo.metrics.map((vm) => (
                                  <li key={vm.id}>
                                    {vm.display_name}:{" "}
                                    {vm.availability === "available" ? vm.value_num : vm.availability.toUpperCase()} (rev.{vm.source_revision})
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {section === "research" && (
              <section className="card">
                <h2>Research Explorer &amp; Title/Thumbnail Intelligence (SP-04 / SP-05)</h2>
                <div className="banner" style={{ marginBottom: 12 }}>
                  <strong>Publico vs Privado (RES-006):</strong> Referencias publicas nao exibem nem estimam CTR, retencao ou receita privada.
                </div>
                {!activeWorkspaceId ? (
                  <p className="muted">Selecione um workspace.</p>
                ) : (
                  <div className="grid-2">
                    <div className="card">
                      <h3>Referencias Publicas Curadas</h3>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          const res = await api.listReferences(session.access_token, activeWorkspaceId);
                          setRefs(res);
                        }}
                      >
                        Atualizar Referencias
                      </button>
                      <p className="muted">Canais: {refs.channels.length} | Videos: {refs.videos.length}</p>
                      <ul>
                        {refs.videos.map((rv) => (
                          <li key={String(rv.id)} style={{ marginBottom: 6 }}>
                            <strong>{String(rv.title)}</strong> [{String(rv.curation_status)}]
                            <button
                              type="button"
                              className="btn"
                              style={{ marginLeft: 8 }}
                              onClick={async () => {
                                if (!session?.access_token) return;
                                await api.curateReference(session.access_token, activeWorkspaceId, String(rv.id), {
                                  entity_type: "video",
                                  status: "approved",
                                  notes: "Aprovado na curadoria UI",
                                  collection_name: "default",
                                });
                                const res = await api.listReferences(session.access_token, activeWorkspaceId);
                                setRefs(res);
                              }}
                            >
                              Aprovar
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="card">
                      <h3>Analise Estrutural &amp; Alternativas de Titulo</h3>
                      <div className="field">
                        <label htmlFor="t-ana">Titulo de referencia</label>
                        <input id="t-ana" className="input" value={titleInput} onChange={(e) => setTitleInput(e.target.value)} />
                      </div>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token || !titleInput.trim()) return;
                          const r = await api.analyzeTitle(session.access_token, activeWorkspaceId, titleInput, activeChannelId || undefined);
                          setTitleAnalysis(r);
                        }}
                      >
                        Analisar Estrutura
                      </button>
                      {titleAnalysis && (
                        <div style={{ marginTop: 8 }}>
                          <p><strong>Formula:</strong> {titleAnalysis.editorial_formula}</p>
                          <p className="muted">Features: {titleAnalysis.features_json.features.join(", ")}</p>
                          <p className="muted">{titleAnalysis.limitations_json[0]}</p>
                        </div>
                      )}
                      <hr style={{ borderColor: "var(--border)", margin: "12px 0" }} />
                      <div className="field">
                        <label htmlFor="t-topic">Tema para alternativas originais</label>
                        <input id="t-topic" className="input" value={titleTopic} onChange={(e) => setTitleTopic(e.target.value)} />
                      </div>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !titleTopic.trim()) return;
                          const r = await api.generateTitleAlternatives(session.access_token, activeWorkspaceId, {
                            channel_name: activeChannel?.display_name ?? "Canal",
                            niche: profNiche || "Editorial",
                            topic: titleTopic,
                            reference_titles: refs.videos.map((v) => String(v.title ?? "")),
                            forbidden_topics: profForbidden.split(",").map((s) => s.trim()).filter(Boolean),
                          });
                          setTitleAlts(r.items);
                        }}
                      >
                        Gerar Alternativas Originais
                      </button>
                      <ul>
                        {titleAlts.map((a, idx) => (
                          <li key={idx}>
                            <strong>{a.title}</strong> — {a.differentiation} (similaridade max: {(a.originality.max_similarity * 100).toFixed(0)}%)
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {activeWorkspaceId && activeChannelId && (
                  <div className="card" style={{ marginTop: 16 }}>
                    <h3>YouTube Studio Trends &amp; Outliers (SP-10..SP-14)</h3>
                    <p className="muted">
                      Coleta assistida na sua sessao autenticada (sem bypass de login/CAPTCHA): Top Searches, Audience Interest, Content Gaps (hipoteses), Watched by my viewers e Outlier Score (3x/5x+).
                    </p>
                    <div className="field-row" style={{ gap: 8, marginBottom: 10 }}>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          const st = await api.studioSessionStatus(session.access_token, activeWorkspaceId, activeChannelId);
                          setStudioSession(st);
                        }}
                      >
                        Verificar Sessao Studio
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          try {
                            const res = await api.openStudioLoginWindow(session.access_token, activeWorkspaceId, activeChannelId);
                            setStudioSession({ authenticated: res.authenticated, reason: res.authenticated ? "ok" : (res.next_action ?? "pendente") });
                          } catch (err) {
                            setNotice(mapErrorToNotice(err));
                          }
                        }}
                      >
                        Abrir Login YouTube Studio (Manual)
                      </button>
                      {studioSession && (
                        <span className={`pill ${studioSession.authenticated ? "info" : "warn"}`}>
                          Sessao Studio: {studioSession.authenticated ? "ATIVA" : studioSession.reason}
                        </span>
                      )}
                    </div>
                    <div className="field-row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                      <input
                        className="input"
                        style={{ maxWidth: 260 }}
                        placeholder="Tema amplo no Studio Trends..."
                        value={studioTopic}
                        onChange={(e) => setStudioTopic(e.target.value)}
                      />
                      <select
                        className="input"
                        style={{ maxWidth: 160 }}
                        value={studioMinInterest}
                        onChange={(e) => setStudioMinInterest(e.target.value)}
                      >
                        <option value="medium">Interesse: Medio+</option>
                        <option value="high">Interesse: Alto+</option>
                        <option value="very_high">Interesse: Muito Alto</option>
                      </select>
                      <select
                        className="input"
                        style={{ maxWidth: 130 }}
                        value={studioDays}
                        onChange={(e) => setStudioDays(Number(e.target.value))}
                      >
                        <option value={28}>Ultimos 28 dias</option>
                        <option value={90}>Ultimos 90 dias</option>
                        <option value={365}>Ultimo ano</option>
                      </select>
                      <select
                        className="input"
                        style={{ maxWidth: 130 }}
                        value={studioMinOutlier}
                        onChange={(e) => setStudioMinOutlier(Number(e.target.value))}
                      >
                        <option value={3}>Outlier &gt;= 3x</option>
                        <option value={5}>Outlier &gt;= 5x</option>
                        <option value={1}>Todos (1x+)</option>
                      </select>
                      <label style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <input type="checkbox" checked={studioWatchedOnly} onChange={(e) => setStudioWatchedOnly(e.target.checked)} />
                        Watched by my viewers
                      </label>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !studioTopic.trim()) return;
                          try {
                            const run = await api.createStudioRun(session.access_token, activeWorkspaceId, {
                              channel_id: activeChannelId,
                              broad_topic: studioTopic,
                              min_interest: studioMinInterest,
                              only_watched_by_my_viewers: studioWatchedOnly,
                              upload_window_days: studioDays,
                              min_outlier_ratio: studioMinOutlier,
                              execute_now: true,
                            });
                            setStudioTerms(
                              run.terms.map((t) => ({ ...t, gap_note: t.is_hypothesis ? "Hipotese a validar" : "" }))
                            );
                            setStudioOutliers(run.outliers.map((o) => ({ ...o, public_views: null })));
                          } catch (err) {
                            setNotice(mapErrorToNotice(err));
                          }
                        }}
                      >
                        Executar Busca no Studio
                      </button>
                    </div>
                    <div className="grid-2">
                      <div>
                        <h4>Top Searches &amp; Content Gaps ({studioTerms.length})</h4>
                        <ul>
                          {studioTerms.map((t) => (
                            <li key={t.id}>
                              <strong>{t.term}</strong> [{t.audience_interest}]{" "}
                              {t.is_hypothesis && <span className="pill warn">CONTENT GAP (HIPOTESE)</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4>Videos Outliers ({studioOutliers.length})</h4>
                        <ul>
                          {studioOutliers.map((o) => (
                            <li key={o.id} style={{ marginBottom: 6 }}>
                              <a href={o.canonical_url} target="_blank" rel="noreferrer">{o.title}</a> —{" "}
                              <span className="pill info">{o.outlier_ratio ? `${o.outlier_ratio}x` : o.outlier_tier}</span>{" "}
                              {o.watched_by_my_viewers && <span className="pill info">Meu publico</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
                {activeWorkspaceId && activeChannelId && (
                  <div className="card" style={{ marginTop: 16 }}>
                    <h3>Passo 4: Confirmacao de Sustentabilidade no Google Trends (SP-15..SP-18)</h3>
                    <p className="muted">
                      Confirma tendencia nos ultimos 12 meses, durabilidade em 5 anos (Perene vs Sazonal vs Pico Morto) e consultas Rising / Breakout (&gt;5.000%) na regiao do canal.
                    </p>
                    <div className="field-row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                      <input
                        className="input"
                        style={{ maxWidth: 240 }}
                        placeholder="Termo para validar..."
                        value={gtKeyword}
                        onChange={(e) => setGtKeyword(e.target.value)}
                      />
                      <input
                        className="input"
                        style={{ maxWidth: 80 }}
                        placeholder="BR"
                        value={gtGeo}
                        onChange={(e) => setGtGeo(e.target.value.toUpperCase())}
                      />
                      <select className="input" style={{ maxWidth: 140 }} value={gtProp} onChange={(e) => setGtProp(e.target.value)}>
                        <option value="youtube">YouTube Search</option>
                        <option value="web">Web Search</option>
                      </select>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !gtKeyword.trim()) return;
                          try {
                            await api.validateGoogleTrends(session.access_token, activeWorkspaceId, {
                              keyword: gtKeyword,
                              channel_id: activeChannelId,
                              geo: gtGeo,
                              gprop: gtProp,
                            });
                            const r = await api.listGoogleTrends(session.access_token, activeWorkspaceId, activeChannelId);
                            setGtItems(r.items);
                          } catch (err) {
                            setNotice(mapErrorToNotice(err));
                          }
                        }}
                      >
                        Validar via Navegador (12m/5a)
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          const r = await api.listGoogleTrends(session.access_token, activeWorkspaceId, activeChannelId);
                          setGtItems(r.items);
                        }}
                      >
                        Carregar Validacoes
                      </button>
                    </div>
                    <details style={{ marginBottom: 12 }}>
                      <summary className="muted" style={{ cursor: "pointer" }}>
                        Fallback sem rate-limit 429: Importar CSVs exportados do Google Trends
                      </summary>
                      <div className="grid-2" style={{ marginTop: 8 }}>
                        <textarea className="input" rows={3} placeholder="CSV multiTimeline 12 meses..." value={gtCsv12m} onChange={(e) => setGtCsv12m(e.target.value)} />
                        <textarea className="input" rows={3} placeholder="CSV multiTimeline 5 anos..." value={gtCsv5y} onChange={(e) => setGtCsv5y(e.target.value)} />
                      </div>
                      <textarea className="input" rows={2} style={{ marginTop: 6 }} placeholder="CSV relatedQueries (Top / Rising / Breakout)..." value={gtCsvRel} onChange={(e) => setGtCsvRel(e.target.value)} />
                      <button
                        type="button"
                        className="btn"
                        style={{ marginTop: 6 }}
                        onClick={async () => {
                          if (!session?.access_token || !gtKeyword.trim()) return;
                          await api.importGoogleTrendsCsv(session.access_token, activeWorkspaceId, {
                            keyword: gtKeyword,
                            channel_id: activeChannelId,
                            geo: gtGeo,
                            gprop: gtProp,
                            timeline_12m_csv: gtCsv12m,
                            timeline_5y_csv: gtCsv5y,
                            related_queries_csv: gtCsvRel,
                          });
                          const r = await api.listGoogleTrends(session.access_token, activeWorkspaceId, activeChannelId);
                          setGtItems(r.items);
                        }}
                      >
                        Processar CSVs Google Trends
                      </button>
                    </details>
                    <ul>
                      {gtItems.map((gt) => (
                        <li key={gt.id} style={{ marginBottom: 10 }}>
                          <strong>{gt.keyword}</strong> ({gt.geo}/{gt.gprop || "web"}) —{" "}
                          <span className={`pill ${gt.verdict === "SUSTAINABLE_GO" ? "info" : "warn"}`}>{gt.verdict}</span>{" "}
                          [12m: {gt.direction_12m} | 5a: {gt.durability_5y}]
                          <div className="muted">{gt.summary}</div>
                          {gt.points_12m_json?.length > 1 && (
                            <svg width={180} height={28} aria-label={`Tendencia 12m ${gt.keyword}`} style={{ display: "block", marginTop: 4 }}>
                              <polyline
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                points={gt.points_12m_json
                                  .map((pt, i) => `${(i / Math.max(1, gt.points_12m_json.length - 1)) * 176 + 2},${26 - (Math.min(100, pt.value) / 100) * 24}`)
                                  .join(" ")}
                              />
                            </svg>
                          )}
                          {gt.breakout_queries_json?.length > 0 && (
                            <div style={{ marginTop: 4 }}>
                              <strong>Breakout (&gt;5.000%):</strong>{" "}
                              {gt.breakout_queries_json.map((bq, i) => (
                                <button
                                  key={i}
                                  type="button"
                                  className="btn"
                                  style={{ marginRight: 6, padding: "2px 6px", fontSize: 12 }}
                                  onClick={() => {
                                    setTitleTopic(bq.term);
                                    setOppTopic(bq.term);
                                  }}
                                >
                                  {bq.term}
                                </button>
                              ))}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {activeWorkspaceId && activeChannelId && (
                  <div className="card" style={{ marginTop: 16 }}>
                    <h3>Engenharia Reversa Viral em 4 Fases &amp; Mecanismo Transferivel (SP-19..SP-23)</h3>
                    <p className="muted">
                      Fases: 1) Selecao 5-10 Canais (6 criterios) | 2) Outliers 20-30 videos &amp; Views/Dia | 3) Autopsia Package + 0-15s/15-30s/Meio + Comentarios | 4) Mecanismo Transferivel &amp; Lote de Teste.
                    </p>
                    <button
                      type="button"
                      className="btn"
                      style={{ marginBottom: 12 }}
                      onClick={async () => {
                        if (!session?.access_token) return;
                        const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                        setReState(st);
                      }}
                    >
                      Carregar Laboratorio 4 Fases
                    </button>
                    <div className="grid-2" style={{ marginBottom: 12 }}>
                      <div className="card">
                        <h4>Fase 1: Selecao de Canais de Referencia (6 Criterios)</h4>
                        <div className="field">
                          <label htmlFor="p1-name">Nome do canal concorrente / referencia</label>
                          <input id="p1-name" className="input" placeholder="Ex: Cronica Oculta" value={reP1Name} onChange={(e) => setReP1Name(e.target.value)} />
                        </div>
                        <div className="inline-grid-3">
                          <input aria-label="Idioma do canal" className="input" placeholder="pt-BR" value={reP1Lang} onChange={(e) => setReP1Lang(e.target.value)} />
                          <input aria-label="Pais alvo" className="input" placeholder="BR" value={reP1Country} onChange={(e) => setReP1Country(e.target.value)} />
                          <input aria-label="Formato de producao" className="input" placeholder="faceless_essay" value={reP1Format} onChange={(e) => setReP1Format(e.target.value)} />
                        </div>
                        <div className="field">
                          <label htmlFor="p1-tags">Publico-alvo / Tags (criterio 5)</label>
                          <input id="p1-tags" className="input" placeholder="historia, documentario" value={reP1Tags} onChange={(e) => setReP1Tags(e.target.value)} />
                        </div>
                        <div className="field">
                          <label htmlFor="p1-views20">Views dos ultimos 20-30 videos (separados por virgula)</label>
                          <textarea id="p1-views20" className="input" rows={2} value={reP1Views20} onChange={(e) => setReP1Views20(e.target.value)} />
                        </div>
                        <div className="field">
                          <label htmlFor="p1-views90">Views recentes (90 dias)</label>
                          <input id="p1-views90" className="input" value={reP1Views90d} onChange={(e) => setReP1Views90d(e.target.value)} />
                        </div>
                        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                          <input type="checkbox" checked={reP1Celebrity} onChange={(e) => setReP1Celebrity(e.target.checked)} />
                          Canal depende de celebridade/mega marca (descarta)
                        </label>
                        <div>
                          <button
                            type="button"
                            className="btn primary"
                            onClick={async () => {
                              if (!session?.access_token || !reP1Name.trim()) return;
                              try {
                                const parseNums = (txt: string) =>
                                  txt.split(/[,\s;]+/).map((n) => Number(n.trim())).filter((n) => Number.isFinite(n) && n >= 0);
                                const tags = reP1Tags.split(",").map((s) => s.trim()).filter(Boolean);
                                await api.runPhase1Channels(session.access_token, activeWorkspaceId, {
                                  channel_id: activeChannelId,
                                  target_language: reP1Lang,
                                  target_country: reP1Country,
                                  feasible_formats: [reP1Format],
                                  target_audience_tags: tags,
                                  candidates: [
                                    {
                                      external_channel_id: `UC-${reP1Name.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 10)}`,
                                      display_name: reP1Name,
                                      language: reP1Lang,
                                      market_country: reP1Country,
                                      recent_video_views_90d: parseNums(reP1Views90d),
                                      all_recent_20_30_views: parseNums(reP1Views20),
                                      production_format: reP1Format,
                                      audience_profile_tags: tags,
                                      is_celebrity_or_mega_brand: reP1Celebrity,
                                    },
                                  ],
                                });
                                const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                                setReState(st);
                              } catch (err) {
                                setNotice(mapErrorToNotice(err));
                              }
                            }}
                          >
                            Avaliar Canal nos 6 Criterios
                          </button>
                        </div>
                        {reState && reState.audits.length > 0 && (
                          <ul style={{ marginTop: 8 }}>
                            {reState.audits.slice(0, 5).map((a) => (
                              <li key={a.id}>
                                <strong>{a.display_name}</strong> —{" "}
                                <span className={`pill ${a.approved ? "ok" : "warn"}`}>
                                  {a.approved ? "APROVADO" : "DESCARTADO"}
                                </span>{" "}
                                | Max Outlier: {a.max_outlier_ratio}x
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                      <div className="card">
                        <h4>Fase 2: Calcular Outliers (Media 20-30 &amp; Views/Dia)</h4>
                        <div className="field">
                          <label htmlFor="p2-ch">Nome do canal de origem</label>
                          <input id="p2-ch" className="input" value={reP2ChannelName} onChange={(e) => setReP2ChannelName(e.target.value)} />
                        </div>
                        <div className="field">
                          <label htmlFor="p2-title">Titulo do video candidato a outlier</label>
                          <input id="p2-title" className="input" placeholder="Ex: A cidade que sumiu em 1 noite" value={reP2Title} onChange={(e) => setReP2Title(e.target.value)} />
                        </div>
                        <div className="inline-grid-3">
                          <input aria-label="Views do video" type="number" className="input" value={reP2Views} onChange={(e) => setReP2Views(e.target.value)} placeholder="Views" />
                          <input aria-label="Dias desde upload" type="number" min={1} className="input" value={reP2Days} onChange={(e) => setReP2Days(e.target.value)} placeholder="Dias" />
                          <input aria-label="Media baseline por video" type="number" className="input" value={reP2BaselineViews} onChange={(e) => setReP2BaselineViews(e.target.value)} placeholder="Media base" />
                        </div>
                        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                          <input type="checkbox" checked={reP2SmallNiche} onChange={(e) => setReP2SmallNiche(e.target.checked)} />
                          Nicho pequeno (limiar 2x em vez de 3x)
                        </label>
                        <div>
                          <button
                            type="button"
                            className="btn primary"
                            onClick={async () => {
                              if (!session?.access_token || !reP2Title.trim()) return;
                              try {
                                const extCh = `UC-${reP2ChannelName.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, 10) || "ref"}`;
                                const baseAvg = Math.max(100, Number(reP2BaselineViews) || 4000);
                                const baseline = Array.from({ length: 19 }, (_, idx) => ({
                                  external_video_id: `base-${idx}`,
                                  external_channel_id: extCh,
                                  channel_name: reP2ChannelName,
                                  title: `Video Base ${idx + 1}`,
                                  views: baseAvg,
                                  days_since_upload: 40 + idx * 5,
                                  topic: "baseline",
                                  format_name: "long",
                                }));
                                await api.runPhase2Outliers(session.access_token, activeWorkspaceId, {
                                  channel_id: activeChannelId,
                                  small_niche: reP2SmallNiche,
                                  videos: [
                                    ...baseline,
                                    {
                                      external_video_id: `out-${Date.now()}`,
                                      external_channel_id: extCh,
                                      channel_name: reP2ChannelName,
                                      title: reP2Title,
                                      views: Math.max(1, Number(reP2Views) || 50000),
                                      days_since_upload: Math.max(1, Number(reP2Days) || 14),
                                      topic: reP2Title.split(" ").slice(0, 3).join(" "),
                                      format_name: "long",
                                      in_suggested_feed: true,
                                    },
                                  ],
                                });
                                const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                                setReState(st);
                              } catch (err) {
                                setNotice(mapErrorToNotice(err));
                              }
                            }}
                          >
                            Calcular Outlier &amp; Views/Dia
                          </button>
                        </div>
                        {reState && reState.viral_outliers?.length > 0 && (
                          <ul style={{ marginTop: 8 }}>
                            {reState.viral_outliers.slice(0, 5).map((o) => (
                              <li key={o.id}>
                                <strong>{o.title}</strong> ({o.outlier_ratio}x | {Math.round(o.views_per_day)} views/dia)
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                    <div className="grid-2">
                      <div className="card">
                        <h4>Fase 3: Autopsia Anti-Plagio (Package + 0-30s + Comentarios)</h4>
                        <input className="input" placeholder="ID do video outlier (ex: xyz12345678)" value={reVidId} onChange={(e) => setReVidId(e.target.value)} style={{ marginBottom: 6 }} />
                        <input className="input" placeholder="Titulo viral analisado" value={reVidTitle} onChange={(e) => setReVidTitle(e.target.value)} style={{ marginBottom: 6 }} />
                        <textarea className="input" rows={3} placeholder="Transcricao ou notas 0-15s / 15-30s / meio..." value={reTranscript} onChange={(e) => setReTranscript(e.target.value)} style={{ marginBottom: 6 }} />
                        <textarea className="input" rows={2} placeholder="Comentarios (1 por linha) para minerar lacunas..." value={reComments} onChange={(e) => setReComments(e.target.value)} style={{ marginBottom: 6 }} />
                        <button
                          type="button"
                          className="btn primary"
                          onClick={async () => {
                            if (!session?.access_token || !reVidTitle.trim()) return;
                            await api.runPhase3Autopsy(session.access_token, activeWorkspaceId, {
                              channel_id: activeChannelId,
                              external_video_id: reVidId || "manual_outlier",
                              title: reVidTitle,
                              transcript_or_notes: reTranscript,
                              comments: reComments.split("\n").map((s) => s.trim()).filter(Boolean),
                            });
                            const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                            setReState(st);
                          }}
                        >
                          Executar Autopsia
                        </button>
                      </div>
                      <div className="card">
                        <h4>Fase 4: Mecanismo Transferivel &amp; Lote de Teste</h4>
                        <input className="input" placeholder="Seu tema validado (ex: Vila Romana Submersa)" value={reOwnTopic} onChange={(e) => setReOwnTopic(e.target.value)} style={{ marginBottom: 6 }} />
                        <input className="input" placeholder="Novo angulo / lacuna preenchida..." value={reNewAngle} onChange={(e) => setReNewAngle(e.target.value)} style={{ marginBottom: 6 }} />
                        <button
                          type="button"
                          className="btn primary"
                          onClick={async () => {
                            if (!session?.access_token || !reOwnTopic.trim() || !reNewAngle.trim()) return;
                            await api.runPhase4Synthesize(session.access_token, activeWorkspaceId, {
                              channel_id: activeChannelId,
                              own_validated_topic: reOwnTopic,
                              new_angle: reNewAngle,
                              target_format: "long",
                            });
                            const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                            setReState(st);
                          }}
                        >
                          Gerar Mecanismo Transferivel (Anti-Plagio)
                        </button>
                        {reState && (
                          <div style={{ marginTop: 10 }}>
                            <p className="muted">
                              Autopsias: {reState.autopsies.length} | Mecanismos: {reState.mechanisms.length} | Lotes de Teste: {reState.batches.length}
                            </p>
                            <ul>
                              {reState.mechanisms.slice(0, 4).map((m) => (
                                <li key={m.id} style={{ marginBottom: 8 }}>
                                  <strong>{m.synthesized_title}</strong> ({m.formula_structure}) —{" "}
                                  <span className={`pill ${m.originality_blocked ? "warn" : "info"}`}>
                                    sim: {(m.originality_max_similarity * 100).toFixed(0)}%
                                  </span>
                                  <div className="muted">{m.synthesized_thumb_concept}</div>
                                  <button
                                    type="button"
                                    className="btn"
                                    style={{ marginTop: 4 }}
                                    onClick={async () => {
                                      if (!session?.access_token) return;
                                      await api.createExperimentBatch(session.access_token, activeWorkspaceId, {
                                        channel_id: activeChannelId,
                                        mechanism_id: m.id,
                                        title: m.synthesized_title,
                                      });
                                      const st = await api.getReverseEngineeringState(session.access_token, activeWorkspaceId, activeChannelId);
                                      setReState(st);
                                    }}
                                  >
                                    Criar Lote de Teste (Impressoes/CTR/Retencao 30s)
                                  </button>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </section>
            )}

            {section === "knowledge" && (
              <section className="card">
                <h2>Knowledge / RAG Studio (SP-06)</h2>
                <p className="muted">Curadoria L0–L3, chunking, embeddings versionados em pgvector e citacoes verificaveis. L0 nao entra por padrao no contexto.</p>
                {!activeWorkspaceId ? (
                  <p className="muted">Selecione um workspace.</p>
                ) : (
                  <div className="grid-2">
                    <div className="card">
                      <h3>Importar Copy / Documento</h3>
                      <div className="field">
                        <label htmlFor="kn-title">Titulo</label>
                        <input id="kn-title" className="input" value={knowTitle} onChange={(e) => setKnowTitle(e.target.value)} />
                      </div>
                      <div className="field">
                        <label htmlFor="kn-body">Conteudo (tratado como dado nao confiavel)</label>
                        <textarea id="kn-body" className="input" rows={4} value={knowContent} onChange={(e) => setKnowContent(e.target.value)} />
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        <button
                          type="button"
                          className="btn primary"
                          onClick={async () => {
                            if (!session?.access_token) return;
                            await api.importKnowledgeSource(session.access_token, activeWorkspaceId, {
                              title: knowTitle,
                              source_type: "script",
                              content_text: knowContent,
                              rights_status: "owned",
                              collection_name: "default",
                            });
                            setKnowTitle("");
                            setKnowContent("");
                            const list = await api.listKnowledgeSources(session.access_token, activeWorkspaceId);
                            setKnowSources(list.items);
                          }}
                        >
                          Importar (L0)
                        </button>
                        <button
                          type="button"
                          className="btn"
                          onClick={async () => {
                            if (!session?.access_token) return;
                            const list = await api.listKnowledgeSources(session.access_token, activeWorkspaceId);
                            setKnowSources(list.items);
                          }}
                        >
                          Listar Fontes
                        </button>
                        <button
                          type="button"
                          className="btn"
                          onClick={async () => {
                            if (!session?.access_token) return;
                            const r = await api.reindexKnowledge(session.access_token, activeWorkspaceId, false);
                            setNotice({ kind: "info", code: "RAG_REINDEXED", message: `Indexados ${r.indexed_sources} fontes (${r.total_chunks} chunks).` });
                          }}
                        >
                          Indexar Aprovados
                        </button>
                      </div>
                      <ul style={{ marginTop: 10 }}>
                        {knowSources.map((s) => (
                          <li key={s.id} style={{ marginBottom: 6 }}>
                            <strong>{s.title}</strong> [{s.curation_level} / {s.status}]
                            <button
                              type="button"
                              className="btn"
                              style={{ marginLeft: 6 }}
                              onClick={async () => {
                                if (!session?.access_token) return;
                                await api.reviewKnowledgeSource(session.access_token, activeWorkspaceId, s.id, {
                                  curation_level: "L2",
                                  status: "APPROVED",
                                });
                                const list = await api.listKnowledgeSources(session.access_token, activeWorkspaceId);
                                setKnowSources(list.items);
                              }}
                            >
                              Aprovar L2
                            </button>
                            <button
                              type="button"
                              className="btn"
                              style={{ marginLeft: 6 }}
                              onClick={async () => {
                                if (!session?.access_token) return;
                                await api.deleteKnowledgeSource(session.access_token, activeWorkspaceId, s.id, false);
                                const list = await api.listKnowledgeSources(session.access_token, activeWorkspaceId);
                                setKnowSources(list.items);
                              }}
                            >
                              Arquivar
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="card">
                      <h3>Busca Hibrida &amp; Citacoes (FTS + pgvector)</h3>
                      <div className="field">
                        <label htmlFor="kn-q">Consulta</label>
                        <input id="kn-q" className="input" value={knowQuery} onChange={(e) => setKnowQuery(e.target.value)} />
                      </div>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !knowQuery.trim()) return;
                          const res = await api.searchKnowledge(session.access_token, activeWorkspaceId, knowQuery);
                          setKnowHits(res.chunks);
                        }}
                      >
                        Buscar Contexto Citavel (L2/L3)
                      </button>
                      {knowHits.length === 0 ? (
                        <p className="muted">Nenhum chunk recuperado ainda.</p>
                      ) : (
                        <ul>
                          {knowHits.map((h) => (
                            <li key={h.chunk_id}>
                              <strong>{h.source_title}</strong> ({h.curation_level}, score {h.hybrid_score.toFixed(2)}): {h.chunk_text}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </section>
            )}

            {section === "opportunities" && (
              <section className="card">
                <h2>Opportunity Engine (SP-07)</h2>
                {!activeWorkspaceId || !activeChannelId ? (
                  <p className="muted">Selecione workspace e canal para gerar oportunidades.</p>
                ) : (
                  <div>
                    <div className="field-row" style={{ gap: 8, marginBottom: 12 }}>
                      <input
                        className="input"
                        style={{ flex: "1 1 280px" }}
                        aria-label="Tema ou hipotese do episodio"
                        placeholder="Tema / hipotese do episodio..."
                        value={oppTopic}
                        onChange={(e) => setOppTopic(e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn primary"
                        onClick={async () => {
                          if (!session?.access_token || !oppTopic.trim()) return;
                          await api.generateOpportunities(session.access_token, activeWorkspaceId, {
                            channel_id: activeChannelId,
                            topic_hint: oppTopic,
                            target_format: "long",
                          });
                          const res = await api.listOpportunities(session.access_token, activeWorkspaceId, activeChannelId);
                          setOpps(res.items);
                        }}
                      >
                        Gerar Oportunidade
                      </button>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          const res = await api.listOpportunities(session.access_token, activeWorkspaceId, activeChannelId);
                          setOpps(res.items);
                        }}
                      >
                        Atualizar
                      </button>
                    </div>
                    {opps.length === 0 ? (
                      <p className="muted">Nenhuma oportunidade gerada ainda.</p>
                    ) : (
                      <ul>
                        {opps.map((o) => (
                          <li key={o.id} style={{ marginBottom: 10 }}>
                            <strong>{o.theme}</strong> — <span className="pill info">{o.status}</span> Score {(o.score * 100).toFixed(0)}% ({o.score_version}) | Confianca {(o.confidence * 100).toFixed(0)}%
                            {o.insufficient_data && <span className="pill warn" style={{ marginLeft: 6 }}>DADOS INSUFICIENTES</span>}
                            <div className="muted">{o.angle}</div>
                            <div style={{ display: "inline-flex", gap: 6, marginTop: 4 }}>
                              <button
                                type="button"
                                className="btn"
                                onClick={async () => {
                                  if (!session?.access_token) return;
                                  await api.reviewOpportunity(session.access_token, activeWorkspaceId, o.id, { decision: "APPROVE", notes: "Aprovada na UI" });
                                  const res = await api.listOpportunities(session.access_token, activeWorkspaceId, activeChannelId);
                                  setOpps(res.items);
                                }}
                              >
                                Aprovar
                              </button>
                              <button
                                type="button"
                                className="btn"
                                onClick={async () => {
                                  if (!session?.access_token) return;
                                  await api.createBrief(session.access_token, activeWorkspaceId, {
                                    opportunity_id: o.id,
                                    title: o.theme,
                                    hook: `Por que ${o.theme} falha e como corrigir.`,
                                    angle: o.angle,
                                    cta: "Inscreva-se para o proximo episodio.",
                                  });
                                  const b = await api.listBriefs(session.access_token, activeWorkspaceId);
                                  setBriefs(b.items);
                                  setSection("briefs");
                                }}
                              >
                                Criar EpisodeBrief
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </section>
            )}

            {section === "briefs" && (
              <section className="card">
                <h2>EpisodeBriefs &amp; Versionamento (SP-07)</h2>
                <button
                  type="button"
                  className="btn"
                  style={{ marginBottom: 12 }}
                  onClick={async () => {
                    if (!session?.access_token || !activeWorkspaceId) return;
                    const res = await api.listBriefs(session.access_token, activeWorkspaceId);
                    setBriefs(res.items);
                  }}
                >
                  Carregar Briefs
                </button>
                {briefs.length === 0 ? (
                  <p className="muted">Nenhum EpisodeBrief criado ainda.</p>
                ) : (
                  <ul>
                    {briefs.map((b) => (
                      <li key={b.id} style={{ marginBottom: 10 }}>
                        <strong>{b.title}</strong> (v{b.version}) — <span className="pill info">{b.status}</span>
                        <div className="muted">SHA: {b.content_sha256.slice(0, 12)}... | Hook: {b.hook}</div>
                        <div style={{ display: "inline-flex", gap: 6, marginTop: 4 }}>
                          {b.status === "DRAFT" && (
                            <button
                              type="button"
                              className="btn primary"
                              onClick={async () => {
                                if (!session?.access_token) return;
                                await api.approveBrief(session.access_token, activeWorkspaceId, b.id);
                                const res = await api.listBriefs(session.access_token, activeWorkspaceId);
                                setBriefs(res.items);
                              }}
                            >
                              Aprovar &amp; Congelar
                            </button>
                          )}
                          <button
                            type="button"
                            className="btn"
                            onClick={async () => {
                              if (!session?.access_token) return;
                              await api.createBriefVersion(session.access_token, activeWorkspaceId, b.id, `${b.title} (rev)`);
                              const res = await api.listBriefs(session.access_token, activeWorkspaceId);
                              setBriefs(res.items);
                            }}
                          >
                            Nova Versao
                          </button>
                          <button
                            type="button"
                            className="btn"
                            onClick={async () => {
                              if (!session?.access_token) return;
                              const ex = await api.exportBrief(session.access_token, activeWorkspaceId, b.id, "markdown");
                              setBriefExportText(ex.content);
                            }}
                          >
                            Exportar MD
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {briefExportText && (
                  <pre style={{ marginTop: 12, padding: 12, overflow: "auto", maxHeight: 240 }}>{briefExportText}</pre>
                )}
              </section>
            )}

            {section === "calendar" && (
              <section className="card">
                <h2>Calendario Editorial Manual (SP-07)</h2>
                <p className="muted">Planejamento manual apenas; auto-publicacao no YouTube permanece desabilitada (EDIT-005).</p>
                {activeWorkspaceId && activeChannelId && (
                  <div className="field-row" style={{ gap: 8, marginBottom: 12 }}>
                    <input placeholder="Titulo planejado..." value={calTitle} onChange={(e) => setCalTitle(e.target.value)} />
                    <input type="date" value={calDate} onChange={(e) => setCalDate(e.target.value)} />
                    <button
                      type="button"
                      className="btn primary"
                      onClick={async () => {
                        if (!session?.access_token || !calTitle.trim()) return;
                        await api.createCalendarItem(session.access_token, activeWorkspaceId, {
                          channel_id: activeChannelId,
                          title: calTitle,
                          scheduled_for: calDate,
                        });
                        const res = await api.listCalendar(session.access_token, activeWorkspaceId);
                        setCalItems(res.items);
                        setCalTitle("");
                      }}
                    >
                      Agendar Manualmente
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={async () => {
                        if (!session?.access_token) return;
                        const res = await api.listCalendar(session.access_token, activeWorkspaceId);
                        setCalItems(res.items);
                      }}
                    >
                      Atualizar
                    </button>
                  </div>
                )}
                {calItems.length === 0 ? (
                  <p className="muted">Nenhum item no calendario editorial.</p>
                ) : (
                  <ul>
                    {calItems.map((c) => (
                      <li key={c.id}>
                        <strong>{c.scheduled_for}</strong> — {c.title} ({c.status}, auto_publish={String(c.auto_publish_enabled)})
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}

            {section === "production" && (
              <section className="card">
                <h2>Producao DarkForge (SP-08 Single-Writer)</h2>
                {!activeWorkspaceId ? (
                  <p className="muted">Selecione um workspace primeiro.</p>
                ) : (
                  <div>
                    <div className="field-row" style={{ gap: 8, marginBottom: 12 }}>
                      <button
                        type="button"
                        className="btn"
                        onClick={async () => {
                          if (!session?.access_token) return;
                          const [h, i, b] = await Promise.all([
                            api.getProductionHealth(session.access_token, activeWorkspaceId),
                            api.listProductionIntents(session.access_token, activeWorkspaceId),
                            api.listBriefs(session.access_token, activeWorkspaceId),
                          ]);
                          setProdHealth(h);
                          setProdIntents(i.items);
                          setBriefs(b.items);
                        }}
                      >
                        Verificar Nucleo DarkForge &amp; Intencoes
                      </button>
                    </div>
                    {prodHealth && (
                      <div className={`notice ${prodHealth.available ? "info" : "warn"}`} style={{ marginBottom: 12 }}>
                        <strong>Gateway DarkForge:</strong> {prodHealth.mode} {prodHealth.reason ? `— ${prodHealth.reason}` : ""}
                      </div>
                    )}
                    <h3>Briefs Aprovados prontos para Intencao de Producao</h3>
                    <ul>
                      {briefs
                        .filter((b) => b.status === "APPROVED")
                        .map((b) => (
                          <li key={b.id} style={{ marginBottom: 6 }}>
                            {b.title} (v{b.version}){" "}
                            <button
                              type="button"
                              className="btn primary"
                              onClick={async () => {
                                if (!session?.access_token) return;
                                try {
                                  await api.createProductionIntent(session.access_token, activeWorkspaceId, b.id, `prod-${b.id}-v${b.version}`);
                                  const i = await api.listProductionIntents(session.access_token, activeWorkspaceId);
                                  setProdIntents(i.items);
                                } catch (err) {
                                  setNotice(mapErrorToNotice(err));
                                }
                              }}
                            >
                              Criar Intencao Idempotente
                            </button>
                          </li>
                        ))}
                    </ul>
                    <h3>Intencoes de Producao ({prodIntents.length})</h3>
                    {prodIntents.length === 0 ? (
                      <p className="muted">Nenhuma intencao de producao criada ainda.</p>
                    ) : (
                      <ul>
                        {prodIntents.map((pi) => (
                          <li key={pi.id} style={{ marginBottom: 8 }}>
                            Brief {pi.brief_id.slice(0, 8)} (v{pi.brief_version}) — <span className="pill info">{pi.status}</span> manifest_validated={String(pi.manifest_validated)}
                            {pi.error_code && <span className="muted"> | {pi.error_code}: {pi.error_message}</span>}
                            <button
                              type="button"
                              className="btn"
                              style={{ marginLeft: 8 }}
                              onClick={async () => {
                                if (!session?.access_token) return;
                                try {
                                  await api.dispatchProductionIntent(session.access_token, activeWorkspaceId, pi.id);
                                } catch (err) {
                                  setNotice(mapErrorToNotice(err));
                                } finally {
                                  const i = await api.listProductionIntents(session.access_token, activeWorkspaceId);
                                  setProdIntents(i.items);
                                }
                              }}
                            >
                              Despachar para Executor
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </section>
            )}

            {section === "settings" && (
              <section className="card">
                <h2>Configuracoes &amp; Conexoes</h2>
                <p><strong>Usuario autenticado:</strong> {session.user.email ?? session.user.id}</p>
                <h3>Conexoes YouTube OAuth ({connections.length})</h3>
                {connections.length === 0 ? (
                  <p className="muted">Nenhuma conexao YouTube cadastrada neste workspace.</p>
                ) : (
                  <ul>
                    {connections.map((c) => (
                      <li key={c.id} style={{ marginBottom: 8 }}>
                        Canal {c.channel_id} — <span className="pill info">{c.status}</span> (escopos: {c.scopes.join(", ")})
                        <div style={{ display: "inline-flex", gap: 6, marginLeft: 8 }}>
                          <button
                            type="button"
                            className="btn"
                            onClick={async () => {
                              if (!session?.access_token || !activeWorkspaceId) return;
                              await api.disconnectConnection(session.access_token, activeWorkspaceId, c.id, "keep_readonly");
                              await loadAnalytics(session.access_token, activeWorkspaceId, activeChannelId || undefined);
                            }}
                          >
                            Desconectar (Manter historico)
                          </button>
                          <button
                            type="button"
                            className="btn"
                            onClick={async () => {
                              if (!session?.access_token || !activeWorkspaceId) return;
                              await api.disconnectConnection(session.access_token, activeWorkspaceId, c.id, "purge_synced_data");
                              await loadAnalytics(session.access_token, activeWorkspaceId, activeChannelId || undefined);
                            }}
                          >
                            Desconectar e Apagar Dados
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="muted">Nenhuma chave privilegiada de servidor e enviada ou armazenada no navegador.</p>
                {activeWorkspaceId && (
                  <div style={{ marginTop: 12 }}>
                    <button
                      type="button"
                      className="btn"
                      onClick={async () => {
                        if (!session?.access_token) return;
                        const d = await api.exportDiagnostics(session.access_token, activeWorkspaceId);
                        setDiagBundle(JSON.stringify(d, null, 2));
                      }}
                    >
                      Exportar Diagnostico com Redaction (JOB-007)
                    </button>
                    {diagBundle && (
                      <pre style={{ marginTop: 8, padding: 12, overflow: "auto", maxHeight: 220 }}>{diagBundle}</pre>
                    )}
                  </div>
                )}
              </section>
            )}

            {section === "reports" && (
              <section className="card" aria-label="Central de Relatorios e Auditoria">
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10, alignItems: "center", marginBottom: 12 }}>
                  <div>
                    <h2 style={{ margin: 0 }}>Relatorios &amp; Central de Inteligencia (SP-24 / SP-25)</h2>
                    <p className="muted" style={{ margin: "4px 0 0" }}>
                      Visao consolidada de Fases 1-4, YouTube Studio Trends, Google Trends (12m/5a/Breakout), Oportunidades dos 4 Analistas e Briefs.
                    </p>
                  </div>
                  <div className="no-print" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <button
                      type="button"
                      className="btn"
                      disabled={!activeWorkspaceId || reportsLoading}
                      onClick={() => session?.access_token && activeWorkspaceId && loadReportsOverview(session.access_token, activeWorkspaceId, activeChannelId || undefined)}
                    >
                      {reportsLoading ? "Atualizando..." : "Atualizar Relatorios"}
                    </button>
                    <button
                      type="button"
                      className="btn primary"
                      disabled={!activeWorkspaceId}
                      onClick={async () => {
                        if (!session?.access_token || !activeWorkspaceId) return;
                        try {
                          const md = await api.exportExecutiveMarkdown(session.access_token, activeWorkspaceId, activeChannelId || undefined);
                          setExecutiveMd(md);
                          const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
                          const dlUrl = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = dlUrl;
                          a.download = "relatorio-executivo-darkforge.md";
                          a.click();
                          URL.revokeObjectURL(dlUrl);
                        } catch (err) {
                          setNotice(mapErrorToNotice(err));
                        }
                      }}
                    >
                      Baixar Relatorio (.md)
                    </button>
                    <button type="button" className="btn" onClick={() => window.print()}>
                      Imprimir / PDF
                    </button>
                  </div>
                </div>

                {!activeWorkspaceId ? (
                  <p className="muted">Selecione ou crie um workspace para visualizar os relatorios reais.</p>
                ) : !reportsOverview ? (
                  <p className="muted">{reportsLoading ? "Carregando relatorios do workspace..." : "Clique em Atualizar Relatorios para consultar os dados."}</p>
                ) : (
                  <>
                    <div className="kpi-grid">
                      <div className="kpi-card">
                        <div className="muted">Fase 1: Canais</div>
                        <div className="kpi-value">{reportsOverview.summary.phase1_selected_count}/{reportsOverview.summary.phase1_audits_total}</div>
                        <div className="muted">Meta: 5-10 aprovados</div>
                      </div>
                      <div className="kpi-card">
                        <div className="muted">Fase 2: Outliers</div>
                        <div className="kpi-value">{reportsOverview.summary.phase2_valid_outliers}</div>
                        <div className="muted">de {reportsOverview.summary.phase2_outliers_total} analisados</div>
                      </div>
                      <div className="kpi-card">
                        <div className="muted">Fase 3 &amp; 4</div>
                        <div className="kpi-value">{reportsOverview.summary.phase3_autopsies_count} / {reportsOverview.summary.phase4_mechanisms_count}</div>
                        <div className="muted">Autopsias / Mecanismos</div>
                      </div>
                      <div className="kpi-card">
                        <div className="muted">Google Trends GO</div>
                        <div className="kpi-value">{reportsOverview.summary.google_trends_sustainable_count}/{reportsOverview.summary.google_trends_count}</div>
                        <div className="muted">SUSTAINABLE_GO</div>
                      </div>
                      <div className="kpi-card">
                        <div className="muted">Studio Trends</div>
                        <div className="kpi-value">{reportsOverview.summary.studio_terms_count} / {reportsOverview.summary.studio_outliers_count}</div>
                        <div className="muted">Buscas / Outliers</div>
                      </div>
                      <div className="kpi-card">
                        <div className="muted">Oportunidades &amp; Briefs</div>
                        <div className="kpi-value">{reportsOverview.summary.opportunities_count} / {reportsOverview.summary.briefs_count}</div>
                        <div className="muted">{reportsOverview.summary.briefs_approved_count} briefs aprovados</div>
                      </div>
                    </div>

                    <div className="tabs-inline no-print" role="tablist" aria-label="Secoes do relatorio">
                      {([
                        ["overview", "Resumo Executivo"],
                        ["channels_outliers", "Canais & Outliers (F1-F2)"],
                        ["autopsies_mechanisms", "Autopsias & Mecanismos (F3-F4)"],
                        ["trends_studio", "Google Trends & Studio"],
                        ["opportunities_score", "Oportunidades & 4 Analistas"],
                      ] as [ReportsTab, string][]).map(([tabId, tabLabel]) => (
                        <button
                          key={tabId}
                          type="button"
                          role="tab"
                          aria-selected={reportsTab === tabId}
                          className="tab-btn"
                          onClick={() => setReportsTab(tabId)}
                        >
                          {tabLabel}
                        </button>
                      ))}
                    </div>

                    {reportsTab === "overview" && (
                      <div className="grid-2">
                        <div className="card">
                          <h3>Canais &amp; Dados Sincronizados (Supabase)</h3>
                          <ul>
                            {reportsOverview.channels.map((ch) => {
                              const pa = reportsOverview.portfolio_analytics?.channels?.find((p) => p.channel_id === ch.id);
                              return (
                                <li key={ch.id} style={{ marginBottom: 6 }}>
                                  <strong>{ch.display_name}</strong>{" "}
                                  {ch.external_channel_id && <code>[{ch.external_channel_id}]</code>}{" "}
                                  <span className="pill ok">{ch.status}</span>
                                  {pa && (pa.video_count > 0 || pa.metrics.length > 0) && (
                                    <div className="muted">
                                      Videos: {pa.video_count} |{" "}
                                      {pa.metrics.map((m) => `${m.display_name}: ${m.value_num}`).join(" · ")}
                                    </div>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                          {reportsOverview.channel_videos && reportsOverview.channel_videos.length > 0 && (
                            <div style={{ marginTop: 10 }}>
                              <h4>Videos Sincronizados do Canal Ativo</h4>
                              <ul>
                                {reportsOverview.channel_videos.map((v) => (
                                  <li key={v.id}>
                                    <strong>{v.title}</strong> (<code>{v.external_video_id}</code>)
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          <h4 style={{ marginTop: 10 }}>Saude do Funil &amp; Calendario</h4>
                          <ul>
                            <li>Canais configurados: <strong>{reportsOverview.summary.channels_count}</strong></li>
                            <li>Lotes de Teste (Impressoes / CTR / Retencao 30s): <strong>{reportsOverview.summary.experiment_batches_count}</strong></li>
                            <li>Coletas YouTube Studio Trends: <strong>{reportsOverview.summary.studio_runs_count}</strong></li>
                            <li>Itens no Calendario Editorial: <strong>{reportsOverview.summary.calendar_items_count}</strong></li>
                          </ul>
                          {reportsOverview.diagnostics && (
                            <div style={{ marginTop: 10 }}>
                              <h4>Diagnostico Sanitizado (Zero Segredos)</h4>
                              <p className="muted">
                                Redaction aplicado: <strong>{String(reportsOverview.diagnostics.redaction_applied)}</strong> | Jobs recentes: {reportsOverview.diagnostics.jobs_recent.length}
                              </p>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                {Object.entries(reportsOverview.diagnostics.environment_flags).map(([k, v]) => (
                                  <span key={k} className={`pill ${v ? "ok" : "warn"}`}>{k}: {v ? "ON" : "OFF"}</span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="card">
                          <h3>Preview Relatorio Executivo (.md)</h3>
                          {!executiveMd ? (
                            <button
                              type="button"
                              className="btn"
                              onClick={async () => {
                                if (!session?.access_token) return;
                                const md = await api.exportExecutiveMarkdown(session.access_token, activeWorkspaceId, activeChannelId || undefined);
                                setExecutiveMd(md);
                              }}
                            >
                              Gerar Preview Markdown Agora
                            </button>
                          ) : (
                            <pre className="report-preview">{executiveMd}</pre>
                          )}
                        </div>
                      </div>
                    )}

                    {reportsTab === "channels_outliers" && (
                      <div>
                        <h3>Fase 1 — Auditoria de Canais de Referencia (6 Criterios)</h3>
                        {reportsOverview.reverse_engineering.audits.length === 0 ? (
                          <p className="muted">Nenhum canal avaliado na Fase 1 ainda (use Pesquisa &gt; Laboratorio 4 Fases).</p>
                        ) : (
                          <div className="table-wrap">
                            <table className="data-table">
                              <thead>
                                <tr>
                                  <th>Canal</th>
                                  <th>Status</th>
                                  <th>Media 20-30</th>
                                  <th>Hits Outlier</th>
                                  <th>Max Ratio</th>
                                  <th>Score</th>
                                  <th>Falhas / Alertas</th>
                                </tr>
                              </thead>
                              <tbody>
                                {reportsOverview.reverse_engineering.audits.map((a) => (
                                  <tr key={a.id}>
                                    <td><strong>{a.display_name}</strong></td>
                                    <td><span className={`pill ${a.approved ? "ok" : "warn"}`}>{a.approved ? "APROVADO" : "DESCARTADO"}</span></td>
                                    <td>{Math.round(a.channel_mean_views).toLocaleString("pt-BR")}</td>
                                    <td>{a.outlier_hits_count}</td>
                                    <td>{a.max_outlier_ratio}x</td>
                                    <td>{a.ranking_score.toFixed(2)}</td>
                                    <td>{(a.failed_criteria_json || []).concat(a.warnings_json || []).join(" | ") || "-"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        <h3 style={{ marginTop: 16 }}>Fase 2 — Outliers Priorizados &amp; Velocidade (Views/Dia)</h3>
                        {reportsOverview.reverse_engineering.viral_outliers.length === 0 ? (
                          <p className="muted">Nenhum video outlier processado na Fase 2 ainda.</p>
                        ) : (
                          <div className="table-wrap">
                            <table className="data-table">
                              <thead>
                                <tr>
                                  <th>Video</th>
                                  <th>Canal</th>
                                  <th>Views</th>
                                  <th>Views/Dia</th>
                                  <th>Outlier</th>
                                  <th>Padrao</th>
                                  <th>Classificacao</th>
                                </tr>
                              </thead>
                              <tbody>
                                {reportsOverview.reverse_engineering.viral_outliers.map((o) => (
                                  <tr key={o.id}>
                                    <td><strong>{o.title}</strong></td>
                                    <td>{o.channel_name}</td>
                                    <td>{o.views.toLocaleString("pt-BR")} ({o.days_since_upload}d)</td>
                                    <td><strong>{Math.round(o.views_per_day).toLocaleString("pt-BR")}</strong></td>
                                    <td>{o.outlier_ratio}x</td>
                                    <td><code>{o.pattern_key}</code></td>
                                    <td>
                                      <span className={`pill ${o.is_false_positive ? "err" : o.confirmed_multi_channel ? "ok" : "info"}`}>
                                        {o.is_false_positive ? "FALSO POSITIVO" : o.confirmed_multi_channel ? "MULTI-CANAL" : "OUTLIER"}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}

                    {reportsTab === "autopsies_mechanisms" && (
                      <div className="grid-2">
                        <div className="card">
                          <h3>Fase 3 — Autopsias (Package, 0-30s e Comentarios)</h3>
                          {reportsOverview.reverse_engineering.autopsies.length === 0 ? (
                            <p className="muted">Nenhuma autopsia executada ainda.</p>
                          ) : (
                            <ul>
                              {reportsOverview.reverse_engineering.autopsies.map((au) => (
                                <li key={au.id} style={{ marginBottom: 10 }}>
                                  <strong>{au.original_title}</strong> — <span className="pill info">{au.narrative_archetype}</span>
                                  {au.package_json?.central_tension && <div className="muted">Tensao: {au.package_json.central_tension}</div>}
                                  {au.script_retention_json?.hook_0_15s && <div className="muted">Hook 0-15s: {au.script_retention_json.hook_0_15s}</div>}
                                  {au.comment_gaps_json?.viewer_questions?.length ? (
                                    <div className="muted">Lacunas: {au.comment_gaps_json.viewer_questions.join("; ")}</div>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                        <div className="card">
                          <h3>Fase 4 — Mecanismos Transferiveis &amp; Lotes de Teste</h3>
                          {reportsOverview.reverse_engineering.mechanisms.length === 0 ? (
                            <p className="muted">Nenhum mecanismo sintetizado ainda.</p>
                          ) : (
                            <ul>
                              {reportsOverview.reverse_engineering.mechanisms.map((m) => (
                                <li key={m.id} style={{ marginBottom: 10 }}>
                                  <strong>{m.synthesized_title}</strong>
                                  <div>
                                    <span className={`pill ${m.originality_blocked ? "warn" : "ok"}`}>
                                      Similaridade {(m.originality_max_similarity * 100).toFixed(0)}% {m.originality_blocked ? "(REESCREVER)" : "(ORIGINAL)"}
                                    </span>
                                  </div>
                                  <div className="muted">
                                    Formula: {m.formula_theme} + {m.formula_angle} + {m.formula_emotion} + {m.formula_structure}
                                  </div>
                                  <div className="muted">Conceito de capa: {m.synthesized_thumb_concept}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    )}

                    {reportsTab === "trends_studio" && (
                      <div className="grid-2">
                        <div className="card">
                          <h3>Google Trends (12m / 5 anos / Breakout)</h3>
                          {reportsOverview.google_trends.length === 0 ? (
                            <p className="muted">Nenhuma validacao Google Trends ainda.</p>
                          ) : (
                            <ul>
                              {reportsOverview.google_trends.map((g) => (
                                <li key={g.id} style={{ marginBottom: 10 }}>
                                  <strong>{g.keyword}</strong> ({g.geo}/{g.gprop || "web"}) —{" "}
                                  <span className={`pill ${g.verdict === "SUSTAINABLE_GO" ? "ok" : g.verdict === "AVOID_DEAD_PEAK" ? "err" : "warn"}`}>{g.verdict}</span>
                                  <div className="muted">12m: {g.direction_12m} | 5a: {g.durability_5y} | Breakout: {g.breakout_queries_json.length}</div>
                                  <div className="muted">{g.summary}</div>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                        <div className="card">
                          <h3>YouTube Studio Trends (Buscas, Gaps &amp; Outliers)</h3>
                          {reportsOverview.studio_trends.terms.length === 0 && reportsOverview.studio_trends.outliers.length === 0 ? (
                            <p className="muted">Nenhum termo ou outlier capturado do YouTube Studio ainda.</p>
                          ) : (
                            <>
                              <ul>
                                {reportsOverview.studio_trends.terms.slice(0, 10).map((t) => (
                                  <li key={t.id}>
                                    <strong>{t.term}</strong> [{t.audience_interest}] {t.is_hypothesis ? "(Content Gap - Hipotese)" : ""}
                                  </li>
                                ))}
                              </ul>
                              {reportsOverview.studio_trends.outliers.length > 0 && (
                                <ul>
                                  {reportsOverview.studio_trends.outliers.slice(0, 10).map((so) => (
                                    <li key={so.id}>
                                      <strong>{so.title}</strong> — {so.outlier_ratio ?? "?"}x ({so.outlier_tier})
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    )}

                    {reportsTab === "opportunities_score" && (
                      <div>
                        <h3>Oportunidades Ranqueadas, Score Breakdown &amp; Parecer dos 4 Analistas</h3>
                        {reportsOverview.opportunities.length === 0 ? (
                          <p className="muted">Nenhuma oportunidade gerada ainda.</p>
                        ) : (
                          reportsOverview.opportunities.map((opp) => (
                            <article key={opp.id} className="card" style={{ marginBottom: 12 }}>
                              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                                <strong>{opp.theme}</strong>
                                <span>
                                  <span className="pill info">{opp.status}</span>{" "}
                                  <span className="pill ok">Score {(opp.score * 100).toFixed(0)}% ({opp.score_version})</span>{" "}
                                  <span className="pill">Confianca {(opp.confidence * 100).toFixed(0)}%</span>
                                </span>
                              </div>
                              <p className="muted" style={{ margin: "6px 0" }}>Angulo: {opp.angle} | Diferenciacao: {opp.differentiation}</p>
                              <div className="muted" style={{ marginBottom: 8 }}>
                                Breakdown: {Object.entries(opp.score_breakdown_json || {}).map(([k, v]) => `${k}=${v}`).join(" | ")}
                              </div>
                              {opp.analyst_reports_json?.length > 0 && (
                                <div className="grid-2">
                                  {opp.analyst_reports_json.map((ar) => (
                                    <div key={ar.analyst} className="analyst-card">
                                      <strong>{ar.analyst}</strong>{" "}
                                      <span className="pill">{ar.data_freshness}</span>{" "}
                                      <span className="muted">conf {(ar.confidence * 100).toFixed(0)}%</span>
                                      <ul style={{ margin: "6px 0" }}>
                                        {ar.findings.map((f, idx) => <li key={idx}>{f}</li>)}
                                      </ul>
                                      {ar.recommendations.length > 0 && (
                                        <div className="muted">Rec: {ar.recommendations.join(" | ")}</div>
                                      )}
                                      {ar.limitations.length > 0 && (
                                        <div className="muted">Limitacoes: {ar.limitations.join(" | ")}</div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </article>
                          ))
                        )}
                      </div>
                    )}
                  </>
                )}
              </section>
            )}

            {!["studio", "dashboard", "reports", "channels", "analytics", "research", "opportunities", "briefs", "calendar", "knowledge", "production", "jobs", "settings"].includes(section) && (
              <section className="card">
                <h2>{NAV_ITEMS.find((i) => i.id === section)?.label}</h2>
                <p className="muted">
                  Modulo planejado para {NAV_ITEMS.find((i) => i.id === section)?.phase}. Nenhuma metrica ou dado ficticio e exibido antes do gate correspondente.
                </p>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
