# SP-08 — Integração com produção DarkForge

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-07 e contratos reais auditados em SP-00  
**Desbloqueia:** SP-09  
**Objetivo:** converter somente briefs aprovados em produção rastreável, sem criar uma segunda aplicação ou fonte de verdade.

## 1. Escopo

Adapter do núcleo, intenção de produção, comandos idempotentes, progresso, pause/resume/cancel, recovery, artifacts, manifests e relatório de qualidade.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-08-T01 | Revalidar contratos do núcleo | Inventário atualizado de comandos, estados e artifacts | O que existe no código é separado do que foi apenas proposto |
| SP-08-T02 | Decidir single-writer e migração | ADR e plano para SQLite legado, se existir | Nenhum dual-write permanente; rollback e reconciliação estão definidos |
| SP-08-T03 | Implementar adapter DarkForge | Fronteira entre Application Services e executor | UI não chama FFmpeg/FFprobe nem altera estado interno diretamente |
| SP-08-T04 | Implementar intenção de produção | Brief aprovado + parâmetros + idempotency key | Somente versão aprovada pode ser enviada; retry não duplica produção |
| SP-08-T05 | Integrar jobs e progresso | Etapas, checkpoints, eventos e estado atual | Progresso vem do executor/fila, não de temporizador; evento perdido é recuperável |
| SP-08-T06 | Integrar artifacts e manifests | Storage, checksum, estado `ready` e relatório de qualidade | Artifact final só aparece após validação e persistência |
| SP-08-T07 | Implementar controles e recovery | Pause/resume/cancel e reconciliação após crash | A UI diferencia pedido de efeito; retry não duplica output |
| SP-08-T08 | Construir UI de produção | Brief, intenção, jobs, artifacts e erros | Usuário acompanha produção e abre resultado validado |
| SP-08-T09 | Criar testes de integração | T-DF-001 e cenários de crash/efeito externo | Produção real de teste conclui ou falha honestamente, sem duas verdades |

## 3. Condições de bloqueio

Se o núcleo DarkForge não estiver disponível ou não expuser contratos suficientes:

- não inventar um executor paralelo;
- não simular produção final com arquivos fake;
- implementar somente contratos/adapters independentes que não criem segunda verdade;
- marcar PROD-001–005 como `BLOCKED` com a dependência exata;
- manter o fluxo editorial funcionando até exportação;
- retomar quando o núcleo e seus contratos estiverem acessíveis.

## 4. Testes mínimos

- Brief rascunho não pode iniciar produção.
- Brief aprovado gera uma única intenção repetível.
- Executor aceita/rejeita comando e informa erro real.
- Crash antes/depois do efeito externo e antes do commit.
- Pause/resume/cancel em cada etapa suportada.
- Artifact sem checksum/manifest não é concluído.
- Reabrir aplicação sem abrir a UI durante o recovery.
- SQLite legado e Supabase não divergem.

## 5. Gate G8

Só avançar quando:

- produção real de teste pode ser iniciada pela UI;
- progresso e controles são reais;
- recovery não duplica efeitos;
- artifact final tem manifest/checksum/estado válido;
- existe um único escritor por entidade;
- PROD-001–005 e ADR-003/004/008 têm evidência ou bloqueio explícito.
