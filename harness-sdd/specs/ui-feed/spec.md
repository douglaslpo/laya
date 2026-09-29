# Spec: UI do feed (Pulse)

**Status:** baseline · **Donos:** `ui/src/routes/feed/+page.svelte`, `ui/src/lib/components/feed/`, `ui/src/lib/{feed,timeline}/`, `ui/src/lib/stores/{feedFilters,feedView,websocket}.ts`

## Requisitos
- **RF-01** Três modos de visualização (`feedView`): `card`, `list`, `timeline`, persistidos em localStorage.
- **RF-02** Visão `card`: colunas flex de 320 px com gap de 16 px, quantidade = `floor((largura+16)/336)`, distribuição round-robin; animação FLIP ao reempacotar.
- **RF-03** Visão `list`: colunas escondidas progressivamente por container query (space < 700 px, persona < 620, tempo < 550, ações < 490).
- **RF-04** Visão `timeline` ("Day Column"): eixo de horário piecewise com faixas silenciosas colapsáveis, lanes, heat rail, calendário e overflow strip; volume bruto vem de `GET /events/day`.
- **RF-05** Filtros compartilhados (`feedFilters`): status, prioridade, ordenação, space, plataformas, brush de horário; persistidos no engine (`feed_preferences`) com debounce de 500 ms; aplicam-se aos três modos.
- **RF-06** Atualizações em tempo real via WS: `card_created`, `card_updated` (reducer puro `cardUpdateReducer.ts`), `card_deleted`, `group_carried_forward`, `context_group_*`.
- **RF-07** Painel de detalhe (420 px) com ações sugeridas, preview de egress e confirmação.
- **RF-08** Atalhos de teclado (bloqueados em inputs ou com diálogo aberto): `c` compose, `a` agente, `s` resumo, `l` chat, `r` recentes, `b` favoritos; ⌘/Ctrl+F busca, +P Pulse, +O Omni, +S Coherence.

## Critérios de aceitação
- **CA-01** Dado um `card_updated` que muda status, então o card muda de estado visual sem recarregar a página e respeita os filtros ativos.
- **CA-02** Dado um thread cujo horário colide com outros e não há lane livre, então ele vai para o overflow strip e **não** é deslocado do horário real.
- **CA-03** Dado um filtro de plataforma, então ele vale nas três visões.
- **CA-04** Dado `reduced motion`, então FLIP, pulsos e transições têm duração efetiva zero.
- **CA-05** Dado o tema claro, glass ligado/desligado ou paleta acessível, então todo status continua distinguível (cor + forma do `StatusDot`).

## Critérios de rejeição / casos-limite
- **CR-01** WS desconectado: reconexão com backoff 1–10 s; fila de até 500 mensagens drenada sem travar a UI.
- **CR-02** Atalhos não disparam dentro de inputs nem com `[role=dialog]` aberto.

## Invariantes
- **INV-01** Layout de colunas é flex round-robin, não CSS columns.
- **INV-02** `feed/+page.svelte` não volta a crescer: lógica em `lib/feed`, `lib/utils/flip.ts`, componentes em `components/feed/`.
- **INV-03** Cores via tokens do Design System.

## Referências
Testes (vitest): `lib/feed/cardUpdateReducer.test.ts`, `lib/timeline/{scale,lanes,threads}.test.ts`, `lib/utils/threadAttention.test.ts`, `lib/stores/feedFilters.test.ts`, `lib/stores/recentCards.test.ts`. Design System: `docs/design-system/`.
