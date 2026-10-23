<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { fade, scale } from 'svelte/transition';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { reducedMotion } from '$lib/stores/reducedMotion';
	import {
		egressConfirmations,
		reloadEgressConfirmations
	} from '$lib/stores/websocket';
	import {
		expireConfirmations,
		resolveConfirmation,
		secondsLeft
	} from '$lib/egress/pendingConfirmations';

	let now = $state(Date.now());
	let busy = $state<'confirm' | 'reject' | null>(null);
	// Outlives the resolved request so a failed send is still reported after the
	// request left the queue (otherwise the dialog would just vanish).
	let notice = $state<{ summary: string; message: string } | null>(null);
	let rejectButton = $state<HTMLButtonElement | null>(null);
	let closeButton = $state<HTMLButtonElement | null>(null);

	const current = $derived($egressConfirmations[0] ?? null);
	const queued = $derived(Math.max(0, $egressConfirmations.length - 1));
	const remaining = $derived(current ? secondsLeft(current, now) : 0);
	const countdown = $derived(
		`${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}`
	);
	const detailEntries = $derived(
		current
			? Object.entries(current.preview.details ?? {}).filter(
					([, v]) => v !== null && v !== undefined && v !== ''
				)
			: []
	);
	const impact = $derived(current?.preview.estimated_impact ?? 'low');
	const impactClass = $derived(
		impact === 'high'
			? 'bg-red-500/10 text-red-400 border-red-500/30'
			: impact === 'medium'
				? 'bg-laya-amber/10 text-laya-amber border-laya-amber/30'
				: 'bg-surface-800 text-surface-300 border-surface-700'
	);
	const duration = $derived($reducedMotion ? 0 : 150);

	// Tick the countdown and drop requests the engine already expired (300 s TTL).
	$effect(() => {
		if (!current) return;
		const timer = setInterval(() => {
			now = Date.now();
			egressConfirmations.update((q) => expireConfirmations(q, now));
		}, 1000);
		return () => clearInterval(timer);
	});

	// Initial focus on the non-destructive action whenever a new request shows.
	$effect(() => {
		if (current && rejectButton) rejectButton.focus();
		else if (!current && notice && closeButton) closeButton.focus();
	});

	async function resolve(action: 'confirm' | 'reject') {
		if (!current || busy) return;
		const { request_id: id, preview } = current;
		busy = action;
		notice = null;
		try {
			const res =
				action === 'confirm'
					? await engineApi.confirmPendingEgress(id)
					: await engineApi.rejectPendingEgress(id);
			egressConfirmations.update((q) => resolveConfirmation(q, id));
			if (res.status === 'failed') {
				const error = (res as { error?: string }).error;
				notice = { summary: preview.summary, message: error || 'The action failed.' };
			}
		} catch (err) {
			notice = {
				summary: preview.summary,
				message: err instanceof Error ? err.message : String(err)
			};
			// Expired / already resolved elsewhere: resync with the engine.
			await reloadEgressConfirmations();
		} finally {
			busy = null;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		e.preventDefault();
		if (!current) {
			notice = null;
			return;
		}
		// Esc rejects: dismissing without a decision would leave the MCP action
		// silently pending; rejecting is the safe default (nothing is sent).
		void resolve('reject');
	}
</script>

{#if current || notice}
	<div
		class="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
		role="dialog"
		aria-modal="true"
		aria-labelledby="egress-confirm-title"
		aria-describedby="egress-confirm-desc"
		tabindex="-1"
		onkeydown={handleKeydown}
		transition:fade={{ duration }}
	>
		<div
			class="mx-4 w-full max-w-lg rounded-xl p-6 shadow-xl shadow-black/30 {$glassTheme
				? 'glass-modal'
				: 'border border-surface-700 bg-surface-800'}"
			transition:scale={{ duration, start: 0.97 }}
		>
			{#if !current && notice}
				<h2 id="egress-confirm-title" class="text-laya-heading text-surface-50 break-words">
					Action not completed
				</h2>
				<p id="egress-confirm-desc" class="mt-1 text-laya-secondary text-surface-400 break-words">
					{notice.summary}
				</p>
				<p class="mt-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-laya-secondary text-red-400" role="alert">
					{notice.message}
				</p>
				<div class="mt-6 flex justify-end">
					<button
						bind:this={closeButton}
						class="rounded-md px-3 py-1.5 text-laya-secondary text-surface-300 hover:bg-surface-700"
						onclick={() => (notice = null)}
					>
						Close
					</button>
				</div>
			{:else if current}
			<div class="flex items-start justify-between gap-3">
				<div class="min-w-0">
					<p class="text-laya-micro font-medium uppercase tracking-wide text-laya-orange">
						Confirmation requested by an MCP client
					</p>
					<h2 id="egress-confirm-title" class="mt-1 text-laya-heading text-surface-50 break-words">
						{current.preview.summary}
					</h2>
					<p class="mt-0.5 text-laya-secondary text-surface-400">
						{current.platform} / {current.action_type}{#if current.connection_id}
							· {current.connection_id}{/if}
					</p>
				</div>
				<span
					class="shrink-0 rounded-md border border-surface-700 px-2 py-0.5 font-mono text-laya-micro text-surface-300"
					aria-label="Time left to confirm: {countdown}"
				>
					{countdown}
				</span>
			</div>

			<p id="egress-confirm-desc" class="mt-3 text-laya-secondary text-surface-300">
				Nothing has been sent yet. Review the action below; it only runs if you click Send.
			</p>

			{#if detailEntries.length > 0}
				<dl class="mt-4 max-h-60 space-y-1.5 overflow-y-auto rounded-lg border border-surface-700 bg-surface-900/50 p-3">
					{#each detailEntries as [key, value] (key)}
						<div class="flex items-start gap-2 text-laya-secondary">
							<dt class="w-24 shrink-0 font-medium text-surface-400">{key}</dt>
							<dd class="min-w-0 break-all text-surface-200 whitespace-pre-wrap">
								{typeof value === 'object' ? JSON.stringify(value) : String(value)}
							</dd>
						</div>
					{/each}
				</dl>
			{/if}

			{#if current.preview.warnings.length > 0}
				<ul class="mt-3 space-y-1" aria-label="Warnings">
					{#each current.preview.warnings as warning, i (i)}
						<li class="flex items-start gap-2 rounded-md border border-laya-amber/20 bg-laya-amber/10 px-3 py-2">
							<svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-laya-amber" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
							</svg>
							<span class="text-laya-secondary text-laya-amber">{warning}</span>
						</li>
					{/each}
				</ul>
			{/if}

			<div class="mt-3 flex items-center gap-2">
				<span class="text-laya-secondary text-surface-400">Impact</span>
				<span class="rounded-md border px-2 py-0.5 text-laya-micro font-medium {impactClass}">
					{impact}
				</span>
				{#if queued > 0}
					<span class="ml-auto text-laya-micro text-surface-400">+{queued} more waiting</span>
				{/if}
			</div>

			{#if notice}
				<p class="mt-3 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-laya-secondary text-red-400" role="alert">
					{notice.summary}: {notice.message}
				</p>
			{/if}

			<div class="mt-6 flex justify-end gap-2">
				<button
					bind:this={rejectButton}
					class="rounded-md px-3 py-1.5 text-laya-secondary text-surface-300 hover:bg-surface-700 disabled:cursor-not-allowed disabled:opacity-50"
					onclick={() => resolve('reject')}
					disabled={busy !== null}
				>
					{busy === 'reject' ? 'Rejecting…' : 'Reject'}
				</button>
				<button
					class="rounded-md bg-laya-orange px-3 py-1.5 text-laya-secondary font-medium text-surface-950 disabled:cursor-not-allowed disabled:opacity-50"
					onclick={() => resolve('confirm')}
					disabled={busy !== null}
				>
					{busy === 'confirm' ? 'Sending…' : 'Send'}
				</button>
			</div>
			{/if}
		</div>
	</div>
{/if}
