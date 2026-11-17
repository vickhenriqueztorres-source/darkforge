# SP-00 — Fundações, auditoria e contratos

**Estado inicial:** NOT_STARTED  
**Depende de:** PRD e arquitetura  
**Desbloqueia:** SP-01  
**Objetivo:** conhecer o código real, fechar contratos críticos e preparar validação antes de escrever funcionalidades.

## 1. Escopo

Inclui auditoria do repositório e do DarkForge existente, ADRs, glossário, máquinas de estado, catálogo de métricas, política de fontes, contratos de integração, estratégia de testes e protótipo navegável. Não inclui implementação de sync, RAG ou produção.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-00-T01 | Ler PRD, arquitetura, instruções do repositório e convenções existentes | Mapa de módulos, comandos e restrições | O agente sabe onde ficam UI, núcleo, workers, testes e migrations; não presume estrutura |
| SP-00-T02 | Auditar o núcleo DarkForge | Inventário de Command Bus, Job Manager, Scheduler, pipeline, artifacts e persistência | Contratos reais e lacunas estão listados; qualquer SQLite legado foi localizado |
| SP-00-T03 | Registrar ADRs obrigatórios | ADR-001 a ADR-015 ou equivalentes locais | Web UI, monólito, fila única, Supabase, RLS, Storage, RAG, IA, aprovação e backup têm decisão explícita |
| SP-00-T04 | Formalizar glossário e estados | Vocabulário e state machines de sync, job, fonte, oportunidade, brief e artifact | Não há estados contraditórios; `unknown`, `partial`, `blocked`, `interrupted` e `ready` têm significado |
| SP-00-T05 | Criar catálogo de métricas e política de fontes | Métricas, dimensões, granularidade, origem, retenção e disponibilidade | Cada métrica tem semântica e comportamento quando ausente/atrasada; público e privado são separados |
| SP-00-T06 | Desenhar contratos de domínio e integração | Schemas de comandos, eventos, APIs, YouTube, IA, RAG e DarkForge | Contratos têm IDs, versão, workspace, idempotência e erros; UI não depende de FFmpeg/SQL privilegiado |
| SP-00-T07 | Preparar avaliação de IA/RAG | Golden datasets e rubricas | Há casos de título, capa, cópia, prompt injection, poucos dados, fonte arquivada e citação |
| SP-00-T08 | Criar protótipo navegável dos fluxos críticos | Fluxos de onboarding, pesquisa, oportunidade, brief, jobs e erro | O protótipo cobre estados vazio/loading/parcial/erro/offline e não apresenta métricas fictícias como reais |
| SP-00-T09 | Preparar ambiente e plano de testes | Matriz de ambientes, dados de teste, quotas e testes de falha | Existe projeto Supabase de teste, dois usuários/workspaces planejados e ambiente de restore |
| SP-00-T10 | Fazer revisão de escopo e rastreabilidade | Matriz inicial preenchida e registro de decisões | Todo requisito MVP tem subplano e teste; desvios estão explícitos |

## 3. Perguntas que a auditoria deve responder

- O Job Manager existente pode persistir no Supabase ou será substituído por um manager único?
- Quem é o escritor de cada entidade hoje?
- O executor aceita comandos idempotentes e informa progresso real?
- Como pause/resume/cancel funcionam de fato?
- O que é artifact válido e onde seu manifest é gravado?
- Quais métricas o YouTube realmente disponibiliza para os canais de teste?
- Quais dados podem ser retidos e por quanto tempo?
- Quais modelos de IA/visão cabem no hardware previsto?

Não responder essas perguntas com suposições. Se o código não estiver disponível, registrar bloqueio e limitar o trabalho a contratos independentes.

## 4. Entregáveis obrigatórios

- ADRs versionados.
- Inventário do núcleo e mapa de single-writer.
- Catálogo de métricas e política de fontes.
- Schemas/contratos versionados.
- State machines e catálogo de erros.
- Golden datasets e plano de avaliação.
- Protótipo dos fluxos e estados.
- Matriz de rastreabilidade inicial.
- `state.md` atualizado com evidências.

## 5. Gate G0

Só avançar quando:

- escopo do MVP estiver confirmado;
- disponibilidade de dados e limitações estiverem documentadas;
- fronteira entre Channel OS e DarkForge estiver clara;
- não houver duas fontes de verdade planejadas;
- os testes de segurança/recovery estiverem especificados;
- nenhum requisito crítico estiver implícito.

**Evidência:** links para ADRs, contratos, inventário, datasets e revisão da matriz.
