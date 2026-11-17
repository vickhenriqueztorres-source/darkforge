from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class ImportKnowledgeRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source_type: str = Field(pattern="^(title|hook|description|cta|script|ad|short|community_post|brand_doc|transcript)$")
    content_text: str = Field(min_length=1)
    language: str = "pt-BR"
    origin_type: str = "manual_import"
    rights_status: str = Field(default="owned", pattern="^(owned|licensed|internal_reference|restricted)$")
    allowed_in_generation: bool = True
    collection_name: str = "default"
    channel_id: UUID | None = None


class ReviewKnowledgeRequest(BaseModel):
    curation_level: str = Field(pattern="^(L0|L1|L2|L3)$")
    status: str = Field(pattern="^(REVIEWED|APPROVED|REJECTED|ARCHIVED)$")
    allowed_in_generation: bool | None = None


class ReindexKnowledgeRequest(BaseModel):
    source_ids: list[UUID] | None = None
    force_new_revision: bool = False


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(min_length=1)
    channel_id: UUID | None = None
    language: str | None = None
    collection_name: str | None = None
    allowed_levels: list[str] = Field(default_factory=lambda: ["L2", "L3"])
    top_k: int = Field(default=5, ge=1, le=20)


class GenerateGroundedRequest(BaseModel):
    goal: str = Field(min_length=2)
    channel_id: UUID | None = None
    profile_version_id: UUID | None = None
    use_external: bool = False
    external_consent_granted: bool = False


def _ser(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _require_knowledge(container: ServiceContainer):
    if container.knowledge is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "KnowledgeService nao configurado.", http_status=503, retryable=True)
    return container.knowledge


@router.get("/knowledge/sources")
def list_knowledge_sources(
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    container.workspaces.require_membership(actor, workspace_id)
    if container.knowledge_repo is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "KnowledgeRepo nao configurado.", http_status=503, retryable=True)
    return {"items": _ser(container.knowledge_repo.list_sources(workspace_id))}


@router.post("/knowledge/sources", status_code=201)
def import_knowledge_source(
    body: ImportKnowledgeRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(
        svc.import_source(
            actor=actor,
            workspace_id=workspace_id,
            title=body.title,
            source_type=body.source_type,
            content_text=body.content_text,
            language=body.language,
            origin_type=body.origin_type,
            rights_status=body.rights_status,
            allowed_in_generation=body.allowed_in_generation,
            collection_name=body.collection_name,
            channel_id=body.channel_id,
        )
    )


@router.post("/knowledge/sources/{source_id}/review")
def review_knowledge_source(
    source_id: UUID,
    body: ReviewKnowledgeRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(svc.review_source(actor, workspace_id, source_id, body.curation_level, body.status, body.allowed_in_generation))


@router.delete("/knowledge/sources/{source_id}")
def delete_or_archive_source(
    source_id: UUID,
    hard_delete: bool = Query(default=False),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(svc.archive_or_delete_source(actor, workspace_id, source_id, hard_delete=hard_delete))


@router.post("/knowledge/reindex")
def reindex_knowledge(
    body: ReindexKnowledgeRequest | None = None,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    req = body or ReindexKnowledgeRequest()
    return _ser(svc.index_approved_sources(actor, workspace_id, source_ids=req.source_ids, force_new_revision=req.force_new_revision))


@router.post("/knowledge/search")
def search_knowledge(
    body: SearchKnowledgeRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(
        svc.retrieve(
            actor=actor,
            workspace_id=workspace_id,
            query=body.query,
            channel_id=body.channel_id,
            language=body.language,
            collection_name=body.collection_name,
            allowed_levels=tuple(body.allowed_levels),
            top_k=body.top_k,
        )
    )


@router.post("/generations", status_code=201)
def create_generation(
    body: GenerateGroundedRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(
        svc.generate_grounded(
            actor=actor,
            workspace_id=workspace_id,
            goal=body.goal,
            channel_id=body.channel_id,
            profile_version_id=body.profile_version_id,
            use_external=body.use_external,
            external_consent_granted=body.external_consent_granted,
        )
    )


@router.get("/generations/{generation_id}/provenance")
def get_generation_provenance(
    generation_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_knowledge(container)
    return _ser(svc.get_generation_provenance(actor, workspace_id, generation_id))
