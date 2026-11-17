# DarkForge Channel OS
## Arquitetura completa de produto e engenharia

**Status:** revisão crítica para validação antes da implementação  
**Versão:** 0.2  
**Data:** 16 de novembro de 2026  
**Tipo de entrega:** documentação; não inclui implementação da ferramenta  
**Mudança desta revisão:** Supabase como persistência principal e análise explícita dos pontos de quebra

---

## 1. Resumo executivo

O **DarkForge Channel OS** é uma estação local de inteligência editorial e gestão de canais. Ele reúne, em um único workspace, canais próprios, vídeos, métricas, pesquisas de mercado, referências públicas, copies aprovadas e decisões editoriais.

A ferramenta deve responder a quatro perguntas com evidências:

1. **Como cada canal e vídeo está performando?**
2. **O que canais semelhantes estão publicando e quais padrões editoriais aparecem?**
3. **Quais temas e episódios fazem sentido para um canal específico agora?**
4. **Como transformar uma oportunidade aprovada em brief, copy e produção sem perder a identidade do canal?**

A aplicação roda no PC do usuário e é acessada pelo navegador, mas o desenho correto é **local-controlled e cloud-backed**, não local-first estrito: interface, workers e processamento pesado ficam no PC; o **Supabase é a fonte de verdade durável** para dados, fila, configurações e metadados, e o Supabase Storage guarda os arquivos. Isso elimina a ilusão de operação offline: sem rede ou sem Supabase, a UI pode mostrar o último estado já carregado, mas não pode confirmar novas escritas nem marcar jobs como concluídos. Serviços de IA externos continuam opcionais e separados dessa dependência.

O sistema não deve prometer viralização, inventar métricas indisponíveis nem copiar títulos, capas ou textos. Ele identifica padrões, mostra as fontes e gera alternativas originais com revisão humana.

---

## 2. Relação com o DarkForge existente

O material de referência descreve um DarkForge com pipeline de produção, Semantic Editing, Scheduler, Artifacts, SQLite, FFmpeg e uma futura interface desktop/EXE. Este projeto deve **reutilizar esse núcleo**, e não criar uma segunda arquitetura paralela.

### 2.1 Decisão de apresentação

Para este projeto, a interface principal passa a ser uma **Web UI local no navegador**. CustomTkinter não é necessário para o Channel OS. Um EXE pode ser criado posteriormente apenas como launcher/instalador que inicia os serviços locais e abre o navegador.

### 2.2 Regras de integração obrigatórias

- A UI nunca chama FFmpeg ou FFprobe diretamente.
- A UI nunca executa SQL nem altera o Supabase diretamente com credenciais privilegiadas.
- A UI não contém regras de negócio duplicadas.
- Toda operação assíncrona passa pelo Command Bus e pelo Job Manager existentes.
- O pipeline de produção continua sendo o único responsável por gerar vídeos e artifacts.
- O Channel OS envia intenções e briefs versionados para o núcleo; não modifica estados internos do pipeline por conta própria.
- O Supabase é a fonte de verdade do Channel OS. O SQLite citado no material antigo só pode existir como detalhe privado/legado do executor DarkForge, nunca como segundo banco de canais, briefs, jobs ou analytics.
- Se o executor legado ainda depender de SQLite, a integração usa um adapter com reconciliação e uma migração de single-writer; **dual-write permanente é proibido**.
- O “Job Manager existente” é uma fronteira lógica, não uma desculpa para manter duas filas: ou ele passa a persistir no Supabase, ou o Channel OS adota um novo manager e o executor recebe somente comandos idempotentes. Essa escolha precisa ser comprovada no código do núcleo antes da Fase 1.
- Um único catálogo lógico de jobs, uma única fonte de verdade por entidade e um único mecanismo de recovery.

### 2.3 Fluxo de integração

```text
Navegador
   ↓ comandos e consultas
API local / Application Services
   ↓
Command Bus
   ↓
Job Manager + Scheduler
   ├── Sync de canais e métricas
   ├── Pesquisa e análise de referências
   ├── Indexação RAG e gerações de IA
   └── Pipeline DarkForge de produção
             ↓
       Artifacts no Storage + Postgres + outbox
             ↓
       UI atualizada por polling/SSE com replay
```

---

## 3. Objetivos e não objetivos

### 3.1 Objetivos

- Centralizar a gestão de vários canais, cada um com posicionamento, voz e objetivos próprios.
- Sincronizar dados de canais próprios com histórico, frescor e origem identificados.
- Permitir análise comparativa entre canais, vídeos, períodos, formatos e pilares editoriais.
- Descobrir referências públicas e construir uma lista auditável de canais semelhantes.
- Extrair padrões de títulos, capas, formatos e temas sem reproduzir o material de referência.
- Sugerir episódios e temas com justificativa, evidências, score e confiança.
- Manter uma biblioteca curada de copies e conhecimento para RAG.
- Gerar títulos, descrições, hooks, outlines, roteiros, CTAs e conceitos de capa com proveniência.
- Transformar recomendações aprovadas em briefs e produções rastreáveis.
- Executar UI e workers localmente, com persistência no Supabase e jobs pausáveis, retomáveis e recuperáveis após reinício.

### 3.2 Não objetivos do primeiro ciclo

- Não oferecer colaboração multiusuário ou operação SaaS pública no primeiro ciclo; o modelo ainda precisa ser tenant-safe, com workspaces, memberships e RLS desde o início.
- Não obter analytics privados de concorrentes.
- Não contornar limites, autenticação, robots, termos de uso ou proteções de plataformas.
- Não fazer scraping indiscriminado como fonte principal.
- Não copiar capas, roteiros ou títulos literalmente.
- Não publicar ou alterar vídeos automaticamente sem uma etapa explícita de autorização.
- Não treinar pesos de modelo no MVP; RAG e curadoria já atendem ao objetivo inicial.
- Não introduzir Kubernetes, Kafka, microserviços ou uma frota de agentes autônomos sem necessidade.

---

## 4. Premissas e decisões de arquitetura

| Tema | Decisão proposta | Motivo |
|---|---|---|
| Execução | UI e workers locais; persistência remota no Supabase | Uso no PC sem transformar o PC em servidor de banco |
| Interface | Next.js/React no navegador | UI rica, reutilizável e independente do toolkit desktop |
| Núcleo | Monólito modular em Python, alinhado ao DarkForge | Reuso do pipeline e menor complexidade operacional |
| API | REST + SSE com replay; Realtime apenas como otimização | Progresso sem depender de evento perdido |
| Persistência | **Supabase Postgres**, migrations SQL e repositórios | Uma fonte de verdade gerenciada e relacional |
| Busca | Postgres Full Text Search + `pg_trgm` quando necessário | Busca lexical e tolerância a variações sem outro serviço |
| Vetores | **pgvector no Supabase**, com modelo/versão/dimensão registrados | RAG no mesmo banco, com filtros e RLS |
| Arquivos | **Supabase Storage privado**; filesystem local só para cache/temporários | Não inflar o Postgres com binários nem perder artifacts |
| Autenticação | Supabase Auth + memberships; YouTube OAuth é uma conexão separada | Sessão e autorização não podem ser confundidas |
| Autorização | RLS em todas as tabelas e buckets; backend privilegiado com escopo obrigatório | Isolamento por workspace e por usuário |
| Jobs | Fila Postgres com lease, heartbeat, fencing token e idempotência | Workers locais podem morrer sem duplicar efeitos |
| IA | Provider Router com modelo local e provedores externos opcionais | Privacidade, custo e portabilidade sem fallback silencioso |
| Fontes externas | APIs oficiais primeiro; importação manual como fallback | Conformidade e estabilidade |
| Autonomia | Recomendação e geração com aprovação humana | Controle editorial e redução de risco |

**Regra de evolução:** os adapters de banco, vetores, IA e plataformas devem permitir substituição futura sem mudar os casos de uso. Isso não significa criar abstrações genéricas para tudo; somente as fronteiras externas e de infraestrutura recebem interfaces estáveis.

---

## 5. Visão de alto nível

```text
┌──────────────────────────────────────────────────────────────┐
│                    NAVEGADOR DO USUÁRIO                      │
│ Dashboard │ Canais │ Analytics │ Pesquisa │ RAG │ Calendário │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP local / SSE com replay
┌───────────────────────────▼──────────────────────────────────┐
│                      API LOCAL / BFF                         │
│ Supabase Auth │ validação │ DTOs │ workspace │ rate limit    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                 APPLICATION / DOMAIN CORE                    │
│ Channel Service      Analytics Service    Research Service   │
│ Opportunity Service  Knowledge Service    Generation Service │
│ Editorial Service    DarkForge Gateway    Policy Service     │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
       ┌────────▼────────┐     ┌────────▼──────────────────────┐
       │  COMMAND BUS    │     │       QUERY REPOSITORIES      │
       │ Jobs e outbox   │     │ Consultas e projeções da UI   │
       └────────┬────────┘     └────────┬──────────────────────┘
                │                       │
┌───────────────▼───────────────────────▼──────────────────────┐
│                  SUPABASE — FONTE DE VERDADE                 │
│ Postgres │ RLS │ Auth │ pgvector │ FTS │ Storage │ outbox    │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
       ┌────────▼────────┐     ┌────────▼──────────────────────┐
       │ ADAPTERS EXTERNOS│     │        WORKERS LOCAIS         │
       │ YouTube APIs     │     │ sync │ research │ RAG │ IA    │
       │ IA local/remota  │     │ thumbnails │ produção DarkForge│
       │ OCR/visão        │     │ lease │ heartbeat │ recovery  │
       └─────────────────┘     └───────────────────────────────┘

Cache e arquivos temporários no PC são descartáveis. Não são fallback
silencioso nem segunda fonte de verdade quando o Supabase estiver indisponível.
```

### 5.1 Stack de referência

- **Web:** Next.js, React e TypeScript; componentes acessíveis e tema claro/escuro.
- **API e domínio:** Python/FastAPI, serviços de aplicação e schemas compartilhados por contratos versionados.
- **Workers:** processos Python separados da API, usando o mesmo Command Bus e Job Manager.
- **Banco:** Supabase Postgres com foreign keys, migrations SQL, índices, constraints e RLS.
- **Busca:** Postgres Full Text Search; `pg_trgm` para similaridade lexical quando o volume justificar.
- **Vetores:** pgvector no Supabase; textos, embeddings, metadados e permissões ficam no mesmo domínio de dados.
- **Arquivos:** Supabase Storage privado para thumbnails, raw payloads, exports e manifests; vídeos e arquivos grandes usam objetos, nunca colunas `bytea` ou base64.
- **Auth:** Supabase Auth para a sessão do usuário; OAuth do YouTube fica em uma conexão separada e criptografada.
- **Mídia:** FFmpeg/FFprobe somente dentro do pipeline DarkForge; OCR e visão atrás de adapters.
- **IA local:** runtime compatível com modelos locais, como Ollama, quando disponível.
- **IA externa:** provedor configurável no servidor, sem chaves no navegador e sem fallback externo automático.
- **Execução:** dois processos em desenvolvimento (`web` e `api/worker`); o pacote local pode expor uma única porta e iniciar os demais processos internamente.
- **Rede:** a aplicação exige conectividade com o Supabase para confirmar persistência; cache local é somente leitura e pode ficar desatualizado.

Redis, Qdrant e um segundo banco não são pré-requisitos. Só entram por uma necessidade medida que o Supabase/Postgres não atender.

---

## 6. Módulos funcionais

### 6.1 Workspace e identidade dos canais

Cada canal possui um **Channel Profile** versionado:

- Nome, plataforma, idioma, país e fuso de exibição.
- Posicionamento, nicho, pilares editoriais e temas proibidos.
- Público declarado, dores, desejos e nível de conhecimento.
- Tom de voz, vocabulário preferido e expressões a evitar.
- Formatos, duração-alvo, cadência e restrições de produção.
- Objetivos do período: alcance, retenção, conversão, autoridade ou comunidade.
- Referências permitidas e concorrentes bloqueados.
- Identidade visual e regras para capas.
- Histórico de mudanças de tema/posicionamento, sem reescrever o passado.

**Mudança de tema:** o sistema cobre dois casos distintos:

1. **Tema visual da interface:** claro, escuro e tokens da marca, sem afetar dados.
2. **Tema editorial do canal:** nova versão do perfil, com data de vigência; recomendações antigas continuam associadas à versão usada na época.

### 6.2 Conexões e sincronização

- Conexão OAuth por canal próprio.
- Inventário de canais, playlists e vídeos.
- Sync incremental, backfill histórico e refresh manual.
- Cursor por fonte e por entidade.
- Cache de respostas e controle de quota.
- Raw payloads imutáveis para replay e auditoria.
- Normalização para um modelo interno independente da API.
- Indicadores de `last_successful_sync`, `source_updated_at`, `freshness` e erros parciais.
- Falha de uma métrica não deve apagar nem zerar as demais.
- O cursor e o resultado parcial são persistidos no Supabase na mesma transação da unidade processada.
- Se o Supabase estiver indisponível, o worker entra em `BLOCKED/RECOVERABLE`; não grava apenas no PC nem declara sucesso.
- Uma resposta da API do YouTube não é considerada sincronizada até o commit e o registro do cursor no Postgres.
- O sync usa upsert com chave natural e revisão da fonte para suportar retry e backfill sem duplicar fatos.

### 6.3 Analytics Center

Visões mínimas:

- **Portfólio:** canais, evolução, cadência, alertas e comparativo de períodos.
- **Canal:** alcance, consumo, engajamento, conversão de inscritos e distribuição por formato.
- **Vídeo:** ficha completa, métricas disponíveis, histórico, fontes de tráfego e retenção quando autorizada.
- **Comparador:** vídeos e canais lado a lado, sempre com período e dimensões equivalentes.
- **Diagnóstico:** achados do analista, evidências e ações recomendadas.
- **Anotações:** publicações, mudanças de tema, campanhas e alterações de capa/título.

Regras:

- Métrica indisponível é `unknown/unavailable`, nunca zero.
- Dados públicos e privados têm rótulos visuais diferentes.
- Estimativas carregam método, intervalo e confiança.
- Toda tela informa período, fuso, origem e última atualização.
- Mudanças de definição da plataforma são versionadas no catálogo de métricas.

### 6.4 Research Explorer

- Pesquisa por tema, palavra-chave, formato, idioma e período.
- Descoberta de canais candidatos por busca e expansão a partir de referências aprovadas.
- Lista curada de concorrentes/referências, com inclusão e exclusão manual.
- Coleta de metadados públicos permitidos de canais e vídeos.
- Snapshots de métricas públicas ao longo do tempo; não tratar um snapshot como histórico completo.
- Deduplicação por IDs da plataforma, URL canônica e hash de conteúdo.
- Painel de evidências com links, datas e origem de cada afirmação.

Não existe um endpoint universal de “canais semelhantes”. A similaridade é calculada pelo sistema a partir de candidatos descobertos e características observáveis.

### 6.5 Title Intelligence

A engenharia reversa de títulos extrai **estrutura**, não texto para clonagem:

- Idioma, tamanho e quantidade de palavras.
- Entidades, tópico e promessa principal.
- Pergunta, lista, número, contraste, urgência, benefício ou curiosidade.
- Ponto de vista, público implícito e estágio de consciência.
- Grau de especificidade e relação título–conteúdo quando houver conteúdo autorizado.
- Padrões recorrentes por canal, formato e período.

Saídas:

- Ficha estrutural do título.
- Fórmula editorial explicável.
- Variações originais para o canal selecionado.
- Alertas de similaridade excessiva, clickbait, promessa não sustentada e termos proibidos.

### 6.6 Thumbnail Intelligence

Quando o acesso e o uso forem permitidos:

- URL e metadados da capa, data de coleta e hash.
- OCR do texto visível.
- Composição, ponto focal, hierarquia, contraste e legibilidade.
- Presença de pessoas, objetos, expressões e elementos recorrentes.
- Paleta e relação com a identidade do canal.
- Comparação entre conceitos, sem declarar causalidade de CTR.

Saídas:

- Brief visual original.
- Lista de elementos a preservar como padrão e elementos a evitar como cópia.
- Conceitos de capa e prompts para uma etapa posterior de criação.
- Checklist de originalidade, direitos de uso e consistência com o conteúdo.

A referência pública não vira automaticamente um asset reutilizável. Por padrão, o sistema guarda a referência e a análise; redistribuição ou reuso exige direito de uso.

### 6.7 Opportunity Engine

O motor combina evidências de canais próprios, pesquisa pública, perfil editorial e restrições de produção para propor:

- Novos episódios.
- Novos temas e subpilares.
- Sequências e séries.
- Atualizações de vídeos existentes.
- Formatos derivados, como Shorts ou cortes, quando aplicável.

Cada oportunidade contém:

- Canal e versão do perfil editorial.
- Tema, hipótese e público.
- Justificativa e evidências com links.
- Diferenciação em relação às referências.
- Sugestão de formato, ângulo e promessa.
- Esforço de produção e dependências.
- Score, confiança, riscos e motivos de penalização.
- Estado: `draft`, `review`, `approved`, `rejected`, `planned`, `in_production`, `published` ou `archived`.

### 6.8 Editorial Studio

- Brief de episódio versionado.
- Títulos, descrições, hooks, CTAs, outline e roteiro.
- Conceitos de capa e assets associados.
- Calendário editorial por canal.
- Checklist de produção e aprovação.
- Comentários e decisões do usuário.
- Exportação em formatos abertos, como Markdown, JSON e CSV.
- Envio ao DarkForge somente após aprovação explícita.

### 6.9 Knowledge/RAG Studio

- Biblioteca de copies, roteiros, documentos de marca, transcrições autorizadas e aprendizados.
- Upload, importação de texto, tags e curadoria.
- Versionamento, deduplicação e controle de status.
- Níveis de qualidade e permissão de uso no RAG.
- Visualização dos chunks e das fontes usadas em uma geração.
- Reindexação como job recuperável.
- Coleções por canal, idioma, objetivo e tipo de peça.
- Avaliação de recuperação e de fidelidade às fontes.

### 6.10 Analistas especializados

Os analistas são módulos determinísticos ou de IA com contratos fechados, não agentes livres com acesso irrestrito:

| Analista | Entrada principal | Saída |
|---|---|---|
| Portfolio Analyst | Métricas de todos os canais | Prioridades, anomalias e comparações |
| Channel Analyst | Histórico e perfil do canal | Forças, gargalos e oportunidades |
| Video Analyst | Métricas e metadados do vídeo | Diagnóstico e ações |
| Audience Analyst | Dados autorizados de audiência | Segmentos e hipóteses, sem inferências proibidas |
| Research Analyst | Referências públicas | Clusters, tendências e lacunas |
| Title Analyst | Títulos e contexto | Padrões e variantes originais |
| Thumbnail Analyst | Capas e análise visual | Briefs e padrões visuais |
| Copy Analyst | Copies e resultados conhecidos | Elementos reutilizáveis e riscos |
| Opportunity Strategist | Achados dos demais módulos | Ranking de oportunidades |

Todo analista retorna `findings`, `evidence`, `recommendations`, `confidence`, `limitations` e `data_freshness`. O orquestrador não pode transformar ausência de dados em conclusão positiva.

---

## 7. Modelo de dados conceitual

Todos os IDs internos são UUIDs. Timestamps são persistidos em UTC e convertidos na apresentação. Entidades externas guardam plataforma, ID externo, URL canônica e origem.

No Supabase, toda tabela de domínio possui `workspace_id` (ou uma relação comprovável até ele), `created_at`, `updated_at` e, quando houver concorrência, `version` para optimistic locking. `WorkspaceMember` relaciona `workspace_id`, `user_id` e `role`; autorização vem dessa tabela protegida, nunca de `user_metadata` editável pelo usuário.

O modelo inclui ainda `OutboxEvent`, `JobLease`, `StorageObject`, `MetricDefinition`, `QuotaLedger` e `EmbeddingRevision`. Essas entidades fecham lacunas de entrega de eventos, concorrência de workers, consistência de arquivos, semântica de métricas, orçamento de APIs e rebuild de embeddings.

| Entidade | Finalidade e campos essenciais |
|---|---|
| `Workspace` | Configuração local, preferências e políticas |
| `Channel` | Identidade interna, plataforma, perfil ativo e status |
| `ChannelProfileVersion` | Posicionamento, voz, pilares, restrições e vigência |
| `PlatformConnection` | Canal autorizado, escopos, status e referência do segredo |
| `Video` | Metadados normalizados, canal, formato e datas |
| `Playlist` | Relação de playlists e vídeos |
| `MetricSnapshot` | Valor em um instante, origem, dimensões e frescor |
| `MetricSeriesPoint` | Série temporal por métrica, granularidade e dimensão |
| `SyncCursor` | Cursor, quota, última execução e resultado parcial |
| `ResearchRun` | Objetivo, filtros, canal-base, status e versão do algoritmo |
| `ReferenceChannel` | Canal público descoberto, similaridade e curadoria |
| `ReferenceVideo` | Vídeo público, metadados e snapshots |
| `TitleAnalysis` | Características estruturais e versão do analisador |
| `ThumbnailAsset` | Referência, hash, direitos de uso, objeto no Storage e cache local opcional |
| `ThumbnailAnalysis` | OCR, composição, atributos visuais e limitações |
| `Opportunity` | Hipótese, score, confiança, estado e justificativa |
| `EvidenceLink` | Liga uma recomendação a fontes e trechos específicos |
| `EpisodeBrief` | Brief editorial versionado e aprovações |
| `EditorialCalendarItem` | Canal, brief, data planejada e estado |
| `KnowledgeSource` | Documento/copy, tipo, licença, status e versão |
| `KnowledgeChunk` | Trecho, posição, metadados, hash e source version |
| `RetrievalRun` | Query, filtros, documentos recuperados e scores |
| `PromptTemplate` | Nome, versão, finalidade e schema de saída |
| `Generation` | Entrada, modelo, prompt, contexto, saída e avaliação |
| `Feedback` | Seleção, edição, nota, motivo e resultado posterior |
| `Job` | Tipo, estado, progresso, checkpoint, tentativas e erro |
| `Artifact` | Arquivo, hash, tipo, produtor e relação com o job |
| `AuditEvent` | Ação, ator, entidade, data e correlação |

### 7.1 Regras de integridade

- Um canal próprio e um canal de referência podem compartilhar o mesmo registro de plataforma, mas seus direitos e métricas são separados.
- Uma métrica sempre declara `source`, `period`, `granularity`, `dimensions`, `is_estimate` e `availability`.
- Uma geração sempre referencia o perfil do canal, o prompt, o modelo e os IDs de contexto utilizados.
- Um brief aprovado é imutável; alterações criam nova versão.
- Um artifact nunca é considerado concluído sem manifest, hash e estado de job consistente.
- Exclusão de uma fonte de conhecimento remove seus chunks do índice e invalida caches de retrieval associados.
- Toda tabela e view exposta tem RLS, grants e políticas de `SELECT`, `INSERT`, `UPDATE` e `DELETE` revisados; habilitar RLS sem policy pode retornar zero linhas sem erro.
- Policies de filhos validam também o relacionamento com o pai e o workspace; `workspace_id` isolado não impede referência cruzada por um ID válido de outro workspace.
- Funções `security definer` ficam em allowlist, com `search_path` fixo, nomes totalmente qualificados e validação explícita de workspace; uma RPC privilegiada não pode contornar o isolamento.
- `service_role` nunca vai ao navegador. Seu bypass de RLS não elimina a necessidade de grants nem de filtros de workspace no backend/worker.
- Chaves naturais possuem constraints de unicidade, por exemplo `(workspace_id, platform, external_id)` e `(video_id, metric_id, period, dimensions_hash, source_revision)`.
- JSONB de dimensões tem schema validado e hash canônico; não se cria um índice para cada combinação de dimensões sem medir cardinalidade.

### 7.2 Índices mínimos

- Canal + data de publicação.
- Vídeo + métrica + período + dimensões.
- Referência + research run + score.
- Oportunidade + canal + estado + score.
- Knowledge chunk + source version + coleção + status.
- Job + estado + próxima tentativa.
- Postgres FTS para títulos, descrições, copies e transcrições autorizadas.
- pgvector com `embedding_model`, `embedding_version` e `dimensions` compatíveis; rebuild não mistura vetores de modelos diferentes.
- Índices parciais para jobs elegíveis e filas por `next_retry_at`, evitando varrer histórico concluído.

---

## 8. Disponibilidade e semântica das métricas

### 8.1 Canais próprios autorizados

Conforme elegibilidade, escopos e disponibilidade da plataforma:

- Views, watch time e duração média de visualização.
- Impressions e CTR.
- Retenção e pontos de abandono.
- Fontes de tráfego.
- Inscritos ganhos/perdidos.
- Dados demográficos e de audiência quando disponíveis e permitidos.
- Relatórios históricos em lote quando a conta for elegível.

### 8.2 Canais e vídeos públicos de referência

Somente o que a fonte pública disponibilizar e permitir, por exemplo:

- Título, descrição, data de publicação, duração e URLs.
- Canal, thumbnails e metadados públicos.
- Views, likes e comentários públicos no momento da coleta.
- Mudanças observadas entre snapshots.

Não estão disponíveis por inferência legítima: impressions, CTR real, retenção, watch time privado, receita, demografia privada ou conversão real. O sistema deve exibir esses campos como indisponíveis.

### 8.3 Fontes de integração

- **YouTube Data API:** catálogo e metadados públicos/autorizados.
- **YouTube Analytics API:** analytics de canais próprios autorizados.
- **YouTube Reporting API:** relatórios em lote quando aplicável e elegível.
- **Importação manual:** CSV/JSON exportado pelo usuário para lacunas ou fontes externas.
- **Transcrições:** somente próprias, fornecidas pelo usuário ou obtidas por meio permitido. Não assumir disponibilidade para concorrentes.

Os escopos, quotas e políticas vigentes devem ser confirmados na documentação oficial durante a implementação. O desenho não depende de valores fixos de quota.

**Ponto de quebra corrigido:** quota do YouTube é um recurso compartilhado do projeto de API, não um orçamento infinito por canal. O `QuotaLedger` reserva custo estimado antes da chamada, registra custo real, aplica circuit breaker e impede que pesquisa de concorrentes bloqueie o sync dos canais próprios. O catálogo de métricas também guarda dimensões compatíveis, atraso de disponibilidade, granularidade e revisão; uma query não pode combinar dimensões arbitrárias e chamar o resultado de comparável. Relatórios assíncronos e dados tardios possuem estados `pending`, `partial`, `final` e `revised`.

---

## 9. Pipeline de pesquisa e recomendação

### 9.1 Etapas

1. **Definir objetivo:** canal, perfil vigente, formato, período e meta.
2. **Construir fingerprint do canal:** pilares, títulos próprios, descrições, formatos e desempenho disponível.
3. **Descobrir candidatos:** buscas controladas e expansão de referências aprovadas.
4. **Filtrar:** idioma, relevância, duplicidade, canais bloqueados e qualidade mínima.
5. **Coletar evidências:** metadados e snapshots públicos permitidos.
6. **Normalizar:** entidades, tópicos, formatos, datas e URLs.
7. **Calcular similaridade:** tópico, formato, linguagem e padrões editoriais observáveis.
8. **Analisar padrões:** títulos, capas, séries, recorrência e lacunas.
9. **Gerar hipóteses:** candidatos de episódios alinhados ao canal, não clones das referências.
10. **Pontuar e explicar:** score, confiança, evidências e penalidades.
11. **Revisar:** usuário aprova, rejeita, edita ou arquiva.
12. **Planejar:** oportunidade aprovada vira brief e item de calendário.

### 9.2 Similaridade de canais

A similaridade deve ser explicável por componentes, não apenas um número:

- Sobreposição temática.
- Semelhança de formato e duração.
- Idioma e região editorial.
- Público declarado ou inferido apenas a partir de conteúdo público, com limitação explícita.
- Recorrência de séries e abordagens.
- Proximidade com os pilares do canal-base.

Dados privados de audiência do usuário podem melhorar o fit interno, mas nunca devem ser usados para alegar sobreposição real de audiência com concorrentes.

### 9.3 Score de oportunidade

Todos os componentes são normalizados de 0 a 100 e acompanhados de explicação:

$$
Score = 0{,}25R + 0{,}20D + 0{,}15L + 0{,}15F + 0{,}10T + 0{,}10V + 0{,}05C - P
$$

Onde:

- **R:** relevância para os pilares do canal.
- **D:** demanda observável nas evidências.
- **L:** lacuna/diferenciação em relação às referências.
- **F:** fit com público, voz e formato.
- **T:** timing e recência.
- **V:** viabilidade de produção.
- **C:** confiança e cobertura das fontes.
- **P:** penalidades por risco, duplicidade, tema proibido ou evidência fraca.

Os pesos ficam versionados por política. O score ordena pesquisa; **não é previsão de views nem garantia de desempenho**.

### 9.4 Anti-cópia e qualidade editorial

- Bloquear duplicidade exata e alertar alta similaridade lexical/semântica.
- Exigir diferenciação de ângulo, promessa ou estrutura.
- Impedir geração quando a fonte não sustenta a afirmação principal.
- Sinalizar promessas absolutas, dados inventados e clickbait incompatível.
- Manter referências fora do output final quando forem usadas apenas como análise.
- Exigir aprovação humana antes de brief final ou produção.

---

## 10. Arquitetura de IA e RAG

### 10.1 Provider Router

A aplicação separa quatro papéis de modelo:

1. **Classificação/extração:** saídas estruturadas e baixo custo.
2. **Geração editorial:** títulos, briefs, copies e roteiros.
3. **Embeddings:** indexação e busca semântica.
4. **Visão/OCR:** análise de capas e texto visual.

Cada papel possui provider, modelo, limites e fallback configuráveis. Nenhum model ID fica espalhado pelo domínio. O usuário pode escolher:

- **Local:** maior privacidade para o conteúdo do prompt, limitada pelo hardware; não elimina a dependência de rede do Supabase.
- **Externo:** maior capacidade potencial, com custo e envio de dados claramente indicados.

Antes de enviar qualquer contexto a um provedor externo, a UI mostra quais tipos de dados serão enviados. Segredos, tokens e dados privados desnecessários nunca entram no prompt. Um modelo local indisponível **nunca dispara fallback para um provedor externo sem consentimento explícito**; o job fica bloqueado/recuperável. Chamadas de IA não ficam dentro de transações do Postgres: o worker reserva o job, encerra a transação, chama o modelo e persiste o resultado com uma chave idempotente.

### 10.2 RAG não é treinamento de pesos

As copies não “treinam” o modelo no sentido de fine-tuning. Elas formam uma base recuperável que condiciona cada geração. Isso permite atualizar, remover, auditar e citar conhecimento sem retreinar modelos.

### 10.3 Ciclo de vida das fontes

```text
IMPORTED → NORMALIZED → DEDUPLICATED → REVIEWED → APPROVED → INDEXED
    │             │             │           │          │
    └─────────────┴─────────────┴───────────┴──────────┴→ REJECTED/ARCHIVED
```

Níveis de curadoria:

| Nível | Significado | Uso padrão no RAG |
|---|---|---|
| L0 — bruto | Importado, sem revisão | Não |
| L1 — revisado | Estrutura e origem conferidas | Somente quando solicitado |
| L2 — aprovado | Copy/conhecimento autorizado | Sim |
| L3 — canônico | Referência principal da marca/canal | Sim, com prioridade |

### 10.4 Taxonomia das copies

- Tipo: título, hook, descrição, CTA, roteiro, anúncio, Short, post de comunidade.
- Canal, nicho, persona, idioma e tom.
- Objetivo e etapa do funil.
- Formato e duração.
- Estrutura e técnicas retóricas.
- Resultado conhecido, período e contexto; sem alegar causalidade automática.
- Direitos de uso, origem e restrições.
- Status de curadoria e versão.

### 10.5 Indexação

1. Normalizar encoding, espaços e estrutura.
2. Remover duplicatas por hash e similaridade.
3. Dividir por seções semânticas, preservando hook, desenvolvimento e CTA.
4. Criar chunks com overlap moderado e sem quebrar unidades importantes.
5. Anexar metadados de canal, tipo, idioma, status e versão.
6. Gerar embeddings em lote, com limite de custo e retry idempotente.
7. Atualizar Postgres FTS e pgvector de forma idempotente, sem segurar transação durante a chamada ao modelo.
8. Registrar `embedding_model`, `embedding_version`, `dimensions`, `chunk_hash` e `indexed_at`; uma troca de modelo cria uma nova `EmbeddingRevision`.
9. Fazer rebuild em índice/revisão separada e trocar a revisão ativa somente depois de validar recall e cobertura.

O índice vetorial é derivado e reconstruível, mas não é automaticamente correto: vetores de dimensões ou modelos diferentes não podem ser misturados, e índices aproximados precisam de avaliação de recall. A fonte e os chunks permanecem como registros auditáveis no Supabase.

### 10.6 Retrieval

```text
Pergunta/objetivo
   ↓
Reescrita controlada da query
   ↓
Filtros obrigatórios: canal, idioma, status, direitos e coleção
   ↓
Busca lexical FTS + busca vetorial
   ↓
Fusão, deduplicação e reranking
   ↓
Context Pack com limite de orçamento e diversidade de fontes
   ↓
Geração estruturada + citações + validação
```

Regras:

- L2/L3 são o padrão; L0 nunca entra silenciosamente.
- Uma fonte arquivada não pode aparecer em novas gerações.
- O filtro de workspace/canal/direitos é aplicado na consulta SQL/RPC e validado novamente antes de montar o contexto; similaridade vetorial sozinha não é autorização.
- RPCs de busca usam `security invoker` quando possível; qualquer `security definer` tem `search_path` fixo e checagem de membership explícita.
- O contexto registra chunk IDs, scores, workspace, revisão do índice e versão do embedding.
- A saída deve distinguir fato da fonte, inferência e proposta criativa.
- Se não houver contexto suficiente, o sistema declara a limitação em vez de preencher com invenção.
- Exclusão e arquivamento invalidam caches e são testados contra buscas antigas, não apenas contra a listagem da biblioteca.

### 10.7 Contrato de geração

Toda geração guarda:

- Objetivo e canal.
- Versão do Channel Profile.
- Prompt e schema de saída.
- Modelo/provider e parâmetros relevantes.
- Retrieval Run e fontes utilizadas.
- Resultado estruturado e validações.
- Avaliação do usuário e edições posteriores.

Conteúdo importado é tratado como **dado não confiável**, nunca como instrução. Prompts e ferramentas não podem ser alterados por texto encontrado em copies, descrições, comentários ou transcrições.

### 10.8 Avaliação de IA

Conjuntos de avaliação versionados por canal e idioma:

- Recall@k das fontes esperadas.
- Precisão das citações.
- Fidelidade das afirmações ao contexto.
- Cobertura de requisitos do brief.
- Taxa de saídas estruturadas válidas.
- Similaridade indevida com referências.
- Taxa de rejeição e distância entre rascunho e versão aprovada.
- Testes de prompt injection e vazamento de dados.

Nenhuma mudança de prompt, modelo ou chunking entra como padrão sem comparação com a baseline.

---

## 11. APIs e contratos locais

A API é versionada em `/api/v1`. Consultas retornam DTOs; comandos longos retornam `202 Accepted` com `job_id`. Mutações relevantes aceitam `Idempotency-Key`. Toda rota resolve `user_id` e `workspace_id` no servidor; IDs de canal/job não são suficientes para autorizar. O SSE aceita `last_event_id`, tem eventos monotônicos e permite reconstruir o estado por `GET /jobs/{id}`; perda de conexão não altera o job.

| Método e rota | Finalidade |
|---|---|
| `POST /connections/youtube/authorize` | Iniciar OAuth do YouTube para uma conexão autorizada |
| `DELETE /connections/{id}` | Revogar conexão e definir retenção dos dados |
| `GET /channels` | Listar canais e frescor dos dados |
| `PUT /channels/{id}/profile` | Criar nova versão do perfil editorial |
| `POST /channels/{id}/sync` | Enfileirar sync incremental/backfill |
| `GET /channels/{id}/analytics` | Consultar métricas normalizadas |
| `GET /videos/{id}` | Obter ficha, métricas e análises do vídeo |
| `POST /research/runs` | Iniciar pesquisa com filtros e objetivo |
| `GET /research/runs/{id}` | Consultar evidências e resultados |
| `POST /opportunities/generate` | Gerar oportunidades a partir de uma pesquisa |
| `POST /opportunities/{id}/decision` | Aprovar, rejeitar ou arquivar |
| `POST /knowledge/sources` | Importar fonte/copy e metadados |
| `POST /knowledge/sources/{id}/review` | Alterar curadoria e permissão de uso |
| `POST /knowledge/reindex` | Reindexar escopo definido |
| `POST /generations` | Gerar conteúdo com contexto e schema |
| `GET /generations/{id}/provenance` | Inspecionar fontes, prompt e modelo |
| `POST /briefs` | Criar brief a partir de oportunidade |
| `POST /briefs/{id}/approve` | Congelar versão aprovada |
| `POST /briefs/{id}/production` | Enviar intenção ao DarkForge |
| `GET /jobs` | Listar fila, histórico e erros |
| `POST /jobs/{id}/pause` | Solicitar pausa em checkpoint seguro |
| `POST /jobs/{id}/resume` | Retomar job pausado/interrompido |
| `POST /jobs/{id}/cancel` | Solicitar cancelamento idempotente |
| `GET /jobs/{id}/events` | Stream SSE de progresso e logs permitidos |

### 11.1 Erros

Formato único com `code`, `message`, `retryable`, `details`, `correlation_id` e `job_id` quando aplicável. A UI não transforma falha parcial em sucesso total.

### 11.2 Eventos de domínio

Eventos mínimos:

- `channel.connected`
- `channel.sync.completed`
- `channel.sync.partially_failed`
- `research.completed`
- `opportunity.approved`
- `knowledge.source.indexed`
- `generation.completed`
- `brief.approved`
- `production.requested`
- `job.interrupted`
- `job.failed`

Eventos carregam ID, versão, timestamp, correlation ID e referência ao agregado. Consumidores devem ser idempotentes.

---

## 12. Jobs, recovery e consistência

### 12.1 Estados

```text
QUEUED → RUNNING → SUCCEEDED
             ├──→ PAUSED → RUNNING
             ├──→ CANCEL_REQUESTED → CANCELLED
             ├──→ BLOCKED → RECOVERABLE → RUNNING
             ├──→ FAILED → QUEUED (retry)
             └──→ INTERRUPTED → RECOVERABLE → RUNNING
```

`BLOCKED` representa dependência externa indisponível (rede, Supabase, quota ou modelo), não sucesso nem falha definitiva. Um processamento local concluído sem manifest persistido fica `LOCAL_COMPLETED_PENDING_SYNC`, nunca `SUCCEEDED` global.

### 12.2 Regras

- Todo job possui tipo, payload validado, `workspace_id`, dono, prioridade e idempotency key com unicidade por escopo.
- A fila é Postgres; a reserva usa uma RPC/transação com `FOR UPDATE SKIP LOCKED` ou mecanismo equivalente. `SELECT` seguido de `UPDATE` pela UI não é fila segura.
- PostgREST não expõe magicamente `SKIP LOCKED`: a reserva precisa de uma função SQL/RPC cuidadosamente autorizada ou de conexão SQL do worker. Não se implementa a fila com chamadas REST concorrentes de leitura e atualização.
- Cada reserva grava `worker_id`, `lease_expires_at`, `heartbeat_at` e um `fencing_token` monotônico. Um worker zumbi com token antigo não pode gravar progresso, artifacts ou transições.
- Payloads de jobs são pequenos e referenciam objetos/fontes por ID; vídeos, raw responses e contextos grandes ficam no Storage ou em tabelas próprias.
- O worker renova o lease em heartbeat; jobs expirados passam por reconciliação. Não existe exactly-once distribuído: a entrega é at-least-once e todos os efeitos são idempotentes.
- Progresso é baseado em etapas reais, não em timer cosmético.
- Checkpoints são gravados após unidades de trabalho confirmadas, junto com o cursor e a revisão da fonte.
- Retry usa backoff com jitter e respeita erros não recuperáveis; quota e indisponibilidade têm políticas diferentes.
- Pause/cancel ocorre em limites seguros; a UI informa quando a solicitação foi apenas registrada.
- Na abertura da aplicação e em um reconciler periódico, jobs `RUNNING` sem heartbeat válido passam por reconciliação; não depende só de o usuário abrir a UI.
- Um job interrompido só é retomado quando seu checkpoint, fencing token e artifacts forem válidos.
- Nenhuma chamada ao YouTube, Storage ou modelo fica dentro de uma transação longa do Postgres.
- A transição de estado e o `OutboxEvent` são gravados na mesma transação. Um publicador separado entrega eventos com inbox/deduplicação; Realtime/SSE é apenas notificação, nunca prova de conclusão.
- Outbox e logs têm retenção, limpeza e payload mínimo; não guardar tokens, copies completas ou dados pessoais desnecessários em eventos imutáveis.
- Escrita de artifact usa objeto temporário/staging, checksum, manifest e promoção para `ready`; uma varredura remove órfãos e marca uploads incompletos.
- Nenhum output é marcado como pronto antes da confirmação do pipeline e da persistência do manifest no Supabase.

### 12.3 Tipos de jobs

- Sync de canal, vídeos e métricas.
- Backfill histórico.
- Pesquisa e atualização de referências.
- OCR/visão de thumbnails.
- Indexação e reindexação RAG.
- Geração e avaliação de conteúdo.
- Upload, exportação e backup lógico.
- Reconciliação de leases, Storage e DarkForge.
- Produção DarkForge.

### 12.4 Concorrência

- Um sync mutuamente exclusivo por conexão/cursor, com constraint/lease no banco.
- Limite de pesquisas simultâneas por quota e por workspace.
- Limite de modelos locais por memória/GPU.
- Prioridade para ações iniciadas pelo usuário sobre manutenção.
- Scheduler nunca duplica um job ativo equivalente.
- Workers não usam conexão por request em loop infinito: pool com limites, timeout, SSL e retry de conexão; o pooler adequado é escolhido para o tipo de workload.
- A UI pode reconectar o SSE e pedir eventos desde `last_event_id`; o estado atual sempre pode ser reconstruído por consulta ao Postgres.

---

## 13. Estrutura lógica proposta do repositório

Esta árvore descreve a organização futura; os arquivos não fazem parte desta entrega.

```text
darkforge-channel-os/
├── apps/
│   ├── web/                    # Next.js, páginas e componentes
│   └── api/                    # FastAPI, rotas e composição
├── core/
│   ├── channels/
│   ├── analytics/
│   ├── research/
│   ├── opportunities/
│   ├── knowledge/
│   ├── generation/
│   ├── editorial/
│   └── darkforge_gateway/
├── workers/
│   ├── sync/
│   ├── research/
│   ├── indexing/
│   └── production/
├── adapters/
│   ├── youtube/
│   ├── ai_providers/
│   ├── vision_ocr/
│   ├── supabase_db/
│   ├── supabase_storage/
│   └── supabase_auth/
├── contracts/
│   ├── api/
│   ├── events/
│   └── schemas/
├── prompts/
│   ├── analysts/
│   ├── generation/
│   └── evaluation/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contracts/
│   ├── evaluation/
│   └── e2e/
├── docs/
│   ├── adr/
│   ├── api/
│   ├── metrics/
│   └── runbooks/
└── scripts/
    ├── backup/
    ├── diagnostics/
    └── packaging/
```

Dependências seguem uma direção: `web → api → application/domain`; adapters implementam portas da aplicação. O domínio não importa FastAPI, React, SDK de YouTube ou detalhes do Supabase. Migrations SQL, policies RLS, grants e funções RPC ficam versionados junto ao schema; a UI nunca administra o banco.

---

## 14. Persistência Supabase e arquivos temporários

### 14.1 Divisão obrigatória de responsabilidades

| Tipo de dado | Onde fica | Observação |
|---|---|---|
| Canais, vídeos, métricas, pesquisas, briefs e copies | Supabase Postgres | Fonte de verdade relacional |
| Embeddings, chunks e índices de busca | Supabase Postgres + pgvector/FTS | Revisão e RLS junto aos dados |
| Jobs, leases, outbox, quotas e auditoria | Supabase Postgres | Não usar Realtime como fila |
| Thumbnails, raw JSON, exports e manifests | Supabase Storage privado | Metadados e hash no Postgres |
| Vídeos e artifacts grandes | Supabase Storage ou storage de produção explicitamente escolhido | Nunca base64/`bytea` no Postgres |
| Cache, downloads para FFmpeg e arquivos parciais | Filesystem local | Descartável e reconciliado |
| Logs de diagnóstico do processo local | Filesystem local + exportação opcional | Sem segredos; não é fonte de verdade |

“Armazenar tudo no Supabase” significa usar o ecossistema Supabase de forma adequada. Colocar vídeos, JSON bruto e imagens em colunas relacionais tornaria backup, queries e custo insustentáveis.

### 14.2 Buckets e objetos

Buckets privados separados por classe de dado, por exemplo `knowledge`, `references`, `exports` e `production`. O caminho contém `workspace_id` e um ID opaco, nunca apenas um nome fornecido pelo usuário. Cada objeto possui registro `StorageObject` com `bucket`, `path`, `workspace_id`, `sha256`, `size`, `content_type`, `status`, `retention_until` e `created_by_job`.

O fluxo é `uploading → verifying → ready`; falha vira `failed/orphaned` e entra na limpeza. A UI recebe signed URL curta ou proxy autorizado, nunca uma URL pública permanente. Policies de Storage verificam membership e path; o service role só é usado no servidor.

Uploads de vídeo e arquivos grandes não passam pelo processo FastAPI nem viram base64: usar upload direto autorizado ao Storage, preferencialmente resumable, com limite de tamanho, checksum e retomada. A API apenas cria a intenção, valida a permissão e confirma o manifest. Downloads para FFmpeg usam URL curta, arquivo temporário e limpeza garantida.

Banco e Storage não têm transação distribuída. Por isso, o manifest só fica `ready` após checksum e confirmação do objeto; um reconciler trata objeto sem registro, registro sem objeto e upload interrompido.

### 14.3 Diretório local descartável

```text
%LOCALAPPDATA%\DarkForge\
├── cache\
├── tmp\
│   ├── downloads\
│   └── renders\
├── logs\
├── diagnostics\
└── settings\             # somente preferências não secretas; não é o banco
```

Projetos e vídeos podem ser processados em pastas escolhidas pelo usuário, fora do diretório de instalação. Após o upload e a verificação, temporários são removidos conforme a política de retenção. Se o PC ficar sem rede, um render pode terminar localmente, mas seu estado global permanece `LOCAL_COMPLETED_PENDING_SYNC` até o manifest e o artifact serem confirmados no Supabase.

### 14.4 Custos e retenção

O desenho precisa medir tamanho do banco, Storage, egress, chamadas de Auth/Realtime e índices vetoriais. Raw payloads e thumbnails de referências têm retenção e política de refresh compatíveis com os termos da fonte. Não se guarda tudo para sempre por padrão.

---

## 15. Segurança, privacidade e conformidade

### 15.1 Identidade, sessão e autorização

- Supabase Auth autentica o usuário; o OAuth do YouTube apenas autoriza uma conexão de plataforma e não substitui a sessão do produto.
- A API local valida o JWT/sessão e resolve o workspace no servidor. O navegador nunca recebe `service_role`, chave de banco ou segredo de OAuth.
- `WorkspaceMember` e roles ficam em tabela protegida; role em `user_metadata` editável não é fonte de autorização.
- RLS é obrigatória em tabelas, views e Storage. Policies cobrem leitura e escrita, inclusive relações filhas e buscas vetoriais.
- O backend/worker com `service_role` aplica `workspace_id` e permissões em cada query, pois essa chave ignora RLS. Bypass não dispensa grants nem revisão de privilégios.
- Funções `security definer` são exceção auditada, com `search_path` fixo, objetos qualificados e validação de membership; não se expõe uma RPC genérica de SQL.
- Sessão local usa cookie `HttpOnly`, `SameSite` adequado, rotação e expiração; a origem exata da UI é allowlistada.
- Tokens OAuth e chaves externas ficam criptografados no servidor/cofre, com acesso por conexão e redaction em logs.
- Refresh token, expiração, revogação e rotação têm estados próprios; um `401` do YouTube não é tratado como canal vazio nem dispara múltiplos refreshes concorrentes.
- A chave de criptografia dos tokens não fica no mesmo registro do token nem no frontend; perda da chave exige fluxo de reconexão, não descriptografia parcial silenciosa.
- O callback OAuth valida `state`, `nonce`/PKCE quando aplicável, origem e workspace de destino; o código de autorização nunca é registrado em logs.

### 15.2 Segurança da API local e da rede

- Bind padrão somente em `127.0.0.1`; exposição em rede exige ação explícita, TLS e autenticação forte.
- Validação de `Origin`, proteção CSRF e CORS restrito à origem local da UI.
- Validação de payloads, uploads, tamanho, extensão, MIME e limites de descompressão.
- Proteção contra SSRF ao buscar URLs externas: allowlist, validação de destino e bloqueio de redes internas.
- Rate limit por usuário/workspace para comandos custosos e proteção contra jobs duplicados.
- TLS e timeouts para Supabase; certificados e erros de rede não são tratados como dados vazios.
- Auditoria de conexões, aprovações, exports, mudanças de role e envios à produção.

### 15.3 Privacidade e dependência de nuvem

- Modo local de IA como opção padrão quando o hardware suportar, sem prometer que o restante do produto funciona offline.
- Indicação clara antes de enviar dados a provedores externos e antes de qualquer fallback de modelo.
- Minimização de contexto e redaction de dados sensíveis.
- Comando de exclusão por canal, fonte e workspace, incluindo chunks, embeddings, Storage e caches.
- A exclusão também precisa considerar retenção de provedores de IA, exports já baixados e backups; a UI informa o que foi removido imediatamente e o que expira conforme a retenção.
- Exportação portátil dos dados do usuário e dos manifests.
- Diagnostics com revisão prévia e redaction.
- A tela informa quando o Supabase está indisponível e distingue “não há dados” de “não foi possível consultar”.

### 15.4 Plataforma e direitos autorais

- Usar APIs oficiais e os escopos mínimos necessários.
- Respeitar quotas, políticas, termos e limitações de armazenamento/refresh das fontes.
- Não contornar autenticação ou restrições técnicas.
- Não apresentar dados públicos como analytics privados.
- Guardar origem, licença e permissão das fontes de conhecimento.
- Referências de concorrentes servem para análise; não implicam licença de reuso.
- Geração de títulos/capas deve passar por checagem de originalidade e revisão humana.

---

## 16. Interface e experiência

### 16.1 Navegação principal

```text
Dashboard
├── Canais
│   ├── Visão geral
│   ├── Vídeos
│   ├── Analytics
│   ├── Perfil editorial
│   └── Referências
├── Pesquisa
│   ├── Canais semelhantes
│   ├── Vídeos e títulos
│   ├── Capas
│   └── Evidências
├── Oportunidades
├── Calendário
├── Briefs e Gerações
├── Knowledge / Copies
├── Produção DarkForge
├── Jobs e Qualidade
└── Configurações
```

### 16.2 Princípios de UX

- O usuário sempre sabe de qual canal, período e versão editorial está falando.
- Toda recomendação abre um painel “Por quê?” com evidências e limitações.
- Dados ausentes não são substituídos por zeros ou estimativas silenciosas.
- Jobs longos não bloqueiam a navegação.
- Aprovação, rejeição e edição são ações rápidas e reversíveis quando possível.
- O usuário consegue inspecionar o contexto RAG sem ver segredos ou prompts internos sensíveis.
- Tema claro/escuro e identidade visual são tokens, não regras espalhadas nos componentes.
- Acessibilidade: navegação por teclado, foco visível, contraste, labels e alternativa textual para análises visuais.

### 16.3 Dashboard inicial

Prioridade de informação:

1. Estado das conexões e frescor dos dados.
2. Jobs que exigem atenção.
3. Oportunidades aguardando revisão.
4. Desempenho dos canais e mudanças relevantes.
5. Próximos itens do calendário.
6. Alertas de quota, storage, modelo e backup.

Evitar encher a página com números sem ação. Cada cartão deve levar a uma decisão ou investigação.

---

## 17. Performance, quotas e capacidade

- Sync incremental por padrão; backfill somente sob demanda ou agendamento.
- Paginação e batch nas integrações.
- Cache com TTL por tipo de recurso e invalidação por sync.
- Orçamento de quota por conexão e por research run.
- Compressão de raw payloads antigos e política de retenção configurável.
- Consultas de analytics por projeções agregadas, sem varrer raw JSON na UI.
- Embeddings em lote e reindexação parcial por source version.
- Limite de concorrência de visão/IA local conforme RAM/VRAM.
- Lazy loading de thumbnails e virtualização de listas grandes.
- Cancelamento de requests da UI sem cancelar automaticamente o job no servidor.
- Policies RLS entram no plano de query: indexar colunas usadas em membership/joins, evitar funções voláteis por linha e medir analytics com RLS ativa, não apenas com service role.
- Região do Supabase próxima dos usuários/workers, timeouts e circuit breaker para latência; indisponibilidade ou pausa do projeto é um estado operacional visível, não uma exceção desconhecida.
- Rate limit de comandos custosos é compartilhado no Postgres quando houver mais de um worker; limite apenas no processo local pode ser contornado por múltiplas instâncias.

Critério para escalar infraestrutura: medir primeiro. O Supabase/Postgres é a escolha inicial, não uma promessa de capacidade infinita. Monitorar conexões, CPU, IOPS, tamanho de índices, latência de RLS, Storage, egress e custo de embeddings. Particionamento de fatos, retenção, agregações e um pooler adequado entram antes de trocar de banco. Redis, Qdrant ou outro serviço só entram por um gargalo medido e com uma fronteira de consistência documentada.

---

## 18. Observabilidade e operação

### 18.1 Logs e diagnóstico

- Logs estruturados com correlation ID, job ID, canal e etapa.
- Níveis consistentes e redaction de tokens, cookies e conteúdo sensível.
- Histórico de comandos e transições de jobs.
- Métricas de duração, retries, quota, falhas por adapter e tamanho da fila.
- Pacote de diagnóstico exportável com informações de versão, ambiente e logs permitidos.
- Tela de Qualidade com erros reais, última sincronização e artifacts afetados.

### 18.2 Backup e restore

- Usar backups/PITR do Supabase conforme o plano contratado; não presumir retenção ou recuperação que o plano não oferece.
- Export lógico versionado de dados e manifests para portabilidade, separado do backup gerenciado.
- Backup do Postgres não inclui automaticamente os objetos do Storage: há inventário, política de retenção e cópia/versionamento dos objetos essenciais.
- Manifest com versão da aplicação, schema, revisões de embedding e checksums.
- Teste periódico de restore em projeto isolado, incluindo RLS, Auth/memberships, Storage e jobs; backup não testado não conta como recuperação.
- Antes de migration destrutiva, criar ponto de recuperação e validar o procedimento de rollback/roll-forward.
- RPO/RTO e retenção são decisões explícitas de produto, não promessas implícitas do fornecedor.

### 18.3 Atualização

- Migrations SQL versionadas, revisadas e aplicadas por pipeline; nenhuma alteração manual de produção fica fora do histórico.
- Compatibilidade de contratos entre API e workers durante upgrade.
- Rollback de aplicação documentado; rollback de banco somente por estratégia explícita.
- Nenhum instalador/launcher apaga dados locais ou remotos ao atualizar ou desinstalar sem confirmação específica.

---

## 19. Estratégia de testes

### 19.1 Testes automatizados

- **Unitários:** scores, normalização, curadoria, estados de jobs e políticas anti-cópia.
- **Contrato:** schemas de API, eventos e saídas estruturadas de IA.
- **Integração:** adapters YouTube com respostas gravadas/mocks, Supabase Postgres, Storage, Auth e fila.
- **Migrações:** upgrade de schemas anteriores, policies, grants e preservação de dados.
- **RLS:** dois workspaces, dois usuários, roles diferentes, IDs cruzados, RPCs e Storage; toda tentativa indevida deve falhar ou retornar vazio conforme o contrato.
- **RAG:** recall, citações, filtros de status, exclusão, rebuild e separação de revisões de embedding.
- **Fila:** dois workers competindo, lease expirado, fencing token antigo, retry, outbox duplicada e reconciliação.
- **Rede:** Supabase fora do ar, timeout, conexão perdida no meio do sync/upload e retorno sem duplicar efeitos.
- **Segurança:** Origin/CSRF, SSRF, path traversal, uploads, redaction e vazamento de `service_role`.
- **E2E:** fluxos principais no navegador, incluindo estado offline/degradado explícito.

### 19.2 Testes de recovery

- Fechar a aplicação durante sync, indexação, upload e produção.
- Reiniciar e reconciliar jobs sem heartbeat, inclusive sem abrir a UI.
- Retomar de checkpoint sem duplicar artifacts ou fatos de métricas.
- Pausar, cancelar e repetir comandos com a mesma idempotency key.
- Simular quota esgotada, token expirado, disco cheio, modelo indisponível e Supabase indisponível.
- Derrubar o worker depois do efeito externo e antes do commit; o retry deve reconciliar, não duplicar.
- Confirmar que nenhuma falha aparece como sucesso e que cache local nunca é apresentado como dado confirmado.

### 19.3 Testes de qualidade editorial

- Golden dataset de títulos e capas com análises esperadas.
- Casos de cópia excessiva e promessa sem evidência.
- Canais com poucos dados e métricas ausentes.
- Copies com instruções maliciosas para prompt injection.
- Mudança de tema editorial sem contaminar recomendações históricas.

---

## 20. Roadmap por fases e gates

### Fase 0 — Fundações e contratos

**Entrega:** ADRs, catálogo de métricas, schemas, modelo de dados, políticas de fontes e protótipo navegável dos fluxos.  
**Gate:** escopo do MVP, disponibilidade de dados e contratos aprovados; nenhuma regra crítica implícita.

### Fase 1 — Shell local e núcleo de execução

**Entrega:** Web UI local, API, Supabase Auth, Postgres/migrations, RLS, Storage, configuração, Command Bus, Job Manager, outbox e recovery.  
**Gate:** abrir no navegador, autenticar, isolar dois workspaces, executar job real de teste, pausar, retomar, cancelar, reiniciar e recuperar sem false success; simular Supabase indisponível sem gravar sucesso falso.

### Fase 2 — Canais próprios e Analytics Center

**Entrega:** OAuth, inventário, sync incremental/backfill, dashboards e ficha de vídeo.  
**Gate:** dados reais autorizados com origem/frescor, métricas ausentes corretamente marcadas e histórico persistente.

### Fase 3 — Research Explorer

**Entrega:** pesquisa pública, candidatos semelhantes, curadoria de referências, snapshots e evidências.  
**Gate:** toda referência rastreável, quota controlada e nenhuma métrica privada inferida como fato.

### Fase 4 — Title e Thumbnail Intelligence

**Entrega:** análise estrutural de títulos, OCR/visão de capas, briefs e checagem de similaridade.  
**Gate:** análise explicável, referências identificadas e geração original sem duplicidade exata.

### Fase 5 — Knowledge/RAG Studio

**Entrega:** importação, curadoria L0–L3, chunks, busca híbrida, proveniência e avaliação.  
**Gate:** fonte aprovada recuperada corretamente, fonte arquivada excluída e citações verificáveis.

### Fase 6 — Oportunidades e Editorial Studio

**Entrega:** analistas, score, geração de episódios, briefs, calendário e feedback.  
**Gate:** recomendação com evidências, limitações e aprovação; edição do usuário preservada como nova versão.

### Fase 7 — Integração com produção DarkForge

**Entrega:** brief aprovado convertido em intenção de produção, acompanhamento de jobs e artifacts.  
**Gate:** produção real iniciada pela UI, progresso, pause/resume/cancel, recovery e output válido sem duas fontes de verdade.

### Fase 8 — Hardening e empacotamento

**Entrega:** backup/restore Postgres + Storage, diagnostics, testes de RLS/fila/rede, instalação local e launcher opcional.  
**Gate:** instalação limpa, upgrade sem perda de dados, restore testado em projeto isolado, isolamento entre workspaces comprovado e fluxo completo repetível.

---

## 21. Definição do MVP

O MVP deve incluir somente o caminho que fecha valor editorial:

1. Um workspace autenticado no Supabase e vários canais próprios.
2. Supabase Auth, memberships e RLS testados antes de qualquer dado real.
3. OAuth e sync de catálogo/métricas disponíveis com cursor persistente.
4. Dashboard de portfólio, canal e vídeo.
5. Pesquisa pública com lista curada de referências e orçamento de quota.
6. Análise de títulos e análise básica de capas.
7. Biblioteca de copies com curadoria e RAG citável em pgvector.
8. Geração de oportunidades com score e evidências.
9. Brief editável/aprovável e exportação.
10. Fila Postgres persistente, logs, recovery, Storage e backup/restore.

Ficam para depois: publicação automática, previsão de desempenho, fine-tuning, colaboração multiusuário, dezenas de plataformas, geração final de capas e automações autônomas sem supervisão.

---

## 22. Critério de aceite ponta a ponta

O fluxo abaixo deve ser executado em uma instalação limpa, com um projeto Supabase de teste e dois workspaces, antes de considerar o produto utilizável:

1. Iniciar a aplicação no PC e abrir a interface pelo navegador.
2. Autenticar no Supabase, entrar no workspace e confirmar que outro usuário/workspace não aparece em consultas, RPCs ou Storage.
3. Conectar um canal de teste autorizado.
4. Sincronizar canal, vídeos e métricas disponíveis.
5. Ver origem, período e última atualização em cada visão.
6. Confirmar que métricas indisponíveis não aparecem como zero.
7. Criar/editar o perfil editorial e registrar uma mudança de tema.
8. Pesquisar canais semelhantes e aprovar um conjunto de referências.
9. Abrir evidências de títulos e capas sem confundir dado público com privado.
10. Importar copies, revisar, aprovar e indexar.
11. Gerar oportunidades e inspecionar score, fontes, limitações e contexto RAG.
12. Rejeitar uma sugestão, editar outra e aprovar uma terceira.
13. Criar brief e verificar que a aprovação congela a versão.
14. Iniciar uma produção DarkForge a partir do brief.
15. Acompanhar progresso real, pausar, retomar e cancelar em jobs distintos.
16. Fechar a aplicação durante um job e abrir novamente.
17. Confirmar estado `INTERRUPTED/RECOVERABLE`, retomar e concluir sem duplicar output.
18. Abrir o artifact final e o relatório de qualidade.
19. Provocar um erro real e verificar mensagem, log e retry apropriado.
20. Derrubar a conectividade com o Supabase durante sync e upload; confirmar `BLOCKED/RECOVERABLE`, ausência de sucesso falso e recuperação sem duplicidade.
21. Reiniciar novamente e confirmar histórico, configurações e calendário.
22. Fazer backup do Postgres e do Storage, restaurar em projeto isolado e validar dados, RLS, arquivos e jobs.

**Gate absoluto:** nenhum false success, nenhuma perda silenciosa de dados e nenhuma recomendação sem proveniência mínima.

---

## 23. Riscos e pontos de quebra

Esta tabela é uma revisão de falhas, não uma lista genérica de riscos. Cada item precisa de teste ou evidência antes do gate correspondente.

| Ponto de quebra | Como a arquitetura falha | Correção obrigatória |
|---|---|---|
| Dependência de rede/Supabase | UI local parece funcionar, mas escritas somem ou ficam desencontradas | Estado degradado explícito, timeout, retry, `BLOCKED/RECOVERABLE` e nenhum sucesso sem commit |
| Cache local tratado como banco | PC reinicia ou troca de máquina e o usuário perde dados | Cache somente leitura/descartável; Supabase é a única fonte de verdade |
| RLS incompleta | Usuário vê ou altera outro workspace; ou policies retornam zero linhas e a UI mostra “sem dados” | Policies por operação, testes com dois workspaces e distinção entre vazio e erro |
| `service_role` no backend | Bypass de RLS vira vazamento por uma query sem filtro | Chave só no servidor, escopo obrigatório, grants mínimos e revisão de cada repositório |
| RPC `security definer` | Função privilegiada contorna isolamento ou sofre `search_path` hijack | Allowlist, `search_path` fixo, objetos qualificados e membership explícito |
| Auth confundida com YouTube OAuth | Token da plataforma é usado como sessão ou role | Supabase Auth + memberships separados das conexões OAuth |
| Fila ingênua | Dois workers executam o mesmo job; worker morto deixa job preso | `SKIP LOCKED`, lease, heartbeat, fencing token, reconciler e idempotência |
| Efeito antes do commit | Retry duplica pesquisa, geração, upload ou produção | Chaves idempotentes, outbox/inbox e reconciliação de efeitos externos |
| Transação durante chamada externa | Locks e conexões ficam presos esperando YouTube/IA/Storage | Reservar/commitar, chamar fora da transação e persistir resultado depois |
| Realtime/SSE como prova | Evento perdido deixa UI eternamente em “processando” | Outbox, `last_event_id`, replay e consulta de estado atual |
| Postgres usado como blob | Vídeos e raw JSON inflam banco, backup e latência | Storage privado para binários; Postgres guarda metadados e manifests |
| Banco e Storage fora de sincronia | Registro aponta para objeto ausente ou objeto órfão ocupa espaço | Estados de upload, checksum, manifest `ready` e reconciler |
| Backup incompleto | Restore traz tabelas, mas perde arquivos, Auth ou embeddings | Backup/PITR + inventário/cópia de Storage + teste de restore completo |
| Migration destrutiva | Upgrade apaga dados ou deixa workers incompatíveis | Migrations versionadas, ponto de recuperação, compatibilidade e roll-forward |
| Quota do YouTube | Research consome a quota e impede sync dos canais próprios | `QuotaLedger`, reserva, circuit breaker, prioridade e backfill incremental |
| Métricas incompatíveis | Query combina dimensões inválidas ou dados tardios parecem definitivos | Catálogo de métricas, validação de dimensões, estados `partial/final/revised` |
| Cursor e fatos não atômicos | Retry duplica fatos ou pula páginas | Upsert por chave natural, revisão da fonte e commit cursor+fatos |
| Embeddings misturados | Troca de modelo/dimensão corrompe busca e recall | `EmbeddingRevision`, dimensão/modelo no registro e rebuild isolado |
| Retrieval sem autorização | Busca vetorial retorna chunk de outro canal/workspace | Filtro SQL/RLS antes do contexto e validação posterior dos chunk IDs |
| Fallback de IA silencioso | Conteúdo privado vai para provedor externo sem consentimento | Fallback explícito, bloqueio recuperável e indicação de dados enviados |
| Custo de IA/embeddings | Reindexações e retries geram cobrança sem limite | Orçamento por job/workspace, deduplicação por hash e métricas de custo |
| Conexões esgotadas | Workers locais abrem conexões demais e derrubam o banco | Pool limitado, timeouts, pooler adequado e backpressure |
| DarkForge com segunda verdade | SQLite legado e Supabase divergem sobre jobs/briefs | Single-writer, adapter de migração e proibição de dual-write permanente |
| Escopo crescer demais | Produto incompleto | MVP e gates por fase |
| Alucinação/cópia/prompt injection | Recomendação sem base ou risco editorial/jurídico | RAG, schemas, citações, similaridade, ferramentas restritas e aprovação humana |

---

## 24. ADRs que devem ser registrados antes do código

1. **ADR-001:** Web UI local como interface principal; EXE somente como launcher opcional.
2. **ADR-002:** Monólito modular e workers, em vez de microserviços.
3. **ADR-003:** Um Command Bus e um Job Manager compartilhados com o DarkForge.
4. **ADR-004:** Supabase Postgres como fonte transacional única; SQLite legado não é segunda verdade.
5. **ADR-005:** APIs oficiais primeiro e limites explícitos para dados públicos.
6. **ADR-006:** RAG com curadoria e proveniência, sem fine-tuning no MVP.
7. **ADR-007:** Provider Router para IA local e externa, sem fallback externo silencioso.
8. **ADR-008:** Aprovação humana obrigatória para brief e produção.
9. **ADR-009:** Versionamento de perfil editorial, prompts, scores, fontes e embeddings.
10. **ADR-010:** pgvector como projeção reconstruível, com revisão e RLS, não fonte independente de verdade.
11. **ADR-011:** Supabase Auth, memberships e RLS como fronteira de autorização.
12. **ADR-012:** Supabase Storage privado para binários; filesystem local somente para temporários/cache.
13. **ADR-013:** Fila Postgres com lease, fencing, outbox e idempotência; Realtime não é fila.
14. **ADR-014:** Estratégia de backup/PITR, Storage e restore testado com RPO/RTO explícitos.
15. **ADR-015:** Comportamento de rede indisponível: modo degradado explícito, sem sucesso local falso.

---

## 25. Decisões de produto a confirmar na implementação

Estas perguntas não impedem a arquitetura, mas devem ser respondidas antes de fechar o MVP:

- Quantidade aproximada de canais, vídeos e referências esperada.
- Hardware do PC, especialmente RAM e GPU, para definir modelos locais.
- Região, plano, limites de conexão, Storage, egress e PITR do Supabase.
- RPO/RTO, retenção e orçamento mensal de banco, Storage e IA.
- Necessidade de leitura degradada sem rede; operação totalmente offline não é compatível com a fonte de verdade remota sem um projeto separado de sincronização.
- Escopo inicial somente YouTube ou adapters adicionais já no primeiro ciclo.
- Estado real do núcleo DarkForge, inclusive qualquer SQLite legado, e quais contratos já existem.
- Necessidade de publicação/exportação direta para a plataforma em fases futuras.
- Política de retenção de raw payloads, thumbnails e transcrições.
- Idiomas dos canais e das copies.
- Nome final do produto e identidade visual.

---

## 26. Resultado arquitetural esperado

Ao final, o Channel OS deve ser uma camada de inteligência e gestão sobre um núcleo de execução único:

```text
DADOS AUTORIZADOS + REFERÊNCIAS PÚBLICAS + CONHECIMENTO CURADO
                              ↓
                 ANALYTICS + PESQUISA + RAG
                              ↓
          OPORTUNIDADES EXPLICÁVEIS E BRIEFS APROVADOS
                              ↓
                 PRODUÇÃO DARKFORGE RASTREÁVEL
                              ↓
             RESULTADOS E FEEDBACK PARA NOVAS ANÁLISES
```

A característica central não é “ter muitos agentes”, e sim **fechar o ciclo editorial com dados confiáveis, contexto versionado, execução recuperável e controle humano**.

---

## 27. Veredito da revisão crítica

A versão anterior tinha uma boa separação de domínio, mas **não estava pronta para implementação**: trocar o nome do banco sem mudar fila, arquivos, autenticação e recovery apenas deslocaria o problema. Os maiores erros eram tratar o PC como banco durável, presumir que jobs locais seriam suficientes, deixar binários no filesystem e não definir uma fronteira de autorização do Supabase.

A arquitetura corrigida fica assim:

```text
Next.js local
   ↓ API local autenticada
Casos de uso + Command Bus
   ↓
Supabase Postgres/RLS ── pgvector/FTS
   ├── Auth + memberships
   ├── fila + leases + outbox
   └── Storage privado + manifests
            ↓
     workers locais e DarkForge
```

### 27.1 O que ainda pode quebrar mesmo com Supabase

Supabase não resolve automaticamente autorização, idempotência, quota, consistência entre banco e Storage, custo de IA ou qualidade de RAG. Esses pontos continuam sendo responsabilidade do produto. Em particular, não é aceitável:

- marcar um job como concluído porque o processo local terminou, sem commit remoto;
- usar `service_role` como atalho para não escrever policies e filtros;
- chamar uma RPC de busca sem validar workspace e direitos;
- considerar um evento Realtime como confirmação de persistência;
- fazer upload de um artifact e esquecer o manifest/checksum;
- trocar o modelo de embedding sem criar uma revisão nova;
- prometer backup sem testar restore de Postgres **e** Storage;
- manter o SQLite do DarkForge escrevendo nas mesmas entidades do Supabase.

### 27.2 Ordem de implementação que reduz o risco

1. **Schema e contratos:** workspaces, memberships, canais, métricas, jobs, outbox, StorageObject e revisões de embedding.
2. **Auth e RLS:** provar isolamento com usuários e workspaces cruzados antes de importar dados reais.
3. **Fila e recovery:** provar concorrência, lease expirado, retry, fencing e outbox antes de conectar IA ou YouTube.
4. **Storage e manifests:** provar upload interrompido, checksum, órfãos, signed URLs e exclusão.
5. **Sync YouTube:** cursor transacional, quota ledger, métricas desconhecidas e backfill.
6. **RAG:** curadoria, pgvector, filtros autorizados, citações, rebuild e avaliação.
7. **Editorial e DarkForge:** aprovação, single-writer, artifacts e reconciliação.
8. **UI completa e empacotamento:** somente depois dos gates de segurança, recovery e restore.

### 27.3 Gate de “pronto para codificar o produto”

A implementação do produto só deve avançar quando houver um projeto Supabase de teste, migrations e policies versionadas, dois usuários/workspaces para testes de isolamento, um worker de fila com recovery demonstrado e um restore de dados + arquivos executado com sucesso. Esta entrega continua sendo documental: nenhum desses testes foi executado aqui e nenhuma integração foi conectada.
