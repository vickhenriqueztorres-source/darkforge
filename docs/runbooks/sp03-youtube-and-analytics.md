# Runbook SP-03 — YouTube OAuth, QuotaLedger e Analytics Center

## 1. Configuracao OAuth Oficial (Escopos Minimos)
- Variaveis no `.env` do servidor:
  - `TOKEN_ENCRYPTION_KEY`: chave AES-256-GCM (32 bytes base64) para cifrar `access_token` e `refresh_token` em `public.platform_connection_secrets`.
  - `YOUTUBE_CLIENT_ID` e `YOUTUBE_CLIENT_SECRET`: credenciais OAuth do Google Cloud Console com APIs `YouTube Data API v3` e `YouTube Analytics API` habilitadas.
  - Escopos solicitados: `youtube.readonly` e `yt-analytics.readonly` (nenhum escopo de escrita/publicacao).

## 2. Regras de Integridade e Honestidade
- `platform_connection_secrets` e `oauth_states` possuem `REVOKE ALL FROM PUBLIC, anon, authenticated` + `FORCE ROW LEVEL SECURITY`.
- Metrica indisponivel, atrasada ou parcial (`unknown`, `delayed`, `partial`, `not_applicable`) persiste `value_num = NULL` (imposto por `CHECK` SQL e pelo dominio).
- `QuotaLedger` reserva orçamento separado para `own_sync` antes de permitir consumo por `public_research`.
- Desconectar conexao apaga segredos OAuth imediatamente e oferece escolha explicita entre `keep_readonly` e `purge_synced_data`.
