from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from fastapi import Depends, Header, Request

from adapters.ai_providers.router import AIProviderRouter
from adapters.darkforge.gateway import DarkForgeGateway
from adapters.google_trends.collector import GoogleTrendsPlaywrightCollector
from adapters.google_trends.csv_importer import parse_related_queries_csv, parse_timeline_csv
from adapters.studio_browser.session import StudioBrowserSessionManager, StudioSessionConfig
from adapters.studio_browser.trends_extractor import StudioTrendsExtractor
from adapters.supabase_auth.jwt_verifier import SupabaseJWTVerifier
from adapters.supabase_db.analytics_repo import PostgresAnalyticsRepository
from adapters.supabase_db.client import SupabaseRestClient
from adapters.supabase_db.editorial_repo import PostgresEditorialRepository
from adapters.supabase_db.google_trends_repo import PostgresGoogleTrendsRepository
from adapters.supabase_db.jobs_repo import PostgresStorageMetadataRepository, SupabaseJobRepository
from adapters.supabase_db.knowledge_repo import PostgresKnowledgeRepository
from adapters.supabase_db.production_repo import PostgresProductionRepository
from adapters.supabase_db.repositories import SupabaseChannelRepository, SupabaseWorkspaceRepository
from adapters.supabase_db.research_repo import PostgresResearchAndIntelRepository
from adapters.supabase_db.reverse_engineering_repo import PostgresReverseEngineeringRepository
from adapters.supabase_db.studio_repo import PostgresStudioRepository
from adapters.supabase_db.external_agents_repo import PostgresExternalAgentsRepository
from adapters.supabase_db.studio_trends_repo import PostgresStudioTrendsRepository
from adapters.supabase_storage.client import StorageService, SupabaseStorageClient
from adapters.youtube.client import OfficialYouTubeAdapter
from adapters.youtube.public_channel import get_shared_public_collector
from adapters.youtube.token_vault import TokenVault
from apps.api.config import Settings, get_settings
from core.analytics.service import AnalyticsService
from core.channels.service import ChannelService
from core.darkforge_gateway.service import ProductionIntentService
from core.editorial.service import EditorialStudioService
from core.errors import AppError, ErrorCode
from core.generation.title_thumbnail import TitleThumbnailService
from core.jobs.service import CommandBus
from core.knowledge.service import KnowledgeService
from core.opportunities.service import OpportunityService
from core.research.google_trends_service import GoogleTrendsService
from core.research.reverse_engineering_service import ReverseEngineeringService
from core.research.service import ResearchService
from core.research.studio_service import StudioTrendsService
from core.studio.service import StudioService
from core.studio.external_agents_service import ExternalAgentsService
from core.telemetry import TelemetryRecorder
from core.workspaces.models import AuthenticatedUser
from core.workspaces.service import WorkspaceService


@dataclass
class ServiceContainer:
    jwt_verifier: SupabaseJWTVerifier
    supabase_client: SupabaseRestClient
    workspaces: WorkspaceService
    channels: ChannelService
    command_bus: CommandBus
    storage_service: StorageService | None = None
    analytics: AnalyticsService | None = None
    research: ResearchService | None = None
    research_repo: PostgresResearchAndIntelRepository | None = None
    title_thumb: TitleThumbnailService | None = None
    knowledge: KnowledgeService | None = None
    knowledge_repo: PostgresKnowledgeRepository | None = None
    opportunities: OpportunityService | None = None
    editorial: EditorialStudioService | None = None
    editorial_repo: PostgresEditorialRepository | None = None
    production: ProductionIntentService | None = None
    production_repo: PostgresProductionRepository | None = None
    studio_trends: StudioTrendsService | None = None
    google_trends: GoogleTrendsService | None = None
    reverse_engineering: ReverseEngineeringService | None = None
    studio: StudioService | None = None
    studio_repo: PostgresStudioRepository | None = None
    external_agents: ExternalAgentsService | None = None
    external_agents_repo: PostgresExternalAgentsRepository | None = None
    telemetry: TelemetryRecorder = field(default_factory=TelemetryRecorder)


def build_default_container(settings: Settings) -> ServiceContainer:
    client = SupabaseRestClient(
        supabase_url=settings.next_public_supabase_url,
        publishable_key=settings.next_public_supabase_publishable_key,
    )
    ws_service = WorkspaceService(SupabaseWorkspaceRepository(client))
    ch_service = ChannelService(ws_service, SupabaseChannelRepository(client))
    bus = CommandBus(ws_service, SupabaseJobRepository(client))
    verifier = SupabaseJWTVerifier(
        supabase_url=settings.next_public_supabase_url,
        jwt_secret=settings.supabase_jwt_secret,
    )
    storage_svc: StorageService | None = None
    analytics_svc: AnalyticsService | None = None
    research_svc: ResearchService | None = None
    research_repo: PostgresResearchAndIntelRepository | None = None
    title_thumb_svc: TitleThumbnailService | None = None
    knowledge_svc: KnowledgeService | None = None
    knowledge_repo: PostgresKnowledgeRepository | None = None
    if settings.database_url and settings.next_public_supabase_url:
        storage_client = SupabaseStorageClient(
            supabase_url=settings.next_public_supabase_url,
            publishable_key=settings.next_public_supabase_publishable_key,
            service_role_key=settings.supabase_service_role_key,
        )
        storage_svc = StorageService(storage_client, PostgresStorageMetadataRepository(settings.database_url))
        analytics_repo = PostgresAnalyticsRepository(
            database_url=settings.database_url,
            vault=TokenVault(settings.token_encryption_key),
        )
        yt_adapter = OfficialYouTubeAdapter(
            client_id=settings.youtube_client_id,
            client_secret=settings.youtube_client_secret,
        )
        analytics_svc = AnalyticsService(ws_service, analytics_repo, yt_adapter, command_bus=bus)
        research_repo = PostgresResearchAndIntelRepository(settings.database_url)
        research_svc = ResearchService(ws_service, research_repo, analytics_repo=analytics_repo)
        title_thumb_svc = TitleThumbnailService(ws_service, research_repo, vision_provider=None)
        knowledge_repo = PostgresKnowledgeRepository(settings.database_url)
        knowledge_svc = KnowledgeService(ws_service, knowledge_repo, AIProviderRouter())
        editorial_repo = PostgresEditorialRepository(settings.database_url)
        opportunities_svc = OpportunityService(ws_service, editorial_repo, knowledge_service=knowledge_svc, ai_router=AIProviderRouter())
        editorial_svc = EditorialStudioService(ws_service, editorial_repo)
        production_repo = PostgresProductionRepository(settings.database_url)
        df_gateway = DarkForgeGateway(core_path=settings.darkforge_core_path, history_path=settings.darkforge_history_path)
        production_svc = ProductionIntentService(ws_service, production_repo, df_gateway, command_bus=bus)
        studio_repo = PostgresStudioTrendsRepository(settings.database_url)
        studio_sess = StudioBrowserSessionManager(StudioSessionConfig(max_runs_per_hour=settings.studio_max_runs_per_hour))
        studio_ext = StudioTrendsExtractor(studio_sess)
        studio_trends_svc = StudioTrendsService(
            ws_service,
            studio_repo,
            session_mgr=studio_sess,
            extractor=studio_ext,
            baseline_fetcher=yt_adapter,
            command_bus=bus,
            youtube_api_key=settings.youtube_api_key,
        )
        gtrends_repo = PostgresGoogleTrendsRepository(settings.database_url)
        gtrends_col = GoogleTrendsPlaywrightCollector(studio_sess)
        google_trends_svc = GoogleTrendsService(
            ws_service,
            gtrends_repo,
            collector=gtrends_col,
            csv_timeline_parser=parse_timeline_csv,
            csv_related_parser=parse_related_queries_csv,
        )
        re_repo = PostgresReverseEngineeringRepository(settings.database_url)
        reverse_eng_svc = ReverseEngineeringService(ws_service, re_repo)
        studio_repo = PostgresStudioRepository(settings.database_url)
        studio_svc = StudioService(
            ws_service,
            studio_repo,
            darkforge_available=bool(settings.darkforge_core_path.strip()),
            avatar_lookup=get_shared_public_collector(settings.youtube_api_key).get_cached_avatar_url,
        )
        ext_agents_repo = PostgresExternalAgentsRepository(settings.database_url)
        ext_agents_svc = ExternalAgentsService(ws_service, ext_agents_repo)
    else:
        editorial_repo = None
        opportunities_svc = None
        editorial_svc = None
        production_repo = None
        production_svc = None
        studio_trends_svc = None
        google_trends_svc = None
        reverse_eng_svc = None
        studio_repo = None
        studio_svc = None
        ext_agents_repo = None
        ext_agents_svc = None

    return ServiceContainer(
        jwt_verifier=verifier,
        supabase_client=client,
        workspaces=ws_service,
        channels=ch_service,
        command_bus=bus,
        storage_service=storage_svc,
        analytics=analytics_svc,
        research=research_svc,
        research_repo=research_repo,
        title_thumb=title_thumb_svc,
        knowledge=knowledge_svc,
        knowledge_repo=knowledge_repo,
        opportunities=opportunities_svc,
        editorial=editorial_svc,
        editorial_repo=editorial_repo,
        production=production_svc,
        production_repo=production_repo,
        studio_trends=studio_trends_svc,
        google_trends=google_trends_svc,
        reverse_engineering=reverse_eng_svc,
        studio=studio_svc,
        studio_repo=studio_repo,
        external_agents=ext_agents_svc,
        external_agents_repo=ext_agents_repo,
    )


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_current_user(
    authorization: str | None = Header(default=None),
    container: ServiceContainer = Depends(get_container),
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(
            code=ErrorCode.AUTH_UNAUTHENTICATED,
            message="Cabecalho Authorization Bearer ausente.",
            http_status=401,
        )
    token = authorization.split(" ", 1)[1]
    return container.jwt_verifier.verify_token(token)


def get_workspace_id(
    x_workspace_id: str | None = Header(default=None),
) -> UUID:
    if not x_workspace_id:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Cabecalho X-Workspace-Id e obrigatorio.",
            http_status=422,
            details={"field": "X-Workspace-Id"},
        )
    try:
        return UUID(x_workspace_id)
    except ValueError as exc:
        raise AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="X-Workspace-Id deve ser um UUID valido.",
            http_status=422,
            details={"field": "X-Workspace-Id"},
        ) from exc


def enforce_origin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        allowed = {settings.web_origin, "http://localhost:3000", "http://127.0.0.1:3000"}
        if origin and origin not in allowed:
            raise AppError(
                code=ErrorCode.WORKSPACE_FORBIDDEN,
                message="Origem da requisicao nao autorizada.",
                http_status=403,
            )
