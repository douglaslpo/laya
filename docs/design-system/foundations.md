# Fundamentos

Valores em OKLCH (`oklch(L C H)`), como em `ui/src/app.css`. Hex só quando o código usa hex (marcas de plataforma).

## 1. Cor

### 1.1 Marca (`@theme`, gera `bg-/text-/border-laya-*`)

| Token | Valor | Ref. | Uso |
|---|---|---|---|
| `--color-laya-orange` | `oklch(0.775 0.130 63)` | #f6ac69 | **Acento primário**: seleção, ativo, foco, switch ligado |
| `--color-laya-gold` | `oklch(0.810 0.120 80)` | #f6bc66 | Destaques secundários |
| `--color-laya-peach` | `oklch(0.905 0.065 72)` | #ffdab9 | `code` inline em markdown |
| `--color-laya-coral` | `oklch(0.740 0.155 50)` | #ff9770 | Alertas suaves de marca |
| `--color-laya-amber` | `oklch(0.700 0.180 58)` | — | Âmbar profundo |
| `--color-laya-sand` | `oklch(0.885 0.045 78)` | — | Fundos neutros quentes |
| `--color-laya-blush` | `oklch(0.940 0.035 70)` | — | Fundos suaves |
| `--color-laya-terracotta` | `oklch(0.620 0.135 45)` | — | Ênfase terrosa |

No tema claro, texto de marca escurece para contraste (ex.: `.text-laya-orange` → `oklch(0.55 0.16 58)`, `.text-laya-coral` → `oklch(0.50 0.18 42)`).

### 1.2 Surface (cinzas quentes, invertida no claro)

| Passo | Dark | Light | Papel semântico |
|---|---|---|---|
| 50 | `0.970 0.008 65` | `0.220 0.018 44` | texto de maior contraste |
| 100 | `0.920 0.010 64` | `0.310 0.017 48` | |
| 200 | `0.840 0.011 62` | `0.410 0.016 53` | texto primário |
| 300 | `0.740 0.013 60` | `0.510 0.014 58` | |
| 400 | `0.630 0.013 58` | `0.615 0.012 62` | texto secundário |
| 500 | `0.520 0.012 56` | `0.720 0.009 65` | texto terciário / desabilitado |
| 600 | `0.420 0.011 54` | `0.810 0.007 68` | divisores, trilho de switch |
| 700 | `0.340 0.009 52` | `0.880 0.006 70` | bordas |
| 800 | `0.265 0.008 50` | `0.935 0.006 72` | card, popover, input |
| 900 | `0.185 0.007 48` | `0.970 0.005 74` | fundo da página |
| 950 | `0.120 0.005 46` | `0.990 0.003 78` | fundo extremo |

Uso: página `bg-surface-900`; card/popover `bg-surface-800`; borda `border-surface-700`; divisor `border-surface-600`; texto `text-surface-50|200` (primário), `text-surface-400|500` (secundário).

### 1.3 Status do card

| Status | Rótulo | Ponto (`StatusDot`) | Forma | `--status-rgb` (glass) | Fundo sólido dark |
|---|---|---|---|---|---|
| `pending` | Processing | yellow | meio círculo, pulsando | `217 119 6` | `bg-amber-950/55` + `card-pulse-amber` |
| `ready` | Ready | amber | círculo cheio | `217 119 6` | `bg-amber-950/55` |
| `agent_running` | Agent Running | violet | círculo cheio, pulsando | `139 92 246` | `bg-violet-950/55` + `card-pulse-violet` |
| `awaiting_input` | Input Needed | violet | triângulo | `127 119 221` | `bg-violet-950/55` |
| `done` | Done | green | check | `99 153 34` | `bg-emerald-950/50` |
| `failed` | Failed | red | X (tooltip com o erro) | `244 63 110` | `bg-rose-950/60` |
| `dismissed` | Dismissed | `surface-500` | traço | `120 113 108` | `bg-surface-800/40` + `opacity-50` |
| `archived` | Archived | `surface-600` | quadrado vazado | `120 113 108` | idem |

Pontos no dark: amber `0.75 0.17 65`, yellow `0.80 0.16 90`, green `0.72 0.19 145`, red `0.55 0.22 27`, violet `0.65 0.20 285`, sky `0.68 0.14 295`. No claro, versões mais escuras; fundos viram pastéis (ex.: pendente `0.94 0.045 75`, falhou `0.94 0.045 25`).

Os pontos usam classes próprias `status-dot-*` (e não `text-*-400`) para escapar das sobrescritas de texto do tema claro, que os deixariam escuros demais. `ready` e `agent_running` compartilham a forma e se distinguem por matiz e pulso — ao criar variações, preserve pelo menos dois canais (forma, matiz, animação, rótulo).

### 1.4 Persona

| Persona | Texto | Chip |
|---|---|---|
| ENGINEER | `text-violet-400` | `bg-violet-500/10 border-violet-500/20` |
| COMMS | `text-emerald-400` | `bg-emerald-500/10 border-emerald-500/20` |
| OPS | `text-amber-400` | `bg-amber-500/10 border-amber-500/20` |
| SALES | `text-sky-400` | `bg-sky-500/10 border-sky-500/20` |
| HR | `text-rose-400` | `bg-rose-500/10 border-rose-500/20` |
| FINANCE | `text-teal-400` | `bg-teal-500/10 border-teal-500/20` |

### 1.5 Prioridade (`cardVisuals.ts`)

| Prioridade | Rótulo | Classes |
|---|---|---|
| CRITICAL | CRIT | `bg-red-600 text-red-50` |
| HIGH | HIGH | `bg-rose-500/25 text-rose-300` |
| MEDIUM | MED | `bg-amber-500/20 text-amber-300` |
| LOW | LOW | `bg-surface-700/40 text-surface-400` |

### 1.6 Plataforma (`cardVisuals.ts`)

gmail `#EA4335` · github `#9CA3AF` · bitbucket / bitbucket_server / jira `#2684FF` · outlook / outlook_calendar `#0078D4` · calendar / google_calendar `#1A73E8` · slack `#611F69` · linear `#5E6AD2` · notion `#8B8B85` · laya `#F97316` · fallback `#6B7280`. Avatares de ator: `oklch(0.62 0.11 {hash})` determinístico por nome (`actorAvatarColor`).

### 1.7 Paleta acessível (`[data-accessible-colors]`)

Eixo azul–amarelo para daltonismo: ready/pending → `#0EA5E9`; done → `#EAB308`; aprovação/agente → `#A855F7`; failed → ardósia `#475569` (distinção por luminância). Personas: Engineer 302°, Sales índigo 265°, Comms teal 195°, HR vermelhão 40°.

### 1.8 Tokens por área

- **Timeline `--tl-*`**: chrome (`--tl-rail-bg`, `--tl-grid`, `--tl-divider`, `--tl-control-*`), cápsula (`--tl-capsule-bg|border|title|foot`), faixa silenciosa (`--tl-quiet-*`), tons de status `node|bg|fg` para ready/running/done/failed/dormant, atenção (`--tl-escalate-*`, `--tl-agent-*`), reuniões (`--tl-meet-*`, `--tl-meet-clash-*`), trilhos (`--tl-heat`, `--tl-now`, `--tl-brush`, `--tl-brush-edge`). Definidos para dark, light, glass e light+glass.
- **Omni `--om-*`**: superfícies (`--om-bar` → `--om-chip`), linhas (`--om-divider`, `--om-border*`), texto em 7 níveis (`--om-text` → `--om-text-faint`), desfechos `ok|warn|alert|neutral` × `dot|bg|fg`, prioridade `--om-pri-*`, camadas `--om-layer-{attention,recent,period,milestone}` (matizes 27/65/250/90). `--om-scale` é **número sem unidade** (= fonte/13).

Estes dois blocos são o **modelo de referência** para novos tokens.

## 2. Tipografia

| Item | Valor |
|---|---|
| Família base/título | `'Inter', system-ui, sans-serif` (`InterVariable.woff2`, 100–900) |
| Mono | `'Geist Mono', ui-monospace, …` (`GeistMono-Variable.woff2`) |
| Números | `font-feature-settings: 'tnum' 1` global |
| Fonte do sistema | `[data-system-font]` troca para `system-ui` |

Escala (base `--laya-font-base`, padrão 13 px, ajustável 12–15):

| Classe | Tamanho | line-height | Uso |
|---|---|---|---|
| `.text-laya-heading` | base + 5 px | 1.4 | títulos de painel/modal |
| `.text-laya-base` | base | 1.5 | corpo |
| `.text-laya-secondary` | base − 2 px | 1.5 | metadados, rótulos |
| `.text-laya-micro` | base − 3 px | 1.4 | badges, timestamps |

Omni tem escala própria em px × `--om-scale` (`.om-num-lg` 29 px mono … `.om-tag` 8 px). Markdown usa `.prose-plan` (h1 1.25rem/700, h2 1.1rem, h3 0.95rem; links e blockquote em laranja).

## 3. Espaço e layout

- Grade Tailwind (múltiplos de 4 px). Card: `px-4 pt-3 pb-2`; seção de settings: `p-6`; `main`: `p-4`.
- Alturas fixas: titlebar 38 px (`--header-h`), rodapé 33 px (`--footer-h`), controle `Dropdown` 38 px (md) / 32 px (sm).
- Feed: card 320 px, gap 16 px, colunas `floor((w+16)/336)`, round-robin. Painel de detalhe 420 px. Chat 460 px (expandido `w-[75vw] min-w-[460px] max-w-[1100px]`).
- Lista: container queries escondem colunas em 700/620/550/490 px.

## 4. Raio

| Token | Uso |
|---|---|
| `rounded-xl` (12 px) | cards, seções sólidas |
| `rounded-lg` (8 px) | menus, inputs grandes, modais |
| `rounded-md` (6 px) | botões, inputs, chips |
| `rounded` (4 px) | badges |
| `rounded-full` | avatares, pontos, switches |
| 14 px | `.glass-section` |
| 7 px | `.glass-icon`, `.tl-capsule`, `.om-row` |
| 5 px | `.om-item-pill` |

## 5. Elevação e camadas

- Sólido: `shadow-lg`; modais `shadow-xl shadow-black/30`.
- Glass: brilho interno `inset 0 0.5px 0 rgb(255 255 255 / .08)` + sombra difusa `0 8px 32px -8px rgb(0 0 0 / .25)`.

| Camada | z-index |
|---|---|
| Titlebar | `z-[9999]` (backdrop de menus `9998`) |
| Modais aninhados em card | `z-[200]` |
| Dropdowns portados | `z-[100]` |
| Modais | `z-50` |
| Chat | `z-40` |

## 6. Vidro (glassmorphism, `[data-glass-theme]`)

| Classe | Uso | Blur / saturate (dark) |
|---|---|---|
| `.glass-card` | cards | 16 px / 1.3 (claro 22 px / 1.8) |
| `.glass-card-flat` | linhas de lista | 16 px / 1.3 |
| `.glass-section` | seções grandes | 14 px / 1.6, raio 14 px |
| `.glass-panel` | colunas | 14 px / 1.6 |
| `.glass-modal` | modais | fundo `rgb(35 30 25 / .88)` |
| `.glass-dropdown` | popovers | 28 px / 1.8 |
| `.glass-menu` | menus | 24 px / 1.5 |
| `.glass-tooltip`, `-dense` | tooltips | 24 px / 1.6 |
| `.glass-input` | inputs | 10 px / 1.4; foco borda `rgb(246 172 105 / .55)` |
| `.glass-icon--{alert,time,info,accent}` | chip de ícone 22 px | 8 px |
| `.glass-badge`, `.linked-badge` | pílulas | 8 px |
| `.glass-dim`, `.glass-focus`, `.glass-hover` | estados de seleção/hover | — |

Fundo glass: `#14110E` com três gradientes radiais quentes (claro `#FAF4EA`). `.glass-card[data-status]` usa `--status-rgb` para borda e brilho. Controles aninhados em superfícies glass herdam estilo automaticamente.

## 7. Movimento

| Token/uso | Valor |
|---|---|
| Tooltip | 75 ms |
| Linhas/pílulas Omni | 120 ms |
| Dropdown (`dropdown-in`) | 150 ms, `translateY(-4px) scale(.97)` |
| Troca de rota | `in:fly={{ y: 6, duration: 150 }}` |
| Glass hover | 180 ms ease |
| Saída de card | 250 ms, `scale(.96)` |
| FLIP (`lib/utils/flip.ts`) | 300 ms, entrada 250 ms |
| Painel | 300 ms |
| Pulsos | `card-pulse-glow` 2.5 s, `status-glow-pulse` 2 s, `tl-escalate` 1.4 s |

Reduced motion (`[data-reduced-motion]`): durações forçadas a 0.01 ms e pulsos desligados; em componentes, `duration: $reducedMotion ? 0 : N`. Omni também respeita `@media (prefers-reduced-motion)`.

## 8. Iconografia

SVG inline estilo Heroicons outline: `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width` 1.5–2 (2.5 em ícones muito pequenos), `stroke-linecap/linejoin="round"`. Tamanhos `h-3`, `h-3.5`, `h-4`. Logos de plataforma em `settings/PlatformIcon.svelte` (`fill="currentColor"`, `size`). Imagens de marca em `lib/assets` (`laya-processing`, `laya-progress`, `laya-splash`). Sem emoji como ícone.
