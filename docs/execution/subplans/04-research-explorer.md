# SP-04 — Research Explorer

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-03  
**Desbloqueia:** SP-05 e o contexto de SP-07  
**Objetivo:** transformar pesquisa pública em referências curadas e evidências auditáveis, sem prometer acesso a dados privados.

## 1. Escopo

Research runs, busca de canais/vídeos públicos, similaridade, snapshots, evidências, curadoria, notas, quota e deduplicação.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-04-T01 | Modelar Research Run e filtros | Objetivo, canal, idioma, período, formato, orçamento e estado | Toda execução tem intenção, versão e parâmetros reproduzíveis |
| SP-04-T02 | Implementar fontes públicas permitidas | Adapter de busca e política de uso | APIs oficiais primeiro; nenhum contorno de robots, autenticação ou termos |
| SP-04-T03 | Implementar candidatos semelhantes | Score de similaridade e explicação | Cada candidato mostra os fatores que o aproximam do canal |
| SP-04-T04 | Persistir snapshots e evidências | Canal/vídeo/título/capa, URL, data e origem | Usuário consegue abrir a referência e saber quando foi observada |
| SP-04-T05 | Implementar curadoria | Aprovar, rejeitar, arquivar, notas e coleções | Decisões são auditáveis e não apagam a trilha da pesquisa |
| SP-04-T06 | Integrar quota e idempotência | Orçamento, reserva, retry e deduplicação | Pesquisa repetida não duplica resultados nem consome quota desnecessária |
| SP-04-T07 | Construir Research Explorer UI | Busca, filtros, candidatos, evidências e curadoria | Público versus privado é visualmente e semanticamente explícito |
| SP-04-T08 | Criar testes de pesquisa | T-RES-001 e testes de retry/quota | Nenhuma métrica privada é inferida como fato; toda evidência é rastreável |

## 3. Regras de produto

- Uma referência pública não prova desempenho privado, causalidade ou intenção do concorrente.
- Similaridade é uma hipótese de pesquisa, não uma verdade editorial.
- O usuário deve conseguir rejeitar ruído antes de alimentar oportunidades.
- Snapshots devem respeitar retenção e direitos configurados.
- Pesquisa deve ter orçamento e prioridade separados do sync próprio.

## 4. Testes mínimos

- Pesquisa sem resultados, resultado duplicado e resultado fora do idioma.
- Fonte indisponível depois do snapshot.
- Retry após timeout e após crash.
- Quota esgotada no meio da pesquisa.
- Aprovação/rejeição/arquivamento e filtro por coleção.
- Tentativa de apresentar métrica pública como analytics privado.
- Acesso a evidência de outro workspace.

## 5. Gate G4

Só avançar quando:

- uma pesquisa real ou ambiente autorizado de teste produz candidatos rastreáveis;
- referências podem ser curadas e revisitadas;
- quota e retry são controlados;
- RES-001–007 têm evidência;
- nenhuma recomendação posterior poderá usar referência sem origem.
