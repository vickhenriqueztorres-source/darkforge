# SP-03 — YouTube, canais próprios e Analytics Center

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-02  
**Desbloqueia:** SP-04 e SP-07  
**Objetivo:** conectar canais autorizados e transformar dados reais em análise com origem, frescor e disponibilidade explícitos.

## 1. Escopo

OAuth YouTube, conexões, catálogo de canais/vídeos, sync incremental/backfill, métricas disponíveis, quota, cursores transacionais, dashboards de portfólio/canal/vídeo e histórico de revisões.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-03-T01 | Implementar adapter oficial YouTube | Interface de plataforma, erros e limites | Não há scraping como fonte principal; adapter é substituível sem mudar casos de uso |
| SP-03-T02 | Implementar OAuth e conexões | Autorização, refresh, expiração, revogação e escopos mínimos | Tokens ficam fora do navegador/logs; revogação não encerra sessão do produto |
| SP-03-T03 | Validar catálogo de métricas | Consultas e dimensões compatíveis | Métricas indisponíveis são `unknown`, não zero; dados tardios têm estado |
| SP-03-T04 | Implementar sync de catálogo | Canal, vídeos, metadados e cursor incremental | Retry não duplica nem pula páginas; backfill é limitado e retomável |
| SP-03-T05 | Implementar sync de métricas | Fatos, revisões, período e origem | Cursor e fatos são confirmados na mesma unidade transacional |
| SP-03-T06 | Implementar QuotaLedger e prioridades | Reserva, consumo, circuit breaker e orçamento | Research não sufoca sync de canais próprios; quota gera estado recuperável |
| SP-03-T07 | Criar projeções de analytics | Consultas/agregações por canal, vídeo, período e formato | Listas são paginadas; comparações incompatíveis são bloqueadas/sinalizadas |
| SP-03-T08 | Construir dashboard de portfólio | Comparação de canais e filtros | Origem, período e última atualização aparecem na visão |
| SP-03-T09 | Construir dashboard de canal e ficha de vídeo | Métricas, metadados, histórico e análises | Usuário entende disponibilidade, frescor e revisões de cada dado |
| SP-03-T10 | Implementar desconexão e retenção | Revogação, impacto e política de dados | Ação explica o que permanece, o que é excluído e o que acontece com jobs |
| SP-03-T11 | Criar testes de sync e analytics | T-YT-001–003 e T-AN-001 | OAuth, cursor, quota, métricas ausentes e revisões têm evidência |

## 3. Regras de dados

- Não preencher lacuna com zero, média ou inferência sem identificação explícita.
- Não misturar dados de canais próprios com dados públicos de referências.
- Guardar fonte, revisão, período, granularidade e timestamp de sincronização.
- Não manter transação aberta durante chamada ao YouTube.
- Sync deve ser incremental; backfill não pode bloquear o sync corrente.
- Erro parcial preserva dados válidos e informa o que falhou.

## 4. Testes mínimos

- OAuth negado, expirado, refresh e revogado.
- Primeira carga, incremental, backfill e retry da mesma página.
- Resposta com métrica ausente, atrasada, parcial e revisada.
- Quota esgotada durante research e durante sync.
- Canal sem vídeos, canal sem permissão e canal com catálogo grande.
- Comparação de períodos/dimensões incompatíveis.
- Reinício no meio de sync e recuperação sem duplicidade.

## 5. Gate G3

Só avançar quando:

- um canal de teste autorizado sincroniza de ponta a ponta;
- dashboards mostram dados reais com origem/frescor;
- métricas desconhecidas não viram zero;
- cursor, quota e recovery têm testes;
- CH-005–008 e AN-001–007 estão cobertos;
- nenhum dado privado de concorrente é necessário para o fluxo.
