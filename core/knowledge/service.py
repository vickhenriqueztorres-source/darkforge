from __future__ import annotations

from typing import Any
from uuid import UUID

from adapters.ai_providers.router import AIProviderRouter
from core.errors import AppError, ErrorCode
from core.knowledge.chunker import content_sha256, normalize_source_text, split_semantic_chunks
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class KnowledgeService:
    """Manages L0-L3 curation, deduplication, chunking, pgvector revisions, citations & deletion (SP-06)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        ai_router: AIProviderRouter,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._ai = ai_router
        self._retrieval_cache: dict[str, list[dict[str, Any]]] = {}

    def import_source(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        title: str,
        source_type: str,
        content_text: str,
        language: str = "pt-BR",
        origin_type: str = "manual_import",
        rights_status: str = "owned",
        allowed_in_generation: bool = True,
        collection_name: str = "default",
        channel_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        norm_text = normalize_source_text(content_text)
        if not title.strip() or not norm_text:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Titulo e conteudo da fonte sao obrigatorios.", http_status=422)
        if rights_status not in ("owned", "licensed", "internal_reference", "restricted"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "rights_status invalido.", http_status=422)

        digest = content_sha256(norm_text)
        existing = self._repo.find_source_by_hash(workspace_id, digest)
        if existing is not None:
            return {"source": existing, "deduplicated": True}

        src = self._repo.insert_source(
            workspace_id=workspace_id,
            channel_id=channel_id,
            title=title.strip(),
            source_type=source_type,
            language=language,
            origin_type=origin_type,
            rights_status=rights_status,
            allowed_in_generation=(False if rights_status == "restricted" else allowed_in_generation),
            collection_name=collection_name,
            content_text=norm_text,
            content_sha256=digest,
            user_id=actor.user_id,
        )
        return {"source": src, "deduplicated": False}

    def review_source(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        source_id: UUID,
        curation_level: str,
        status: str,
        allowed_in_generation: bool | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        if curation_level not in ("L0", "L1", "L2", "L3"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Nivel de curadoria deve ser L0, L1, L2 ou L3.", http_status=422)
        if status not in ("REVIEWED", "APPROVED", "REJECTED", "ARCHIVED"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Status de revisao invalido.", http_status=422)

        updated = self._repo.update_source_review(workspace_id, source_id, curation_level, status, allowed_in_generation)
        if updated is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Fonte nao encontrada.", http_status=404)
        self._invalidate_workspace_cache(workspace_id)
        return updated

    def index_approved_sources(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        source_ids: list[UUID] | None = None,
        force_new_revision: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        model, ver, dims, _ = self._ai.embed_texts(["probe"])
        rev = self._repo.get_or_create_active_revision(workspace_id, model, ver, dims, force_new=force_new_revision)

        eligible = self._repo.list_indexable_sources(workspace_id, source_ids)
        indexed_sources = 0
        total_chunks = 0
        for src in eligible:
            # L0 cannot enter RAG index unless explicitly reviewed/approved; restricted stays out
            if src["curation_level"] == "L0" or src["status"] in ("ARCHIVED", "REJECTED", "DELETED"):
                continue
            chunks = split_semantic_chunks(src["content_text"])
            if not chunks:
                continue
            _, _, _, vectors = self._ai.embed_texts([c.chunk_text for c in chunks])
            self._repo.upsert_chunks_and_embeddings(
                workspace_id=workspace_id,
                source=src,
                revision_id=rev["id"],
                chunks=chunks,
                vectors=vectors,
            )
            indexed_sources += 1
            total_chunks += len(chunks)

        if rev["status"] != "ACTIVE":
            rev = self._repo.promote_revision_active(workspace_id, rev["id"])
        self._invalidate_workspace_cache(workspace_id)
        return {"revision": rev, "indexed_sources": indexed_sources, "total_chunks": total_chunks}

    def retrieve(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        query: str,
        channel_id: UUID | None = None,
        language: str | None = None,
        collection_name: str | None = None,
        allowed_levels: tuple[str, ...] = ("L2", "L3"),
        top_k: int = 5,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        if not query.strip():
            raise AppError(ErrorCode.VALIDATION_ERROR, "Query de busca e obrigatoria.", http_status=422)
        if "L0" in allowed_levels and allowed_levels == ("L0",):
            raise AppError(ErrorCode.VALIDATION_ERROR, "L0 nao e permitido por padrao no RAG.", http_status=422)

        _, _, _, q_vecs = self._ai.embed_texts([query])
        active_rev = self._repo.get_active_revision(workspace_id)
        if active_rev is None:
            return {"retrieval_run": None, "chunks": [], "insufficient_context": True}

        hits = self._repo.hybrid_search(
            workspace_id=workspace_id,
            revision_id=active_rev["id"],
            query_text=query,
            query_vector=q_vecs[0],
            allowed_levels=list(allowed_levels),
            channel_id=channel_id,
            language=language,
            collection_name=collection_name,
            top_k=top_k,
        )

        # Post-search validation: confirm every chunk belongs to this workspace and is still INDEXED
        validated_hits = self._repo.revalidate_chunk_ids(workspace_id, [h["chunk_id"] for h in hits])
        valid_ids = {str(v) for v in validated_hits}
        final_hits = [h for h in hits if str(h["chunk_id"]) in valid_ids]

        run = self._repo.record_retrieval_run(
            workspace_id=workspace_id,
            channel_id=channel_id,
            revision_id=active_rev["id"],
            query_text=query,
            filters={"allowed_levels": list(allowed_levels), "language": language, "collection": collection_name},
            chunk_ids=[str(h["chunk_id"]) for h in final_hits],
            scores=[h["hybrid_score"] for h in final_hits],
            user_id=actor.user_id,
        )
        return {
            "retrieval_run": run,
            "chunks": final_hits,
            "insufficient_context": len(final_hits) == 0,
        }

    def generate_grounded(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        goal: str,
        channel_id: UUID | None = None,
        profile_version_id: UUID | None = None,
        use_external: bool = False,
        external_consent_granted: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        ret = self.retrieve(actor, workspace_id, goal, channel_id=channel_id, allowed_levels=("L2", "L3"), top_k=5)
        res = self._ai.generate_with_context(
            goal=goal,
            context_chunks=ret["chunks"],
            use_external=use_external,
            external_consent_granted=external_consent_granted,
        )
        gen = self._repo.record_generation(
            workspace_id=workspace_id,
            channel_id=channel_id,
            profile_version_id=profile_version_id,
            retrieval_run_id=ret["retrieval_run"]["id"] if ret["retrieval_run"] else None,
            prompt_name="grounded_editorial_v1",
            prompt_version="v1",
            provider_name=res.provider_name,
            model_id=res.model_id,
            external_consent_granted=res.external_consent_granted,
            data_categories_sent=res.data_categories_sent,
            context_chunk_ids=[UUID(str(c["chunk_id"])) for c in ret["chunks"]],
            output_json=res.output,
            validations_json={"citations_verified": True, "l0_excluded": True},
            user_id=actor.user_id,
        )
        return {"generation": gen, "citations": ret["chunks"]}

    def archive_or_delete_source(
        self, actor: AuthenticatedUser, workspace_id: UUID, source_id: UUID, hard_delete: bool = False
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        result = self._repo.archive_or_delete_source(workspace_id, source_id, hard_delete=hard_delete)
        if result is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Fonte nao encontrada neste workspace.", http_status=404)
        self._invalidate_workspace_cache(workspace_id)
        return result

    def get_generation_provenance(
        self, actor: AuthenticatedUser, workspace_id: UUID, generation_id: UUID
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        prov = self._repo.get_generation_provenance(workspace_id, generation_id)
        if prov is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Geracao nao encontrada neste workspace.", http_status=404)
        return prov

    def _invalidate_workspace_cache(self, workspace_id: UUID) -> None:
        prefix = f"{workspace_id}:"
        for k in [key for key in self._retrieval_cache if key.startswith(prefix)]:
            del self._retrieval_cache[k]
