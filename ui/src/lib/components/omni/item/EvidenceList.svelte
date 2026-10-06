<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { OmniBucket, OmniEvidenceCard } from '$lib/api/types';
	import { BUCKET_GROUP_LABELS, BUCKET_TOKEN, describeBuckets, groupByBucket } from '$lib/omni/buckets';
	import { num } from '$lib/omni/layers';
	import type { EvidenceActionContext } from '$lib/omni/evidenceActions';
	import EvidenceRow from './EvidenceRow.svelte';
	import { t, locale } from '$lib/i18n';

	let {
		cards,
		totalCount,
		activeFilter,
		expandedCardIds,
		showAll,
		loading,
		onToggleCard,
		onExpandAll,
		onCollapseAll,
		onShowAll,
		actions
	}: {
		/** Cards after the active filter has been applied. */
		cards: OmniEvidenceCard[];
		/** Total source_cards on the item, including any that failed to load. */
		totalCount: number;
		activeFilter: OmniBucket | null;
		expandedCardIds: Set<string>;
		showAll: boolean;
		loading: boolean;
		onToggleCard: (cardId: string) => void;
		onExpandAll: (cardIds: string[]) => void;
		onCollapseAll: () => void;
		onShowAll: () => void;
		actions: EvidenceActionContext;
	} = $props();

	// At most 8 rows initially. This is what keeps "112 emails triaged" usable:
	// eight rows and a count, not 112 fully-expanded panels.
	const PAGE_SIZE = 8;

	const visible = $derived(showAll ? cards : cards.slice(0, PAGE_SIZE));
	const hidden = $derived(showAll ? [] : cards.slice(PAGE_SIZE));
	const groups = $derived(groupByBucket(visible));
	const groupLabels = $derived.by(() => {
		void $locale;
		return { ...BUCKET_GROUP_LABELS };
	});
	const hiddenSummary = $derived.by(() => {
		void $locale;
		return describeBuckets(hidden);
	});

	// The control acts on what is on screen: "expand all" opens the rendered rows
	// (not the ones still behind "show all"), and only flips to "collapse all"
	// once every one of them is open.
	const visibleIds = $derived(visible.map((c) => c.card_id));
	const allExpanded = $derived(visibleIds.length > 0 && visibleIds.every((id) => expandedCardIds.has(id)));

	// The scroller is set directly rather than via scrollIntoView: the row expands
	// in place, and scrollIntoView would yank the whole page around it.
	let listEl = $state<HTMLDivElement | null>(null);
	export function scrollToTop() {
		if (listEl) listEl.scrollTop = 0;
	}
</script>

<div class="flex min-h-0 flex-1 flex-col">
	<div class="flex flex-none items-center gap-[9px] px-[22px] pt-2.5 pb-2">
		<span class="om-title-sm" style="color: var(--om-text);">{$t('omniTrace.evidence', 'Evidence')}</span>
		<span
			class="om-mono rounded-full px-[7px] py-px text-[calc(10px*var(--om-scale))]"
			style="background: var(--om-chip); color: var(--om-text-mid);"
		>{totalCount === 1
			? $t('omniTrace.cards_one', '{count} card', { count: num(totalCount, $locale) })
			: $t('omniTrace.cards_other', '{count} cards', { count: num(totalCount, $locale) })}</span>
		<span class="flex-1"></span>
		<span class="om-pill-t" style="color: var(--om-text-meta);">{$t('omniTrace.grouped_by_outcome', 'grouped by outcome')}</span>
		<button
			type="button"
			class="om-hint rounded-md px-2 py-[3px] transition-colors disabled:opacity-40"
			style="border: 1px solid var(--om-border-input); color: var(--om-text-mid);"
			disabled={visibleIds.length === 0}
			onclick={() => (allExpanded ? onCollapseAll() : onExpandAll(visibleIds))}
		>{allExpanded ? $t('omniTrace.collapse_all', 'Collapse all') : $t('omniTrace.expand_all', 'Expand all')}</button>
	</div>

	<div bind:this={listEl} class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3.5">
		{#if loading}
			<!-- Skeleton rather than a blank page: the claim above is already
			     readable, so the evidence should look like it's arriving, not missing. -->
			{#each Array(5) as _, i}
				<div class="flex items-center gap-2.5 px-2.5 py-2" aria-hidden="true">
					<span class="h-1.5 w-1.5 rounded-full" style="background: var(--om-chip);"></span>
					<span class="h-2.5 w-[112px] rounded" style="background: var(--om-chip);"></span>
					<span
						class="h-2.5 flex-1 rounded"
						style="background: var(--om-chip); opacity: {1 - i * 0.15};"
					></span>
				</div>
			{/each}
		{:else if cards.length === 0}
			<p class="om-item-t px-2.5 py-3" style="color: var(--om-text-meta);">
				{#if activeFilter}
					{$t('omniTrace.no_cards_in_outcome', 'No cards in this outcome. Clear the filter to see the rest.')}
				{:else}
					{$t('omniTrace.no_evidence_loaded', 'No evidence cards could be loaded for this line.')}
				{/if}
			</p>
		{:else}
			{#each groups as group (group.bucket)}
				<div class="flex items-center gap-2 px-2 pt-[7px] pb-1">
					<span
						class="h-[5px] w-[5px] rounded-full"
						style="background: var(--om-{BUCKET_TOKEN[group.bucket]}-dot);"
					></span>
					<span
						class="om-mono text-[calc(9px*var(--om-scale))] font-semibold tracking-[0.11em]"
						style="color: var(--om-{BUCKET_TOKEN[group.bucket]}-fg);"
					>{groupLabels[group.bucket]}</span>
					<span class="h-px flex-1" style="background: var(--om-border);"></span>
				</div>
				{#each group.cards as card (card.card_id)}
					<EvidenceRow
						{card}
						expanded={expandedCardIds.has(card.card_id)}
						onToggle={() => onToggleCard(card.card_id)}
						{actions}
					/>
				{/each}
			{/each}
		{/if}
	</div>

	{#if hidden.length > 0}
		<!-- Pinned outside the scroller so the count stays visible while reading -->
		<div
			class="om-pill-t mx-6 mb-3 flex flex-none items-center gap-2 px-2.5 pt-[9px]"
			style="border-top: 1px dashed var(--om-border); color: var(--om-text-meta);"
		>
			<span class="om-mono">+{hidden.length}</span>
			{hidden.length === 1
				? $t('omniTrace.more_cards_one', 'more card in this aggregate — {summary}', { summary: hiddenSummary })
				: $t('omniTrace.more_cards_other', 'more cards in this aggregate — {summary}', { summary: hiddenSummary })}
			<span class="flex-1"></span>
			<button type="button" class="transition-colors" style="color: var(--om-comp-label);" onclick={onShowAll}>
				{$t('omniTrace.show_all', 'Show all {count}', { count: num(cards.length, $locale) })}
			</button>
		</div>
	{/if}
</div>
