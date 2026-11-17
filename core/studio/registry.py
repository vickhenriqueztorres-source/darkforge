from __future__ import annotations

from dataclasses import dataclass

from core.errors import AppError, ErrorCode
from core.studio.contracts import (
    ChannelInsightPayload,
    OpportunityPayload,
    ProductionStatusPayload,
    PublicationPlanPayload,
    ResearchFindingsPayload,
    ScriptDraftPayload,
    StrictContractModel,
    ThumbnailConceptsPayload,
    TitleOptionsPayload,
)


@dataclass(frozen=True)
class AgentSpec:
    key: str
    display_name: str
    room_key: str
    output_type: str
    contract_version: int
    requires_approval: bool
    responsibility: str
    payload_model: type[StrictContractModel]
    depends_on_agents: tuple[str, ...]
    next_agents: tuple[str, ...]
    source_optional: bool = False


AGENT_REGISTRY: dict[str, AgentSpec] = {
    "dados": AgentSpec(
        key="dados",
        display_name="Analista de Dados",
        room_key="sala_dados",
        output_type="channel_insight",
        contract_version=1,
        requires_approval=False,
        responsibility="interpretar as métricas sincronizadas do canal no período e apontar mudanças relevantes com evidência",
        payload_model=ChannelInsightPayload,
        depends_on_agents=(),
        next_agents=("estrategia",),
    ),
    "pesquisa": AgentSpec(
        key="pesquisa",
        display_name="Pesquisador",
        room_key="pesquisa",
        output_type="research_findings",
        contract_version=1,
        requires_approval=False,
        responsibility="avaliar referências públicas aprovadas e dizer se o tema tem evidência suficiente",
        payload_model=ResearchFindingsPayload,
        depends_on_agents=(),
        next_agents=("estrategia",),
    ),
    "estrategia": AgentSpec(
        key="estrategia",
        display_name="Estrategista",
        room_key="mesa_agentes",
        output_type="opportunity",
        contract_version=1,
        requires_approval=True,
        responsibility="propor uma oportunidade de vídeo com ângulo, diferenciação, score explicado e limitações",
        payload_model=OpportunityPayload,
        depends_on_agents=("dados", "pesquisa"),
        next_agents=("titulos", "roteiro", "thumbnail"),
    ),
    "titulos": AgentSpec(
        key="titulos",
        display_name="Especialista Títulos",
        room_key="mesa_agentes",
        output_type="title_options",
        contract_version=1,
        requires_approval=False,
        responsibility="propor de 5 a 10 títulos originais, explicando padrão e diferenciação de cada um",
        payload_model=TitleOptionsPayload,
        depends_on_agents=("estrategia",),
        next_agents=("edicao",),
    ),
    "roteiro": AgentSpec(
        key="roteiro",
        display_name="Roteirista",
        room_key="mesa_agentes",
        output_type="script_draft",
        contract_version=1,
        requires_approval=False,
        responsibility="escrever hook, outline e rascunho de roteiro coerentes com a voz do canal",
        payload_model=ScriptDraftPayload,
        depends_on_agents=("estrategia",),
        next_agents=("edicao",),
    ),
    "thumbnail": AgentSpec(
        key="thumbnail",
        display_name="Designer de Capa",
        room_key="design_thumbnail",
        output_type="thumbnail_concepts",
        contract_version=1,
        requires_approval=False,
        responsibility="propor de 3 a 5 conceitos de capa originais, com composição e texto de sobreposição",
        payload_model=ThumbnailConceptsPayload,
        depends_on_agents=("estrategia",),
        next_agents=("edicao",),
    ),
    "edicao": AgentSpec(
        key="edicao",
        display_name="Produção",
        room_key="gravacao",
        output_type="production_status",
        contract_version=1,
        requires_approval=False,
        responsibility="resumir o estado real da produção e os checks de qualidade, sem estimar progresso inexistente",
        payload_model=ProductionStatusPayload,
        depends_on_agents=("titulos", "roteiro", "thumbnail"),
        next_agents=("publicacao",),
        source_optional=True,
    ),
    "publicacao": AgentSpec(
        key="publicacao",
        display_name="Publicação",
        room_key="estrategia_publicacao",
        output_type="publication_plan",
        contract_version=1,
        requires_approval=True,
        responsibility="montar plano de publicação para aprovação humana, com data, título escolhido, descrição e tags",
        payload_model=PublicationPlanPayload,
        depends_on_agents=("edicao",),
        next_agents=(),
    ),
}

PIPELINE_ORDER: tuple[str, ...] = (
    "dados",
    "pesquisa",
    "estrategia",
    "titulos",
    "roteiro",
    "thumbnail",
    "edicao",
    "publicacao",
)

STUDIO_ROOM_KEYS: tuple[str, ...] = (
    "sala_dados",
    "pesquisa",
    "mesa_agentes",
    "gravacao",
    "design_thumbnail",
    "estrategia_publicacao",
)

# Transicoes validas de stage para content_items (UI-01-T03)
ALLOWED_STAGE_TRANSITIONS: dict[str, set[str]] = {
    "ideia": {"pesquisa", "estrategia", "arquivado"},
    "pesquisa": {"estrategia", "arquivado"},
    "estrategia": {"roteiro", "design", "arquivado"},
    "roteiro": {"design", "producao", "arquivado"},
    "design": {"producao", "arquivado"},
    "producao": {"publicacao", "arquivado"},
    "publicacao": {"publicado_manual", "arquivado"},
    "publicado_manual": {"arquivado"},
    "arquivado": set(),
}


def get_agent_spec(agent_key: str) -> AgentSpec:
    spec = AGENT_REGISTRY.get(agent_key)
    if spec is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Agente desconhecido: {agent_key}.",
            http_status=422,
            details={"field": "agent_key"},
        )
    return spec


def assert_stage_transition(current_stage: str, target_stage: str) -> None:
    if current_stage == target_stage:
        return
    allowed = ALLOWED_STAGE_TRANSITIONS.get(current_stage)
    if allowed is None or target_stage not in allowed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Transicao de estagio invalida: {current_stage} -> {target_stage}.",
            http_status=422,
            details={"current_stage": current_stage, "target_stage": target_stage},
        )
