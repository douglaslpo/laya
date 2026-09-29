# Laya Design System

Linguagem visual **quente, densa e calma**: cinzas com matiz quente, laranja de marca como único acento forte, informação compacta com números tabulares, movimento discreto. A UI é uma ferramenta de trabalho aberta o dia inteiro — ela deve ser legível em 13 px, confortável no escuro e nunca gritar.

| Documento | Conteúdo |
|---|---|
| [foundations.md](foundations.md) | Tokens: cor (marca, surface, status, persona, prioridade, plataforma, acessível), tipografia, espaço, raio, elevação, camadas, glass, movimento, iconografia |
| [components.md](components.md) | Inventário dos componentes Svelte, props e quando usar |
| [patterns.md](patterns.md) | Padrões de composição (modal, switch, select, navegação, toast, tooltip, seção, layouts de feed/timeline/omni), acessibilidade e conteúdo |
| [tokens.json](tokens.json) | Tokens em formato de máquina (referência para ferramentas e revisão) |

Fonte da verdade do código: `ui/src/app.css` (tokens e receitas), `ui/src/routes/+layout.svelte` (aplicação dos eixos de aparência), `ui/src/lib/utils/cardVisuals.ts` (mapas semânticos), `ui/src/lib/stores/*` (preferências).

## Princípios

1. **Token antes de valor.** Componentes consomem tokens semânticos (`surface-*`, `laya-*`, `--tl-*`, `--om-*`). Um valor cru num componente é um token que ainda não existe.
2. **Um acento.** O laranja de marca (`--color-laya-orange`) marca seleção, foco, estado ativo e ação primária. Cores de status e persona informam; não decoram.
3. **Nunca só cor.** Status tem forma (`StatusDot`) e rótulo; a paleta acessível troca o eixo vermelho–verde por azul–amarelo.
4. **Densidade ajustável.** Tipografia deriva de `--laya-font-base` (12–15 px); densidade de card (`cardSize`) e descrições (`cardDescriptions`) são preferências.
5. **Movimento com propósito.** Transições curtas (75–300 ms) explicam mudança de posição/estado; tudo zera com reduced motion.
6. **Temas por inversão, não por variantes.** A escala `surface` inverte no tema claro; componentes não escrevem `dark:`.
7. **Tempo é verdade.** Na timeline, um item nunca sai do seu horário real para "caber".

## Eixos de aparência

Aplicados em `<html>` pelo layout raiz a partir de stores persistidas em localStorage:

| Eixo | Atributo / variável | Store | Padrão |
|---|---|---|---|
| Tema | `data-theme="dark\|light"` | `theme.ts` (`laya-theme`) | dark |
| Vidro | `data-glass-theme` | `glassTheme.ts` | ligado |
| Paleta acessível | `data-accessible-colors` | `accessibleColors.ts` | desligado |
| Movimento reduzido | `data-reduced-motion` | `reducedMotion.ts` | preferência do SO no 1º uso |
| Fonte do sistema | `data-system-font` | `systemFont.ts` | desligado |
| Escala de fonte | `--laya-font-base` (12–15 px), `--om-scale` | `fontScale.ts` | 13 px |
| Cores de card | `data-card-colors="on\|off"` | `cardColors.ts` | on |
| Modo do feed | `data-feed-view="card\|list\|timeline"` | `feedView.ts` | card |
| Densidade Omni | `data-omni-density="compact"` | — | normal |

Todo componente novo deve funcionar na matriz **tema (2) × vidro (2) × paleta acessível (2) × reduced motion (2)** e nas escalas 12 e 15 px.

## Stack

Tailwind CSS v4 (`@theme` gera `bg-laya-*`, `text-laya-*`), Skeleton v4 apenas como CSS base e tema `cerberus` (o pacote `skeleton-svelte` não é usado), fontes Inter e Geist Mono auto-hospedadas, ícones SVG inline, sem biblioteca de componentes externa.

## Governança

- **Novo token**: defina em `app.css` para dark, light, glass, light+glass e acessível (modelo: blocos `--tl-*` e `--om-*`), registre em `foundations.md` e `tokens.json`.
- **Novo componente**: siga `patterns.md`, documente em `components.md`, extraia lógica pura para `lib/` com teste vitest.
- **Revisão**: checklist de aparência do `docs/guardrails.md` (G-UI-02, G-UI-03, G-UI-08).
- Skill de apoio para agentes: `.cursor/skills/laya-ui-design-system`.

## Dívidas do DS

| Dívida | Direção |
|---|---|
| Mapa de cores de persona duplicado em 5 componentes (`ActionCard`, `CardGroup`, `ListRow`, `CardDetail`, `ClassificationDialog`) | Consolidar em `cardVisuals.ts` (`PERSONA_COLORS`) |
| ~200 sobrescritas de utilitários Tailwind por tema/paleta no feed | Migrar para tokens semânticos no estilo `--tl-*` |
| Tamanhos arbitrários (`text-[10px]`, `text-[11px]`…) | Mapear para `text-laya-micro/secondary` ou novos tokens |
| Sem `focus-visible:` (44 `focus:`), só 1 `sr-only`, modais sem focus trap, 67 `svelte-ignore a11y` | Padrão de foco visível e utilitário de focus trap |
| Sem testes de componente/visuais | Avaliar Testing Library + Playwright (decisão #50) |
