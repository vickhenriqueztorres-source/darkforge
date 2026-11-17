# UI-00 — Descoberta e adaptação

**Objetivo:** entender o código real antes de mudar qualquer coisa e decidir como o studio se encaixa nele.  
**Depende de:** nada.  
**Gate:** G-UI0.

## Tarefas

### UI-00-T01 — Mapa do repositório
Levantar o framework e a versão, o roteamento, a biblioteca de UI e estilos, os tokens de design, o cliente Supabase (server/browser), o padrão de migrations, os testes existentes, o worker/fila e o uso de Realtime.  
**Pronto quando:** o mapa estiver em `state.md` com os caminhos reais dos arquivos.

### UI-00-T02 — Inventário de schema
Listar as tabelas existentes e compará-las com `schema-reference.sql`. Para cada uma: reutilizar, estender, criar ou trocar por view.  
**Pronto quando:** a tabela de decisão estiver no ADR.

### UI-00-T03 — Status dos SPs dependentes
Verificar SP-01, SP-02, SP-03, SP-04, SP-05, SP-06, SP-07 e SP-08 e preencher a tabela "Agentes por disponibilidade" em `state.md`.  
**Pronto quando:** cada agente estiver marcado como disponível ou indisponível, com o motivo.

### UI-00-T04 — ADR de encaixe
Escrever `docs/studio-ui/adr/ADR-UI-001-encaixe.md` com o contexto, as decisões de tabela, a rota da tela, como o worker de agente usa a fila existente e os riscos.  
**Pronto quando:** o ADR estiver aprovado (ou registrado como decisão provisória).

### UI-00-T05 — Clean plate da cena
Preparar a imagem de fundo sem textos, pessoas nem painéis flutuantes, em pelo menos 2560px de largura, com versão WebP/AVIF. Se ainda não houver imagem, gerar com o prompt abaixo.  
**Pronto quando:** o arquivo estiver em `public/studio/` com dimensões registradas.

Prompt sugerido para o clean plate:
```text
Photorealistic tilt-shift photograph of an empty architectural scale model of a YouTube content studio on a dark oak desk, top-down 45-degree view. Open-ceiling rooms: data room with miniature server racks, research room with pinboards, central circular glass meeting room with a round table and chairs, recording room with tiny camera and ring light, thumbnail design room with monitors, strategy and publishing room with a wall calendar. NO people, NO text, NO signs, NO floating panels, NO logos. Warm brass desk lamp light, soft amber accent strips along corridors, walnut, brass and slate materials, shallow depth of field, ultra detailed, 16:9.
```

## Gate G-UI0
- [ ] Mapa do repositório em `state.md`
- [ ] ADR-UI-001 escrito
- [ ] Agentes marcados por disponibilidade
- [ ] Clean plate disponível
