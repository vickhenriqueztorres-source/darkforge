-- =====================================================================
-- DarkForge Studio UI — SQL DE REFERÊNCIA
-- NÃO aplicar direto. A IDE deve adaptar este schema às tabelas
-- existentes (workspaces, channels, jobs, memberships, helper de RLS)
-- e gerar migrations versionadas no padrão do repositório.
-- Pressupõe: public.workspaces, public.channels, public.jobs e
-- uma função public.is_workspace_member(uuid) criada no SP-01.
-- =====================================================================

-- ---------- Catálogos ----------
create table if not exists public.studio_rooms (
  key         text primary key,
  label       text not null,
  sort_order  int  not null default 0
);

insert into public.studio_rooms (key, label, sort_order) values
  ('sala_dados',            'Sala de Dados',            10),
  ('pesquisa',              'Pesquisa',                 20),
  ('mesa_agentes',          'Agentes de IA',            30),
  ('gravacao',              'Gravação',                 40),
  ('design_thumbnail',      'Design – Thumbnail',       50),
  ('estrategia_publicacao', 'Estratégia e Publicação',  60)
on conflict (key) do nothing;

create table if not exists public.agent_definitions (
  key               text primary key,
  display_name      text not null,
  room_key          text not null references public.studio_rooms(key),
  description       text not null,
  output_types      text[] not null,
  requires_approval boolean not null default false,
  contract_version  int not null default 1,
  active            boolean not null default true
);

insert into public.agent_definitions (key, display_name, room_key, description, output_types, requires_approval) values
  ('dados',      'Analista de Dados',   'sala_dados',            'Interpreta analytics sincronizados',  array['channel_insight'],       false),
  ('pesquisa',   'Pesquisador',         'pesquisa',              'Referências públicas e validação',    array['research_findings'],     false),
  ('estrategia', 'Estrategista',        'mesa_agentes',          'Oportunidades com score',             array['opportunity'],           true),
  ('titulos',    'Especialista Títulos','mesa_agentes',          'Análise e alternativas de título',    array['title_options'],         false),
  ('roteiro',    'Roteirista',          'mesa_agentes',          'Outline e roteiro',                   array['script_draft'],          false),
  ('thumbnail',  'Designer de Capa',    'design_thumbnail',      'Conceitos de thumbnail',              array['thumbnail_concepts'],    false),
  ('edicao',     'Produção',            'gravacao',              'Acompanha produção DarkForge',        array['production_status'],     false),
  ('publicacao', 'Publicação',          'estrategia_publicacao', 'Plano de publicação (sem publicar)',  array['publication_plan'],      true)
on conflict (key) do nothing;

-- ---------- Equipe por canal ----------
create table if not exists public.channel_agents (
  id                  uuid primary key default gen_random_uuid(),
  workspace_id        uuid not null references public.workspaces(id) on delete cascade,
  channel_id          uuid not null references public.channels(id)   on delete cascade,
  agent_key           text not null references public.agent_definitions(key),
  enabled             boolean not null default true,
  display_name        text,
  avatar_key          text,
  config              jsonb not null default '{}'::jsonb,
  model_policy        jsonb not null default '{"mode":"local_only"}'::jsonb,
  monthly_budget_cents int check (monthly_budget_cents is null or monthly_budget_cents >= 0),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (channel_id, agent_key)
);
create index if not exists channel_agents_workspace_idx on public.channel_agents (workspace_id);

-- ---------- Vídeo que percorre o studio ----------
create table if not exists public.content_items (
  id               uuid primary key default gen_random_uuid(),
  workspace_id     uuid not null references public.workspaces(id) on delete cascade,
  channel_id       uuid not null references public.channels(id)   on delete cascade,
  working_title    text not null,
  opportunity_id   uuid,  -- FK para opportunities (SP-07), adaptar
  brief_id         uuid,  -- FK para briefs (SP-07), adaptar
  brief_version    int,
  stage            text not null default 'ideia' check (stage in
                    ('ideia','pesquisa','estrategia','roteiro','design','producao','publicacao','publicado_manual','arquivado')),
  status           text not null default 'ativo' check (status in
                    ('ativo','aguardando_aprovacao','bloqueado','concluido','arquivado')),
  scheduled_for    timestamptz,
  created_by       uuid references auth.users(id),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists content_items_channel_stage_idx on public.content_items (channel_id, stage);
create index if not exists content_items_workspace_idx on public.content_items (workspace_id);

-- ---------- Execuções ----------
create table if not exists public.agent_runs (
  id                  uuid primary key default gen_random_uuid(),
  workspace_id        uuid not null references public.workspaces(id) on delete cascade,
  channel_id          uuid not null references public.channels(id)   on delete cascade,
  channel_agent_id    uuid not null references public.channel_agents(id),
  agent_key           text not null references public.agent_definitions(key),
  content_item_id     uuid references public.content_items(id) on delete set null,
  job_id              uuid references public.jobs(id),  -- fila única (SP-02)
  status              text not null default 'queued' check (status in
                       ('queued','working','waiting_input','needs_review','waiting_approval',
                        'blocked','failed','cancelled','done')),
  stage_label         text,
  progress            numeric(5,4) check (progress is null or (progress >= 0 and progress <= 1)),
  attempt             int not null default 1,
  idempotency_key     text not null,
  input_hash          text,
  prompt_version      text,
  model_id            text,
  provider            text,
  cost_estimate_cents int,
  heartbeat_at        timestamptz,
  started_at          timestamptz,
  finished_at         timestamptz,
  error_code          text,
  error_message       text,
  created_at          timestamptz not null default now(),
  unique (workspace_id, idempotency_key)
);
create index if not exists agent_runs_channel_status_idx on public.agent_runs (channel_id, status);
create index if not exists agent_runs_item_agent_idx     on public.agent_runs (content_item_id, agent_key, created_at desc);
create index if not exists agent_runs_job_idx            on public.agent_runs (job_id);
create index if not exists agent_runs_channel_agent_idx  on public.agent_runs (channel_agent_id);

-- ---------- Eventos (feed + replay) ----------
create table if not exists public.agent_events (
  id              bigint generated always as identity primary key,
  workspace_id    uuid not null references public.workspaces(id) on delete cascade,
  channel_id      uuid not null references public.channels(id)   on delete cascade,
  run_id          uuid not null references public.agent_runs(id) on delete cascade,
  content_item_id uuid references public.content_items(id) on delete set null,
  seq             int  not null,
  event_type      text not null check (event_type in
                   ('run_queued','run_started','stage_changed','progress','output_saved','output_validated',
                    'needs_review','handoff_created','blocked','failed','cancelled','completed')),
  summary         text not null,
  payload         jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  unique (run_id, seq)
);
create index if not exists agent_events_channel_cursor_idx on public.agent_events (channel_id, id);
create index if not exists agent_events_item_idx           on public.agent_events (content_item_id, id);

-- ---------- Outputs ----------
create table if not exists public.agent_outputs (
  id                 uuid primary key default gen_random_uuid(),
  workspace_id       uuid not null references public.workspaces(id) on delete cascade,
  channel_id         uuid not null references public.channels(id)   on delete cascade,
  run_id             uuid not null references public.agent_runs(id),
  content_item_id    uuid references public.content_items(id) on delete set null,
  agent_key          text not null references public.agent_definitions(key),
  output_type        text not null,
  schema_version     int  not null,
  version            int  not null,
  content            jsonb not null,
  content_hash       text not null,
  status             text not null default 'draft' check (status in
                      ('draft','validated','needs_review','approved','rejected','superseded')),
  validation         jsonb not null default '{}'::jsonb,
  originality_score  numeric(5,4),
  created_at         timestamptz not null default now(),
  unique (run_id, output_type, content_hash)
);
create unique index if not exists agent_outputs_item_type_version_uidx
  on public.agent_outputs (content_item_id, output_type, version) where content_item_id is not null;
create index if not exists agent_outputs_channel_idx on public.agent_outputs (channel_id, output_type, created_at desc);

create table if not exists public.agent_output_sources (
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  output_id    uuid not null references public.agent_outputs(id) on delete cascade,
  source_kind  text not null check (source_kind in
                ('metric','research_reference','knowledge_chunk','profile_version','agent_output','artifact')),
  source_id    text not null,
  locator      text,
  note         text
);
create unique index if not exists agent_output_sources_uidx
  on public.agent_output_sources (output_id, source_kind, source_id, coalesce(locator, ''));

-- ---------- Handoffs ----------
create table if not exists public.agent_handoffs (
  id                 uuid primary key default gen_random_uuid(),
  workspace_id       uuid not null references public.workspaces(id) on delete cascade,
  channel_id         uuid not null references public.channels(id)   on delete cascade,
  content_item_id    uuid not null references public.content_items(id) on delete cascade,
  from_run_id        uuid not null references public.agent_runs(id),
  output_id          uuid not null references public.agent_outputs(id),
  to_agent_key       text not null references public.agent_definitions(key),
  status             text not null default 'pending' check (status in ('pending','accepted','consumed','cancelled')),
  consumed_by_run_id uuid references public.agent_runs(id),
  created_at         timestamptz not null default now(),
  unique (output_id, to_agent_key)
);
create index if not exists agent_handoffs_pending_idx on public.agent_handoffs (channel_id, to_agent_key, status);

-- ---------- Aprovações humanas ----------
create table if not exists public.approvals (
  id             uuid primary key default gen_random_uuid(),
  workspace_id   uuid not null references public.workspaces(id) on delete cascade,
  channel_id     uuid not null references public.channels(id)   on delete cascade,
  target_kind    text not null check (target_kind in ('agent_output','opportunity','brief','publication_plan')),
  target_id      uuid not null,
  target_version int  not null,
  decision       text not null check (decision in ('approved','rejected','changes_requested')),
  reason         text,
  decided_by     uuid not null references auth.users(id),
  decided_at     timestamptz not null default now()
);
create index if not exists approvals_target_idx on public.approvals (target_kind, target_id, target_version);

-- ---------- RLS ----------
alter table public.channel_agents       enable row level security;
alter table public.content_items        enable row level security;
alter table public.agent_runs           enable row level security;
alter table public.agent_events         enable row level security;
alter table public.agent_outputs        enable row level security;
alter table public.agent_output_sources enable row level security;
alter table public.agent_handoffs       enable row level security;
alter table public.approvals            enable row level security;
alter table public.studio_rooms         enable row level security;
alter table public.agent_definitions    enable row level security;

create policy studio_rooms_read      on public.studio_rooms      for select to authenticated using (true);
create policy agent_definitions_read on public.agent_definitions for select to authenticated using (true);

-- Leitura por membership. Escrita de runs/eventos/outputs/handoffs é
-- feita pelo worker no backend (papel de serviço), nunca pelo navegador.
create policy channel_agents_rw on public.channel_agents for all to authenticated
  using (public.is_workspace_member(workspace_id)) with check (public.is_workspace_member(workspace_id));
create policy content_items_rw on public.content_items for all to authenticated
  using (public.is_workspace_member(workspace_id)) with check (public.is_workspace_member(workspace_id));
create policy agent_runs_read on public.agent_runs for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy agent_events_read on public.agent_events for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy agent_outputs_read on public.agent_outputs for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy agent_output_sources_read on public.agent_output_sources for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy agent_handoffs_read on public.agent_handoffs for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy approvals_read on public.approvals for select to authenticated
  using (public.is_workspace_member(workspace_id));
create policy approvals_insert on public.approvals for insert to authenticated
  with check (public.is_workspace_member(workspace_id) and decided_by = auth.uid());

-- ---------- Views para a UI (respeitam RLS) ----------
create or replace view public.v_studio_agent_state with (security_invoker = true) as
select distinct on (ca.id)
  ca.workspace_id, ca.channel_id, ca.id as channel_agent_id, ca.agent_key,
  ad.room_key, coalesce(ca.display_name, ad.display_name) as display_name, ca.avatar_key,
  r.id as run_id, r.content_item_id,
  case
    when r.id is null then 'idle'
    when r.status = 'working' and (r.heartbeat_at is null or r.heartbeat_at < now() - interval '2 minutes') then 'no_signal'
    else r.status
  end as status,
  r.stage_label, r.progress, r.heartbeat_at, r.error_code, r.created_at as run_created_at
from public.channel_agents ca
join public.agent_definitions ad on ad.key = ca.agent_key
left join public.agent_runs r on r.channel_agent_id = ca.id
where ca.enabled
order by ca.id, r.created_at desc nulls last;

create or replace view public.v_studio_room_state with (security_invoker = true) as
select
  s.workspace_id, s.channel_id, s.room_key,
  count(*) filter (where s.status = 'working')                          as working,
  count(*) filter (where s.status in ('needs_review','waiting_approval')) as awaiting_human,
  count(*) filter (where s.status in ('blocked','no_signal'))            as blocked,
  count(*) filter (where s.status = 'failed')                            as failed,
  count(*)                                                               as agents
from public.v_studio_agent_state s
group by s.workspace_id, s.channel_id, s.room_key;
