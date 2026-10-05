<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { health, healthError } from '$lib/stores/health';
	import { wsStatus, lastMessage } from '$lib/stores/websocket';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import type { DashboardResponse, ThroughputResponse } from '$lib/api/types';
	import StatCard from '$lib/components/dashboard/StatCard.svelte';
	import BarChart from '$lib/components/dashboard/BarChart.svelte';
	import DonutChart from '$lib/components/dashboard/DonutChart.svelte';
	import FeatureCostChart from '$lib/components/dashboard/FeatureCostChart.svelte';
	import ThroughputChart from '$lib/components/dashboard/ThroughputChart.svelte';
	import WaitTimeChart from '$lib/components/dashboard/WaitTimeChart.svelte';
	import { t } from '$lib/i18n';

	const cardClass = $derived($glassTheme ? 'rounded-xl glass-section p-4' : 'rounded-xl border border-surface-700 bg-surface-800 p-4');

	// --- Service health ---
	function statusIcon(status: string | undefined): string {
		if (status === 'healthy' || status === 'connected' || status === 'available') return 'text-green-400';
		if (status === 'unreachable' || status === 'not_configured') return 'text-surface-500';
		if (status === 'starting') return 'text-yellow-400';
		return 'text-red-400';
	}

	function statusLabel(status: string | undefined, fallback = 'unknown'): string {
		const value = status ?? fallback;
		if (value === 'checking...') return $t('status.checking', 'Checking...');
		return $t(`shell.svc_${value}`, value);
	}

	// n8n process management (available in Tauri)
	let n8nProcessStatus = $state('checking...');
	let n8nAction = $state('');
	let wsExpanded = $state(false);

	async function invoke(cmd: string): Promise<any> {
		try {
			const { invoke: tauriInvoke } = await import('@tauri-apps/api/core');
			return await tauriInvoke(cmd);
		} catch {
			return null;
		}
	}

	async function checkN8nProcess() {
		const status = await invoke('n8n_status');
		n8nProcessStatus = status ?? 'unknown';
	}

	async function startN8n() {
		n8nAction = 'starting';
		await invoke('start_n8n');
		await new Promise((r) => setTimeout(r, 2000));
		await checkN8nProcess();
		n8nAction = '';
	}

	async function stopN8n() {
		n8nAction = 'stopping';
		await invoke('stop_n8n');
		await new Promise((r) => setTimeout(r, 1000));
		await checkN8nProcess();
		n8nAction = '';
	}

	// --- Throughput ---
	let throughputData: ThroughputResponse | null = $state(null);
	let throughputLoading = $state(true);
	let throughputError = $state('');
	let throughputMinutes = $state(60);

	async function loadThroughput() {
		throughputLoading = true;
		throughputError = '';
		try {
			throughputData = await engineApi.getThroughput(throughputMinutes);
		} catch (e) {
			throughputError = e instanceof Error ? e.message : $t('shell.load_throughput_failed', 'Failed to load throughput');
		} finally {
			throughputLoading = false;
		}
	}

	// --- Dashboard / Analytics ---
	let dashboard: DashboardResponse | null = $state(null);
	let dashLoading = $state(true);
	let dashError = $state('');
	let days = $state(30);

	async function loadDashboard() {
		dashLoading = true;
		dashError = '';
		try {
			dashboard = await engineApi.getDashboard(days);
		} catch (e) {
			dashError = e instanceof Error ? e.message : $t('shell.load_analytics_failed', 'Failed to load analytics');
		} finally {
			dashLoading = false;
			// Scroll to hash anchor after data loads (e.g. #cost from footer link)
			if (window.location.hash) {
				requestAnimationFrame(() => {
					const el = document.querySelector(window.location.hash);
					el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
				});
			}
		}
	}

	const cardStatusData = $derived.by(() => {
		const d = dashboard;
		if (!d) return [];
		return [
			{ label: $t('shared.status_pending', 'Pending'), value: d.stats.cards_pending, color: '#f6bc66' },
			{ label: $t('shared.status_approved', 'Approved'), value: d.stats.cards_approved, color: '#f6ac69' },
			{ label: $t('shared.status_dismissed', 'Dismissed'), value: d.stats.cards_dismissed, color: '#8b7a62' }
		];
	});

	const actionStatusData = $derived.by(() => {
		const d = dashboard;
		if (!d) return [];
		return [
			{ label: $t('shared.status_completed', 'Completed'), value: d.stats.actions_completed, color: '#f6ac69' },
			{ label: $t('shared.status_failed', 'Failed'), value: d.stats.actions_failed, color: '#ff9770' },
			{
				label: $t('shell.in_progress', 'In Progress'),
				value: Math.max(0, d.stats.actions_executed - d.stats.actions_completed - d.stats.actions_failed),
				color: '#f6bc66'
			}
		];
	});

	const sourceData = $derived.by(() => {
		const d = dashboard;
		if (!d) return [];
		return d.events_by_source.map((s: { source: string; count: number }) => ({ label: s.source, value: s.count }));
	});

	const approvalData = $derived.by(() => {
		const d = dashboard;
		if (!d) return [];
		return d.approval_by_persona.map((p: { persona: string; rate: number }) => ({
			label: $t(`shared.persona_${p.persona}`, p.persona),
			value: Math.round(p.rate * 100)
		}));
	});

	const costByModel = $derived.by(() => {
		const d = dashboard;
		if (!d) return [];
		return Object.entries(d.llm_costs.by_model).map(([label, value]) => ({
			label,
			value: Math.round((value as number) * 1000) / 1000
		}));
	});


	function formatCost(usd: number): string {
		return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
	}

	function formatTokens(n: number): string {
		if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
		if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
		return String(n);
	}

	function formatTime(minutes: number): string {
		if (minutes >= 60) return `${(minutes / 60).toFixed(1)}h`;
		return `${Math.round(minutes)}m`;
	}

	onMount(() => {
		checkN8nProcess();
		loadDashboard();
		loadThroughput();
	});
</script>

<svelte:head>
	<title>{$t('shell.status_page_title', 'Status - Laya')}</title>
</svelte:head>

<div class="mx-auto max-w-6xl space-y-8">
	<!-- System Status section -->
	<section>
		<h2 class="mb-4 text-lg font-semibold">{$t('nav.status', 'System Status')}</h2>
		<div class="grid grid-cols-2 gap-3 sm:grid-cols-5">
			<!-- Engine -->
			<div class={cardClass}>
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">Engine</div>
				{#if $healthError || !$health}
					<span class="text-sm text-red-400">{$t('shell.offline', 'Offline')}</span>
				{:else}
					<span class="text-sm {statusIcon($health.engine)}">{statusLabel($health.engine)}</span>
					<div class="mt-1 text-[10px] text-surface-500">
						{$t('shell.uptime', 'Uptime: {h}h {m}m {s}s', {
							h: Math.floor($health.uptime_seconds / 3600),
							m: Math.floor(($health.uptime_seconds % 3600) / 60),
							s: Math.floor($health.uptime_seconds % 60)
						})}
					</div>
				{/if}
			</div>

			<!-- SQLite -->
			<div class={cardClass}>
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">SQLite</div>
				{#if $healthError || !$health}
					<span class="text-sm text-red-400">{$t('shell.offline', 'Offline')}</span>
				{:else}
					<span class="text-sm {statusIcon($health.sqlite)}">{statusLabel($health.sqlite)}</span>
				{/if}
			</div>

			<!-- ChromaDB -->
			<div class={cardClass}>
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">ChromaDB</div>
				{#if $healthError || !$health}
					<span class="text-sm text-red-400">{$t('shell.offline', 'Offline')}</span>
				{:else}
					<span class="text-sm {statusIcon($health.chromadb)}">{statusLabel($health.chromadb)}</span>
					{#if $health.chromadb === 'starting'}
						<div class="mt-1 text-[10px] text-surface-500">{$t('shell.vector_setting_up', 'Setting up semantic search')}</div>
					{/if}
				{/if}
			</div>

			<!-- n8n -->
			<div class={cardClass}>
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">n8n</div>
				{#if $healthError || !$health}
					<span class="text-sm text-red-400">{$t('shell.offline', 'Offline')}</span>
				{:else}
					<span class="text-sm {statusIcon($health.n8n)}">{statusLabel($health.n8n)}</span>
				{/if}
			</div>

			<!-- WebSocket -->
			<div class={cardClass}>
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">WebSocket</div>
				<span class="text-sm {statusIcon($wsStatus === 'connected' ? 'healthy' : 'unhealthy')}">
					{statusLabel($wsStatus)}
				</span>
			</div>
		</div>

		<!-- Embeddings info -->
		{#if $health?.embeddings}
			{@const emb = $health.embeddings}
			<div class="mt-3 {cardClass}">
				<div class="flex items-center justify-between">
					<div>
						<div class="text-[10px] uppercase tracking-wider text-surface-400">Embeddings</div>
						<div class="mt-1 flex items-center gap-2">
							{#if emb.status === 'not_initialized'}
								<span class="text-sm text-surface-400">
									{$health.chromadb === 'starting'
										? $t('common.loading', 'Loading…')
										: $t('shell.not_loaded', 'Not loaded')}
								</span>
							{:else}
								<span class="text-sm text-surface-200">{emb.model}</span>
								<span class="text-[10px] text-surface-500">{emb.dimensions}d</span>
							{/if}
							{#if emb.status === 'fallback'}
								<span class="rounded-full bg-laya-gold/20 px-2 py-0.5 text-[10px] font-medium text-laya-amber">{$t('shell.fallback', 'Fallback')}</span>
							{:else if emb.status === 'active'}
								<span class="rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-medium text-green-400">{$t('common.active', 'Active')}</span>
							{:else if emb.status !== 'not_initialized'}
								<span class="rounded-full bg-surface-600/50 px-2 py-0.5 text-[10px] font-medium text-surface-400">{statusLabel(emb.status)}</span>
							{/if}
						</div>
					</div>
					<div class="text-right">
						<div class="text-[10px] text-surface-500">Backend</div>
						<div class="mt-0.5 text-xs text-surface-300">
							{#if emb.backend === 'nomic'}
								sentence-transformers
							{:else if emb.backend === 'chromadb_default'}
								{$t('shell.chromadb_builtin', 'ChromaDB built-in (onnxruntime)')}
							{:else if emb.status === 'not_initialized'}
								—
							{:else}
								{emb.backend}
							{/if}
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- n8n process control -->
		<div class="mt-3 {cardClass}">
			<div class="flex items-center justify-between">
				<div>
					<div class="text-[10px] uppercase tracking-wider text-surface-400">{$t('shell.n8n_process', 'n8n Process')}</div>
					<div class="mt-1 text-sm">
						<span class={n8nProcessStatus === 'running' ? 'text-green-400' : n8nProcessStatus === 'starting' ? 'text-yellow-400' : 'text-surface-400'}>
							{statusLabel(n8nProcessStatus)}
						</span>
					</div>
				</div>
				<div class="flex gap-2">
					{#if n8nProcessStatus !== 'running' && n8nProcessStatus !== 'starting'}
						<button
							class="rounded-md bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-50"
							onclick={startN8n}
							disabled={!!n8nAction}
						>
							{n8nAction === 'starting' ? $t('shell.starting', 'Starting...') : $t('shell.start', 'Start')}
						</button>
					{:else if n8nProcessStatus === 'running'}
						<button
							class="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500 disabled:opacity-50"
							onclick={stopN8n}
							disabled={!!n8nAction}
						>
							{n8nAction === 'stopping' ? $t('shell.stopping', 'Stopping...') : $t('shell.stop', 'Stop')}
						</button>
					{/if}
				</div>
			</div>
		</div>

		<!-- Last WS message (collapsible) -->
		{#if $lastMessage}
			{@const wsJson = JSON.stringify($lastMessage, null, 2)}
			{@const wsLines = wsJson.split('\n')}
			{@const wsOverflows = wsLines.length > 7}
			<div class="mt-3 {cardClass}">
				<div class="mb-1.5 text-[10px] uppercase tracking-wider text-surface-400">{$t('shell.last_ws_message', 'Last WS Message')}</div>
				<pre
					class="overflow-x-auto text-xs text-surface-300"
					style="max-height: {wsExpanded || !wsOverflows ? 'none' : '7.5lh'}; overflow-y: hidden; {wsOverflows && !wsExpanded ? '-webkit-mask-image: linear-gradient(to bottom, black 50%, transparent 100%); mask-image: linear-gradient(to bottom, black 50%, transparent 100%);' : ''}"
				>{wsJson}</pre>
				{#if wsOverflows}
					<button
						class="mt-1 text-[10px] text-surface-400 transition-colors hover:text-surface-200"
						onclick={() => wsExpanded = !wsExpanded}
					>
						{wsExpanded
							? $t('shell.collapse', 'Collapse')
							: $t('shell.show_all_lines', 'Show all ({count} lines)', { count: wsLines.length })}
					</button>
				{/if}
			</div>
		{/if}
	</section>

	<!-- Throughput & Wait Time section -->
	<section>
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{$t('shell.throughput_wait_title', 'Throughput & Wait Time')}</h2>
			<select
				bind:value={throughputMinutes}
				onchange={loadThroughput}
				class="rounded-lg border px-3 py-1.5 text-sm text-surface-200 focus:border-laya-orange/50 focus:outline-none {$glassTheme ? 'glass-input' : 'border-surface-600 bg-surface-800'}"
			>
				<option value={60}>{$t('shell.last_60_min', 'Last 60 min')}</option>
				<option value={300}>{$t('shell.last_hours', 'Last {count} hours', { count: 5 })}</option>
				<option value={1440}>{$t('shell.last_hours', 'Last {count} hours', { count: 24 })}</option>
				<option value={10080}>{$t('shell.last_days', 'Last {count} days', { count: 7 })}</option>
				<option value={43200}>{$t('shell.last_days', 'Last {count} days', { count: 30 })}</option>
			</select>
		</div>

		{#if throughputLoading}
			<div class="flex items-center justify-center py-12">
				<div class="h-5 w-5 animate-spin rounded-full border-2 border-laya-orange border-t-transparent"></div>
			</div>
		{:else if throughputError}
			<div class="rounded-xl border border-red-800 bg-red-900/20 p-4 text-sm text-red-300">
				{throughputError}
			</div>
		{:else if throughputData && throughputData.buckets.length > 0}
			<div class="space-y-3">
				<ThroughputChart buckets={throughputData.buckets} windowMinutes={throughputData.window_minutes} />
				<WaitTimeChart buckets={throughputData.buckets} windowMinutes={throughputData.window_minutes} />
			</div>
		{:else}
			<div class={cardClass}>
				<p class="text-sm text-surface-500">{$t('shell.no_throughput', 'No throughput data in the selected window.')}</p>
			</div>
		{/if}
	</section>

	<!-- Analytics section -->
	<section>
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{$t('shell.analytics', 'Analytics')}</h2>
			<select
				bind:value={days}
				onchange={loadDashboard}
				class="rounded-lg border px-3 py-1.5 text-sm text-surface-200 focus:border-laya-orange/50 focus:outline-none {$glassTheme ? 'glass-input' : 'border-surface-600 bg-surface-800'}"
			>
				<option value={7}>{$t('shell.last_days', 'Last {count} days', { count: 7 })}</option>
				<option value={14}>{$t('shell.last_days', 'Last {count} days', { count: 14 })}</option>
				<option value={30}>{$t('shell.last_days', 'Last {count} days', { count: 30 })}</option>
				<option value={90}>{$t('shell.last_days', 'Last {count} days', { count: 90 })}</option>
			</select>
		</div>

		{#if dashLoading}
			<div class="flex items-center justify-center py-12">
				<div class="h-5 w-5 animate-spin rounded-full border-2 border-laya-orange border-t-transparent"></div>
			</div>
		{:else if dashError}
			<div class="rounded-xl border border-red-800 bg-red-900/20 p-4 text-sm text-red-300">
				{dashError}
			</div>
		{:else if dashboard}
			<!-- Top-level stats -->
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
				<StatCard label={$t('shell.stat_events_processed', 'Events Processed')} value={String(dashboard.stats.events_processed)} />
				<StatCard
					label={$t('shell.stat_events_filtered', 'Events Filtered')}
					value={String(dashboard.stats.events_filtered)}
					subtitle={$t('shell.stat_filter_rate', '{rate}% filter rate', {
						rate: dashboard.stats.events_processed > 0 ? Math.round((dashboard.stats.events_filtered / dashboard.stats.events_processed) * 100) : 0
					})}
				/>
				<StatCard
					label={$t('shell.stat_cards_generated', 'Cards Generated')}
					value={String(dashboard.stats.cards_generated)}
					color="text-blue-400"
				/>
				<StatCard
					label={$t('shell.stat_actions_executed', 'Actions Executed')}
					value={String(dashboard.stats.actions_executed)}
					color="text-emerald-400"
				/>
				<StatCard
					label={$t('shell.stat_time_saved', 'Time Saved (BETA)')}
					value={formatTime(dashboard.time_saved.total_minutes)}
					color="text-amber-400"
				/>
			</div>

			<!-- Cost + Response Time row -->
			<div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
				<StatCard
					label={$t('shell.stat_llm_cost', 'LLM Cost')}
					value={formatCost(dashboard.llm_costs.total_cost_usd)}
					subtitle={$t('shell.stat_tokens', '{input} in / {output} out', {
						input: formatTokens(dashboard.llm_costs.total_input_tokens),
						output: formatTokens(dashboard.llm_costs.total_output_tokens)
					})}
				/>
				<StatCard
					label={$t('shell.stat_avg_response', 'Avg Response')}
					value="{Math.round(dashboard.response_time.avg_ms)}ms"
					subtitle="p50: {Math.round(dashboard.response_time.p50_ms)}ms / p95: {Math.round(dashboard.response_time.p95_ms)}ms"
				/>
				<StatCard
					label={$t('shell.stat_approval_rate', 'Approval Rate')}
					value="{dashboard.stats.cards_approved + dashboard.stats.cards_dismissed > 0 ? Math.round((dashboard.stats.cards_approved / (dashboard.stats.cards_approved + dashboard.stats.cards_dismissed)) * 100) : 0}%"
					subtitle={$t('shell.stat_approved_dismissed', '{approved} approved / {dismissed} dismissed', {
						approved: dashboard.stats.cards_approved,
						dismissed: dashboard.stats.cards_dismissed
					})}
					color="text-green-400"
				/>
			</div>

			<!-- Charts row -->
			<div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
				<DonutChart data={cardStatusData} title={$t('shell.chart_cards_by_status', 'Cards by Status')} />
				<DonutChart data={actionStatusData} title={$t('shell.chart_actions_by_status', 'Actions by Status')} />
			</div>

			{#if sourceData.length > 0}
				<div class="mt-3">
					<BarChart data={sourceData} title={$t('shell.chart_events_by_source', 'Events by Source')} />
				</div>
			{/if}

			{#if dashboard.llm_costs.by_feature && Object.keys(dashboard.llm_costs.by_feature).length > 0}
				<div id="cost" class="mt-3">
					<FeatureCostChart
						byFeature={dashboard.llm_costs.by_feature}
						byStep={dashboard.llm_costs.by_step}
					/>
				</div>
			{/if}

			{#if costByModel.length > 0}
				<div class="mt-3">
					<BarChart data={costByModel} title={$t('shell.chart_cost_by_model', 'LLM Cost by Model ($)')} />
				</div>
			{/if}

			{#if approvalData.length > 0}
				<div class="mt-3">
					<BarChart data={approvalData} title={$t('shell.chart_approval_by_persona', 'Approval Rate by Persona (%)')} />
				</div>
			{/if}
		{/if}
	</section>
</div>
