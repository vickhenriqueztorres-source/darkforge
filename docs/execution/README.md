# Execução do DarkForge Channel OS via IDE

Este diretório transforma o [PRD](../prd.md) e a [arquitetura](../architecture.md) em um plano executável por um agente de código em uma IDE.

**Nada neste pacote é implementação.** Ele é o contrato de execução para a IDE.

## Arquivos

- [Plano mestre](master-plan.md): sequência, dependências, gates, regras e estratégia de verificação.
- [Prompt geral](master-prompt.md): texto para colar na IDE e iniciar a execução completa.
- [Rastreabilidade](traceability.md): cobertura dos requisitos do PRD, ADRs e testes obrigatórios.
- [Estado da execução](state.md): arquivo vivo para retomar o trabalho sem perder contexto.
- [Subplanos](subplans/): tarefas detalhadas por fase.

## Subplanos

| ID | Arquivo | Resultado |
|---|---|---|
| SP-00 | [Fundações e contratos](subplans/00-foundations-contracts.md) | Escopo, ADRs, contratos, métricas e avaliação preparados |
| SP-01 | [Workspace, Auth e dados](subplans/01-workspace-auth-data.md) | Shell, autenticação, workspaces, perfis e RLS |
| SP-02 | [Jobs, Storage e recovery](subplans/02-jobs-storage-recovery.md) | Fila única, workers, arquivos e recuperação confiáveis |
| SP-03 | [YouTube e Analytics](subplans/03-youtube-analytics.md) | Canais conectados, sync e dashboards honestos |
| SP-04 | [Research Explorer](subplans/04-research-explorer.md) | Pesquisa pública, referências e evidências |
| SP-05 | [Title e Thumbnail Intelligence](subplans/05-title-thumbnail.md) | Análise e geração original de títulos/capas |
| SP-06 | [Knowledge/RAG Studio](subplans/06-knowledge-rag.md) | Curadoria, busca, citações e avaliação de RAG |
| SP-07 | [Oportunidades e Editorial Studio](subplans/07-opportunities-editorial.md) | Oportunidades, briefs, calendário e aprovação |
| SP-08 | [Produção DarkForge](subplans/08-darkforge-production.md) | Brief aprovado até artifact validado |
| SP-09 | [Hardening e release](subplans/09-hardening-release.md) | Segurança, restore, E2E, instalação e piloto |

## Como usar na IDE

1. Copie a pasta `docs` inteira para o repositório do projeto, preservando os links relativos.
2. Abra o [prompt geral](master-prompt.md), copie todo o conteúdo e cole no agente da IDE.
3. Garanta que a IDE tenha acesso ao código do DarkForge existente, se esse núcleo estiver em outro diretório.
4. Forneça as credenciais somente pelo mecanismo seguro de ambiente da IDE. Nunca cole segredos no prompt.
5. O agente deve atualizar `state.md` e `traceability.md` a cada tarefa e ao final de cada gate.
6. Se a conversa da IDE for reiniciada, o próximo agente deve ler primeiro `state.md`, o plano mestre e o subplano atual, retomando da última tarefa com evidência.

## Regra de continuidade

Não apague tarefas, requisitos, falhas ou decisões para “limpar” o plano. Marque o estado real: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE` ou `REJECTED_WITH_REASON` (`PENDING` pode ser usado para gates). Um item só é `DONE` quando implementação, teste e evidência estiverem registrados.
