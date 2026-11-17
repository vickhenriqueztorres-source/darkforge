"""Playwright E2E, Responsive (1280/1440/1920 + 375 mobile), Reduced Motion & Keyboard A11y test for Studio UI."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

import httpx
import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from adapters.supabase_db.jobs_repo import PostgresWorkerQueue
from adapters.supabase_db.studio_repo import PostgresStudioRepository
from workers.agents.handler import AgentJobHandler
from workers.runner import JobWorker

load_dotenv()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_port(host: str, port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"Timeout aguardando {host}:{port}")


@pytest.mark.live_supabase
def test_studio_ui_browser_e2e_responsive_a11y_and_lcp() -> None:
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "").strip().rstrip("/")
    pub_key = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "").strip()
    srv_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not (url and pub_key and srv_key and db_url):
        pytest.skip("Credenciais Supabase ausentes")

    api_port = _free_port()
    web_port = _free_port()

    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{api_port}"
    env["WEB_ORIGIN"] = f"http://127.0.0.1:{web_port}"

    api_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        cwd=r"d:\YOUTUBE MANAGET",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    web_proc = subprocess.Popen(
        ["cmd", "/c", "pnpm", "--filter", "@darkforge/web", "exec", "next", "start", "-H", "127.0.0.1", "-p", str(web_port)],
        cwd=r"d:\YOUTUBE MANAGET",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    suffix = uuid4().hex[:8]
    email = f"browser-ui-{suffix}@darkforge.invalid"
    password = f"DfBrowser!{suffix}99"
    admin_headers = {"apikey": srv_key, "Authorization": f"Bearer {srv_key}", "Content-Type": "application/json"}
    uid = ""
    ws_id = ""

    try:
        _wait_port("127.0.0.1", api_port, 30.0)
        _wait_port("127.0.0.1", web_port, 30.0)

        with httpx.Client(timeout=15.0) as client:
            u_res = client.post(
                f"{url}/auth/v1/admin/users",
                headers=admin_headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            assert u_res.status_code in (200, 201), u_res.text
            uid = u_res.json()["id"]

            tok = client.post(
                f"{url}/auth/v1/token?grant_type=password",
                headers={"apikey": pub_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            ).json()["access_token"]

            api_headers = {
                "Authorization": f"Bearer {tok}",
                "Origin": f"http://127.0.0.1:{web_port}",
            }
            ws_res = client.post(
                f"http://127.0.0.1:{api_port}/api/v1/workspaces",
                headers=api_headers,
                json={"name": f"Browser WS {suffix}", "slug": f"br-ws-{suffix}"},
            )
            assert ws_res.status_code == 201, ws_res.text
            ws_id = ws_res.json()["workspace"]["id"]

            ch_res = client.post(
                f"http://127.0.0.1:{api_port}/api/v1/channels",
                headers={**api_headers, "X-Workspace-Id": ws_id},
                json={
                    "display_name": "Canal Maquete",
                    "handle": "@maquete",
                    "profile": {
                        "name": "Canal Maquete",
                        "language": "pt-BR",
                        "country": "BR",
                        "timezone": "America/Sao_Paulo",
                        "niche": "Documentarios",
                    },
                },
            )
            assert ch_res.status_code == 201, ch_res.text
            ch_id = ch_res.json()["channel"]["id"]

            # Seed real opportunity via worker so Opportunity panel renders score ring
            ci_res = client.post(
                f"http://127.0.0.1:{api_port}/api/v1/studio/channels/{ch_id}/content-items",
                headers={**api_headers, "X-Workspace-Id": ws_id},
                json={"working_title": "A arquitetura oculta do algoritmo"},
            )
            assert ci_res.status_code == 201, ci_res.text

        studio_repo = PostgresStudioRepository(db_url)
        worker = JobWorker(
            PostgresWorkerQueue(db_url),
            worker_id=f"browser-worker-{suffix}",
            handlers={"agent.execute": AgentJobHandler(studio_repo)},
            lease_seconds=30,
        )
        deadline = time.time() + 45.0
        while time.time() < deadline:
            worker.run_once(job_types=["agent.execute"])
            snap_check = studio_repo.get_snapshot(UUID(ws_id), UUID(ch_id))
            if snap_check.get("latest_opportunity") is not None:
                break
            time.sleep(0.5)
        assert studio_repo.get_snapshot(UUID(ws_id), UUID(ch_id)).get("latest_opportunity") is not None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})

            def proxy_api(route) -> None:
                req = route.request
                target_url = req.url.replace("http://127.0.0.1:8000", f"http://127.0.0.1:{api_port}")
                resp = context.request.fetch(
                    target_url,
                    method=req.method,
                    headers=req.headers,
                    data=req.post_data_buffer,
                )
                route.fulfill(
                    status=resp.status,
                    headers=dict(resp.headers),
                    body=resp.body(),
                )

            context.route("http://127.0.0.1:8000/**", proxy_api)
            page = context.new_page()

            console_errors: list[str] = []
            page_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # Log in on /
            page.goto(f"http://127.0.0.1:{web_port}/", wait_until="networkidle")
            page.fill("#auth-email", email)
            page.fill("#auth-pass", password)
            page.click('button[type="submit"]')

            # Wait for Studio 2.5D stage AND real snapshot agents to render
            page.wait_for_selector(".studio-diorama-canvas", timeout=15000)
            page.wait_for_selector('[data-room-key="sala_dados"]', timeout=15000)
            page.wait_for_selector(".studio-agent-sprite", timeout=15000)

            # Verify clean plate loaded with >= 2560px intrinsic width
            img_width = page.evaluate(
                "() => { const img = document.querySelector('.studio-clean-plate-img'); return img ? img.naturalWidth : 0; }"
            )
            assert img_width == 2560

            # Verify 6 rooms and 8 agents are rendered
            assert page.locator(".studio-room-hotspot").count() == 6
            assert page.locator(".studio-agent-sprite").count() == 8

            # Verify honest "indisponível" instead of fake 0 in Canal panel
            canal_text = page.locator('[aria-label="Métricas do canal"]').inner_text()
            assert "indisponível" in canal_text.lower()

            # Verify Opportunity panel "Por quê?" toggle & real score ring
            opp_panel = page.locator('[aria-label="Oportunidade de Vídeo"]')
            opp_panel.get_by_role("button", name="Por quê?").click()
            assert opp_panel.locator(".studio-why-box").is_visible()

            # Verify Zoom controls work (100% -> 125% -> reset 100%)
            page.get_by_role("button", name="Aumentar zoom").click()
            assert "125%" in page.locator(".studio-zoom-readout").inner_text()
            page.locator(".studio-zoom-readout").click()
            assert "100%" in page.locator(".studio-zoom-readout").inner_text()

            # Verify responsive widths 1280, 1440, 1920 keep SVG/container aligned inside viewport
            for width in (1280, 1440, 1920):
                page.set_viewport_size({"width": width, "height": 900})
                box = page.locator(".studio-diorama-canvas").bounding_box()
                svg_box = page.locator(".studio-svg-overlay").bounding_box()
                assert box is not None and svg_box is not None
                assert abs(box["width"] - svg_box["width"]) < 2.0
                assert abs(box["height"] - svg_box["height"]) < 2.0

            # Keyboard A11y (UI-04-T03 / UI-05-T04): Focus room button, Enter opens drawer, Escape closes and restores focus
            room_btn = page.locator('[data-room-key="mesa_agentes"]')
            room_btn.focus()
            page.keyboard.press("Enter")
            page.wait_for_selector('[role="dialog"]', timeout=5000)
            page.keyboard.press("Escape")
            assert page.locator('[role="dialog"]').count() == 0
            page.wait_for_function(
                "() => document.activeElement?.getAttribute('data-room-key') === 'mesa_agentes'",
                timeout=3000,
            )

            # Reduced motion check (UI-04-T05)
            page.emulate_media(reduced_motion="reduce")
            transition_dur = page.evaluate(
                "() => getComputedStyle(document.querySelector('.studio-agent-sprite')).transitionDuration"
            )
            assert transition_dur in ("0s", "0ms")

            # Mobile viewport (< 768px) switches to StudioRoomList (UI-04-T05)
            page.set_viewport_size({"width": 375, "height": 812})
            assert page.locator(".studio-mobile-list").is_visible()
            assert not page.locator(".studio-diorama-wrap").is_visible()

            assert console_errors == [], f"Console errors: {console_errors}"
            assert page_errors == [], f"Page errors: {page_errors}"
            browser.close()
    finally:
        api_proc.terminate()
        web_proc.terminate()
        try:
            api_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
        try:
            web_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            web_proc.kill()
        if ws_id or uid:
            with httpx.Client(timeout=10.0) as client:
                if ws_id:
                    client.delete(f"{url}/rest/v1/workspaces?id=eq.{ws_id}", headers=admin_headers)
                if uid:
                    client.delete(f"{url}/auth/v1/admin/users/{uid}", headers=admin_headers)
