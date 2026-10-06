<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<!--
	Threads that found no free lane. They are NEVER shifted in time to fit — the
	strip keeps them at their true minutes as thin bars, and clicking it widens
	the lanes so they can be read properly.
-->
<script lang="ts">
	import type { Thread } from '$lib/timeline/threads';
	import { statusTone } from '$lib/timeline/threads';
	import type { TimeScale } from '$lib/timeline/scale';
	import { formatMinutes } from '$lib/timeline/scale';
	import { t } from '$lib/i18n';

	let {
		threads = [],
		scale,
		width = 50,
		showSpace = false,
		onexpand,
		onhover,
		onleave
	}: {
		threads?: { thread: Thread; startMin: number; endMin: number }[];
		scale: TimeScale;
		width?: number;
		/** Only true when the day's threads span more than one space. */
		showSpace?: boolean;
		onexpand: () => void;
		onhover?: (el: HTMLElement, text: string) => void;
		onleave?: () => void;
	} = $props();
</script>

<div
	class="tl-glass-surface absolute bottom-0 top-0 border-l border-dashed"
	style="right: 0; width: {width}px; border-color: var(--tl-strip-border); background: var(--tl-rail-bg);"
>
	<button
		class="absolute inset-0 h-full w-full cursor-pointer"
		onclick={onexpand}
		title={threads.length === 1
			? $t('feedGroups.show_overflow_one', 'Show {count} overflowed thread in extra lanes', { count: threads.length })
			: $t('feedGroups.show_overflow_other', 'Show {count} overflowed threads in extra lanes', { count: threads.length })}
		aria-label={$t('feedGroups.expand_overflow', 'Expand overflow lanes')}
	>
		<span class="absolute inset-x-0 top-[5px] text-center font-mono text-[9px] font-semibold" style="color: var(--color-surface-400)">
			+{threads.length}
		</span>
		<span class="absolute inset-x-0 top-[19px] text-center text-[7.5px] leading-[1.35]" style="color: var(--tl-micro)">
			{$t('feedGroups.low_signal_top', 'low')}<br />{$t('feedGroups.low_signal_bottom', 'signal')}
		</span>
	</button>

	{#each threads as item, i (item.thread.key)}
		{@const top = scale.y(item.startMin)}
		{@const height = Math.max(14, scale.y(item.endMin) - top)}
		{@const tone = `var(--tl-node-${statusTone(item.thread.latest.status)})`}
		{@const spaceColor = showSpace ? item.thread.spaceColor : undefined}
		<!-- Each bar is itself the expand affordance: it sits above the full-strip
		     button, so a click landing on a bar would otherwise do nothing.
		     Across spaces the bar body takes the space colour and keeps the latest
		     status as a cap, so spilled threads still say both. -->
		<button
			class="absolute w-1 overflow-hidden rounded-[2px] opacity-[0.32] transition-opacity hover:opacity-90"
			style="top: {top}px; height: {height}px; left: {8 + (i % 6) * 7}px; background: {spaceColor ?? tone};"
			aria-label={$t('feedGroups.thread_expand_overflow', '{title} — expand overflow lanes', { title: item.thread.title })}
			onclick={onexpand}
			onmouseenter={(e) =>
				onhover?.(
					e.currentTarget as HTMLElement,
					`${item.thread.title} · ${formatMinutes(item.startMin)}–${formatMinutes(item.endMin)} · ${
						item.thread.cardCount === 1
							? $t('feedGroups.events_one', '{count} event', { count: item.thread.cardCount })
							: $t('feedGroups.events_other', '{count} events', { count: item.thread.cardCount })
					}${
						showSpace && item.thread.spaceName ? ` · ${item.thread.spaceName}` : ''
					}`
				)}
			onmouseleave={() => onleave?.()}
		>
			{#if spaceColor}
				<span class="absolute inset-x-0 top-0 h-[5px]" style="background: {tone};"></span>
			{/if}
		</button>
	{/each}
</div>
