# SP-02 — Jobs, Storage e recovery

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-01  
**Desbloqueia:** SP-03 e todos os trabalhos assíncronos  
**Objetivo:** construir uma única infraestrutura de execução recuperável antes de conectar YouTube, IA ou produção.

## 1. Escopo

Fila Postgres, Command Bus, workers locais, leases, heartbeat, fencing, idempotência, outbox/inbox, progresso com replay, Storage privado, manifests, checksums e reconciliação.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-02-T01 | Definir modelo e máquina de estados de jobs | Job, JobAttempt, JobEvent e transições válidas | Estados `QUEUED`, `RUNNING`, `PAUSED`, `CANCELLED`, `FAILED`, `BLOCKED`, `INTERRUPTED`, `RECOVERABLE` e `SUCCEEDED` têm semântica clara |
| SP-02-T02 | Implementar claim concorrente | Fila com lock/lease e prioridade | Dois workers não executam o mesmo claim; `SKIP LOCKED` ou mecanismo equivalente é testado |
| SP-02-T03 | Implementar heartbeat e fencing | Expiração de lease e validação de escritor | Worker antigo não consegue commitar depois que outro assumiu o job |
| SP-02-T04 | Implementar idempotência e deduplicação | Chaves de comando, efeito e retry | Repetir comando/evento não duplica fatos, uploads, gerações ou produções |
| SP-02-T05 | Implementar outbox/inbox e replay | Eventos persistentes, cursor e reconciliação | Evento perdido não deixa UI eternamente processando; estado atual pode ser consultado |
| SP-02-T06 | Integrar Command Bus e worker lifecycle | Registro, execução, checkpoint e recovery | Reinício sem abrir a UI reconcilia jobs; não existe segunda fila paralela |
| SP-02-T07 | Implementar controles de job | Pause/resume/cancel com confirmação | UI diferencia solicitação registrada de efeito confirmado; cancelamento não vira sucesso |
| SP-02-T08 | Implementar Storage privado e manifests | Buckets/policies, upload, checksum, `StorageObject` e manifest | Arquivo só fica `ready` após validação; signed URL respeita workspace |
| SP-02-T09 | Implementar reconciler de banco/Storage | Detecção de objeto ausente, órfão e upload incompleto | Inconsistências são reportadas e recuperáveis, sem apagar dados automaticamente |
| SP-02-T10 | Implementar progresso e diagnóstico de jobs | Etapas reais, logs redacted, polling/SSE com replay | Não há progresso baseado apenas em tempo; erros têm código e ação |
| SP-02-T11 | Criar testes de falha e recuperação | T-JOB-001–004 e T-STO-001 | Crash, timeout, retry, outage e upload interrompido não geram falso sucesso |
| SP-02-T12 | Construir UI de Jobs e Qualidade | Fila, histórico, filtros, detalhe e ações | Usuário entende estado, última etapa, erro e próxima ação |

## 3. Ordem interna obrigatória

1. Schema e transições.
2. Claim/lease/fencing.
3. Idempotência/outbox.
4. Worker e recovery.
5. Storage/manifests.
6. Progresso e UI.
7. Testes destrutivos controlados.

Não conectar provedores externos antes de os testes de fila e recovery passarem.

## 4. Cenários de falha obrigatórios

- Dois workers tentando o mesmo job.
- Worker morto com lease ativo e depois expirado.
- Crash antes da chamada externa, depois dela e antes do commit.
- Retry com a mesma chave de idempotência.
- Evento duplicado, atrasado ou perdido.
- Supabase indisponível durante claim, checkpoint e conclusão.
- Upload concluído sem manifest e manifest sem objeto.
- Objeto de outro workspace solicitado por ID ou signed URL.
- Pausa/cancelamento durante cada etapa suportada.

## 5. Gate G2

Só avançar quando:

- existe um único catálogo lógico de jobs;
- jobs reais de teste podem ser pausados, retomados, cancelados e recuperados;
- fencing e idempotência foram demonstrados;
- Storage e banco são reconciliáveis;
- rede/Supabase indisponível produz estado explícito;
- nenhum teste apresenta sucesso sem commit e validação;
- JOB-001–006 e os ADRs 003/004/012/013/015 têm evidência.
