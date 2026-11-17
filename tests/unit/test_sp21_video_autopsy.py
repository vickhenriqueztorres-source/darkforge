from __future__ import annotations

import httpx

from adapters.youtube.client import OfficialYouTubeAdapter
from core.research.video_autopsy import (
    ALLOWED_TO_MODEL,
    FORBIDDEN_TO_COPY,
    run_full_video_autopsy,
)


def test_full_video_autopsy_package_0_30s_blocks_and_comment_gaps() -> None:
    transcript = (
        "Em apenas uma noite, toda a cidade desapareceu sem deixar nenhum rastro visivel. "
        "Mas o erro de engenharia no subsolo ja estava selando esse colapso semanas antes! "
        "No primeiro registro de arquivo, os sensores marcaram pressao anomala no mapa. "
        "Entretanto, ninguem fechou as comportas a tempo ate que a barragem rompeu."
    )
    comments = [
        "Faltou falar sobre qual foi o custo da reconstrucao depois!",
        "Como os engenheiros nao viram a rachadura antes?",
        "Faz parte 2 explicando o destino do prefeito!",
        "Otimo video gostei muito",
    ]
    report = run_full_video_autopsy(
        external_video_id="xyz98765432",
        title="A cidade que desapareceu em uma noite",
        transcript_or_notes=transcript,
        comments=comments,
        thumbnail_focus="Ruina inundada com holofote vermelho",
        thumbnail_visual_question="O que causou o colapso repentino?",
        thumbnail_emotion="misterio_choque",
        thumbnail_text="NINGUEM SAIU",
        first_visual_description="Mapa antigo rasgando sobre foto aerea do desastre",
    )
    assert report.package.allowed_to_model == ALLOWED_TO_MODEL
    assert report.package.forbidden_to_copy == FORBIDDEN_TO_COPY
    assert report.package.thumbnail_text_complements_title is True
    assert report.package.central_tension_or_risk == "perda_ameaca_ou_colapso"
    assert report.script_retention.hook_0_15s_confirms_promise_no_fluff is True
    assert report.script_retention.segment_15_30s_planted_risk_before_context is True
    assert report.script_retention.open_loops_count >= 1
    assert report.script_retention.visual_proofs_count >= 1
    assert len(report.comments.missing_detail_complaints) == 1
    assert len(report.comments.unanswered_questions) == 1
    assert len(report.comments.sequel_requests) == 1
    assert report.detected_narrative_archetype.startswith("documentario_climax_invertido")


def test_adapter_fetches_public_video_comments_via_mock_transport() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if "/commentThreads" in str(req.url):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "Faltou citar as fontes primarias!"}}}},
                        {"snippet": {"topLevelComment": {"snippet": {"textDisplay": "Faz parte 2 disso!"}}}},
                    ]
                },
            )
        return httpx.Response(404)

    yt = OfficialYouTubeAdapter("", "", http_transport=httpx.MockTransport(handler))
    comments, cost = yt.fetch_public_video_comments("xyz98765432", api_key="AIzaMock")
    assert len(comments) == 2
    assert cost == 1
