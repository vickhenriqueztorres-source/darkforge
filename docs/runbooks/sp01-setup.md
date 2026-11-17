# Runbook SP-01 — Aplicacao Local, Migrations e Validacao RLS

## 1. Subir API local e Web UI
```powershell
# Terminal 1 (API FastAPI em 127.0.0.1:8000)
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

# Terminal 2 (Web UI Next.js em 127.0.0.1:3000)
pnpm dev:web
```

## 2. Aplicar Migrations SQL (SP-01-T02 / SP-01-T05)
Requer `DATABASE_URL` ou `supabase link --project-ref pqtwhwjrpgxpagkyxktk` autenticado na conta dona do projeto:
- `migrations/0001_sp01_workspace_auth_channels.sql`
- `migrations/0002_sp01_rls_and_security.sql`

## 3. Executar Testes
```powershell
# Suite unitaria e de contratos (offline / sem segredos privilegiados)
.\.venv\Scripts\python.exe -m pytest -m "not live_supabase" -v

# Suite viva de isolamento entre dois usuarios e dois workspaces (T-SEC-001)
# Exige SUPABASE_SERVICE_ROLE_KEY e migrations aplicadas no projeto de teste
.\.venv\Scripts\python.exe -m pytest -m live_supabase -v
```
