<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { locale, setLocale, t, type SupportedLocale } from '$lib/i18n';

	const languages: Array<{ code: SupportedLocale; flag: string; label: string }> = [
		{ code: 'pt-BR', flag: '🇧🇷', label: 'PT' },
		{ code: 'en', flag: '🇺🇸', label: 'EN' },
		{ code: 'es', flag: '🇪🇸', label: 'ES' }
	];

	function handleSelect(code: SupportedLocale) {
		setLocale(code);
	}
</script>

<div class="flex items-center gap-0.5 bg-surface-800 border border-surface-700 rounded-lg p-0.5 text-xs font-medium">
	{#each languages as lang}
		<button
			onclick={() => handleSelect(lang.code)}
			class="px-2 py-0.5 rounded transition-all flex items-center gap-1
				{$locale === lang.code
					? 'bg-laya-orange/20 text-laya-orange font-semibold shadow-sm border border-laya-orange/30'
					: 'text-surface-400 hover:text-surface-200 hover:bg-surface-700'}"
			title={$t('shell.change_language', 'Change language to {language}', { language: lang.label })}
		>
			<span>{lang.flag}</span>
			<span>{lang.label}</span>
		</button>
	{/each}
</div>
