# SP-09 — Hardening, operação e release do piloto

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-00 a SP-08  
**Desbloqueia:** piloto controlado  
**Objetivo:** provar que o sistema completo é seguro, recuperável, instalável e honesto em condições reais de uso.

## 1. Escopo

Segurança, testes cruzados, performance, acessibilidade, telemetria, diagnóstico, backup/restore, instalação limpa, upgrade, E2E e relatório de release. Launcher/EXE é opcional e só depois do núcleo estar pronto.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-09-T01 | Fazer auditoria de segurança | Revisão de RLS, grants, RPCs, tokens, uploads, SSRF, CSRF e logs | Nenhum atalho privilegiado ou segredo exposto; achados têm correção |
| SP-09-T02 | Executar testes de isolamento completos | T-SEC-001/002 em UI, API, RPC, busca e Storage | Dois workspaces não vazam dados nem arquivos |
| SP-09-T03 | Executar matriz de falhas | T-JOB-001–004, T-STO-001, T-YT-001–003 e T-DF-001 | Falhas são recuperáveis e nenhuma vira falso sucesso |
| SP-09-T04 | Validar RAG e IA | T-RAG-001/002, T-AI-001 e golden datasets | Citações, filtros, exclusão, rebuild e consentimento passam |
| SP-09-T05 | Medir performance e custo | Latência, listas, sync, conexões, Storage, egress e IA | Gargalos têm limite/otimização; não há reindexação ou retry sem controle |
| SP-09-T06 | Fazer auditoria de acessibilidade | Teclado, foco, contraste, labels, estados e movimento | Fluxo principal é utilizável sem mouse e não depende só de cor |
| SP-09-T07 | Instrumentar produto e diagnóstico | Eventos permitidos, logs redacted e pacote seguro | Métricas do PRD são medidas sem coletar segredos/copies por padrão |
| SP-09-T08 | Testar backup e restore | Postgres, Auth/config necessária, Storage, embeddings e manifests | Restore em projeto isolado valida dados, RLS, arquivos e jobs; RPO/RTO registrados |
| SP-09-T09 | Testar instalação e upgrade | Instalação limpa, configuração, migrations e upgrade | Não há perda de dados; launcher não é necessário para usar a Web UI |
| SP-09-T10 | Executar E2E completo | T-E2E-001 com os 21 passos do PRD | Fluxo completo é repetível, incluindo erro, reinício, outage e restore |
| SP-09-T11 | Auditar rastreabilidade e escopo | Matriz final e lista de desvios | Todo requisito MVP está DONE ou tem desvio aprovado; nada foi apagado |
| SP-09-T12 | Preparar relatório de piloto | Release notes, limitações, métricas, riscos e próximos passos | Relatório separa fatos verificados de hipóteses e itens bloqueados |

## 3. E2E obrigatório

Executar em instalação limpa, projeto Supabase de teste e dois workspaces:

1. Autenticar e provar isolamento.
2. Criar/editar perfil e mudar tema.
3. Conectar canal autorizado.
4. Sincronizar catálogo e métricas.
5. Conferir origem, período e frescor.
6. Confirmar que ausência não é zero.
7. Pesquisar e aprovar referências.
8. Abrir evidências de títulos/capas.
9. Importar, revisar, aprovar e indexar copies.
10. Gerar oportunidades e inspecionar fontes/score/limitações/RAG.
11. Rejeitar, editar e aprovar sugestões.
12. Criar brief e congelar a versão.
13. Exportar brief e localizar fontes.
14. Iniciar produção DarkForge quando o contrato estiver disponível.
15. Pausar, retomar e cancelar jobs distintos.
16. Fechar a aplicação durante job e recuperar sem duplicar.
17. Abrir artifact e relatório de qualidade.
18. Provocar erro real e validar log/mensagem/retry.
19. Derrubar Supabase durante sync/upload e confirmar bloqueio recuperável.
20. Reiniciar e confirmar histórico/configurações/calendário.
21. Restaurar backup de dados e arquivos em projeto isolado.

## 4. Gate G9 / pronto para piloto

Só declarar pronto quando:

- todos os gates anteriores passaram ou têm desvio formal;
- zero falso sucesso;
- zero perda silenciosa de dados;
- zero acesso indevido entre workspaces;
- nenhuma recomendação sem proveniência mínima;
- restore completo foi executado;
- limitações e custos conhecidos estão documentados;
- o relatório final não apresenta mocks como integrações reais.

Se qualquer item falhar, o resultado é `NOT_READY`, com a lista exata do que falta. Não maquiar o status para concluir o prompt.
