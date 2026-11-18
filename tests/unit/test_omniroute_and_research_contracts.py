from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from adapters.ai_providers.omniroute import OmniRouteClient, extract_json_object
from core.errors import AppError
from core.studio.contracts import validate_agent_output_envelope


def test_extract_json_object_handles_fences_and_prose() -> None:
    assert extract_json_object('{"ok": true}') == {"ok": True}
    assert extract_json_object("```json\n{\"items\": [1, 2]}\n```") == {"items": [1, 2]}
    assert extract_json_object("Aqui esta:\n{\"a\": \"b\"}\nFim.") == {"a": "b"}
    with pytest.raises(ValueError):
        extract_json_object("sem json aqui")


def test_omniroute_client_chat_json_and_errors() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path.endswith("/chat/completions")
        assert req.headers["Authorization"] == "Bearer test-key"
        body = json.loads(req.content)
        if body["model"] == "fail-model":
            return httpx.Response(503, text="upstream down")
        return httpx.Response(
            200,
            json={
                "model": "if/glm-4.7",
                "choices": [{"message": {"content": "```json\n{\"hello\": \"world\"}\n```"}}],
            },
        )

    client = OmniRouteClient(
        base_url="http://127.0.0.1:20128/v1",
        api_key="test-key",
        default_model="auto/best-fast",
        http_transport=httpx.MockTransport(handler),
    )
    data, used = client.chat_json("sys", "usr")
    assert data == {"hello": "world"}
    assert used == "if/glm-4.7"

    with pytest.raises(AppError):
        client.chat_json("sys", "usr", model="fail-model")


def test_research_findings_contract_supports_episode_suggestions_and_legacy() -> None:
    ch_id = uuid4()
    legacy = {
        "agent_key": "pesquisa",
        "contract_version": 1,
        "channel_id": str(ch_id),
        "content_item_id": None,
        "summary": "Tema validado (2 referencias)",
        "confidence": "media",
        "limitations": [],
        "sources": [],
        "payload": {
            "question": "Tem demanda?",
            "candidates": [],
            "topic_validation": {"topic": "Infraestrutura", "status": "validado", "reason": "ok"},
        },
    }
    _, parsed_legacy = validate_agent_output_envelope(
        legacy,
        expected_agent_key="pesquisa",
        expected_output_type="research_findings",
        expected_channel_id=ch_id,
        expected_content_item_id=None,
    )
    assert parsed_legacy.episode_suggestions == []  # type: ignore[attr-defined]

    with_eps = {
        **legacy,
        "payload": {
            **legacy["payload"],
            "episode_suggestions": [
                {
                    "title": "Como Dois Tatuzoes Escavam o Metro de Sao Paulo?",
                    "alternative_title": "O Anel de Concreto Que Segura 2.600 Toneladas no Subsolo",
                    "theme": "Dois tatuzoes da Linha 2-Verde",
                    "angle": "Solucao de engenharia contraintuitiva: escavacao e revestimento simultaneos",
                    "thumbnail_structure": {
                        "hero_object": "Corte esquematico sob a Penha com roda de corte do tatuzao em 4K",
                        "shock_text": "DOIS TATUZÕES",
                        "visual_composition": "Fundo Carbon Black #060709, seta Sodium Orange #FF5500, medidor 2.600t em #00FF66",
                    },
                    "opening_hook": "0-15s: mapa das duas frentes na Penha e anel de concreto travando o solo.",
                    "why_now": "Obra em andamento com 14,5K views no comparavel e ligacao direta com o subsolo de SP.",
                    "reference_ids": ["ref-1"],
                }
            ],
        },
    }
    _, parsed_eps = validate_agent_output_envelope(
        with_eps,
        expected_agent_key="pesquisa",
        expected_output_type="research_findings",
        expected_channel_id=ch_id,
        expected_content_item_id=None,
    )
    assert len(parsed_eps.episode_suggestions) == 1  # type: ignore[attr-defined]
    assert parsed_eps.episode_suggestions[0].thumbnail_structure.shock_text == "DOIS TATUZÕES"  # type: ignore[attr-defined]
