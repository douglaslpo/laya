# Translating the Laya UI

Every user-visible string in the UI goes through `$lib/i18n` in three locales: `pt-BR` (default), `en`, `es`.

## Where keys live

- `index.ts` holds the core dictionary (navigation, common words, settings tabs).
- `locales/<area>.ts` holds one dictionary per UI area. Files are merged automatically (`import.meta.glob`); never edit `index.ts` to register them.
- Keys are prefixed with the area id: `settingsRules.filter_title`. Reuse `common.*` keys from `index.ts` instead of duplicating them.

```ts
// locales/<area>.ts
import type { LocaleDict } from '../types';

const dict: LocaleDict = {
	'pt-BR': { 'area.key': '…' },
	en: { 'area.key': '…' },
	es: { 'area.key': '…' }
};

export default dict;
```

## In components

```svelte
<script lang="ts">
	import { t, locale } from '$lib/i18n';
	let label = $derived($t('area.count', '{count} cards', { count }));
</script>

<h3>{$t('area.title', 'Filter Rules')}</h3>
<input placeholder={$t('area.search_placeholder', 'Search…')} />
```

- Second argument is the English text (fallback and documentation).
- `{name}` placeholders are filled from the third argument. Never build sentences by concatenating translated fragments.
- Plurals: separate keys `area.cards_one` / `area.cards_other`.
- Dates and numbers: `toLocaleString($locale, …)` / `Intl.*($locale)` instead of a hard-coded `'en-US'`.
- Plain `.ts` modules: `tr(key, fallback, params)` (non-reactive). Tests run in Node with the default locale `pt-BR`; call `locale.set('en')` in tests that assert English text.

## Do not translate

Product and platform names (Laya, Pulse, Omni, Slack, GitHub, Jira, Ollama…), values sent to or compared against the engine (statuses, priorities, personas, categories, event types, field paths, operators), code identifiers, CSS classes, keyboard keys, URLs, log messages.

When a value is both logic and label (e.g. `HIGH`), keep the value and translate only its display. Priorities, personas, categories and card statuses already have labels in `locales/shared.ts`: `$t(\`shared.priority_${p}\`, p)`, `shared.persona_*`, `shared.category_*`, `shared.status_*`.

## Check

```bash
npx vitest run src/lib/i18n   # same keys in every locale, no empty strings, placeholders match
npx svelte-check --tsconfig ./tsconfig.json
```
