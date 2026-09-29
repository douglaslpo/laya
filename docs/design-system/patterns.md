# Padrões

## Superfície / seção

```svelte
<section class="{$glassTheme ? 'glass-section' : 'rounded-xl border border-surface-700 bg-surface-800'} p-6">
  <h2 class="text-laya-heading text-surface-50">Título</h2>
  <p class="text-laya-secondary text-surface-400">Descrição curta.</p>
</section>
```

## Modal

```svelte
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
     role="dialog" aria-modal="true" aria-labelledby="m-title" tabindex="-1"
     onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="{$glassTheme ? 'glass-modal' : 'border border-surface-700 bg-surface-800'} w-[480px] rounded-xl p-6 shadow-xl shadow-black/30">
    <h2 id="m-title" class="text-laya-heading text-surface-50">…</h2>
    <div class="mt-6 flex justify-end gap-2">
      <button class="rounded-md px-3 py-1.5 text-laya-secondary text-surface-300 hover:bg-surface-700" onclick={onclose}>Cancel</button>
      <button class="rounded-md bg-laya-orange px-3 py-1.5 text-laya-secondary font-medium text-surface-950">Confirm</button>
    </div>
  </div>
</div>
```

Regras: Esc fecha; foco inicial no primeiro controle; ação primária à direita em laranja; aninhado em card usa `z-[200]`; no claro+glass o backdrop vira véu quente automaticamente.

## Switch

```svelte
<button role="switch" aria-checked={on} aria-label={label} onclick={() => (on = !on)}
  class="relative h-6 w-11 rounded-full transition-colors {on ? 'bg-laya-orange' : 'bg-surface-600'}">
  <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {on ? 'translate-x-5' : ''}"></span>
</button>
```

## Select

Sempre `Dropdown` (`<Dropdown bind:value options={opts} size="sm" />`), nunca `<select>` nativo.

## Navegação

Ativo: `bg-laya-orange/10 text-laya-orange`. Inativo: `text-surface-400 hover:bg-surface-800 hover:text-surface-200`. A navegação da titlebar colapsa em dois estágios por detecção de colisão.

## Tooltip

```svelte
<span class="group/tip relative">
  <button aria-label="Retry">…</button>
  <span class="glass-tooltip pointer-events-none absolute … text-[10px] opacity-0 transition-opacity duration-75 group-hover/tip:opacity-100">Retry</span>
</span>
```

Tooltip complementa, nunca substitui, o `aria-label`.

## Toast

Aviso `bg-amber-950/90`, informação `bg-surface-800/90`, some após 5 s, empilhado no layout raiz.

## Popover / menu

Ação `use:portal` (`lib/actions/portal.ts`), posição fixa por `getBoundingClientRect`, `z-[100]`, classe `glass-dropdown` ou `glass-menu` com fallback sólido `bg-surface-800 border-surface-700`.

## Card com status

Fundo e borda por status (tabela em `foundations.md` §1.3), `StatusDot` com forma, rótulo textual, pulso só em `pending`/`agent_running`. Com `data-card-colors="off"`, tintas de status somem mas prioridade permanece.

## Confirmação de ação externa

Qualquer envio (e-mail, comentário, merge, transição) passa por `ConfirmAction`: resumo do `summary_template`, avisos (ex.: > 3 destinatários, transição terminal), impacto (`low|medium|high`) e botões Cancel / Confirm. Nunca envie direto de um clique sem este passo.

## Layouts

- **Feed card**: colunas flex round-robin (não CSS columns), FLIP ao reempacotar.
- **Feed list**: container queries escondem colunas; `content-visibility: auto` nas linhas.
- **Timeline**: eixo piecewise com faixas silenciosas colapsáveis; lanes 5–12; `hourPx` 15/30/60/120; itens sem lane vão para o overflow strip — nunca deslocados no tempo.
- **Omni**: tokens `--om-*`, escala `.om-*`, densidade via `data-omni-density`.
- **Painéis laterais**: detalhe 420 px, chat 460 px; durante a transição do painel o blur e as container queries ficam suspensos (`.panel-transitioning`).

## Atalhos

Teclas simples (fora de inputs e sem diálogo aberto): `c` compose, `a` agente, `s` resumo, `l` chat, `r` recentes, `b` favoritos. Com ⌘/Ctrl: `F` busca, `S` Coherence, `P` Pulse, `O` Omni, `D` descrições, `Shift+D` densidade, `[`/`]` histórico. Novo atalho → registrar em `KeybindingsConfig` e no layout raiz.

## Acessibilidade

- Botão só-ícone: `aria-label` obrigatório.
- Modal: `role="dialog"`, `aria-modal`, `aria-labelledby`, Esc, foco inicial (focus trap é dívida).
- Switch: `role="switch"`, `aria-checked`. Listas de opções: `role="listbox"`/`option`, `aria-selected`.
- Status: cor + forma + texto.
- Contraste: use os passos semânticos de `surface`; no claro, as sobrescritas de texto de status já garantem contraste.
- Foco: prefira `focus-visible:ring-2 focus-visible:ring-laya-orange/60` em controles novos.
- Movimento: respeite `$reducedMotion`.
- Não adicione `svelte-ignore a11y_*` sem justificar em comentário.

## Conteúdo

- UI em inglês, frases curtas, verbos no imperativo nos botões ("Send", "Retry", "Dismiss").
- Rótulos de status fixos: Processing, Ready, Agent Running, Input Needed, Done, Failed, Dismissed, Archived.
- Prioridade abreviada: CRIT, HIGH, MED, LOW.
- Números com `tnum`; custos com 2 casas; tempos relativos para < 24 h.
- Sem emoji na UI.
