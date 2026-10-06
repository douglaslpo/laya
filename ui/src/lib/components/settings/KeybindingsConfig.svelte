<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { glassTheme } from '$lib/stores/glassTheme';
	import { t } from '$lib/i18n';

	const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent);
	const mod = isMac ? '⌘' : 'Ctrl+';

	const keybindings = [
		{ key: 'A', id: 'run_agent', description: 'Open run agent dialog', scope: 'global', note: 'not_in_input' },
		{ key: 'B', id: 'bookmarks', description: 'Toggle bookmarks filter', scope: 'global', note: 'not_in_input' },
		{ key: 'C', id: 'compose', description: 'Open compose modal', scope: 'global', note: 'not_in_input' },
		{ key: 'L', id: 'chat', description: 'Toggle chat panel', scope: 'global', note: 'not_in_input' },
		{ key: `${mod}O`, id: 'omni', description: 'Go to Omni', scope: 'global', note: '' },
		{ key: `${mod}P`, id: 'pulse', description: 'Go to Pulse (feed)', scope: 'global', note: '' },
		{ key: 'R', id: 'recent', description: 'Toggle recent items', scope: 'global', note: 'not_in_input' },
		{ key: 'S', id: 'day_summary', description: 'Toggle day summary', scope: 'global', note: 'not_in_input' },
		{ key: `${mod}D`, id: 'card_descriptions', description: 'Toggle card descriptions', scope: 'global', note: '' },
		{ key: `${isMac ? '⇧⌘' : 'Ctrl+Shift+'}D`, id: 'card_layout', description: 'Toggle compact / relaxed card layout', scope: 'global', note: '' },
		{ key: 'Esc', id: 'dismiss_popover', description: 'Dismiss popover / dropdown', scope: 'modals', note: 'esc' },
		{ key: `${mod}.`, id: 'close_modal', description: 'Close modal', scope: 'modals', note: 'close_modal' },
		{ key: `${mod}↵`, id: 'send_compose', description: 'Send compose form', scope: 'compose', note: '' },
		{ key: `${mod}F`, id: 'focus_search', description: 'Focus search box', scope: 'feed', note: '' },
		{ key: `${mod}S`, id: 'coherence_search', description: 'Go to Coherence and focus search', scope: 'global', note: '' },
		{ key: `${mod}[`, id: 'back', description: 'Navigate back', scope: 'global', note: '' },
		{ key: `${mod}]`, id: 'forward', description: 'Navigate forward', scope: 'global', note: '' },
	];

	const scopeFallbacks: Record<string, string> = {
		global: 'Global',
		modals: 'Modals',
		compose: 'Compose modal',
		feed: 'Feed',
	};

	const noteFallbacks: Record<string, string> = {
		not_in_input: 'Only when not focused on an input field',
		esc: 'Closes auto-suggest or directory dropdown first',
		close_modal: 'Compose and Run Agent modals',
	};
</script>

<div class="space-y-8">
	<div class="{$glassTheme ? 'glass-section' : 'rounded-xl border border-surface-700 bg-surface-800'} p-6">
		<h3 class="mb-1 text-laya-heading font-semibold text-surface-50">{$t('settingsRules.kb_title', 'Keyboard Shortcuts')}</h3>
		<p class="mb-5 text-laya-base text-surface-400">{$t('settingsRules.kb_desc', 'View all available keyboard shortcuts across the application.')}</p>

		<div class="overflow-hidden rounded-lg border {$glassTheme ? 'border-white/[0.06]' : 'border-surface-700'}">
			<table class="w-full text-laya-base">
				<thead>
					<tr class="border-b {$glassTheme ? 'border-white/[0.06] bg-white/[0.03]' : 'border-surface-700 bg-surface-900/50'}">
						<th class="px-4 py-2.5 text-left text-laya-secondary font-medium uppercase tracking-wider text-surface-400">{$t('settingsRules.kb_col_key', 'Key')}</th>
						<th class="px-4 py-2.5 text-left text-laya-secondary font-medium uppercase tracking-wider text-surface-400">{$t('settingsRules.kb_col_action', 'Action')}</th>
						<th class="px-4 py-2.5 text-left text-laya-secondary font-medium uppercase tracking-wider text-surface-400">{$t('settingsRules.kb_col_scope', 'Scope')}</th>
					</tr>
				</thead>
				<tbody>
					{#each keybindings as binding, i}
						<tr class="border-b last:border-0 {$glassTheme ? 'border-white/[0.04]' : 'border-surface-700/50'} {$glassTheme ? (i % 2 === 0 ? 'bg-white/[0.02]' : 'bg-transparent') : (i % 2 === 0 ? 'bg-surface-800' : 'bg-surface-850/30')}">
							<td class="px-4 py-2.5">
								<kbd class="inline-flex min-w-[2rem] items-center justify-center rounded-md border px-2 py-0.5 font-mono text-laya-secondary text-surface-200 {$glassTheme ? 'border-white/[0.12] bg-white/[0.06]' : 'border-surface-600 bg-surface-900'}">{binding.key}</kbd>
							</td>
							<td class="px-4 py-2.5 text-surface-200">
								{$t(`settingsRules.kb_${binding.id}`, binding.description)}
								{#if binding.note}
									<span class="ml-1 text-laya-secondary text-surface-500">({$t(`settingsRules.kb_note_${binding.note}`, noteFallbacks[binding.note])})</span>
								{/if}
							</td>
							<td class="px-4 py-2.5">
								<span class="rounded-full {$glassTheme ? 'bg-white/[0.06]' : 'bg-surface-700/50'} px-2 py-0.5 text-laya-secondary text-surface-400">{$t(`settingsRules.kb_scope_${binding.scope}`, scopeFallbacks[binding.scope])}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
