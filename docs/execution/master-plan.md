# DarkForge Channel OS — Plano mestre de execução

**Versão:** 0.1  
**Data:** 16 de novembro de 2026  
**Destino:** execução por agente de código em IDE  
**Fontes normativas:** [PRD](../prd.md) e [arquitetura](../architecture.md)  
**Natureza desta entrega:** documentação de execução; nenhum código foi implementado aqui

---

## 1. Missão

Executar o DarkForge Channel OS do início ao piloto, preservando todos os requisitos do PRD e todas as decisões da arquitetura, sem transformar o projeto em uma coleção de telas, mocks ou agentes desconectados.

O caminho de valor obrigatório é:

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

A execução deve ser incremental, mas não pode pular os fundamentos de segurança, persistência e recovery para chegar mais rápido à interface.

---

## 2. Hierarquia de decisões

Em caso de dúvida, usar esta ordem:

1. Requisitos explícitos do PRD.
2. Decisões e restrições da arquitetura.
3. ADRs registrados no repositório.
4. Contratos reais do núcleo DarkForge existente.
5. Convenções já presentes no repositório.
6. Decisão nova documentada, sem contradizer os itens anteriores.

Nenhuma preferência de framework, pressa ou sugestão de biblioteca pode derrubar as regras de isolamento, fonte única de verdade, proveniência, aprovação humana ou recuperação.

---

## 3. Regras inegociáveis

1. **Supabase é a fonte de verdade** do Channel OS; cache local não é banco durável.
2. **Um único catálogo lógico de jobs** e um único mecanismo de recovery.
3. **Nenhum dual-write permanente** entre SQLite legado e Supabase para a mesma entidade.
4. **RLS e escopo de workspace** em todas as consultas, RPCs, buscas e arquivos.
5. **Nenhuma credencial privilegiada no navegador** e nenhum segredo em logs, prompts ou commits.
6. **Nenhum falso sucesso:** job concluído somente após resultado persistido e validado.
7. **Nenhuma métrica ausente como zero** e nenhuma métrica privada de concorrente inventada.
8. **APIs oficiais primeiro**, com quota, termos e limites respeitados.
9. **RAG com curadoria e citações**, sem fine-tuning no MVP.
10. **Nenhum fallback externo de IA silencioso** e nenhum envio de dados privados sem consentimento.
11. **Aprovação humana** antes de brief aprovado e intenção de produção.
12. **Sem publicação automática** no MVP.
13. **UI não chama FFmpeg/FFprobe**, não executa SQL privilegiado e não duplica regras de negócio.
14. **Realtime/SSE não é prova de persistência**; estado atual e replay são obrigatórios.
15. **Nenhum requisito pode ser removido silenciosamente** para declarar o MVP pronto.

---

## 4. Estratégia de execução

### 4.1 Fatias verticais

Cada subplano deve entregar uma fatia utilizável e verificável, contendo, quando aplicável:

- contrato e schema;
- regra de domínio;
- persistência e autorização;
- comando/job;
- API ou serviço de aplicação;
- interface e estados de erro;
- testes automatizados;
- evidência de aceite;
- atualização de estado e rastreabilidade.

Não criar primeiro todas as telas e deixar a lógica para depois. Também não criar todo o backend sem nenhuma validação de fluxo.

### 4.2 Sequência e dependências

```text
SP-00 Fundações
   ↓
SP-01 Workspace/Auth/Dados
   ↓
SP-02 Jobs/Storage/Recovery
   ↓
SP-03 YouTube/Analytics
   ↓
SP-04 Research ───────┐
   ↓                  │
SP-05 Title/Thumbnail │
   ↓                  │
SP-06 Knowledge/RAG ──┘
   ↓
SP-07 Oportunidades/Editorial
   ↓
SP-08 Produção DarkForge
   ↓
SP-09 Hardening/Release
```

SP-04 e SP-06 podem ter preparação paralela depois de SP-03, mas a integração de oportunidades só começa quando ambos tiverem seus gates. A ordem padrão é sequencial para reduzir contexto e retrabalho.

### 4.3 Gates

Um gate é uma condição de entrada, não uma formalidade. Se falhar:

1. reproduzir a falha;
2. identificar a causa;
3. corrigir a menor fatia responsável;
4. repetir o teste afetado e os testes de regressão;
5. registrar evidência;
6. somente então avançar.

Se houver um bloqueio externo real, marcar `BLOCKED`, explicar o que falta e continuar somente em trabalho independente que não viole a dependência.

---

## 5. Catálogo de subplanos

| ID | Nome | Depende de | Entrega principal | Gate de saída |
|---|---|---|---|---|
| SP-00 | Fundações e contratos | PRD + arquitetura | ADRs, inventário do núcleo, schemas, catálogo de métricas, políticas e avaliação | Escopo e contratos aprovados; nenhum ponto crítico implícito |
| SP-01 | Workspace, Auth e dados | SP-00 | App shell, Supabase Auth, memberships, RLS, perfis e migrations | Dois workspaces isolados; perfil versionado; erros não parecem vazio |
| SP-02 | Jobs, Storage e recovery | SP-01 | Fila Postgres, workers, outbox, idempotência, Storage e manifests | Concorrência, crash, retry, pausa, retomada, cancelamento e outage sem falso sucesso |
| SP-03 | YouTube e Analytics | SP-02 | OAuth, sync incremental/backfill, quota, catálogo e dashboards | Dados reais autorizados, cursor transacional, frescor e métricas desconhecidas corretas |
| SP-04 | Research Explorer | SP-03 | Pesquisa pública, candidatos, snapshots, referências e evidências | Toda referência rastreável; quota controlada; público não vira privado |
| SP-05 | Title e Thumbnail Intelligence | SP-04 | Análise de títulos/capas, alternativas e originalidade | Análise explicável, referências visíveis e similaridade sinalizada |
| SP-06 | Knowledge/RAG Studio | SP-01, SP-02; integra SP-04/05 | Importação, L0–L3, chunks, embeddings, busca e citações | Fonte aprovada recuperada; arquivada excluída; citações e filtros verificáveis |
| SP-07 | Oportunidades e Editorial Studio | SP-03, SP-04, SP-05, SP-06 | Score, oportunidades, feedback, briefs, calendário e exportação | Recomendação explicável; aprovação congela versão; histórico preservado |
| SP-08 | Produção DarkForge | SP-07 + contratos do núcleo | Intenção de produção, adapter, jobs e artifacts | Produção real, recovery, artifact válido e single-writer |
| SP-09 | Hardening e release | Todos os anteriores | Segurança, performance, backup/restore, E2E, instalação e piloto | Fluxo completo repetível, restore validado e nenhum gate absoluto violado |

Os detalhes e os IDs de tarefa estão nos arquivos de [subplanos](subplans/).

---

## 6. Protocolo obrigatório por tarefa

Para cada `SP-xx-Tyy`, o agente deve executar este ciclo:

### Antes

- Ler o subplano, os requisitos relacionados e os contratos existentes.
- Verificar se a tarefa já foi parcialmente implementada.
- Localizar callers, testes, migrations e componentes afetados.
- Registrar `IN_PROGRESS` em `state.md`.

### Durante

- Implementar a menor fatia completa que satisfaça o critério.
- Reutilizar o núcleo e os padrões existentes.
- Manter compatibilidade ou registrar migração explícita.
- Não introduzir dependência nova sem justificar e verificar instalação.
- Não esconder erro atrás de mock, fallback ou estado vazio.

### Depois

- Rodar o teste mais estreito que cobre a mudança.
- Rodar testes de regressão relacionados.
- Conferir lint/typecheck/build quando aplicável ao pacote alterado.
- Registrar arquivos alterados, comandos, resultados e limitações.
- Atualizar a matriz de rastreabilidade.
- Marcar `DONE` somente com evidência; caso contrário, `BLOCKED` ou `IN_PROGRESS`.

### Registro mínimo

```text
Tarefa:
Requisitos:
Implementação:
Arquivos:
Testes e comandos:
Resultado:
Evidência de aceite:
Decisões/ADRs:
Bloqueios:
Próxima ação:
```

---

## 7. Estratégia de testes

### 7.1 Pirâmide

- **Unitários:** domínio, scores, parsers, métricas, estados, idempotência e validações.
- **Contrato:** APIs, comandos, adapters YouTube/IA/DarkForge e schemas.
- **Integração:** Postgres, RLS, Storage, fila, cursor, embeddings e outbox.
- **Falha/recovery:** processo morto, lease expirado, timeout, rede, quota, retry e efeito antes do commit.
- **E2E:** fluxo do usuário do onboarding ao brief e à produção.
- **Qualidade de IA:** golden datasets, citações, originalidade, prompt injection e dados insuficientes.
- **Release:** instalação limpa, upgrade, backup/restore e isolamento.

### 7.2 Testes destrutivos controlados

Devem ser executados em ambiente de teste, com dados descartáveis e sem credenciais de produção:

- matar worker antes e depois de uma chamada externa;
- expirar lease e tentar commit com fencing antigo;
- derrubar conectividade com Supabase durante sync e upload;
- repetir o mesmo comando e o mesmo evento;
- interromper upload e criar objeto órfão;
- revogar OAuth no meio do sync;
- esgotar quota de pesquisa;
- trocar revisão de embedding;
- arquivar/excluir fonte usada em uma geração anterior;
- tentar acessar outro workspace por ID, RPC, busca e signed URL.

### 7.3 Evidência

“Funciona” sem comando, resultado e cenário não é evidência. Guardar no estado da execução o comando, a data, o ambiente e o resultado. Não guardar segredos ou dados pessoais nos logs.

---

## 8. Ambiente e configuração

Antes de dados reais, o agente deve verificar e documentar:

- versões de Node, Python, banco e ferramentas do repositório;
- projeto Supabase de teste e migrations aplicáveis;
- dois usuários e dois workspaces de teste;
- bucket privado e políticas de Storage;
- canal YouTube de teste e OAuth com escopos mínimos;
- quotas e limites de APIs;
- provedor de IA local ou externo escolhido explicitamente;
- hardware disponível para visão/modelos locais;
- localização e contratos do núcleo DarkForge;
- procedimento de backup e ambiente isolado de restore.

Se algum item não existir, criar configuração de exemplo sem segredos e marcar o bloqueio real. Não substituir uma integração nomeada por dados fake na entrega final.

---

## 9. Controle de mudanças e escopo

- Toda decisão nova que altere contrato, segurança, persistência ou escopo vira ADR ou registro de decisão.
- Toda alteração de requisito atualiza PRD, rastreabilidade e subplano afetado.
- Não introduzir novas plataformas, colaboração, publicação automática ou fine-tuning no meio do MVP.
- Não apagar código legado antes de comprovar o caminho de migração e rollback.
- Não fazer migration destrutiva sem backup, plano de compatibilidade e validação.
- Não fazer push, deploy ou publicação externa sem autorização do usuário.

---

## 10. Definição global de pronto

O projeto só está pronto para o piloto quando:

- todos os requisitos MVP estão cobertos ou têm desvio aprovado e explícito;
- todos os subplanos e gates estão concluídos;
- o fluxo E2E foi executado em instalação limpa;
- dois workspaces foram testados contra vazamento;
- jobs sobrevivem a reinício e falhas sem duplicidade;
- dados e arquivos foram restaurados em ambiente isolado;
- RAG tem avaliação, citações e exclusão verificadas;
- briefs têm versão e aprovação;
- produção e artifacts têm estado real;
- métricas de produto e diagnóstico estão instrumentados;
- limitações conhecidas estão visíveis;
- não há segredos no repositório;
- o relatório final separa claramente `DONE`, `BLOCKED` e `NOT_STARTED`.

**Gate absoluto:** zero falso sucesso, zero perda silenciosa de dados, zero acesso indevido entre workspaces e nenhuma recomendação sem proveniência mínima.
