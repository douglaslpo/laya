<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { OmniEvidenceCard, OmniItemResponse, OmniLineage } from '$lib/api/types';
	import { LAYER_BY_TYPE, countdownTo, duration, num } from '$lib/omni/layers';
	import { cardBucket } from '$lib/omni/buckets';
	import { parseBackendDate } from '$lib/utils/datetime';
	import { t, locale } from '$lib/i18n';

	let {
		lineage,
		version,
		shareOfDay,
		missingCardIds,
		cards,
		onAsk,
		onShowMissing
	}: {
		lineage: OmniLineage | null;
		version: number | null;
		shareOfDay: OmniItemResponse['share_of_day'] | null;
		missingCardIds: string[];
		cards: OmniEvidenceCard[];
		onAsk: (prompt: string) => void;
		onShowMissing: () => void;
	} = $props();

	let composerText = $state('');

	// --- THIS LINE IN OMNI ---
	// The honest answer to "how did this line get here". Built from the lineage
	// walk rather than invented: each row is a real version range.
	type Step = { text: string; meta: string; state: 'past' | 'current' | 'future' };

	const steps = $derived.by((): Step[] => {
		if (!lineage || lineage.section_history.length === 0) return [];
		void $locale;
		const history = lineage.section_history;
		const firstStep = history[0];
		const current = history[history.length - 1];
		const out: Step[] = [];
		const cardCount = (count: number) =>
			count === 1
				? $t('omniTrace.cards_one', '{count} card', { count })
				: $t('omniTrace.cards_other', '{count} cards', { count });

		const firstAt = parseBackendDate(firstStep.generated_at);
		const firstAgo = firstAt ? duration(Date.now() - firstAt.getTime()) : '';
		const firstLayer = LAYER_BY_TYPE[firstStep.section]?.title ?? firstStep.section;
		out.push({
			text: $t('omniTrace.step_first_synthesized', 'First synthesized into {layer}', { layer: firstLayer }),
			meta: [
				`v${firstStep.version}`,
				firstAgo ? $t('omniTrace.time_ago', '{time} ago', { time: firstAgo }) : null,
				cardCount(firstStep.source_count)
			]
				.filter(Boolean)
				.join(' · '),
			state: 'past'
		});

		// The middle: how it grew between first appearance and now.
		if (history.length > 2) {
			const middleStart = history[1];
			const middleEnd = history[history.length - 2];
			const grew = current.source_count - firstStep.source_count;
			out.push({
				text:
					grew > 0
						? grew === 1
							? $t('omniTrace.step_grew_one', 'Grew as {count} more card landed', { count: grew })
							: $t('omniTrace.step_grew_other', 'Grew as {count} more cards landed', { count: grew })
						: $t('omniTrace.step_carried_unchanged', 'Carried forward unchanged'),
				meta: [
					middleStart.version === middleEnd.version
						? `v${middleStart.version}`
						: `v${middleStart.version} → v${middleEnd.version}`,
					lineage.rewrite_count > 0
						? $t('omniTrace.counts_rewritten', 'counts rewritten {count}×', {
								count: lineage.rewrite_count
							})
						: null
				]
					.filter(Boolean)
					.join(' · '),
				state: 'past'
			});
		}

		const currentLayer = LAYER_BY_TYPE[current.section]?.title ?? current.section;
		out.push({
			text: $t('omniTrace.step_standing_in', 'Standing in {layer} now', { layer: currentLayer }),
			meta: `v${current.version} · ${cardCount(current.source_count)} · ${$t('omniTrace.you_are_here', 'you are here')}`,
			state: 'current'
		});

		if (lineage.next_fold) {
			const target = LAYER_BY_TYPE[lineage.next_fold.to_section]?.title ?? lineage.next_fold.to_section;
			const eta = countdownTo(lineage.next_fold.expected_at);
			out.push({
				text: $t('omniTrace.step_folds_into', 'Folds into {layer}', { layer: target }),
				meta: eta
					? $t('omniTrace.next_synthesis_eta', 'at the next synthesis, {eta} away', { eta })
					: $t('omniTrace.next_synthesis_at', 'at the next synthesis'),
				state: 'future'
			});
		}

		return out;
	});

	const sharePct = $derived(
		shareOfDay && shareOfDay.day_events > 0
			? Math.round(shareOfDay.ratio * 1000) / 10
			: null
	);

	// --- ASK ABOUT THIS LINE ---
	// Prompts generated from what is actually on the page, not a fixed list.
	const prompts = $derived.by(() => {
		const out: string[] = [];
		const awaiting = cards.filter((c) => cardBucket(c) === 'awaiting_you');
		if (awaiting.length > 1) {
			out.push(
				$t('omniTrace.prompt_blocking', 'Which of these {count} items is actually blocking someone?', {
					count: awaiting.length
				})
			);
		} else if (awaiting.length === 1) {
			out.push(
				$t('omniTrace.prompt_what_to_do', 'What do I need to do about {ref}?', {
					ref: awaiting[0].source_ref ?? awaiting[0].header
				})
			);
		}

		const byPlatform = new Map<string, number>();
		for (const c of cards) {
			if (c.platform) byPlatform.set(c.platform, (byPlatform.get(c.platform) ?? 0) + 1);
		}
		const dominant = [...byPlatform.entries()].sort((a, b) => b[1] - a[1])[0];
		if (dominant) {
			out.push(
				$t('omniTrace.prompt_summarise_platform', 'Summarise what changed on {platform} in these cards.', {
					platform: dominant[0]
				})
			);
		}

		// Oldest still-open card — the one most likely to have gone stale.
		const oldestOpen = cards
			.filter((c) => cardBucket(c) !== 'resolved')
			.map((c) => ({ c, t: parseBackendDate(c.created_at)?.getTime() ?? Infinity }))
			.sort((a, b) => a.t - b.t)[0];
		if (oldestOpen?.c.actor_name) {
			out.push(
				oldestOpen.c.source_ref
					? $t('omniTrace.prompt_draft_reply', 'Draft a reply to {name} on {ref}.', {
							name: oldestOpen.c.actor_name.split(' ')[0],
							ref: oldestOpen.c.source_ref
						})
					: $t('omniTrace.prompt_draft_reply_thread', 'Draft a reply to {name} on this thread.', {
							name: oldestOpen.c.actor_name.split(' ')[0]
						})
			);
		}

		if (out.length === 0) {
			out.push($t('omniTrace.prompt_state_of_line', 'What is the state of everything in this line?'));
		}
		return out.slice(0, 3);
	});

	function send() {
		const text = composerText.trim();
		if (!text) return;
		composerText = '';
		onAsk(text);
	}
</script>

<div
	class="om-rail om-glass flex w-[344px] flex-none flex-col overflow-y-auto"
	style="border-left: 1px solid var(--om-border);"
>
	{#if steps.length > 0}
		<div class="flex-none px-4 pt-3.5 pb-3" style="border-bottom: 1px solid var(--om-divider);">
			<div class="om-micro mb-2.5">{$t('omniTrace.this_line_in_omni', 'This line in Omni')}</div>
			<div class="flex flex-col gap-2.5">
				{#each steps as step (step.text)}
					<div class="flex gap-2.5">
						<span
							class="mt-[3px] h-2 w-2 flex-none rounded-full"
							style="background: {step.state === 'current'
								? 'var(--color-laya-orange)'
								: step.state === 'future'
									? 'transparent'
									: 'var(--om-text-faint)'};
								{step.state === 'current'
								? 'box-shadow: 0 0 0 3px var(--om-comp-bg);'
								: ''}
								{step.state === 'future' ? 'border: 1px solid var(--om-text-faint);' : ''}"
						></span>
						<div class="min-w-0 flex-1">
							<div
								class="om-item-t leading-[1.4]"
								style="color: {step.state === 'current' ? 'var(--om-text-strong)' : 'var(--om-text-body)'};
									{step.state === 'current' ? 'font-weight: 600;' : ''}"
							>{step.text}</div>
							<div class="om-meta mt-0.5">{step.meta}</div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	{#if sharePct !== null && shareOfDay}
		<div
			class="flex flex-none flex-col gap-2.5 px-4 py-[13px]"
			style="border-bottom: 1px solid var(--om-divider);"
		>
			<div class="om-micro">{$t('omniTrace.share_of_today', 'Share of today')}</div>
			<div class="flex items-baseline gap-2">
				<span class="om-num-md" style="color: var(--om-comp-num);">
					{sharePct}<span class="text-[calc(15px*var(--om-scale))]">%</span>
				</span>
				<span class="om-pill-t leading-[1.35]" style="color: var(--om-text-meta);">
					{$t('omniTrace.share_events_of', '{count} of {total} events', {
						count: num(shareOfDay.cards, $locale),
						total: num(shareOfDay.day_events, $locale)
					})}<br />{$t('omniTrace.processed_today', 'processed today')}
				</span>
			</div>
			<div class="h-1.5 overflow-hidden rounded-[3px]" style="background: var(--om-chip);">
				<span
					class="block h-full"
					style="width: {Math.max(1, Math.min(100, sharePct))}%; background: var(--color-laya-orange);"
				></span>
			</div>
		</div>
	{/if}

	{#if missingCardIds.length > 0}
		<!-- Never render a count the page can't back up without saying so. This is
		     the fix for the old silent-allSettled drop. -->
		<div
			class="mx-4 my-[13px] flex flex-none gap-2.5 rounded-lg px-3 py-2.5"
			style="border: 1px solid var(--om-attn-border); background: var(--om-attn-bg);"
		>
			<span
				class="flex-none text-[calc(12px*var(--om-scale))] leading-[1.3]"
				style="color: var(--om-alert-fg);"
				aria-hidden="true">!</span
			>
			<div class="om-entry-t leading-[1.5]" style="color: var(--om-text-body);">
				<strong class="font-semibold" style="color: var(--om-alert-fg);">
					{missingCardIds.length === 1
						? $t('omniTrace.missing_cards_one', '{count} source card unavailable.', {
								count: missingCardIds.length
							})
						: $t('omniTrace.missing_cards_other', '{count} source cards unavailable.', {
								count: missingCardIds.length
							})}
				</strong>
				{$t(
					'omniTrace.missing_cards_body',
					"They were archived after this snapshot was written, so this aggregate's counts are ahead of what you can open."
				)}
				<button
					type="button"
					class="mt-1.5 block transition-colors"
					style="color: var(--om-comp-label);"
					onclick={onShowMissing}
				>{$t('omniTrace.see_what_dropped', 'See what was dropped')}</button>
			</div>
		</div>
	{/if}

	<div class="flex min-h-0 flex-1 flex-col" style="border-top: 1px solid var(--om-divider);">
		<div class="flex flex-none items-center gap-2 px-4 pt-3 pb-2.5">
			<span class="om-title-sm" style="color: var(--om-text);">{$t('omniTrace.ask_about_line', 'Ask about this line')}</span>
			<span class="flex-1"></span>
			<span class="om-mono text-[calc(9px*var(--om-scale))]" style="color: var(--om-text-faint);">
				{$t('omniTrace.in_context', '{count} in context', { count: num(cards.length, $locale) })}
			</span>
		</div>

		<div class="flex flex-col gap-1.5 px-4">
			{#each prompts as prompt (prompt)}
				<button
					type="button"
					class="om-entry-t om-prompt-pill block rounded-[7px] px-2.5 py-2 text-left transition-colors"
					onclick={() => onAsk(prompt)}
				>{prompt}</button>
			{/each}
		</div>

		<div class="flex-1"></div>

		<div
			class="mx-4 mt-3 mb-3.5 flex flex-none items-center gap-2 rounded-lg px-[11px] py-2"
			style="border: 1px solid var(--om-border-input); background: var(--om-inset);"
		>
			<input
				type="text"
				class="om-entry-t min-w-0 flex-1 bg-transparent outline-none"
				style="color: var(--om-text-body);"
				placeholder={$t('omniTrace.ask_placeholder', 'Ask anything about these {count} cards…', { count: cards.length })}
				bind:value={composerText}
				onkeydown={(e) => {
					if (e.key === 'Enter') {
						e.preventDefault();
						send();
					}
				}}
			/>
			<button
				type="button"
				class="flex h-5 w-5 flex-none items-center justify-center rounded-md text-[calc(11px*var(--om-scale))] disabled:opacity-40"
				style="background: var(--color-laya-orange); color: var(--om-bar);"
				aria-label={$t('omniTrace.ask', 'Ask')}
				disabled={!composerText.trim()}
				onclick={send}
			>↑</button>
		</div>
	</div>
</div>

<style>
	/* Hover lives in CSS so the two tokens it swaps stay next to each other. */
	.om-prompt-pill {
		border: 1px solid var(--om-border-card);
		background: var(--om-prompt);
		color: var(--om-text-body);
	}
	.om-prompt-pill:hover {
		border-color: var(--om-accent-hover);
		color: var(--om-text-strong);
	}
</style>
