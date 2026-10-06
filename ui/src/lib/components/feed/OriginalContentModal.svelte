<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { SourceEvent } from '$lib/api/types';
	import { engineApi } from '$lib/api/engine';
	import { parseBackendDate } from '$lib/utils/datetime';
	import { glassTheme } from '$lib/stores/glassTheme';
	import MarkdownRender from '$lib/components/MarkdownRender.svelte';
	import PlatformBadge from '$lib/components/PlatformBadge.svelte';
	import { t, locale } from '$lib/i18n';

	let {
		cardId,
		onclose
	}: {
		cardId: string;
		onclose: () => void;
	} = $props();

	let event = $state<SourceEvent | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	$effect(() => {
		const id = cardId;
		loading = true;
		error = null;
		engineApi
			.getCardSourceEvent(id)
			.then((e) => (event = e))
			.catch((e) => (error = e instanceof Error ? e.message : $t('feedCards.original_failed', 'Failed to load original content')))
			.finally(() => (loading = false));
	});

	// Always-present, structured fields shown as labeled rows at the top.
	let headerRows = $derived(
		event
			? ([
					[$t('feedCards.field_from', 'From'), event.actor_name],
					[$t('feedCards.field_email', 'Email'), event.actor_email],
					[$t('feedCards.field_handle', 'Handle'), event.actor_handle],
					[$t('feedCards.field_subject', 'Subject'), event.subject_title],
					[$t('feedCards.field_reference', 'Reference'), event.subject_id],
					[$t('feedCards.field_received', 'Received'), parseBackendDate(event.timestamp)?.toLocaleString($locale)]
				].filter(([, v]) => v) as [string, string][])
			: []
	);

	// Platform-specific metadata rendered generically as key → value.
	let metadataRows = $derived(
		event
			? Object.entries(event.metadata ?? {}).map(([k, v]) => [
					k,
					typeof v === 'string' ? v : JSON.stringify(v)
				] as [string, string])
			: []
	);
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
	role="dialog"
	aria-label={$t('feedCards.original_title', 'Original content')}
	tabindex="-1"
	onclick={(e) => { if (e.target === e.currentTarget) onclose(); }}
	onkeydown={(e) => { if (e.key === 'Escape') onclose(); }}
>
	<div class="mx-4 flex max-h-[85vh] w-full max-w-2xl flex-col rounded-xl border {$glassTheme ? 'glass-card border-surface-700/40 bg-surface-900/40' : 'border-surface-700 bg-surface-800 shadow-2xl'}">
		<!-- Header -->
		<div class="flex items-center justify-between gap-3 border-b px-5 py-4 {$glassTheme ? 'border-surface-700/40' : 'border-surface-700'}">
			<div class="flex min-w-0 items-center gap-2">
				<h3 class="text-sm font-semibold text-surface-50">{$t('feedCards.original_title', 'Original content')}</h3>
				{#if event}
					<PlatformBadge platform={event.platform} />
					<span class="truncate text-xs text-surface-500">{event.raw_event_type}</span>
				{/if}
			</div>
			<button
				class="rounded p-1 text-surface-400 transition-colors hover:text-surface-100"
				aria-label={$t('common.close', 'Close')}
				onclick={onclose}
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>

		<!-- Body -->
		<div class="flex-1 overflow-y-auto px-5 py-4">
			{#if loading}
				<p class="text-sm text-surface-400">{$t('feedCards.original_loading', 'Loading original content…')}</p>
			{:else if error}
				<div class="rounded-lg border border-red-800 bg-red-900/30 px-3 py-2 text-xs text-red-300">{error}</div>
			{:else if event}
				<!-- Structured fields -->
				{#if headerRows.length || event.subject_url}
					<dl class="mb-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
						{#each headerRows as [label, value]}
							<dt class="font-semibold uppercase tracking-wider text-surface-500">{label}</dt>
							<dd class="min-w-0 break-words text-surface-300">{value}</dd>
						{/each}
						{#if event.subject_url}
							<dt class="font-semibold uppercase tracking-wider text-surface-500">{$t('feedCards.field_link', 'Link')}</dt>
							<dd class="min-w-0 break-all">
								<a
									href={event.subject_url}
									target="_blank"
									rel="noopener noreferrer"
									class="text-laya-orange transition-colors hover:text-laya-peach"
								>{event.subject_url}</a>
							</dd>
						{/if}
					</dl>
				{/if}

				<!-- Original message body -->
				{#if event.body && event.body.trim()}
					<div class="mb-4">
						<div class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500">{$t('feedCards.message', 'Message')}</div>
						<div class="rounded-lg border px-3 py-2 {$glassTheme ? 'border-surface-700/40 bg-surface-900/30' : 'border-surface-700 bg-surface-900/50'}">
							<MarkdownRender content={event.body} class="text-sm text-surface-200" />
						</div>
					</div>
				{:else}
					<p class="mb-4 text-sm text-surface-500">{$t('feedCards.no_body', 'No message body was captured for this event.')}</p>
				{/if}

				<!-- Platform metadata (generic key → value) -->
				{#if metadataRows.length}
					<div>
						<div class="mb-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500">{$t('feedCards.metadata', 'Metadata')}</div>
						<dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
							{#each metadataRows as [key, value]}
								<dt class="font-medium text-surface-400">{key}</dt>
								<dd class="min-w-0 break-words font-mono text-surface-300">{value}</dd>
							{/each}
						</dl>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>
