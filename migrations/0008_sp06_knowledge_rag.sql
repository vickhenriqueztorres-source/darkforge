-- ============================================================================
-- Migration 0008: Knowledge/RAG Studio, Curadoria L0-L3, pgvector & FTS
-- Subplano: SP-06 (SP-06-T01..T08)
-- ADRs: ADR-006, ADR-007, ADR-009, ADR-010, ADR-011
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Knowledge Sources (copies, roteiros, transcricoes, guias)
CREATE TABLE IF NOT EXISTS public.knowledge_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL,
    title text NOT NULL CHECK (char_length(trim(title)) BETWEEN 1 AND 200),
    source_type text NOT NULL CHECK (
        source_type IN ('title', 'hook', 'description', 'cta', 'script', 'ad', 'short', 'community_post', 'brand_doc', 'transcript')
    ),
    language text NOT NULL DEFAULT 'pt-BR',
    origin_type text NOT NULL DEFAULT 'manual_import',
    rights_status text NOT NULL DEFAULT 'owned' CHECK (rights_status IN ('owned', 'licensed', 'internal_reference', 'restricted')),
    allowed_in_generation boolean NOT NULL DEFAULT true,
    curation_level text NOT NULL DEFAULT 'L0' CHECK (curation_level IN ('L0', 'L1', 'L2', 'L3')),
    status text NOT NULL DEFAULT 'IMPORTED' CHECK (
        status IN ('IMPORTED', 'NORMALIZED', 'DEDUPLICATED', 'REVIEWED', 'APPROVED', 'INDEXED', 'REJECTED', 'ARCHIVED', 'DELETED')
    ),
    collection_name text NOT NULL DEFAULT 'default',
    content_text text NOT NULL CHECK (char_length(trim(content_text)) >= 1),
    content_sha256 text NOT NULL,
    source_version integer NOT NULL DEFAULT 1 CHECK (source_version >= 1),
    parent_source_id uuid NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, content_sha256, source_version),
    UNIQUE (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_sources_filter
    ON public.knowledge_sources (workspace_id, status, curation_level, language, collection_name);

CREATE TRIGGER trg_knowledge_sources_updated_at
    BEFORE UPDATE ON public.knowledge_sources
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 2. Knowledge Chunks (FTS + rastreabilidade por secao)
CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    source_id uuid NOT NULL,
    channel_id uuid NULL,
    source_version integer NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    section_label text NOT NULL DEFAULT 'general',
    chunk_text text NOT NULL,
    chunk_hash text NOT NULL,
    language text NOT NULL DEFAULT 'pt-BR',
    fts_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (source_id, source_version, chunk_index),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_chunks_source_ws
        FOREIGN KEY (workspace_id, source_id)
        REFERENCES public.knowledge_sources(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_fts
    ON public.knowledge_chunks USING GIN (fts_tsv);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_ws_src
    ON public.knowledge_chunks (workspace_id, source_id, source_version);

-- 3. Embedding Revisions (isolamento estrito de modelo/dimensao - ADR-010)
CREATE TABLE IF NOT EXISTS public.embedding_revisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    embedding_model text NOT NULL,
    embedding_version text NOT NULL,
    dimensions integer NOT NULL CHECK (dimensions BETWEEN 8 AND 4096),
    status text NOT NULL DEFAULT 'BUILDING' CHECK (
        status IN ('BUILDING', 'VALIDATING', 'ACTIVE', 'DEPRECATED', 'RETIRED', 'FAILED_VALIDATION')
    ),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, embedding_model, embedding_version, dimensions),
    UNIQUE (workspace_id, id)
);

CREATE TRIGGER trg_embedding_revisions_updated_at
    BEFORE UPDATE ON public.embedding_revisions
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 4. Knowledge Embeddings (projecao reconstruivel no pgvector)
CREATE TABLE IF NOT EXISTS public.knowledge_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    chunk_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (chunk_id, revision_id),
    CONSTRAINT fk_emb_chunk_ws
        FOREIGN KEY (workspace_id, chunk_id)
        REFERENCES public.knowledge_chunks(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_emb_rev_ws
        FOREIGN KEY (workspace_id, revision_id)
        REFERENCES public.embedding_revisions(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_ws_rev
    ON public.knowledge_embeddings (workspace_id, revision_id);

-- 5. Retrieval Runs, Prompt Templates & Generations (proveniencia completa)
CREATE TABLE IF NOT EXISTS public.retrieval_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL,
    revision_id uuid NULL,
    query_text text NOT NULL,
    filters_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    chunk_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    scores_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS public.generations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL,
    profile_version_id uuid NULL,
    retrieval_run_id uuid NULL,
    prompt_name text NOT NULL,
    prompt_version text NOT NULL,
    provider_name text NOT NULL,
    model_id text NOT NULL,
    external_consent_granted boolean NOT NULL DEFAULT false,
    data_categories_sent text[] NOT NULL DEFAULT ARRAY[]::text[],
    context_chunk_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    output_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    validations_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

-- 6. RLS & Grants SP-06
REVOKE ALL ON public.knowledge_sources FROM PUBLIC, anon;
REVOKE ALL ON public.knowledge_chunks FROM PUBLIC, anon;
REVOKE ALL ON public.embedding_revisions FROM PUBLIC, anon;
REVOKE ALL ON public.knowledge_embeddings FROM PUBLIC, anon;
REVOKE ALL ON public.retrieval_runs FROM PUBLIC, anon;
REVOKE ALL ON public.generations FROM PUBLIC, anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.knowledge_sources TO authenticated;
GRANT SELECT, INSERT, DELETE ON public.knowledge_chunks TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.embedding_revisions TO authenticated;
GRANT SELECT, INSERT, DELETE ON public.knowledge_embeddings TO authenticated;
GRANT SELECT, INSERT ON public.retrieval_runs TO authenticated;
GRANT SELECT, INSERT ON public.generations TO authenticated;

ALTER TABLE public.knowledge_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE public.embedding_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.embedding_revisions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_embeddings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.retrieval_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retrieval_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.generations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generations FORCE ROW LEVEL SECURITY;

CREATE POLICY knowledge_sources_member ON public.knowledge_sources
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY knowledge_chunks_member ON public.knowledge_chunks
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY embedding_revisions_member ON public.embedding_revisions
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY knowledge_embeddings_member ON public.knowledge_embeddings
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY retrieval_runs_member ON public.retrieval_runs
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY generations_member ON public.generations
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
