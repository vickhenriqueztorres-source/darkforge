from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from core.errors import AppError, ErrorCode
from core.generation.title_thumbnail import (
    TitleThumbnailService,
    analyze_title_structure,
    check_originality,
    generate_original_title_alternatives,
    validate_safe_external_url,
)
from core.research.service import compute_channel_similarity
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from tests.unit.test_sp01_workspace_and_channels import InMemoryWorkspaceRepo
from core.workspaces.service import WorkspaceService

ROOT = Path(__file__).resolve().parents[2]


def test_title_thumbnail_golden_dataset_cases() -> None:
    ds_path = ROOT / "tests" / "evaluation" / "datasets" / "title_thumbnail_golden.jsonl"
    cases = [json.loads(line) for line in ds_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_id = {c["case_id"]: c for c in cases}

    # TT-001: Title structural analysis
    c1 = by_id["TT-001"]
    res1 = analyze_title_structure(c1["input"]["title"])
    for feat in c1["expected"]["features"]:
        assert feat in res1["features"]
    assert "nao comprova causalidade de CTR" in res1["limitations"][0]

    # TT-002: Literal/near copy flagged and blocked
    c2 = by_id["TT-002"]
    res2 = check_originality(c2["input"]["candidate_title"], [c2["input"]["reference_title"]])
    assert res2["similarity_flagged"] is True
    assert res2["approval_blocked"] is True
    assert res2["error_code"] == c2["expected"]["error_code"]

    # TT-004: Unsupported promise flagged
    c4 = by_id["TT-004"]
    res4 = check_originality(c4["input"]["candidate_title"], [])
    assert res4["approval_blocked"] is True
    assert "garantido" in res4["unverified_promise_hits"]


def test_vision_unavailable_never_invents_ocr_and_ssrf_blocked() -> None:
    with pytest.raises(AppError) as ssrf_exc:
        validate_safe_external_url("http://169.254.169.254/latest/meta-data/")
    assert ssrf_exc.value.code == ErrorCode.WORKSPACE_FORBIDDEN

    with pytest.raises(AppError) as local_exc:
        validate_safe_external_url("http://127.0.0.1:8080/internal.png")
    assert local_exc.value.code == ErrorCode.WORKSPACE_FORBIDDEN

    class FakeRepo:
        def upsert_thumbnail_asset(self, **kw): return {"id": uuid4(), **kw}
        def save_thumbnail_analysis(self, **kw): return {"id": uuid4(), **kw}

    ws_repo = InMemoryWorkspaceRepo()
    ws_svc = WorkspaceService(ws_repo)
    actor = AuthenticatedUser(user_id=uuid4())
    ws, _ = ws_svc.create_workspace(actor, "WS Intel", "ws-intel")
    svc = TitleThumbnailService(ws_svc, FakeRepo(), vision_provider=None)

    res = svc.analyze_thumbnail(actor, ws.id, "https://i.ytimg.com/vi/abc123/hqdefault.jpg")
    assert res["vision_status"] == "unavailable"
    assert res["ocr_text"] is None


def test_explainable_similarity_and_original_title_alternatives() -> None:
    sim = compute_channel_similarity(
        channel_niche="documentario historia antiga",
        channel_pillars=["egito", "piramides", "arqueologia"],
        channel_language="pt-BR",
        candidate_title_corpus="Segredos da Arqueologia no Egito e Piramides",
        candidate_language="pt",
    )
    assert sim.score > 50
    assert "egito" in sim.factors["matched_terms"]
    assert "nao mede audiencia privada" in sim.factors["limitation"]

    alts = generate_original_title_alternatives(
        channel_name="Outrora",
        niche="Historia",
        topic="Construcao de Gize",
        reference_titles=["Como Construiram as Piramides"],
        forbidden_topics=["alienigenas"],
    )
    assert len(alts) == 3
    assert all(not a["originality"]["approval_blocked"] for a in alts)

    with pytest.raises(AppError):
        generate_original_title_alternatives(
            channel_name="Outrora",
            niche="Historia",
            topic="Alienigenas em Gize",
            reference_titles=[],
            forbidden_topics=["alienigenas"],
        )
