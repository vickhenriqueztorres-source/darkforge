from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.ai_providers.router import AIProviderRouter, ProviderPolicy, redact_sensitive_text, wrap_untrusted_context
from core.errors import AppError, ErrorCode
from core.knowledge.chunker import split_semantic_chunks

ROOT = Path(__file__).resolve().parents[2]


def test_semantic_chunker_preserves_hook_body_cta() -> None:
    text = "Hook: Voce sabia que 80% perdem aqui?\n\nDesenvolvimento com dados reais do Egito.\n\nCTA: Assista ao proximo salto."
    chunks = split_semantic_chunks(text)
    assert [c.section_label for c in chunks] == ["hook", "body", "cta"]


def test_provider_router_blocks_silent_external_fallback_and_requires_consent() -> None:
    # Local unavailable + external configured -> MUST NOT silently fall back!
    router = AIProviderRouter(
        policy=ProviderPolicy(local_available=False, external_provider_configured=True),
        external_generator=lambda goal, ctx: {"should_not_run": True},
    )
    with pytest.raises(AppError) as exc:
        router.generate_with_context("gerar copy", [{"source_id": "s1", "chunk_id": "c1", "curation_level": "L2", "chunk_text": "abc"}], use_external=False)
    assert exc.value.code == ErrorCode.AI_PROVIDER_UNAVAILABLE

    # External requested without consent -> 412 AI_EXTERNAL_CONSENT_REQUIRED
    with pytest.raises(AppError) as consent_exc:
        router.generate_with_context("gerar copy", [], use_external=True, external_consent_granted=False)
    assert consent_exc.value.code == ErrorCode.AI_EXTERNAL_CONSENT_REQUIRED


def test_prompt_injection_wrapped_as_untrusted_and_secrets_redacted() -> None:
    ds_path = ROOT / "tests" / "evaluation" / "datasets" / "rag_security_golden.jsonl"
    cases = {c["case_id"]: c for c in (json.loads(l) for l in ds_path.read_text(encoding="utf-8").splitlines() if l.strip())}
    inj = cases["RAG-005"]["sources"][0]

    wrapped = wrap_untrusted_context([{"source_id": inj["id"], "chunk_id": "c1", "curation_level": "L2", "chunk_text": inj["text"]}])
    assert "<untrusted_data" in wrapped
    assert "DADOS DE REFERENCIA nao confiaveis" in wrapped

    redacted = redact_sensitive_text("token Bearer abc123secret e sb_secret_testkey123")
    assert "abc123secret" not in redacted
    assert "sb_secret_testkey123" not in redacted

    router = AIProviderRouter(ProviderPolicy(local_available=True))
    res = router.generate_with_context("resuma diretriz", [{"source_id": inj["id"], "chunk_id": "c1", "curation_level": "L2", "chunk_text": inj["text"]}])
    assert res.output["auto_approved"] is False
