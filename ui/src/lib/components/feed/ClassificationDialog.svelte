<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { PRIORITY_COLORS } from '$lib/utils/cardVisuals';
	import type { ActionCard } from '$lib/api/types';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { t } from '$lib/i18n';

	let {
		card,
		onclose,
		onupdated
	}: {
		card: ActionCard;
		onclose: () => void;
		onupdated?: () => void;
	} = $props();

	const priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
	const personas = ['ENGINEER', 'COMMS', 'OPS', 'SALES', 'HR', 'FINANCE'] as const;

	// svelte-ignore state_referenced_locally
	let priority = $state(card.priority);
	// svelte-ignore state_referenced_locally
	let persona = $state(card.persona);
	let ruleText = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	let hasChanges = $derived(
		priority !== card.priority || persona !== card.persona || ruleText.trim() !== ''
	);

	async function save() {
		if (!hasChanges) return;
		saving = true;
		error = null;
		try {
			await engineApi.updateCardClassification(card.card_id, {
				priority: priority !== card.priority ? priority : undefined,
				persona: persona !== card.persona ? persona : undefined,
				rule_text: ruleText.trim() || undefined
			});
			onupdated?.();
			onclose();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('feedCards.classify_failed', 'Failed to update classification');
		} finally {
			saving = false;
		}
	}

	const priorityColors = PRIORITY_COLORS;

	const personaColors: Record<string, string> = {
		ENGINEER: 'border-violet-500 text-violet-400',
		COMMS: 'border-emerald-500 text-emerald-400',
		OPS: 'border-amber-500 text-amber-400',
		SALES: 'border-sky-500 text-sky-400',
		HR: 'border-rose-500 text-rose-400',
		FINANCE: 'border-teal-500 text-teal-400'
	};
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
	role="dialog"
	aria-label={$t('feedCards.classify_dialog_label', 'Adjust classification')}
	tabindex="-1"
	onclick={(e) => { if (e.target === e.currentTarget) onclose(); }}
	onkeydown={(e) => { if (e.key === 'Escape') onclose(); }}
>
	<div class="mx-4 w-full max-w-lg rounded-xl border {$glassTheme ? 'glass-card border-surface-700/40 bg-surface-900/40' : 'border-surface-700 bg-surface-800 shadow-2xl'}">
		<!-- Header -->
		<div class="border-b px-5 py-4 {$glassTheme ? 'border-surface-700/40' : 'border-surface-700'}">
			<h3 class="text-sm font-semibold text-surface-50">{$t('feedCards.classify_title', 'Adjust Classification')}</h3>
			<p class="mt-1 text-xs text-surface-400">{$t('feedCards.classify_desc', 'Correct the priority or persona for this card. Your changes help Laya learn.')}</p>
		</div>

		<!-- Body -->
		<div class="space-y-4 px-5 py-4">
			{#if error}
				<div class="rounded-lg border border-red-800 bg-red-900/30 px-3 py-2 text-xs text-red-300">{error}</div>
			{/if}

			<!-- Priority -->
			<div>
				<span class="mb-1.5 block text-xs font-medium text-surface-300">{$t('feedCards.priority', 'Priority')}</span>
				<div class="flex gap-1.5" role="group" aria-label={$t('feedCards.priority', 'Priority')}>
					{#each priorities as p}
						<button
							class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors
								{priority === p
									? priorityColors[p]
									: 'bg-surface-700 text-surface-400 hover:text-surface-200'}"
							onclick={() => (priority = p)}
						>
							{$t(`shared.priority_${p}`, p)}
						</button>
					{/each}
				</div>
				{#if priority !== card.priority}
					<p class="mt-1 text-[10px] text-surface-500">{$t(`shared.priority_${card.priority}`, card.priority)} → {$t(`shared.priority_${priority}`, priority)}</p>
				{/if}
			</div>

			<!-- Persona -->
			<div>
				<span class="mb-1.5 block text-xs font-medium text-surface-300">{$t('feedCards.persona', 'Persona')}</span>
				<div class="flex gap-1.5" role="group" aria-label={$t('feedCards.persona', 'Persona')}>
					{#each personas as p}
						<button
							class="rounded-md border px-3 py-1.5 text-xs font-medium transition-colors
								{persona === p
									? personaColors[p]
									: 'border-surface-600 text-surface-400 hover:text-surface-200'}"
							onclick={() => (persona = p)}
						>
							{$t(`shared.persona_${p}`, p)}
						</button>
					{/each}
				</div>
				{#if persona !== card.persona}
					<p class="mt-1 text-[10px] text-surface-500">{$t(`shared.persona_${card.persona}`, card.persona)} → {$t(`shared.persona_${persona}`, persona)}</p>
				{/if}
			</div>

			<!-- Rule (optional) -->
			<div>
				<label class="mb-1.5 block text-xs font-medium text-surface-300" for="classification-rule">
					{$t('feedCards.add_rule', 'Add a rule')} <span class="font-normal text-surface-500">{$t('feedCards.optional', '(optional)')}</span>
				</label>
				<input
					id="classification-rule"
					bind:value={ruleText}
					placeholder={$t('feedCards.rule_placeholder', 'e.g., "Always treat emails from legal@acme.com as HIGH priority"')}
					class="w-full rounded-lg border px-3 py-2 text-sm text-surface-50 placeholder-surface-500 {$glassTheme ? 'border-surface-600/40 bg-surface-800/40 backdrop-blur-sm' : 'border-surface-600 bg-surface-900'}"
				/>
				<p class="mt-1 text-[10px] text-surface-500">{$t('feedCards.rule_hint', 'Rules are applied to all future cards and can be managed in Settings → Rules.')}</p>
			</div>
		</div>

		<!-- Footer -->
		<div class="flex justify-end gap-2 border-t px-5 py-3 {$glassTheme ? 'border-surface-700/40' : 'border-surface-700'}">
			<button
				class="rounded-md px-3 py-1.5 text-xs text-surface-400 transition-colors hover:text-surface-200"
				onclick={onclose}
				disabled={saving}
			>
				{$t('common.cancel', 'Cancel')}
			</button>
			<button
				class="rounded-md bg-laya-orange px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-laya-orange/80 disabled:opacity-50"
				onclick={save}
				disabled={!hasChanges || saving}
			>
				{saving ? $t('feedCards.saving', 'Saving...') : $t('common.save', 'Save')}
			</button>
		</div>
	</div>
</div>
