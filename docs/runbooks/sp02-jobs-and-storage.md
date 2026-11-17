# Runbook SP-02 — Worker Local, Reconciler, Fila Postgres e Storage Privado

## 1. Iniciar Worker + Reconciler Local
O reconciler (`reconcile_expired_leases`) executa automaticamente no boot e antes de cada `claim_next`, sem depender de a UI estar aberta (`JOB-004`, `SP-02-T06`).

```powershell
# Executar ciclo unico de reconciliacao e processamento (ou loop continuo)
.\.venv\Scripts\python.exe -c "import os; from dotenv import load_dotenv; load_dotenv(); from adapters.supabase_db.jobs_repo import PostgresWorkerQueue; from workers.runner import JobWorker; w = JobWorker(PostgresWorkerQueue(os.environ['DATABASE_URL']), 'local-worker-1'); print('reconciled=', w.reconcile_expired(), 'processed=', w.run_once())"
```

## 2. Garantias de Seguranca e Consistencia
- Fila unica Postgres com `FOR UPDATE SKIP LOCKED` (`app.claim_next_job`).
- `fencing_token` monotônico impede worker zumbi com lease expirado de gravar progresso ou transicao.
- `idempotent_effects` garante que efeitos externos nao dupliquem apos crash pre-commit.
- `outbox_events` e `inbox_events` entregam eventos de dominio na mesma transacao das transicoes.
- Buckets privados `knowledge`, `references`, `exports`, `production` validam `<workspace_id>/...` via RLS e promocao `UPLOADING -> VERIFYING -> READY` por SHA-256.
