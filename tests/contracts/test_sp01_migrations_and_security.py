from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sp01_migrations_rls_and_security_definer_hardening() -> None:
    m1 = (ROOT / "migrations" / "0001_sp01_workspace_auth_channels.sql").read_text(encoding="utf-8")
    m2 = (ROOT / "migrations" / "0002_sp01_rls_and_security.sql").read_text(encoding="utf-8")
    m3 = (ROOT / "migrations" / "0003_sp01_public_rpc_create_workspace.sql").read_text(encoding="utf-8")

    expected_tables = [
        "workspaces",
        "workspace_members",
        "channels",
        "channel_profile_versions",
        "editorial_theme_changes",
        "audit_events",
    ]
    for tbl in expected_tables:
        assert f"CREATE TABLE IF NOT EXISTS public.{tbl}" in m1
        assert f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;" in m2
        assert f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;" in m2
        assert f"REVOKE ALL ON public.{tbl} FROM PUBLIC, anon;" in m2

    # Every SECURITY DEFINER function must set a fixed search_path
    sec_def_blocks = re.findall(
        r"CREATE OR REPLACE FUNCTION\s+([^\s(]+).*?SECURITY DEFINER(.*?)\$\$",
        m2 + "\n" + m3,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert len(sec_def_blocks) >= 4
    for fn_name, header in sec_def_blocks:
        assert "SET search_path = pg_catalog, public" in header, f"{fn_name} missing fixed search_path"

    # Historical profile versions and theme changes must forbid UPDATE/DELETE
    assert "trg_profile_versions_immutable" in m1
    assert "trg_theme_changes_immutable" in m1
    assert "trg_audit_events_immutable" in m1


def test_sp02_migrations_rls_and_worker_rpc_security() -> None:
    m4 = (ROOT / "migrations" / "0004_sp02_jobs_outbox_storage.sql").read_text(encoding="utf-8")
    for tbl in (
        "jobs",
        "job_attempts",
        "job_events",
        "outbox_events",
        "inbox_events",
        "idempotent_effects",
        "storage_objects",
        "artifacts",
    ):
        assert f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;" in m4
        assert f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;" in m4
        assert f"REVOKE ALL ON public.{tbl} FROM PUBLIC, anon;" in m4

    # Worker queue RPCs must be revoked from authenticated/anon/PUBLIC
    for fn in (
        "app.claim_next_job",
        "app.heartbeat_job",
        "app.checkpoint_job",
        "app.transition_job_with_fencing",
        "app.reconcile_expired_leases",
    ):
        assert f"REVOKE ALL ON FUNCTION {fn}" in m4
        assert "FROM PUBLIC, authenticated, anon;" in m4

    sec_defs = re.findall(
        r"CREATE OR REPLACE FUNCTION\s+([^\s(]+).*?SECURITY DEFINER(.*?)\$\$",
        m4,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert len(sec_defs) >= 5
    for fn_name, header in sec_defs:
        assert "SET search_path = pg_catalog, public" in header, f"{fn_name} missing fixed search_path"


def test_sp03_migrations_rls_and_secret_table_lockdown() -> None:
    m5 = (ROOT / "migrations" / "0005_sp03_youtube_analytics.sql").read_text(encoding="utf-8")
    for tbl in (
        "oauth_states",
        "platform_connections",
        "platform_connection_secrets",
        "videos",
        "playlists",
        "metric_definitions",
        "metric_snapshots",
        "sync_cursors",
        "quota_ledger",
    ):
        assert f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;" in m5
        assert f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;" in m5

    assert "REVOKE ALL ON public.platform_connection_secrets FROM PUBLIC, anon, authenticated;" in m5
    assert "REVOKE ALL ON public.oauth_states FROM PUBLIC, anon, authenticated;" in m5
    assert "chk_unavailable_has_null_value" in m5


def test_sp04_sp05_migrations_rls() -> None:
    m7 = (ROOT / "migrations" / "0007_sp04_sp05_research_title_thumb.sql").read_text(encoding="utf-8")
    for tbl in (
        "research_runs",
        "reference_channels",
        "reference_videos",
        "title_analyses",
        "thumbnail_assets",
        "thumbnail_analyses",
    ):
        assert f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;" in m7
        assert f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;" in m7
        assert f"REVOKE ALL ON public.{tbl} FROM PUBLIC, anon;" in m7


def test_sp06_migrations_rls() -> None:
    m8 = (ROOT / "migrations" / "0008_sp06_knowledge_rag.sql").read_text(encoding="utf-8")
    for tbl in (
        "knowledge_sources",
        "knowledge_chunks",
        "embedding_revisions",
        "knowledge_embeddings",
        "retrieval_runs",
        "generations",
    ):
        assert f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;" in m8
        assert f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;" in m8
        assert f"REVOKE ALL ON public.{tbl} FROM PUBLIC, anon;" in m8


def test_sp07_migrations_rls() -> None:
    m9 = (ROOT / "migrations" / "0009_sp07_opportunities_briefs_calendar.sql").read_text(encoding="utf-8")
    for tbl in (
        "opportunities",
        "evidence_links",
        "opportunity_feedback",
        "episode_briefs",
        "brief_decision_history",
        "editorial_calendar_items",
    ):
        assert f"'{tbl}'" in m9
    assert "ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;" in m9
    assert "ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;" in m9
    assert "REVOKE ALL ON public.%I FROM PUBLIC, anon;" in m9
    assert "trg_episode_briefs_freeze" in m9
    assert "CHECK (auto_publish_enabled = false)" in m9


def test_sp08_migrations_rls() -> None:
    m10 = (ROOT / "migrations" / "0010_sp08_production_intents.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE public.production_intents ENABLE ROW LEVEL SECURITY;" in m10
    assert "ALTER TABLE public.production_intents FORCE ROW LEVEL SECURITY;" in m10
    assert "REVOKE ALL ON public.production_intents FROM PUBLIC, anon;" in m10
    assert "chk_ready_requires_validated_manifest" in m10


def test_web_has_no_privileged_secrets_or_ffmpeg() -> None:
    web_src = ROOT / "apps" / "web" / "src"
    forbidden = ["service_role", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "DATABASE_URL", "ffmpeg", "ffprobe"]
    for file in web_src.rglob("*"):
        if file.is_file():
            content = file.read_text(encoding="utf-8")
            for term in forbidden:
                assert term not in content, f"Forbidden token {term} found in {file}"


def test_core_has_no_framework_or_http_imports() -> None:
    core_dir = ROOT / "core"
    forbidden = ["import fastapi", "from fastapi", "import httpx", "from httpx", "import jwt", "from jwt", "playwright", "selenium"]
    for file in core_dir.rglob("*.py"):
        content = file.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in content, f"Boundary violation {term} in {file}"


def test_sp13_migrations_rls() -> None:
    m11 = (ROOT / "migrations" / "0011_sp13_studio_trends_and_outliers.sql").read_text(encoding="utf-8")
    for tbl in ("studio_trend_runs", "studio_search_terms", "studio_video_outliers"):
        assert f"'{tbl}'" in m11
    assert "ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;" in m11
    assert "ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;" in m11
    assert "REVOKE ALL ON public.%I FROM PUBLIC, anon;" in m11


def test_sp17_migrations_rls() -> None:
    m12 = (ROOT / "migrations" / "0012_sp15_google_trends.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE public.google_trends_validations ENABLE ROW LEVEL SECURITY;" in m12
    assert "ALTER TABLE public.google_trends_validations FORCE ROW LEVEL SECURITY;" in m12
    assert "REVOKE ALL ON public.google_trends_validations FROM PUBLIC, anon;" in m12


def test_sp22_migrations_rls() -> None:
    m13 = (ROOT / "migrations" / "0013_sp19_reverse_engineering_engine.sql").read_text(encoding="utf-8")
    for tbl in (
        "reference_channel_audits",
        "viral_outlier_snapshots",
        "video_autopsies",
        "transferable_mechanisms",
        "experiment_batches",
    ):
        assert f"'{tbl}'" in m13
    assert "ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;" in m13
    assert "ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;" in m13
    assert "REVOKE ALL ON public.%I FROM PUBLIC, anon;" in m13

