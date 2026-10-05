<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { OmniChangesResponse, TimelineEntry } from '$lib/api/types';
	import { duration, hhmm, layerLabel } from '$lib/omni/layers';
	import { parseBackendDate } from '$lib/utils/datetime';
	import VersionPicker from './VersionPicker.svelte';
	import { t, locale } from '$lib/i18n';

	let {
		changes,
		loading,
		baseVersion,
		displayVersion,
		entries,
		onBaseChange,
		onDisplayChange,
		onFullHistory,
		onOpenItem
	}: {
		changes: OmniChangesResponse | null;
		loading: boolean;
		baseVersion: number;
		displayVersion: number;
		/** Selectable versions from the sampled timeline, newest first. */
		entries: TimelineEntry[];
		onBaseChange: (version: number) => void;
		onDisplayChange: (version: number) => void;
		onFullHistory: () => void;
		/** `atVersion` is the version where the entry last saw its item — folded
		 *  and resolved rows name items the displayed snapshot no longer carries,
		 *  and the drill-down needs to know where to look instead. */
		onOpenItem: (itemKey: string, section: string, atVersion?: number) => void;
	} = $props();

	// The base list only offers versions OLDER than the displayed one — comparing
	// against something newer than what you're looking at is meaningless.
	const baseEntries = $derived(entries.filter((e) => e.version < displayVersion));
	const displayEntries = $derived(entries);

	const sinceLabel = $derived.by(() => {
		void $locale;
		const at = parseBackendDate(changes?.base_generated_at);
		if (!at) return null;
		return duration(Date.now() - at.getTime());
	});

	type Entry = {
		kind: 'added' | 'folded' | 'resolved';
		glyph: string;
		text: string;
		meta: string;
		itemKey: string;
		section: string;
		atVersion?: number;
	};

	// Order: added → folded → resolved. What arrived, what moved, what's finished.
	const rows = $derived.by((): Entry[] => {
		if (!changes) return [];
		const out: Entry[] = [];

		void $locale;
		for (const a of changes.added) {
			const bits = [layerLabel(a.section)];
			if (a.source_count) {
				bits.push(
					a.source_count === 1
						? $t('omniTrace.from_events_one', 'from {count} event', { count: a.source_count })
						: $t('omniTrace.from_events_other', 'from {count} events', { count: a.source_count })
				);
			}
			if (a.platforms.length) bits.push(a.platforms.join(', '));
			out.push({
				kind: 'added',
				glyph: '+',
				text: a.text,
				meta: bits.join(' · '),
				itemKey: a.item_key,
				section: a.section,
				atVersion: a.version
			});
		}

		for (const f of changes.folded) {
			const text = f.to_section
				? $t('omniTrace.change_folded_into', '"{from}" folded into "{to}"', {
						from: f.from_text,
						to: f.to_text ?? ''
					})
				: $t('omniTrace.change_compressed_away', '"{text}" compressed away', { text: f.from_text });
			const meta = f.to_section
				? `${layerLabel(f.from_section)} → ${layerLabel(f.to_section)}`
				: $t('omniTrace.change_dropped_meta', '{section} · dropped', {
						section: layerLabel(f.from_section)
					});
			out.push({
				kind: 'folded',
				glyph: '↓',
				text,
				meta,
				itemKey: f.item_key,
				section: f.to_section ?? f.from_section,
				// A real fold's key names the DESTINATION item, present at the fold's
				// own version; a compressed-away line last existed one version before.
				atVersion: f.version !== undefined ? (f.to_section ? f.version : f.version - 1) : undefined
			});
		}

		for (const r of changes.resolved) {
			const closed = hhmm(r.resolved_at);
			out.push({
				kind: 'resolved',
				glyph: '✓',
				text: $t('omniTrace.change_resolved', '"{text}" resolved', { text: r.text }),
				meta: closed
					? $t('omniTrace.change_closed_meta', '{section} · closed {time}', {
							section: layerLabel(r.section),
							time: closed
						})
					: layerLabel(r.section),
				itemKey: r.item_key,
				section: r.section,
				// The write at r.version dropped the line; its last state is one back.
				atVersion: r.version !== undefined ? r.version - 1 : undefined
			});
		}

		return out;
	});

	const KIND_STYLE: Record<Entry['kind'], string> = {
		added: 'background: var(--om-ok-bg); color: var(--om-ok-fg);',
		folded: 'background: var(--om-warn-bg); color: var(--om-warn-fg);',
		resolved: 'background: var(--om-neutral-bg); color: var(--om-neutral-fg);'
	};

	const chips = $derived.by(() => {
		if (!changes) return [];
		return (
			[
				{ kind: 'added' as const, glyph: '+', n: changes.counts.added, label: $t('omni.new') },
				{ kind: 'folded' as const, glyph: '↓', n: changes.counts.folded, label: $t('omni.folded') },
				{ kind: 'resolved' as const, glyph: '✓', n: changes.counts.resolved, label: $t('omni.resolved') }
			] satisfies Array<{ kind: Entry['kind']; glyph: string; n: number; label: string }>
		).filter((c) => c.n > 0);
	});
</script>

<div
	class="om-rail om-glass flex w-[326px] flex-none flex-col"
	style="border-left: 1px solid var(--om-border);"
>
	<!-- z-10 so the version popovers' anchors sit above the entry rows below -->
	<div class="relative z-10 flex flex-none flex-col gap-1 px-[15px] pt-3 pb-2">
		<div class="flex items-center gap-2">
			<span class="om-title" style="color: var(--om-text);">{$t('omni.what_changed')}</span>
			<span class="flex-1"></span>
			<VersionPicker
				value={baseVersion}
				entries={baseEntries}
				variant="base"
				caption={$t('omniTrace.compare_against', 'Compare against')}
				disabled={baseEntries.length === 0}
				onSelect={onBaseChange}
				{onFullHistory}
			/>
			<span class="om-mono text-[calc(10px*var(--om-scale))]" style="color: var(--om-text-faint);">→</span>
			<VersionPicker
				value={displayVersion}
				entries={displayEntries}
				variant="display"
				caption={$t('omniTrace.show_version', 'Show version')}
				onSelect={onDisplayChange}
				{onFullHistory}
			/>
		</div>
		<span class="om-pill-t" style="color: var(--om-text-meta);">
			{#if sinceLabel}
				{$t('omni.since_last_looked')}, {sinceLabel}
			{:else}
				{$t('omniTrace.compared_with_version', 'compared with v{version}', { version: baseVersion })}
			{/if}
		</span>
	</div>

	{#if chips.length > 0}
		<div class="flex flex-none flex-wrap gap-1.5 px-[15px] pb-2.5">
			{#each chips as chip (chip.kind)}
				<span
					class="om-pill-t inline-flex items-center gap-1.5 rounded-full px-[9px] py-[2.5px] font-semibold"
					style={KIND_STYLE[chip.kind]}
				>
					<span class="om-mono text-[calc(11px*var(--om-scale))]" aria-hidden="true">{chip.glyph}</span>
					{chip.n}
					{chip.label}
				</span>
			{/each}
		</div>
	{/if}

	<div
		class="flex min-h-0 flex-1 flex-col overflow-y-auto"
		style="border-top: 1px solid var(--om-divider);"
	>
		{#if loading}
			<p class="om-pill-t px-[15px] py-3" style="color: var(--om-text-meta);">{$t('omniTrace.reading_diff', 'Reading the diff…')}</p>
		{:else if rows.length === 0}
			<p class="om-entry-t px-[15px] py-3" style="color: var(--om-text-meta);">
				{#if changes && changes.unsummarized_versions.length > 0}
					<!-- Honest about the gap rather than claiming nothing happened:
					     pre-migration-072 snapshots recorded no diff to read back. -->
					{$t('omniTrace.no_recorded_changes', 'No recorded changes between v{base} and v{display}.', {
						base: baseVersion,
						display: displayVersion
					})}
					{changes.unsummarized_versions.length === 1
						? $t('omniTrace.versions_predate_one', '{count} version predates change tracking.', {
								count: changes.unsummarized_versions.length
							})
						: $t('omniTrace.versions_predate_other', '{count} versions predate change tracking.', {
								count: changes.unsummarized_versions.length
							})}
				{:else}
					{$t('omniTrace.nothing_changed_since', 'Nothing has changed since v{version}.', {
						version: baseVersion
					})}
				{/if}
			</p>
		{:else}
			{#each rows as row, i (row.kind + row.itemKey + i)}
				<button
					type="button"
					class="om-row flex w-full gap-[9px] rounded-none px-[15px] text-left"
					style="padding-block: calc(9px * var(--om-density));
						border-bottom: 1px solid var(--om-divider);"
					onclick={() => onOpenItem(row.itemKey, row.section, row.atVersion)}
				>
					<span
						class="om-mono flex h-[17px] w-[17px] flex-none items-center justify-center rounded-[5px] text-[calc(10px*var(--om-scale))] font-semibold"
						style={KIND_STYLE[row.kind]}
						aria-hidden="true">{row.glyph}</span
					>
					<span class="min-w-0 flex-1">
						<span
							class="om-entry-t block"
							style="color: {row.kind === 'resolved'
								? 'var(--om-text-dim)'
								: 'var(--om-text-strong)'};
								{row.kind === 'resolved'
								? 'text-decoration: line-through; text-decoration-color: var(--om-bar-low);'
								: ''}"
						>{row.text}</span>
						<span class="om-meta mt-[3px] block uppercase">{row.meta}</span>
					</span>
				</button>
			{/each}
		{/if}
	</div>
</div>
