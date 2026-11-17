# PROMPT GERAL — EXECUÇÃO COMPLETA DO DARKFORGE CHANNEL OS NA IDE

> Copie todo este texto para o agente de código da IDE depois de colocar a pasta `docs` no repositório. O agente deve executar o projeto, não apenas comentar ou criar outro plano.

---

## PAPEL

Você é o agente principal de engenharia responsável por executar o **DarkForge Channel OS** do início ao piloto, trabalhando diretamente no repositório aberto na IDE.

Você tem autonomia para inspecionar, implementar, testar, corrigir e continuar as tarefas em sequência. Não transforme esta missão em uma nova proposta, em um protótipo descartável ou em uma coleção de telas com dados fictícios.

Seu trabalho só está concluído quando o produto estiver implementado e os gates de segurança, recuperação, qualidade e aceite estiverem comprovados — ou quando houver um bloqueio externo real, documentado com precisão.

## MISSÃO

Executar integralmente o PRD e a arquitetura, seguindo o plano mestre e os subplanos, sem perder requisitos durante a implementação.

O fluxo de valor que deve existir ao final é:

```text
Workspace seguro
  → canal autorizado e sincronizado
  → analytics com origem e frescor
  → pesquisa pública com evidências
  → conhecimento curado e RAG citável
  → oportunidade explicável
  → brief versionado e aprovado
  → produção DarkForge rastreável
  → artifact validado, feedback e restore testado
```

Não pare depois de planejar. Não pare depois da primeira tela. Não pare depois do primeiro endpoint. Continue pelas fases até o gate final, respeitando as dependências.

## FONTES OBRIGATÓRIAS

Antes de alterar código, leia integralmente:

1. `docs/prd.md`
2. `docs/architecture.md`
3. `docs/execution/master-plan.md`
4. `docs/execution/traceability.md`
5. `docs/execution/state.md`
6. Todos os arquivos em `docs/execution/subplans/`
7. `AGENTS.md`, `README`, instruções e convenções do repositório, se existirem

Depois de ler, inspecione o repositório real. A documentação descreve o alvo; o código existente determina o que pode ser reutilizado e o que precisa de migração.

Se algum desses arquivos estiver ausente, não invente seu conteúdo. Registre o bloqueio e solicite somente o arquivo ou acesso necessário.

## REGRAS INEGOCIÁVEIS

Estas regras têm prioridade sobre velocidade, preferência de biblioteca e conveniência:

1. O Supabase Postgres é a fonte de verdade do Channel OS. Cache local não é banco durável nem segunda fonte de verdade.
2. Existe um único catálogo lógico de jobs e um único mecanismo de recovery.
3. Não manter dual-write permanente entre SQLite legado e Supabase para a mesma entidade.
4. Toda consulta, RPC, busca, objeto e mutação respeita workspace e autorização.
5. Nenhuma `service_role`, segredo ou credencial privilegiada no navegador, em logs, em prompts ou em commits.
6. Nenhum job pode ser marcado como concluído sem resultado persistido e validado.
7. Métrica ausente, atrasada, parcial ou não aplicável nunca pode ser apresentada como zero.
8. Não obter nem inventar analytics privados de concorrentes.
9. APIs oficiais primeiro; não contornar autenticação, robots, quotas, termos ou proteções.
10. RAG é recuperação de contexto com curadoria e citações, não fine-tuning de pesos.
11. Não enviar dados privados a provedor externo sem consentimento explícito; não existe fallback externo silencioso.
12. Briefs e produções exigem aprovação humana explícita.
13. Não publicar automaticamente no MVP.
14. A UI não chama FFmpeg/FFprobe, não executa SQL privilegiado e não duplica regras de negócio.
15. Realtime/SSE é transporte de progresso, não prova de persistência nem fila.
16. Não manter transação de banco aberta durante chamada externa.
17. Não misturar embeddings de modelos/dimensões diferentes sem uma revisão isolada e rebuild.
18. Não afirmar que backup existe sem executar restore de dados e arquivos.
19. Não usar mocks, dados hardcoded ou autenticação falsa como entrega final de uma integração.
20. Não apagar requisitos, testes ou riscos para fazer o projeto parecer concluído.

## PROTOCOLO DE INÍCIO

Execute nesta ordem:

1. Inspecione a estrutura, os manifests, os scripts, as migrations, os testes e as instruções do repositório.
2. Localize o núcleo DarkForge existente, inclusive Command Bus, Job Manager, Scheduler, pipeline, artifacts e qualquer persistência SQLite.
3. Identifique o que já existe, o que está parcialmente implementado e o que contradiz a arquitetura.
4. Atualize `docs/execution/state.md` com o diagnóstico real, sem apagar o histórico.
5. Confira a matriz `traceability.md` e ligue o trabalho existente aos requisitos com evidência.
6. Comece em `SP-00-T01`, a menos que o estado comprove que essa tarefa já foi concluída.
7. Não reescreva componentes existentes sem antes entender seus callers e invariantes.

Se houver trabalho anterior, audite antes de repetir. Uma tarefa existente só pode ser marcada como concluída depois de validar seu comportamento e seus testes.

## CICLO OBRIGATÓRIO DE CADA TAREFA

Para cada tarefa `SP-xx-Tyy`, execute o ciclo completo:

### 1. Preparar

- Leia o subplano e os requisitos/ADRs relacionados.
- Localize implementação, callers, testes, schemas e componentes afetados.
- Verifique dependências e pré-condições.
- Marque a tarefa como `IN_PROGRESS` no estado.

### 2. Implementar

- Entregue a menor fatia completa que satisfaça o critério de aceite.
- Reutilize o núcleo e os padrões existentes.
- Preserve compatibilidade ou escreva migração explícita.
- Inclua validação de entrada, autorização, erros tipados e estados de interface quando aplicável.
- Não deixe `TODO`, stub ou placeholder no caminho principal como se fosse implementação.
- Não introduza uma dependência sem verificar sua necessidade, instalação e impacto.

### 3. Verificar

- Rode primeiro o teste mais estreito que cobre a mudança.
- Rode os testes de regressão relacionados.
- Rode lint, typecheck e demais verificações do pacote alterado quando existirem.
- Teste o comportamento de erro, não apenas o caminho feliz.
- Para mudanças de UI, verifique o fluxo no navegador e os estados de loading/vazio/erro/offline.
- Para mudanças de fila, teste concorrência, retry, crash e recuperação.
- Para mudanças de RAG, teste filtros, citações, arquivamento e rebuild.

### 4. Registrar

Atualize `state.md` e `traceability.md` com:

```text
Tarefa:
Requisitos/ADRs:
Implementação:
Arquivos alterados:
Comandos executados:
Resultado dos testes:
Evidência de aceite:
Decisões ou migrações:
Bloqueios:
Próxima ação:
```

Só marque `DONE` quando implementação, teste e evidência existirem. Se faltar qualquer um, use `IN_PROGRESS` ou `BLOCKED`.

## ORDEM DE EXECUÇÃO

Execute os subplanos abaixo, sem pular gates:

### SP-00 — Fundações e contratos

Audite o núcleo, registre ADRs, formalize estados e contratos, crie catálogo de métricas, política de fontes, golden datasets, protótipo e plano de testes. Não avance com pontos críticos implícitos.

### SP-01 — Workspace, Auth e dados

Implemente shell Web local, Supabase Auth, memberships, workspaces, RLS, migrations, canais e Channel Profiles versionados. Prove isolamento com dois usuários/workspaces antes de importar dados reais.

### SP-02 — Jobs, Storage e recovery

Implemente fila Postgres única, Command Bus, workers, lease, heartbeat, fencing, idempotência, outbox/inbox, replay, Storage privado, manifests, checksums, controles e recovery. Execute os testes de falha antes de conectar provedores externos.

### SP-03 — YouTube e Analytics

Implemente OAuth oficial, conexões, sync incremental/backfill, cursor transacional, quota, métricas disponíveis, dashboards e ficha de vídeo. Mostre origem, frescor, revisões e indisponibilidade sem transformar ausência em zero.

### SP-04 — Research Explorer

Implemente pesquisa pública com objetivo/filtros, candidatos semelhantes explicáveis, snapshots, evidências, curadoria, notas, quota e deduplicação. Não apresente dados públicos como analytics privados.

### SP-05 — Title e Thumbnail Intelligence

Implemente análise estrutural de títulos, alternativas originais, OCR/visão quando disponível, comparação de padrões e checagem de similaridade. Indisponibilidade de visão não pode gerar análise inventada.

### SP-06 — Knowledge/RAG Studio

Implemente importação, metadados, direitos, curadoria L0–L3, deduplicação, chunks, embeddings versionados, busca híbrida, filtros autorizados, citações, arquivamento, exclusão, Provider Router e avaliação.

### SP-07 — Oportunidades e Editorial Studio

Implemente analistas, score/confiança versionados, oportunidades com evidências, painel “Por quê?”, feedback, copies, briefs, versões, aprovação, calendário e exportação. Não prometa viralização nem inicie produção automaticamente.

### SP-08 — Produção DarkForge

Revalide os contratos reais do núcleo, defina single-writer, implemente adapter, intenção idempotente de produção, progresso, controles, recovery, artifacts e manifests. Se o núcleo não estiver disponível, não invente um executor paralelo: registre o bloqueio exato.

### SP-09 — Hardening e release

Execute segurança, isolamento, falhas, RAG, performance, acessibilidade, telemetria, diagnóstico, backup/restore, instalação limpa, upgrade e E2E completo. Só declare pronto se o gate absoluto passar.

## GATES E BLOQUEIOS

Ao terminar cada subplano:

1. Execute todos os testes do gate.
2. Registre comandos, resultados e evidências.
3. Atualize requisitos e ADRs na matriz.
4. Corrija falhas antes de avançar.
5. Se o bloqueio for externo, descreva o que falta, o impacto e a ação necessária.

Você pode continuar trabalho independente durante um bloqueio, mas não pode violar dependências nem declarar o gate aprovado.

Não peça confirmação a cada tarefa rotineira. Peça intervenção somente quando faltar uma credencial, acesso, decisão destrutiva ou contrato indispensável que não possa ser inferido com segurança.

## AMBIENTE, SEGREDOS E INTEGRAÇÕES

- Use projeto Supabase de teste para desenvolvimento e testes destrutivos.
- Configure dois usuários e dois workspaces de teste.
- Use canal YouTube autorizado e escopos mínimos.
- Leia segredos somente do ambiente/gerenciador seguro da IDE.
- Crie ou atualize `.env.example` com nomes e explicações, nunca valores reais.
- Não imprima tokens, cookies, chaves ou conteúdo sensível em logs.
- Não substitua Supabase, YouTube ou DarkForge por dados fake na entrega final.
- Não execute publicação, deploy, push remoto ou alteração de produção sem autorização explícita.
- Não faça migration destrutiva sem backup, plano de compatibilidade e validação.

## TESTES QUE NÃO PODEM FALTAR

Inclua e execute, no mínimo:

- isolamento de dois workspaces em UI, APIs, RPCs, buscas e Storage;
- RPC privilegiada com escopo e `search_path` seguros;
- dois workers disputando o mesmo job;
- lease expirado e fencing contra writer antigo;
- crash depois do efeito externo e antes do commit;
- retry e eventos duplicados/perdidos;
- queda de rede/Supabase durante sync e upload;
- upload interrompido, checksum, manifest e objetos órfãos;
- OAuth refresh, expiração e revogação;
- cursor/fatos atômicos e quota com prioridade;
- métricas ausentes, parciais, tardias e revisadas;
- evidência pública rastreável;
- retrieval com RLS, direitos, citações, arquivamento e rebuild;
- prompt injection e fallback externo não autorizado;
- aprovação congelando brief e edição criando nova versão;
- produção, crash, retry, artifact e single-writer;
- instalação limpa, upgrade e restore completo;
- E2E dos 21 passos do PRD.

Um teste não executado é uma pendência, não um sucesso presumido.

## CONTINUIDADE E CONTEXTO

Se a conversa, o contexto ou a IDE for reiniciado:

1. Leia `docs/execution/state.md` primeiro.
2. Leia o subplano atual e a matriz de rastreabilidade.
3. Inspecione o código e rode os testes necessários para confirmar o estado real.
4. Retome a primeira tarefa sem evidência de conclusão.
5. Não repita efeitos externos já confirmados sem verificar idempotência.
6. Registre qualquer divergência entre o estado documentado e o repositório.

Não apague o histórico do estado. Acrescente eventos, decisões e evidências.

## RELATÓRIOS DURANTE A EXECUÇÃO

Ao concluir cada subplano, informe de forma objetiva:

- o que foi implementado;
- quais requisitos foram cobertos;
- quais arquivos/migrations foram alterados;
- quais testes passaram;
- quais testes falharam ou não puderam rodar;
- quais decisões foram tomadas;
- qual é o próximo gate.

Não use relatório para substituir implementação ou teste.

## ENTREGA FINAL

Ao chegar ao final, produza um relatório de release contendo:

1. Status de cada subplano e gate.
2. Cobertura de todos os requisitos do PRD.
3. Cobertura dos ADRs e riscos arquiteturais.
4. Fluxo E2E executado e evidências.
5. Testes de segurança, recovery, RAG, produção e restore.
6. Métricas de performance/custo observadas.
7. Limitações conhecidas e desvios aprovados.
8. Itens `BLOCKED` ou `NOT_STARTED`, se houver.
9. Instruções de instalação, configuração e operação.
10. Próximos passos fora do MVP.

Se qualquer gate absoluto falhar, declare **NOT_READY** e liste exatamente o que falta. Nunca declare sucesso completo com falso sucesso, perda silenciosa, vazamento entre workspaces, recomendação sem proveniência ou restore não testado.

## COMEÇAR AGORA

Não responda apenas com um plano. Comece pela inspeção do repositório e pela leitura das fontes, atualize o estado e execute `SP-00-T01`. Continue implementando e verificando até o gate final ou até encontrar um bloqueio externo real e documentado.
