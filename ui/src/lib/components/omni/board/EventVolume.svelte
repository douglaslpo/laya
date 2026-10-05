<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { OmniVolumeResponse } from '$lib/api/types';
	import { num } from '$lib/omni/layers';
	import { t, locale } from '$lib/i18n';

	let { volume }: { volume: OmniVolumeResponse | null } = $props();

	const series = $derived(volume?.series ?? []);
	// Scale to the busiest day so a quiet fortnight still shows relief. Floor of
	// 1 keeps the division safe when every day is empty.
	const peak = $derived(Math.max(1, ...series.map((d) => d.count)));

	function label(date: string, loc: string = $locale): string {
		const d = new Date(date + 'T00:00:00');
		return d
			.toLocaleDateString(loc, { day: 'numeric', month: 'short' })
			.toUpperCase();
	}

	// Three ticks — start, middle, end — matching the axis in the design.
	const axis = $derived.by(() => {
		if (series.length === 0) return [];
		const mid = Math.floor(series.length / 2);
		const loc = $locale;
		return [series[0], series[mid], series[series.length - 1]].map((d) => label(d.date, loc));
	});
</script>

<div
	class="om-instrument om-glass flex min-w-0 flex-1 flex-col gap-[5px] rounded-[9px] px-[11px]"
	style="padding-block: calc(8px * var(--om-density));"
>
	<div class="flex items-center gap-2">
		<span class="om-micro whitespace-nowrap">{$t('omni.event_volume')} · {volume?.days ?? 14} {$t('omni.days')}</span>
		<span class="flex-1"></span>
		<span class="om-mono text-[calc(11px*var(--om-scale))]" style="color: var(--om-text-strong);">
			{num(volume?.total, $locale)}
		</span>
		<span class="text-[calc(9.5px*var(--om-scale))]" style="color: var(--om-text-meta);">
			{$t('omniTrace.volume_today', 'today {count}', { count: num(volume?.today, $locale) })}
		</span>
	</div>

	<div class="relative min-h-0 flex-1">
		<div class="absolute inset-0 flex items-end gap-[3px]">
			{#each series as day (day.date)}
				{@const isToday = day.date === volume?.today_date}
				<div
					class="flex-1 rounded-t-[2px]"
					style="height: {Math.max(day.count > 0 ? 6 : 2, (day.count / peak) * 100)}%;
						background: {isToday ? 'var(--om-volume-today)' : 'var(--om-volume-bar)'};"
					title={$t('omniTrace.day_events_title', '{date} — {count} events', { date: label(day.date, $locale), count: num(day.count, $locale) })}
				></div>
			{/each}
		</div>
	</div>

	<div
		class="om-mono flex justify-between text-[calc(8px*var(--om-scale))]"
		style="color: var(--om-text-faint);"
	>
		{#each axis as tick}<span>{tick}</span>{/each}
	</div>
</div>
