<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import type { ActionCard, WorkspaceEvent, WorkspaceSession, Repo } from '$lib/api/types';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { parseBackendDate } from '$lib/utils/datetime';
	import { goto } from '$app/navigation';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	import { t, locale } from '$lib/i18n';

	let {
		card,
		session,
		events,
		context,
		allRepos = [],
		selectedAddDirs = $bindable(new Set<string>())
	}: {
		card: ActionCard;
		session: WorkspaceSession | null;
		events: WorkspaceEvent[];
		context: Record<string, unknown>;
		allRepos?: Repo[];
		selectedAddDirs?: Set<string>;
	} = $props();

	let showAddPath = $state(false);

	const isAgentActive = $derived(
		session != null && ['starting', 'running'].includes(session.status)
	);

	const availableRepos = $derived(
		allRepos.filter((r) => r.path !== session?.repo_path)
	);

	function toggleDir(path: string) {
		const next = new Set(selectedAddDirs);
		if (next.has(path)) next.delete(path);
		else next.add(path);
		selectedAddDirs = next;
	}

	const priorityColors: Record<string, string> = {
		CRITICAL: 'text-red-400',
		HIGH: 'text-orange-400',
		MEDIUM: 'text-blue-400',
		LOW: 'text-surface-400'
	};

	const statusColors: Record<string, string> = {
		pending: 'text-yellow-400',
		approved: 'text-green-400',
		executing: 'text-blue-400',
		completed: 'text-green-500',
		failed: 'text-red-500',
		dismissed: 'text-surface-500',
		agent_running: 'text-violet-400',
		awaiting_input: 'text-violet-400',
		staged: 'text-emerald-400'
	};

	const isTerminal = $derived(
		session ? ['completed', 'failed', 'cancelled'].includes(session.status) : false
	);

	const toolStats = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const ev of events) {
			if (ev.event_type === 'file_read') counts['Files read'] = (counts['Files read'] ?? 0) + 1;
			else if (ev.event_type === 'file_write') counts['Files written'] = (counts['Files written'] ?? 0) + 1;
			else if (ev.event_type === 'tool_call') {
				const tool = (ev.content.tool as string) ?? 'Other';
				if (tool === 'Bash') counts['Commands run'] = (counts['Commands run'] ?? 0) + 1;
				else if (tool === 'Grep' || tool === 'Glob') counts['Searches'] = (counts['Searches'] ?? 0) + 1;
				else counts['Other tools'] = (counts['Other tools'] ?? 0) + 1;
			}
		}
		return counts;
	});

	const toolStatLabelKeys: Record<string, string> = {
		'Files read': 'actions.stat_files_read',
		'Files written': 'actions.stat_files_written',
		'Commands run': 'actions.stat_commands_run',
		Searches: 'actions.stat_searches',
		'Other tools': 'actions.stat_other_tools'
	};

	const stagedOutputTitle = $derived.by(() => {
		switch (card.staged_output?.type) {
			case 'code_fix': return $t('actions.output_code_fix', 'Code Fix');
			case 'draft_reply': return $t('actions.output_draft_reply', 'Draft Reply');
			case 'briefing': return $t('actions.output_briefing', 'Briefing');
			case 'agent_result': return $t('actions.output_agent_result', 'Agent Result');
			case 'agent_plan': return $t('actions.implementation_plan', 'Implementation Plan');
			default: return $t('actions.output_generic', 'Output');
		}
	});

	const sessionDuration = $derived.by(() => {
		if (!session?.started_at) return null;
		const end = session.completed_at ?? session.updated_at;
		const endDate = parseBackendDate(end);
		const startDate = parseBackendDate(session.started_at);
		if (!endDate || !startDate) return null;
		const ms = endDate.getTime() - startDate.getTime();
		if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
		if (ms < 3600_000) return `${Math.round(ms / 60_000)}m`;
		return `${Math.round(ms / 3600_000 * 10) / 10}h`;
	});

	// Research file browsing — only for research sessions
	const isResearch = $derived(session?.session_type === 'research');
	let researchFiles = $state<Array<{ name: string; path: string; size: number; modified: number }>>([]);
	let filesLoaded = $state(false);
	let filesLoading = $state(false);
	let viewingFile = $state<{ name: string; content: string } | null>(null);
	let fileLoading = $state(false);
	let fileCopied = $state(false);

	async function copyFileContent() {
		if (!viewingFile) return;
		await navigator.clipboard.writeText(viewingFile.content);
		fileCopied = true;
		setTimeout(() => (fileCopied = false), 1500);
	}

	$effect(() => {
		if (isResearch && session && !filesLoaded) {
			loadFiles();
		}
	});

	async function loadFiles() {
		filesLoading = true;
		try {
			const result = await engineApi.listResearchFiles(card.card_id);
			researchFiles = result.files;
			filesLoaded = true;
		} catch {
			researchFiles = [];
			filesLoaded = true;
		} finally {
			filesLoading = false;
		}
	}

	async function viewFile(filePath: string) {
		fileLoading = true;
		try {
			const result = await engineApi.readResearchFile(card.card_id, filePath);
			viewingFile = { name: result.name, content: result.content };
		} catch {
			// failed to load
		} finally {
			fileLoading = false;
		}
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		const oneDecimal = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toLocaleString($locale, oneDecimal)} KB`;
		return `${(bytes / (1024 * 1024)).toLocaleString($locale, oneDecimal)} MB`;
	}

	const relatedEntities = $derived(
		((context.related_entities as Array<{ entity_type: string; value: string } | string>) ?? []).map(
			(e) => (typeof e === 'string' ? e : e.value)
		)
	);
	const researchPlan = $derived((context.research_plan as string[]) ?? []);
</script>

<div class="flex h-full w-80 flex-col border-l border-t {$glassTheme ? 'glass-panel border-white/[0.06]' : 'border-surface-700 bg-surface-850'}">
	<div class="flex h-11 shrink-0 items-center justify-between border-b {$glassTheme ? 'border-white/[0.06]' : 'border-surface-700'} px-4">
		<h2 class="text-xs font-semibold uppercase tracking-wider text-surface-400">{$t('actions.context', 'Context')}</h2>
		<button
			class="rounded-md p-1 text-surface-400 transition-colors {$glassTheme ? 'glass-hover' : 'hover:bg-surface-800'} hover:text-surface-200"
			onclick={() => goto('/feed')}
			aria-label={$t('actions.close_workspace', 'Close workspace')}
			title={$t('actions.close_workspace', 'Close workspace')}
		>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>

	<div class="flex-1 overflow-y-auto space-y-4 p-4">
		<!-- Session outcome -->
		{#if session && isTerminal}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.session_outcome', 'Session Outcome')}</h3>
				<div class="space-y-1.5 text-xs">
					<div class="flex justify-between">
						<span class="text-surface-400">{$t('actions.status', 'Status')}</span>
						<span class={statusColors[session.status] ?? 'text-surface-300'}>{$t(`actions.session_status_${session.status}`, session.status)}</span>
					</div>
					{#if sessionDuration}
						<div class="flex justify-between">
							<span class="text-surface-400">{$t('actions.duration', 'Duration')}</span>
							<span class="text-surface-200">{sessionDuration}</span>
						</div>
					{/if}
					{#if session.error_message}
						<div class="mt-1.5 rounded px-2 py-1.5 text-[11px] text-red-300 {$glassTheme ? 'bg-red-400/15' : 'bg-red-900/20'}">
							{session.error_message}
						</div>
					{/if}
				</div>
				{#if Object.keys(toolStats).length > 0}
					<div class="mt-2.5 border-t {$glassTheme ? 'border-white/[0.08]' : 'border-surface-700/50'} pt-2">
						<h4 class="mb-1.5 text-[10px] font-medium text-surface-500">{$t('actions.tool_usage', 'Tool Usage')}</h4>
						<div class="space-y-1">
							{#each Object.entries(toolStats) as [label, count]}
								<div class="flex justify-between text-[11px]">
									<span class="text-surface-400">{$t(toolStatLabelKeys[label] ?? label, label)}</span>
									<span class="text-surface-300">{count}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Working Directory -->
		{#if session?.repo_path}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<div class="mb-1.5 flex items-center justify-between">
					<h3 class="text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.working_directory', 'Working Directory')}</h3>
					{#if isResearch && filesLoaded}
						<button
							class="text-[10px] text-cyan-400 hover:text-cyan-300 transition-colors"
							onclick={loadFiles}
							disabled={filesLoading}
						>
							{filesLoading ? '...' : $t('actions.refresh', 'Refresh')}
						</button>
					{/if}
				</div>
				<p class="break-all font-mono text-[11px] text-surface-200">{session.repo_path}</p>

				{#if isResearch}
					<!-- Research files -->
					{#if filesLoading && !filesLoaded}
						<p class="mt-2 text-[11px] text-surface-500">{$t('actions.loading_files', 'Loading files...')}</p>
					{:else if researchFiles.length > 0}
						<div class="mt-2.5 border-t {$glassTheme ? 'border-white/[0.08]' : 'border-surface-700/50'} pt-2">
							<h4 class="mb-1.5 text-[10px] font-medium text-surface-500">{$t('actions.generated_files', 'Generated Files')}</h4>
							<div class="space-y-1">
								{#each researchFiles as file}
									<button
										class="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left transition-colors {$glassTheme ? 'hover:bg-white/[0.08]' : 'hover:bg-surface-700/50'}"
										onclick={() => viewFile(file.path)}
									>
										<div class="flex min-w-0 items-center gap-1.5">
											<svg class="h-3 w-3 shrink-0 text-surface-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
											</svg>
											<span class="truncate text-[11px] text-surface-200">{file.name}</span>
										</div>
										<span class="shrink-0 text-[10px] text-surface-500">{formatFileSize(file.size)}</span>
									</button>
								{/each}
							</div>
						</div>
					{:else if filesLoaded}
						<p class="mt-2 text-[11px] text-surface-500">{$t('actions.no_files_yet', 'No files generated yet')}</p>
					{/if}
				{/if}

				{#if session.add_dirs && session.add_dirs.length > 0}
					<h3 class="mt-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.additional_directories', 'Additional Directories')}</h3>
					<div class="space-y-1">
						{#each session.add_dirs as dir}
							<p class="break-all font-mono text-[11px] text-surface-300">{dir}</p>
						{/each}
					</div>
				{/if}

				<!-- Add Path — available when agent is not running -->
				{#if !isAgentActive && availableRepos.length > 0}
					{#if showAddPath}
						<div class="mt-3 border-t {$glassTheme ? 'border-white/[0.08]' : 'border-surface-700/50'} pt-2">
							<div class="mb-1.5 flex items-center justify-between">
								<span class="text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.add_paths', 'Add paths')}</span>
								<button
									class="text-[10px] text-surface-500 hover:text-surface-300"
									onclick={() => { showAddPath = false; }}
								>{$t('common.close', 'Close')}</button>
							</div>
							<div class="space-y-1">
								{#each availableRepos as repo}
									<button
										class="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[11px] transition-colors
											{selectedAddDirs.has(repo.path)
												? 'bg-laya-orange/15 text-laya-orange'
												: $glassTheme ? 'text-surface-300 hover:bg-white/[0.08]' : 'text-surface-300 hover:bg-surface-700'}"
										onclick={() => toggleDir(repo.path)}
									>
										<span class="flex h-3.5 w-3.5 flex-shrink-0 items-center justify-center rounded border text-[9px]
											{selectedAddDirs.has(repo.path)
												? 'border-laya-orange/50 bg-laya-orange/20 text-laya-orange'
												: $glassTheme ? 'border-white/[0.12]' : 'border-surface-600'}"
										>{selectedAddDirs.has(repo.path) ? '✓' : ''}</span>
										<span class="truncate font-medium">{repo.name}</span>
									</button>
								{/each}
							</div>
						</div>
					{:else}
						<div class="mt-2.5 flex items-center gap-2">
							<button
								class="rounded px-2 py-1 text-[10px] text-surface-400 border transition-colors {$glassTheme ? 'border-white/[0.10] hover:border-white/[0.20]' : 'border-surface-700 hover:border-surface-500'} hover:text-surface-200"
								onclick={() => { showAddPath = true; }}
							>
								{$t('actions.add_path_button', '+ Add Path')}
							</button>
							{#if selectedAddDirs.size > 0}
								<span class="text-[10px] text-laya-orange">{selectedAddDirs.size === 1
									? $t('actions.added_one', '{count} added', { count: selectedAddDirs.size })
									: $t('actions.added_other', '{count} added', { count: selectedAddDirs.size })}</span>
							{/if}
						</div>
					{/if}
				{/if}
			</div>
		{/if}

		<!-- Card metadata -->
		<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
			<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.card_info', 'Card Info')}</h3>
			<div class="space-y-1.5 text-xs">
				<div class="flex justify-between">
					<span class="text-surface-400">{$t('actions.priority', 'Priority')}</span>
					<span class={priorityColors[card.priority] ?? 'text-surface-300'}>{$t(`shared.priority_${card.priority}`, card.priority)}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-surface-400">{$t('actions.persona', 'Persona')}</span>
					<span class="text-surface-200">{$t(`shared.persona_${card.persona}`, card.persona)}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-surface-400">{$t('actions.category', 'Category')}</span>
					<span class="text-surface-200">{$t(`shared.category_${card.category}`, card.category)}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-surface-400">{$t('actions.status', 'Status')}</span>
					<span class={statusColors[card.status] ?? 'text-surface-300'}>{$t(`shared.status_${card.status}`, card.status)}</span>
				</div>
				{#if card.confidence}
					<div class="flex justify-between">
						<span class="text-surface-400">{$t('actions.confidence', 'Confidence')}</span>
						<span class="text-surface-200">{Math.round(card.confidence * 100)}%</span>
					</div>
				{/if}
			</div>
		</div>

		<!-- Staged output -->
		{#if card.staged_output}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">
					{stagedOutputTitle}
				</h3>
				{#if card.staged_output.type === 'code_fix'}
					<pre class="whitespace-pre-wrap break-words overflow-y-auto rounded p-2 text-[11px] text-surface-200 max-h-48 {$glassTheme ? 'bg-white/[0.04]' : 'bg-surface-900'}">{card.staged_output.content}</pre>
				{:else}
					<p class="text-xs text-surface-200 whitespace-pre-wrap max-h-48 overflow-y-auto">{card.staged_output.content}</p>
				{/if}
			</div>
		{/if}

		<!-- Related entities -->
		{#if relatedEntities.length > 0}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.related_entities', 'Related Entities')}</h3>
				<div class="flex flex-wrap gap-1.5">
					{#each relatedEntities as entity}
						<span class="min-w-0 max-w-full truncate rounded px-2 py-0.5 text-[11px] text-surface-300 {$glassTheme ? 'bg-white/[0.08]' : 'bg-surface-700'}" title={entity}>{entity}</span>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Research plan -->
		{#if researchPlan.length > 0}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.research_plan', 'Research Plan')}</h3>
				<ol class="space-y-1">
					{#each researchPlan as step, i}
						<li class="flex items-start gap-2 text-xs text-surface-300">
							<span class="flex-shrink-0 text-surface-500">{i + 1}.</span>
							{step}
						</li>
					{/each}
				</ol>
			</div>
		{/if}

		<!-- Intelligence -->
		{#if card.intelligence && card.intelligence.length > 0}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.intelligence', 'Intelligence')}</h3>
				<ul class="space-y-1">
					{#each card.intelligence as point}
						<li class="flex items-start gap-2 text-xs text-surface-300">
							<span class="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-surface-500"></span>
							{point}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		<!-- Suggested actions -->
		{#if card.suggested_actions && card.suggested_actions.length > 0}
			<div class="rounded-lg p-3 {$glassTheme ? 'glass-section' : 'border border-surface-700 bg-surface-800'}">
				<h3 class="mb-2 text-[10px] font-semibold uppercase tracking-wider text-surface-500">{$t('actions.actions_heading', 'Actions')}</h3>
				<div class="space-y-1.5">
					{#each card.suggested_actions as action}
						<div class="flex items-center justify-between text-xs">
							<span class="text-surface-200">{action.label}</span>
							<span class="text-[10px] text-surface-500">{action.target_platform}</span>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>

<!-- File viewer modal -->
{#if viewingFile}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
		role="dialog"
		aria-label={$t('actions.file_viewer', 'File viewer')}
		tabindex="-1"
		onclick={(e) => { if (e.target === e.currentTarget) viewingFile = null; }}
		onkeydown={(e) => { if (e.key === 'Escape') viewingFile = null; }}
	>
		<div class="mx-4 flex h-[80vh] w-full max-w-3xl flex-col rounded-xl border shadow-2xl {$glassTheme ? 'glass-modal border-white/[0.12]' : 'border-surface-600 bg-surface-800'}">
			<!-- Modal header -->
			<div class="flex shrink-0 items-center justify-between border-b px-5 py-3 {$glassTheme ? 'border-white/[0.08]' : 'border-surface-700'}">
				<div class="flex items-center gap-2">
					<svg class="h-4 w-4 text-cyan-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					<span class="text-sm font-medium text-surface-100">{viewingFile.name}</span>
				</div>
				<div class="flex items-center gap-1">
					<!-- Copy button -->
					<button
						class="rounded-md px-2 py-1 text-[11px] transition-colors {fileCopied ? 'text-green-400' : $glassTheme ? 'text-surface-400 hover:bg-white/[0.08] hover:text-surface-200' : 'text-surface-400 hover:bg-surface-700 hover:text-surface-200'}"
						onclick={copyFileContent}
					>
						{#if fileCopied}
							{$t('common.copied', 'Copied!')}
						{:else}
							<span class="flex items-center gap-1">
								<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
								</svg>
								{$t('common.copy', 'Copy')}
							</span>
						{/if}
					</button>
					<!-- Close button -->
					<button
						class="rounded-md p-1 text-surface-400 transition-colors {$glassTheme ? 'hover:bg-white/[0.08]' : 'hover:bg-surface-700'} hover:text-surface-200"
						onclick={() => (viewingFile = null)}
						aria-label={$t('common.close', 'Close')}
					>
						<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
							<path stroke-linecap="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
			<!-- Modal body -->
			<div class="flex-1 overflow-y-auto p-5">
				{#if viewingFile.name.endsWith('.md')}
					<div class="research-file-content" class:research-glass={$glassTheme}>
						{@html DOMPurify.sanitize(marked(viewingFile.content) as string)}
					</div>
				{:else}
					<pre class="whitespace-pre-wrap break-words rounded-lg p-4 font-mono text-[11px] text-surface-200 {$glassTheme ? 'bg-white/[0.04]' : 'bg-surface-900'}">{viewingFile.content}</pre>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	/* Research file markdown renderer — compact sizing with proper table support */
	.research-file-content {
		color: var(--color-surface-200);
		font-size: 12px;
		line-height: 1.6;
	}
	.research-file-content :global(h1) {
		font-size: 16px;
		font-weight: 700;
		color: var(--color-surface-100);
		margin: 1.25em 0 0.5em;
		padding-bottom: 0.3em;
		border-bottom: 1px solid var(--color-surface-700);
	}
	.research-file-content :global(h2) {
		font-size: 14px;
		font-weight: 600;
		color: var(--color-surface-100);
		margin: 1em 0 0.4em;
		padding-bottom: 0.25em;
		border-bottom: 1px solid var(--color-surface-700);
	}
	.research-file-content :global(h3) {
		font-size: 13px;
		font-weight: 600;
		color: var(--color-surface-100);
		margin: 0.8em 0 0.3em;
	}
	.research-file-content :global(h4),
	.research-file-content :global(h5),
	.research-file-content :global(h6) {
		font-size: 12px;
		font-weight: 600;
		color: var(--color-surface-100);
		margin: 0.6em 0 0.25em;
	}
	.research-file-content :global(p) {
		margin: 0.5em 0;
	}
	.research-file-content :global(ul),
	.research-file-content :global(ol) {
		margin: 0.4em 0;
		padding-left: 1.5em;
	}
	.research-file-content :global(li) {
		margin: 0.15em 0;
	}
	.research-file-content :global(a) {
		color: var(--color-laya-orange);
	}
	.research-file-content :global(strong) {
		color: var(--color-surface-100);
		font-weight: 600;
	}
	.research-file-content :global(code) {
		color: var(--color-laya-orange);
		background: var(--color-surface-900);
		padding: 0.1em 0.3em;
		border-radius: 3px;
		font-size: 11px;
	}
	.research-file-content :global(pre) {
		background: var(--color-surface-900);
		border: 1px solid var(--color-surface-700);
		border-radius: 6px;
		padding: 0.75em;
		overflow-x: auto;
		margin: 0.5em 0;
		font-size: 11px;
	}
	.research-file-content :global(pre code) {
		background: none;
		padding: 0;
	}
	.research-file-content :global(blockquote) {
		border-left: 3px solid var(--color-surface-600);
		padding-left: 0.75em;
		margin: 0.5em 0;
		color: var(--color-surface-400);
	}
	.research-file-content :global(hr) {
		border: none;
		border-top: 1px solid var(--color-surface-700);
		margin: 1em 0;
	}
	/* Table styles */
	.research-file-content :global(table) {
		width: 100%;
		border-collapse: collapse;
		margin: 0.5em 0;
		font-size: 11px;
	}
	.research-file-content :global(thead) {
		border-bottom: 2px solid var(--color-surface-600);
	}
	.research-file-content :global(th) {
		text-align: left;
		font-weight: 600;
		color: var(--color-surface-100);
		padding: 0.4em 0.75em;
		background: var(--color-surface-900);
	}
	.research-file-content :global(td) {
		padding: 0.35em 0.75em;
		border-bottom: 1px solid var(--color-surface-700);
		color: var(--color-surface-300);
	}
	.research-file-content :global(tr:hover td) {
		background: var(--color-surface-800);
	}
	/* Glass-aware overrides for markdown renderer */
	.research-glass :global(h1),
	.research-glass :global(h2) {
		border-bottom-color: rgb(255 255 255 / 0.08);
	}
	.research-glass :global(code) {
		background: rgb(255 255 255 / 0.08);
	}
	.research-glass :global(pre) {
		background: rgb(255 255 255 / 0.05);
		border-color: rgb(255 255 255 / 0.08);
	}
	.research-glass :global(blockquote) {
		border-left-color: rgb(255 255 255 / 0.12);
	}
	.research-glass :global(hr) {
		border-top-color: rgb(255 255 255 / 0.08);
	}
	.research-glass :global(th) {
		background: rgb(255 255 255 / 0.05);
	}
	.research-glass :global(thead) {
		border-bottom-color: rgb(255 255 255 / 0.10);
	}
	.research-glass :global(td) {
		border-bottom-color: rgb(255 255 255 / 0.06);
	}
	.research-glass :global(tr:hover td) {
		background: rgb(255 255 255 / 0.06);
	}
	:global([data-theme='light']) .research-glass :global(h1),
	:global([data-theme='light']) .research-glass :global(h2) {
		border-bottom-color: rgb(0 0 0 / 0.10);
	}
	:global([data-theme='light']) .research-glass :global(code) {
		background: rgb(0 0 0 / 0.06);
	}
	:global([data-theme='light']) .research-glass :global(pre) {
		background: rgb(0 0 0 / 0.04);
		border-color: rgb(0 0 0 / 0.08);
	}
	:global([data-theme='light']) .research-glass :global(blockquote) {
		border-left-color: rgb(0 0 0 / 0.12);
	}
	:global([data-theme='light']) .research-glass :global(hr) {
		border-top-color: rgb(0 0 0 / 0.08);
	}
	:global([data-theme='light']) .research-glass :global(th) {
		background: rgb(0 0 0 / 0.04);
	}
	:global([data-theme='light']) .research-glass :global(thead) {
		border-bottom-color: rgb(0 0 0 / 0.10);
	}
	:global([data-theme='light']) .research-glass :global(td) {
		border-bottom-color: rgb(0 0 0 / 0.06);
	}
	:global([data-theme='light']) .research-glass :global(tr:hover td) {
		background: rgb(0 0 0 / 0.04);
	}
</style>
