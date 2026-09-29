---
name: laya-ui-design-system
description: Aplica o Design System do Laya ao construir ou alterar UI SvelteKit/Svelte 5 (tokens OKLCH, surface invertida no tema claro, glass, paleta acessível, tipografia text-laya-*, padrões de modal/switch/dropdown, movimento e acessibilidade). Use ao criar componentes, telas, estilos em ui/src, ou quando o usuário mencionar tema, cores, dark/light, glass, acessibilidade ou layout do feed/omni/timeline.
---

# UI com o Design System do Laya

Referência completa: `docs/design-system/` (README, foundations, components, patterns). Tokens em máquina: `docs/design-system/tokens.json`.

## Regras rápidas

1. **Runes Svelte 5** (`$props`, `$state`, `$derived`, `$effect`); eventos `onclick`; callbacks `onxxx`.
2. **Cores só por token**:
   - superfícies `bg-surface-900` (página) / `bg-surface-800` (card, popover) / `border-surface-700`;
   - texto `text-surface-50|200` (primário), `text-surface-400|500` (secundário);
   - marca `text-laya-orange`, `bg-laya-orange/10`;
   - áreas com tokens próprios: timeline `var(--tl-*)`, omni `var(--om-*)`.
   A escala `surface` é **invertida** no tema claro — não escreva variantes `dark:`.
3. **Mapas semânticos** vêm de `lib/utils/cardVisuals.ts` (prioridade, plataforma, avatar). Não copie mapas de persona/status em componentes novos; adicione ao módulo.
4. **Tipografia**: `text-laya-heading | base | secondary | micro` (seguem `--laya-font-base` 12–15 px). Evite `text-[Npx]`.
5. **Glass**: `class={$glassTheme ? 'glass-section' : 'rounded-xl border border-surface-700 bg-surface-800'}`.
6. **Movimento**: `transition:slide={{ duration: $reducedMotion ? 0 : 150 }}`; FLIP via `lib/utils/flip.ts`.
7. **Ícones**: SVG inline estilo Heroicons outline (`stroke="currentColor"`, `stroke-width` 1.5–2, `h-3.5 w-3.5`/`h-4 w-4`). Logos em `settings/PlatformIcon.svelte`. Sem emoji.
8. **A11y**: `aria-label` em botão só-ícone; modal com `role="dialog"`, `aria-modal`, Esc fecha, foco inicial; switch com `role="switch"` + `aria-checked`; status nunca só por cor (`StatusDot` usa forma).

## Padrões prontos

Modal:
```svelte
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
     role="dialog" aria-modal="true" aria-labelledby="dlg-title" tabindex="-1"
     onkeydown={(e) => e.key === 'Escape' && onclose()}>
  <div class="{$glassTheme ? 'glass-modal' : 'bg-surface-800 border border-surface-700'} w-[480px] rounded-xl p-6 shadow-xl">
    <h2 id="dlg-title" class="text-laya-heading text-surface-50">Título</h2>
  </div>
</div>
```

Switch:
```svelte
<button role="switch" aria-checked={on} aria-label="Ativar X" onclick={() => (on = !on)}
  class="relative h-6 w-11 rounded-full transition-colors {on ? 'bg-laya-orange' : 'bg-surface-600'}">
  <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {on ? 'translate-x-5' : ''}"></span>
</button>
```

Select: use `lib/components/Dropdown.svelte` (`bind:value`, `options`, `size`, `variant`) — não `<select>` nativo.

Navegação ativa: `bg-laya-orange/10 text-laya-orange`; inativa: `text-surface-400 hover:text-surface-200 hover:bg-surface-800`.

## Antes de concluir

```
- [ ] npm run check sem erros; lógica pura com teste vitest
- [ ] Dark e light
- [ ] Glass on e off
- [ ] Paleta acessível ([data-accessible-colors])
- [ ] Reduced motion
- [ ] Escala de fonte 12 e 15 px sem quebra
- [ ] Nenhum hex cru novo (exceto cores de marca de plataforma em cardVisuals.ts)
```

Novo token de cor: defina nas **cinco** variantes relevantes (dark, light, glass, light+glass, accessible) seguindo o modelo dos blocos `--tl-*`/`--om-*` em `ui/src/app.css`, e registre em `docs/design-system/foundations.md` e `tokens.json`.
