from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx

from adapters.ai_providers.omniroute import OmniRouteClient
from adapters.youtube.public_channel import PublicChannelCollector
from core.studio.contracts import validate_agent_output_envelope
from workers.agents.handler import (
    AgentJobHandler,
    default_local_agent_model_caller,
    resolve_research_queries,
    resolve_research_topic,
)


def test_resolve_research_topic_priority() -> None:
    ctx = {
        "channel": {
            "display_name": "O Outro Lado",
            "editorial_theme": "O Outro Lado",
            "niche": "Documentario & Investigacao",
            "pillars_json": ["o outro lado", "outliers", "retencao"],
        },
        "content_item": {"working_title": "Ilha Submersa"},
    }
    assert resolve_research_topic(ctx, "misterios oceanicos") == "misterios oceanicos"
    assert resolve_research_topic(ctx) == "Ilha Submersa"
    ctx_no_item = {**ctx, "content_item": None}
    assert resolve_research_topic(ctx_no_item) == "Documentario & Investigacao"

    ctx_hsl = {
        "channel": {
            "display_name": "O Outro Lado",
            "niche": "Engenharia, Infraestrutura e Sistemas Ocultos",
            "pillars_json": ["outliers", "engenharia e grandes obras", "infraestrutura oculta e energia"],
        },
        "content_item": None,
    }
    assert resolve_research_queries(ctx_hsl) == [
        "engenharia e grandes obras",
        "infraestrutura oculta e energia",
    ]


def test_default_caller_pesquisa_statuses_and_contract() -> None:
    ch_id = uuid4()
    base_ctx = {
        "channel": {
            "id": str(ch_id),
            "display_name": "O Outro Lado",
            "niche": "Documentario",
            "pillars_json": ["misterios"],
            "profile_version_id": str(uuid4()),
            "version_number": 1,
        },
        "content_item": None,
        "references": [],
        "studio_outliers": [],
        "google_trends": [],
    }

    # 0 refs -> sem_evidencia
    out_empty = default_local_agent_model_caller("p", base_ctx, {"agent_key": "pesquisa"})
    assert out_empty["payload"]["topic_validation"]["status"] == "sem_evidencia"
    validate_agent_output_envelope(
        out_empty,
        expected_agent_key="pesquisa",
        expected_output_type="research_findings",
        expected_channel_id=ch_id,
        expected_content_item_id=None,
    )

    # 1 ref -> fraco
    one_ctx = {
        **base_ctx,
        "references": [
            {
                "id": str(uuid4()),
                "canonical_url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                "title": "Caso Unico",
                "public_views_snapshot": 120000,
                "channel_name": "Canal X",
            }
        ],
    }
    out_weak = default_local_agent_model_caller("p", one_ctx, {"agent_key": "pesquisa"})
    assert out_weak["payload"]["topic_validation"]["status"] == "fraco"
    assert "120K views" in out_weak["payload"]["candidates"][0]["why_similar"]

    # 2+ refs -> validado
    two_ctx = {
        **base_ctx,
        "references": one_ctx["references"]
        + [
            {
                "id": str(uuid4()),
                "canonical_url": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
                "title": "Segundo Caso",
                "public_views_snapshot": 2500000,
                "outlier_ratio": 4.2,
                "channel_name": "Canal Y",
            }
        ],
    }
    out_ok = default_local_agent_model_caller("p", two_ctx, {"agent_key": "pesquisa"})
    assert out_ok["payload"]["topic_validation"]["status"] == "validado"
    assert "2.5M views" in out_ok["payload"]["candidates"][1]["why_similar"]
    assert "outlier 4.2x" in out_ok["payload"]["candidates"][1]["why_similar"]


class _FakeStudioRepo:
    def __init__(self, channel_id, workspace_id, actor_id):
        self.channel_id = channel_id
        self.workspace_id = workspace_id
        self.actor_id = actor_id
        self.saved_ids: list[str] = []
        self.committed: dict | None = None

    def mark_run_started(self, run_id, fencing_token):
        return {"id": str(run_id)}

    def update_run_progress(self, run_id, fencing_token, *, stage_label, progress, summary):
        return None

    def load_authorized_context(self, workspace_id, channel_id, agent_key, content_item_id):
        return {
            "channel": {
                "id": str(self.channel_id),
                "display_name": "O Outro Lado",
                "niche": "Documentario",
                "pillars_json": ["misterios"],
                "language": "pt-BR",
                "country": "BR",
                "external_channel_id": "UCf6Ox9rzQbIkDeE94to9AEQ",
                "created_by": str(self.actor_id),
                "profile_version_id": str(uuid4()),
                "version_number": 1,
            },
            "channel_agent": {"display_name": "Pesquisador", "model_policy": {"mode": "local_only", "external_consent": False}},
            "content_item": None,
            "handoffs": [],
            "prior_outputs": [],
            "metrics": [],
            "references": [],
            "studio_outliers": [],
            "google_trends": [],
            "knowledge_chunks": [],
            "production_intents": [],
            "calendar_items": [],
        }

    def save_discovered_research_references(self, *, workspace_id, channel_id, actor_id, run_id, topic, language, candidates):
        out = []
        for c in candidates:
            rid = str(uuid4())
            self.saved_ids.append(rid)
            out.append(
                {
                    "id": rid,
                    "external_video_id": c["video_id"],
                    "canonical_url": c["url"],
                    "title": c["title"],
                    "public_views_snapshot": c.get("views"),
                    "snapshot_observed_at": "2026-11-17T14:00:00Z",
                    "channel_name": c.get("channel_name"),
                    "outlier_ratio": c.get("outlier_ratio"),
                }
            )
        return out

    def verify_sources_in_scope(self, workspace_id, channel_id, sources):
        return sources, []

    def commit_agent_run_atomic(self, **kwargs):
        self.committed = kwargs
        return kwargs


def test_agent_job_handler_pesquisa_runs_live_collector_and_persists() -> None:
    ws_id, ch_id, actor_id, run_id, job_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    repo = _FakeStudioRepo(ch_id, ws_id, actor_id)

    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "VID11111111",
                                                "title": {"runs": [{"text": "Como Escavam o Subsolo"}]},
                                                "ownerText": {"runs": [{"text": "Canal Docs", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCf6Ox9rzQbIkDeE94to9AEQ"}}}]},
                                                "viewCountText": {"simpleText": "150.000 visualizações"},
                                                "lengthText": {"simpleText": "12:00"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "VID33333333",
                                                "title": {"runs": [{"text": "Serial Killer Case"}]},
                                                "ownerText": {"runs": [{"text": "True Crime"}]},
                                                "viewCountText": {"simpleText": "900.000 visualizações"},
                                                "lengthText": {"simpleText": "20:00"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "VID22222222",
                                                "title": {"runs": [{"text": "Engenharia de Tuneis"}]},
                                                "ownerText": {"runs": [{"text": "Canal Docs", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCf6Ox9rzQbIkDeE94to9AEQ"}}}]},
                                                "viewCountText": {"simpleText": "320.000 visualizações"},
                                                "lengthText": {"simpleText": "18:30"},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    # Inject forbidden_topics via repo.load_authorized_context monkeypatch
    orig_load = repo.load_authorized_context

    def load_with_restrictions(*args, **kwargs):
        ctx = orig_load(*args, **kwargs)
        ctx["channel"]["restrictions_json"] = {"forbidden_topics": ["serial killer"]}
        return ctx

    repo.load_authorized_context = load_with_restrictions  # type: ignore[method-assign]
    search_html = f"<html><script>var ytInitialData = {json.dumps(initial_data)};</script></html>"

    def transport(req: httpx.Request) -> httpx.Response:
        if "youtube.com/results" in str(req.url):
            return httpx.Response(200, text=search_html)
        return httpx.Response(404)

    collector = PublicChannelCollector(api_key="", http_transport=httpx.MockTransport(transport))
    # Mesmo com OmniRoute configurado, modo local_only NAO pode chamar provedor externo (ADR-007)
    omni_calls = {"count": 0}

    def omni_should_not_run(req: httpx.Request) -> httpx.Response:
        omni_calls["count"] += 1
        return httpx.Response(500)

    omni = OmniRouteClient(api_key="test-key", http_transport=httpx.MockTransport(omni_should_not_run))
    handler = AgentJobHandler(repo, public_collector=collector, omniroute_client=omni)  # type: ignore[arg-type]

    job = SimpleNamespace(
        job_id=job_id,
        workspace_id=ws_id,
        channel_id=ch_id,
        fencing_token=1,
        payload_json={"run_id": str(run_id), "agent_key": "pesquisa", "channel_id": str(ch_id), "topic": "ilha submersa"},
    )
    ctx = SimpleNamespace(
        heartbeat=lambda: None,
        checkpoint=lambda *args, **kwargs: None,
    )
    handler(job, ctx)  # type: ignore[arg-type]

    assert omni_calls["count"] == 0
    assert repo.committed is not None
    assert repo.committed["provider"] == "local"
    assert repo.committed["output_status"] == "validated"
    cj = repo.committed["content_json"]
    assert cj["topic_validation"]["topic"] == "ilha submersa"
    assert cj["topic_validation"]["status"] == "validado"
    assert len(cj["candidates"]) == 2
    assert len(cj["episode_suggestions"]) >= 1
    assert len(repo.saved_ids) == 2


def test_agent_job_handler_pesquisa_uses_omniroute_when_consented_and_filters_noise() -> None:
    ws_id, ch_id, actor_id, run_id, job_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    repo = _FakeStudioRepo(ch_id, ws_id, actor_id)

    orig_load = repo.load_authorized_context

    def load_consented(*args, **kwargs):
        ctx = orig_load(*args, **kwargs)
        ctx["channel"]["positioning"] = "Documentarios investigativos faceless de engenharia e sistemas ocultos"
        ctx["channel_agent"]["model_policy"] = {"mode": "external_consented", "external_consent": True}
        ctx["knowledge_chunks"] = [
            {"chunk_id": str(uuid4()), "source_title": "Eng Reversa 2", "chunk_text": "Foco em engenharia contraintuitiva e escala."}
        ]
        return ctx

    repo.load_authorized_context = load_consented  # type: ignore[method-assign]

    initial_data = {
        "contents": {
            "twoColumnSearchResultsRenderer": {
                "primaryContents": {
                    "sectionListRenderer": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "contents": [
                                        {
                                            "videoRenderer": {
                                                "videoId": "VIDAAA11111",
                                                "title": {"runs": [{"text": "Como Escavam Dois Tatuzoes no Metro"}]},
                                                "ownerText": {"runs": [{"text": "Obra Decifrada"}]},
                                                "viewCountText": {"simpleText": "240.000 visualizações"},
                                                "lengthText": {"simpleText": "14:10"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "VIDNOISE111",
                                                "title": {"runs": [{"text": "Entrevista sobre obras | InsurCortes Podcast"}]},
                                                "ownerText": {"runs": [{"text": "InsurCortes"}]},
                                                "viewCountText": {"simpleText": "900.000 visualizações"},
                                                "lengthText": {"simpleText": "11:00"},
                                            }
                                        },
                                        {
                                            "videoRenderer": {
                                                "videoId": "VIDBBB22222",
                                                "title": {"runs": [{"text": "A Fabrica de Concreto no Mar"}]},
                                                "ownerText": {"runs": [{"text": "Efeito Geo"}]},
                                                "viewCountText": {"simpleText": "510.000 visualizações"},
                                                "lengthText": {"simpleText": "16:20"},
                                            }
                                        },
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    search_html = f"<html><script>var ytInitialData = {json.dumps(initial_data)};</script></html>"

    def yt_transport(req: httpx.Request) -> httpx.Response:
        if "youtube.com/results" in str(req.url):
            return httpx.Response(200, text=search_html)
        return httpx.Response(404)

    omni_step = {"n": 0}

    def omni_transport(req: httpx.Request) -> httpx.Response:
        omni_step["n"] += 1
        if omni_step["n"] == 1:
            return httpx.Response(
                200,
                json={"model": "if/glm-4.7", "choices": [{"message": {"content": json.dumps({"queries": ["tatuzoes metro engenharia", "fabrica concreto mar"]})}}]},
            )
        synth = {
            "summary": "2 refs validadas e 2 novos episodios",
            "confidence": "alta",
            "limitations": [],
            "question": "Demanda validada para grandes obras?",
            "topic_validation": {"topic": "Documentario", "status": "validado", "reason": "Forte tracao em obras subterraneas e maritimas."},
            "candidate_notes": [],
            "episode_suggestions": [
                {
                    "title": "Como Dois Tatuzoes Escavam o Subsolo de Sao Paulo ao Mesmo Tempo?",
                    "alternative_title": "O Anel de Concreto de 2.600 Toneladas Debaixo da Penha",
                    "theme": "Dois tatuzoes da Linha 2-Verde",
                    "angle": "Solucao de engenharia contraintuitiva: escavacao e revestimento simultaneo.",
                    "thumbnail_structure": {
                        "hero_object": "Corte esquematico sob a Penha com duas tuneladoras em direcoes opostas",
                        "shock_text": "DOIS TATUZÕES",
                        "visual_composition": "Carbon Black #060709, seta Sodium Orange #FF5500, medidor 2.600t em #00FF66",
                    },
                    "opening_hook": "0-15s: mapa das duas frentes na Penha + erro de previsao sobre como o solo nao desaba.",
                    "why_now": "Comparaveis entre 240K e 510K views no formato documental de engenharia.",
                    "reference_ids": ["id-inexistente-sera-filtrado"],
                }
            ],
        }
        return httpx.Response(
            200,
            json={"model": "if/glm-4.7", "choices": [{"message": {"content": json.dumps(synth)}}]},
        )

    collector = PublicChannelCollector(api_key="", http_transport=httpx.MockTransport(yt_transport))
    omni = OmniRouteClient(api_key="test-key", http_transport=httpx.MockTransport(omni_transport))
    handler = AgentJobHandler(repo, public_collector=collector, omniroute_client=omni)  # type: ignore[arg-type]

    job = SimpleNamespace(
        job_id=job_id,
        workspace_id=ws_id,
        channel_id=ch_id,
        fencing_token=1,
        payload_json={"run_id": str(run_id), "agent_key": "pesquisa", "channel_id": str(ch_id)},
    )
    ctx = SimpleNamespace(heartbeat=lambda: None, checkpoint=lambda *args, **kwargs: None)
    handler(job, ctx)  # type: ignore[arg-type]

    assert repo.committed is not None
    assert repo.committed["provider"] == "external"
    assert repo.committed["model_id"] == "if/glm-4.7"
    assert repo.committed["output_status"] == "validated"
    cj = repo.committed["content_json"]
    # InsurCortes podcast filtrado fora!
    assert len(cj["candidates"]) == 2
    assert len(cj["episode_suggestions"]) == 1
    assert cj["episode_suggestions"][0]["thumbnail_structure"]["shock_text"] == "DOIS TATUZÕES"
    # reference_ids invalido foi substituido por um reference_id real do banco
    assert cj["episode_suggestions"][0]["reference_ids"][0] in repo.saved_ids
