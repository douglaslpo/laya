<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { getEngineUrl } from '$lib/config';
	import { t, tr } from '$lib/i18n';

	// Active tab: 'commands' | 'learning' | 'agents' | 'mcp'
	let activeTab = $state<'commands' | 'learning' | 'agents' | 'mcp'>('commands');

	// Backend & System State
	let engineStatus = $state<{ healthy: boolean; engine: string; sqlite: string; chromadb: string; uptime: number }>({
		healthy: false,
		engine: 'checking...',
		sqlite: 'checking...',
		chromadb: 'checking...',
		uptime: 0
	});

	let customProviders = $state<any[]>([]);
	let availableModels = $state<any[]>([]);
	let activeModels = $state<Record<string, string>>({});
	let contextRules = $state<any[]>([]);
	let learnedRulesCount = $state<number>(0);

	// Event Simulator Form
	let simPlatform = $state<'github' | 'slack' | 'jira' | 'gmail' | 'custom'>('custom');
	let simTitle = $state(tr('shell.hub_sim_default_title', 'My Project Ingestion Alert'));
	let simBody = $state(
		tr(
			'shell.hub_sim_default_body',
			'Build error detected in the production pipeline. Failure in the authentication module.'
		)
	);
	let simSpace = $state('default');
	let simSending = $state(false);
	let simResult = $state<{ success: boolean; message: string; cardId?: string } | null>(null);

	// Context Rule Add Form
	let newRuleText = $state('');
	let newRuleSpace = $state('default');
	let addingRule = $state(false);

	// Quick Code Snippets Generator
	let selectedSnippetLang = $state<'curl' | 'python' | 'js' | 'mcp'>('curl');
	let copiedState = $state(false);

	onMount(async () => {
		await refreshStatus();
		await loadContextRules();
	});

	async function refreshStatus() {
		try {
			const res = await fetch(`${getEngineUrl()}/health`);
			if (res.ok) {
				const data = await res.json();
				engineStatus = {
					healthy: data.engine === 'healthy',
					engine: data.engine,
					sqlite: data.sqlite,
					chromadb: data.chromadb,
					uptime: data.uptime_seconds || 0
				};
			}
		} catch {
			engineStatus.healthy = false;
		}

		try {
			const settingsRes = await fetch(`${getEngineUrl()}/settings`);
			if (settingsRes.ok) {
				const settings = await settingsRes.json();
				activeModels = settings.models || {};
				customProviders = settings.custom_providers || [];
			}
		} catch (e) {
			console.error('Failed to load settings', e);
		}

		try {
			const modelsRes = await fetch(`${getEngineUrl()}/settings/available-models`);
			if (modelsRes.ok) {
				const data = await modelsRes.json();
				availableModels = data.providers || [];
			}
		} catch (e) {
			console.error('Failed to load available models', e);
		}
	}

	async function loadContextRules() {
		try {
			const res = await fetch(`${getEngineUrl()}/context-rules`);
			if (res.ok) {
				const data = await res.json();
				contextRules = data.rules || data || [];
				learnedRulesCount = contextRules.length;
			}
		} catch (e) {
			console.error('Failed to load context rules', e);
		}
	}

	async function sendSimulatedEvent() {
		simSending = true;
		simResult = null;
		try {
			const payload = {
				source_platform: simPlatform,
				event_type: 'project_dispatch',
				space_id: simSpace,
				payload: {
					title: simTitle,
					body: simBody,
					timestamp: new Date().toISOString(),
					source: 'Laya Command Hub Simulator'
				}
			};

			const res = await fetch(`${getEngineUrl()}/api/v1/events/ingest`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (res.ok) {
				const data = await res.json();
				simResult = {
					success: true,
					message: $t(
						'shell.hub_sim_success',
						'Event sent successfully! Ollama will process it and generate the Action Card.'
					),
					cardId: data.card_id || data.id
				};
			} else {
				simResult = {
					success: false,
					message: $t('shell.hub_sim_failed', 'Ingestion failed ({status}): {error}', {
						status: res.status,
						error: await res.text()
					})
				};
			}
		} catch (err: any) {
			simResult = {
				success: false,
				message: $t('shell.hub_network_error', 'Network error: {error}', {
					error: String(err?.message || err)
				})
			};
		} finally {
			simSending = false;
		}
	}

	async function addContextDirective() {
		if (!newRuleText.trim()) return;
		addingRule = true;
		try {
			const res = await fetch(`${getEngineUrl()}/context-rules`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					rule_text: newRuleText,
					space_id: newRuleSpace
				})
			});
			if (res.ok) {
				newRuleText = '';
				await loadContextRules();
			}
		} catch (err) {
			console.error('Erro ao adicionar regra', err);
		} finally {
			addingRule = false;
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		copiedState = true;
		setTimeout(() => (copiedState = false), 2000);
	}

	let snippetContent = $derived.by(() => {
		const engine = getEngineUrl();
		if (selectedSnippetLang === 'curl') {
			return `curl -X POST ${engine}/api/v1/events/ingest \\
  -H "Content-Type: application/json" \\
  -d '{
    "source_platform": "custom_project",
    "event_type": "build_alert",
    "space_id": "${simSpace}",
    "payload": {
      "title": "${simTitle}",
      "body": "${simBody}"
    }
  }'`;
		} else if (selectedSnippetLang === 'python') {
			return `import requests

url = "${engine}/api/v1/events/ingest"
payload = {
    "source_platform": "my_python_app",
    "event_type": "log_analysis",
    "space_id": "${simSpace}",
    "payload": {
        "title": "${simTitle}",
        "body": "${simBody}"
    }
}
response = requests.post(url, json=payload)
print("Status:", response.status_code, response.json())`;
		} else if (selectedSnippetLang === 'js') {
			return `async function sendLayaEvent() {
  const res = await fetch('${engine}/api/v1/events/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_platform: 'web_client',
      event_type: 'user_feedback',
      space_id: '${simSpace}',
      payload: {
        title: '${simTitle}',
        body: '${simBody}'
      }
    })
  });
  return await res.json();
}`;
		} else {
			return `{
  "mcpServers": {
    "laya": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sse", "${engine}/mcp"]
    }
  }
}`;
		}
	});
</script>

<div class="min-h-screen bg-surface-950 text-surface-100 p-6 md:p-10 font-sans">
	<!-- Top Hero Header -->
	<header class="max-w-7xl mx-auto mb-8">
		<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-surface-800/80 pb-6">
			<div>
				<div class="flex items-center gap-3">
					<div class="h-9 w-9 rounded-xl bg-gradient-to-br from-amber-500 via-orange-600 to-rose-600 p-0.5 shadow-lg shadow-orange-500/20 flex items-center justify-center">
						<svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
						</svg>
					</div>
					<div>
						<h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
							{$t('hub.title', 'Laya Command Center & Learning Hub')}
							<span class="text-xs px-2.5 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20 font-mono">v1.0 Local</span>
						</h1>
						<p class="text-xs text-surface-400 mt-0.5">
							{$t('hub.subtitle', 'Centralize commands, teach context to your agents, and integrate with Ollama across your projects.')}
						</p>
					</div>
				</div>
			</div>

			<!-- Live Status Badge -->
			<div class="flex items-center gap-3 bg-surface-900 border border-surface-800 rounded-xl px-4 py-2.5 shadow-sm">
				<div class="flex items-center gap-2">
					<span class="relative flex h-3 w-3">
						{#if engineStatus.healthy}
							<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
							<span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
						{:else}
							<span class="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
						{/if}
					</span>
					<span class="text-xs font-medium text-surface-300">
						Engine: <strong class={engineStatus.healthy ? 'text-emerald-400' : 'text-rose-400'}>{engineStatus.healthy
								? $t('shell.hub_engine_active', 'Active (Port 8420)')
								: $t('shell.hub_engine_inactive', 'Inactive')}</strong>
					</span>
				</div>
				<span class="h-3 w-px bg-surface-800"></span>
				<div class="text-xs text-surface-400">
					Ollama: <span class="text-amber-400 font-mono font-medium">{activeModels.router || 'ollama-local'}</span>
				</div>
				<button onclick={refreshStatus} class="text-surface-400 hover:text-white transition-colors p-1 rounded-md hover:bg-surface-800" title={$t('shell.hub_refresh_status', 'Refresh status')}>
					<svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
				</button>
			</div>
		</div>

		<!-- Main Navigation Tabs -->
		<div class="flex items-center gap-2 mt-6 overflow-x-auto border-b border-surface-800/60 pb-1">
			<button
				onclick={() => activeTab = 'commands'}
				class="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap
					{activeTab === 'commands' ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30 shadow-sm' : 'text-surface-400 hover:text-surface-200 hover:bg-surface-900'}"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
				</svg>
				{$t('hub.tab_commands', 'Command Center & Ingestion')}
			</button>

			<button
				onclick={() => activeTab = 'learning'}
				class="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap
					{activeTab === 'learning' ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30 shadow-sm' : 'text-surface-400 hover:text-surface-200 hover:bg-surface-900'}"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
				</svg>
				{$t('hub.tab_learning', 'General & Per-Project Context Rules')}
				<span class="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-300">{$t('shell.hub_rules_count', '{count} rules', { count: learnedRulesCount })}</span>
			</button>

			<button
				onclick={() => activeTab = 'agents'}
				class="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap
					{activeTab === 'agents' ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30 shadow-sm' : 'text-surface-400 hover:text-surface-200 hover:bg-surface-900'}"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
				</svg>
				{$t('hub.tab_agents', 'General vs. Specialized Agents')}
			</button>

			<button
				onclick={() => activeTab = 'mcp'}
				class="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap
					{activeTab === 'mcp' ? 'bg-orange-500/15 text-orange-400 border border-orange-500/30 shadow-sm' : 'text-surface-400 hover:text-surface-200 hover:bg-surface-900'}"
			>
				<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
				</svg>
				{$t('hub.tab_mcp', 'MCP Integration (Cursor, Claude, IDEs)')}
			</button>
		</div>
	</header>

	<!-- Main Content Area -->
	<main class="max-w-7xl mx-auto space-y-8">
		{#if activeTab === 'commands'}
			<!-- TAB 1: Interactive Command Center & Event Dispatcher -->
			<div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
				<!-- Left Column: Interactive Dispatcher Form -->
				<div class="lg:col-span-6 bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl space-y-5">
					<div class="border-b border-surface-800 pb-4">
						<h2 class="text-base font-bold text-white flex items-center gap-2">
							<span class="flex h-2 w-2 rounded-full bg-orange-500"></span>
							{$t('hub.sim_title', 'Project Event Simulator (Dispatch)')}
						</h2>
						<p class="text-xs text-surface-400 mt-1">
							{$t('hub.sim_desc', 'Send a test event from your project. Laya will classify via Ollama and generate an Action Card.')}
						</p>
					</div>

					<div class="space-y-4 text-xs">
						<div>
							<label for="sim-platform" class="block font-medium text-surface-300 mb-1">{$t('shell.hub_platform_label', 'Platform / Source:')}</label>
							<select id="sim-platform" bind:value={simPlatform} class="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500">
								<option value="custom">{$t('shell.hub_opt_custom', 'Custom Project (REST API)')}</option>
								<option value="github">{$t('shell.hub_opt_github', 'GitHub Commit / PR Alert')}</option>
								<option value="jira">{$t('shell.hub_opt_jira', 'Jira Issue Tracker')}</option>
								<option value="slack">{$t('shell.hub_opt_slack', 'Slack Channel DM')}</option>
								<option value="gmail">{$t('shell.hub_opt_gmail', 'Gmail Inbound Message')}</option>
							</select>
						</div>

						<div>
							<label for="sim-space" class="block font-medium text-surface-300 mb-1">{$t('shell.hub_space_label', 'Space (Project Context):')}</label>
							<input id="sim-space" type="text" bind:value={simSpace} placeholder={$t('shell.hub_space_placeholder', 'e.g. default, laya, auth-api')} class="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500 font-mono" />
						</div>

						<div>
							<label for="sim-title" class="block font-medium text-surface-300 mb-1">{$t('shell.hub_event_title_label', 'Event Title:')}</label>
							<input id="sim-title" type="text" bind:value={simTitle} class="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500" />
						</div>

						<div>
							<label for="sim-body" class="block font-medium text-surface-300 mb-1">{$t('shell.hub_event_body_label', 'Content / Logs / Details:')}</label>
							<textarea id="sim-body" rows="4" bind:value={simBody} class="w-full bg-surface-950 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500 font-mono"></textarea>
						</div>

						<button
							onclick={sendSimulatedEvent}
							disabled={simSending}
							class="w-full bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-semibold py-2.5 rounded-lg transition-all shadow-md flex items-center justify-center gap-2 disabled:opacity-50"
						>
							{#if simSending}
								<span class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
								{$t('shell.hub_sending', 'Sending and processing via Ollama...')}
							{:else}
								<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
								</svg>
								{$t('hub.sim_send', 'Dispatch Event to Laya')}
							{/if}
						</button>

						{#if simResult}
							<div class="p-3 rounded-lg border text-xs flex items-start gap-2.5 {simResult.success ? 'bg-emerald-950/40 border-emerald-800/80 text-emerald-300' : 'bg-rose-950/40 border-rose-800/80 text-rose-300'}">
								<svg class="h-4 w-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
									{#if simResult.success}
										<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
									{:else}
										<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
									{/if}
								</svg>
								<div>
									<p class="font-medium">{simResult.message}</p>
									{#if simResult.cardId}
										<p class="mt-1 font-mono text-[11px] text-surface-300">{$t('shell.hub_card_id', 'Card ID: {id}', { id: simResult.cardId })}</p>
									{/if}
								</div>
							</div>
						{/if}
					</div>
				</div>

				<!-- Right Column: Code Generator for Projects -->
				<div class="lg:col-span-6 bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl flex flex-col justify-between space-y-4">
					<div>
						<div class="flex items-center justify-between border-b border-surface-800 pb-3 mb-4">
							<h2 class="text-base font-bold text-white flex items-center gap-2">
								<svg class="h-4 w-4 text-orange-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
								</svg>
								{$t('hub.code_generator', 'Integration Code Generator')}
							</h2>
							<div class="flex items-center gap-1 bg-surface-950 p-1 rounded-lg border border-surface-800 text-[11px]">
								<button onclick={() => selectedSnippetLang = 'curl'} class="px-2 py-0.5 rounded {selectedSnippetLang === 'curl' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-surface-400'}">cURL</button>
								<button onclick={() => selectedSnippetLang = 'python'} class="px-2 py-0.5 rounded {selectedSnippetLang === 'python' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-surface-400'}">Python</button>
								<button onclick={() => selectedSnippetLang = 'js'} class="px-2 py-0.5 rounded {selectedSnippetLang === 'js' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-surface-400'}">JavaScript</button>
								<button onclick={() => selectedSnippetLang = 'mcp'} class="px-2 py-0.5 rounded {selectedSnippetLang === 'mcp' ? 'bg-orange-500/20 text-orange-400 font-semibold' : 'text-surface-400'}">MCP</button>
							</div>
						</div>

						<p class="text-xs text-surface-400 mb-3">
							{$t('shell.hub_snippet_desc', 'Copy and paste this code into your projects so they send updates and alerts directly to Laya:')}
						</p>

						<div class="relative bg-surface-950 border border-surface-800 rounded-xl p-4 font-mono text-[11px] text-emerald-300 overflow-x-auto shadow-inner">
							<button
								onclick={() => copyToClipboard(snippetContent)}
								class="absolute top-2.5 right-2.5 bg-surface-800 hover:bg-surface-700 text-surface-200 px-2.5 py-1 rounded text-[10px] font-sans transition-colors flex items-center gap-1"
							>
								{#if copiedState}
									<span class="text-emerald-400 font-medium">{$t('common.copied', 'Copied!')}</span>
								{:else}
									<svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
									</svg>
									{$t('common.copy', 'Copy')}
								{/if}
							</button>
							<pre class="whitespace-pre-wrap">{snippetContent}</pre>
						</div>
					</div>

					<div class="bg-amber-950/20 border border-amber-800/40 rounded-xl p-4 text-xs text-amber-200/90 flex items-start gap-3">
						<svg class="h-5 w-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						<div>
							<strong class="font-semibold text-amber-300">{$t('shell.hub_how_title', 'How Laya processes this:')}</strong>
							<p class="mt-0.5 text-amber-200/80">
								{$t(
									'shell.hub_how_body',
									'As soon as the request arrives, Laya queries the hybrid memory (ChromaDB + SQLite) to correlate the event with other tickets or PRs, calls your **Ollama** model to draft a solution, and creates an **Action Card** for your decision.'
								)}
							</p>
						</div>
					</div>
				</div>
			</div>

		{:else if activeTab === 'learning'}
			<!-- TAB 2: General vs Specific Context Rules Learning -->
			<div class="space-y-6">
				<div class="bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl">
					<div class="flex flex-col md:flex-row md:items-center justify-between border-b border-surface-800 pb-4 mb-6 gap-4">
						<div>
							<h2 class="text-lg font-bold text-white flex items-center gap-2">
								<svg class="h-5 w-5 text-amber-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
									<path stroke-linecap="round" stroke-linejoin="round" d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0112 20.055a11.952 11.952 0 01-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
								</svg>
								{$t('hub.learning_title', 'Context Learning System (General vs. Specific)')}
							</h2>
							<p class="text-xs text-surface-400 mt-1">
								{$t('hub.learning_desc', 'As you use Laya across projects, it extracts natural language rules from your approvals and corrections.')}
							</p>
						</div>

						<div class="flex items-center gap-3">
							<span class="text-xs text-surface-300 font-medium">{$t('shell.hub_auto_consolidation', 'Automatic LLM Consolidation:')} <strong class="text-emerald-400">{$t('shell.hub_consolidation_on', 'On')}</strong></span>
						</div>
					</div>

					<!-- Form to add manual context directive -->
					<div class="bg-surface-950 border border-surface-800 rounded-xl p-4 mb-6 text-xs space-y-3">
						<h3 class="font-semibold text-surface-200">{$t('hub.teach_rule', 'Teach a new rule or directive to Laya:')}</h3>
						<div class="flex flex-col sm:flex-row gap-3">
							<input
								type="text"
								bind:value={newRuleText}
								placeholder={$t(
									'shell.hub_rule_placeholder',
									"e.g. 'Failure notifications in the billing module must always be marked as HIGH priority'"
								)}
								class="flex-1 bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500"
							/>
							<input
								type="text"
								bind:value={newRuleSpace}
								placeholder={$t('shell.hub_rule_space_placeholder', 'Space (e.g. default or billing)')}
								class="w-full sm:w-44 bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-surface-200 focus:outline-none focus:border-orange-500 font-mono"
							/>
							<button
								onclick={addContextDirective}
								disabled={addingRule}
								class="bg-orange-600 hover:bg-orange-500 text-white font-semibold px-4 py-2 rounded-lg transition-colors flex items-center justify-center gap-1.5 shrink-0"
							>
								{$t('hub.add_rule', 'Add Rule')}
							</button>
						</div>
					</div>

					<!-- Grid of Context Rules -->
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div class="border border-surface-800 rounded-xl p-4 bg-surface-950/60">
							<div class="flex items-center justify-between border-b border-surface-800 pb-2 mb-3">
								<h3 class="text-xs font-bold text-orange-400 uppercase tracking-wider flex items-center gap-1.5">
									<span class="h-2 w-2 rounded-full bg-orange-400"></span>
									{$t('hub.global_rules', 'General Contexts (Global Team Rules)')}
								</h3>
								<span class="text-[10px] text-surface-500 font-mono">space_id: default</span>
							</div>

							<ul class="space-y-2.5 text-xs text-surface-300">
								<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
									<strong class="text-white block font-medium">{$t('shell.hub_rule_people_title', 'Cross-Person Correlation:')}</strong>
									{$t('shell.hub_rule_people_body', 'Link GitHub, Jira, and Slack mentions that refer to the same developer.')}
								</li>
								<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
									<strong class="text-white block font-medium">{$t('shell.hub_rule_daily_title', 'Daily Summaries:')}</strong>
									{$t('shell.hub_rule_daily_body', 'Consolidate overnight pipeline activity into the 07:00 briefing.')}
								</li>
								{#each contextRules.filter(r => !r.space_id || r.space_id === 'default') as rule}
									<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
										<p>{rule.rule_text || rule}</p>
									</li>
								{/each}
							</ul>
						</div>

						<div class="border border-surface-800 rounded-xl p-4 bg-surface-950/60">
							<div class="flex items-center justify-between border-b border-surface-800 pb-2 mb-3">
								<h3 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
									<span class="h-2 w-2 rounded-full bg-amber-400"></span>
									{$t('hub.project_rules', 'Project-Specific Contexts (Spaces)')}
								</h3>
								<span class="text-[10px] text-surface-500 font-mono">{$t('shell.hub_per_space_rules', 'per-space rules')}</span>
							</div>

							<ul class="space-y-2.5 text-xs text-surface-300">
								<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
									<span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 float-right">Space: laya</span>
									<strong class="text-white block font-medium">{$t('shell.hub_rule_engine_title', 'Laya Engine Project:')}</strong>
									{$t('shell.hub_rule_engine_body', 'Any change to `requirements.txt` files requires hash validation in the lockfile.')}
								</li>
								<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
									<span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 float-right">Space: auth-api</span>
									<strong class="text-white block font-medium">{$t('shell.hub_rule_auth_title', 'Authentication Service:')}</strong>
									{$t('shell.hub_rule_auth_body', 'JWT token renewal errors must trigger the Engineering agent immediately.')}
								</li>
								{#each contextRules.filter(r => r.space_id && r.space_id !== 'default') as rule}
									<li class="bg-surface-900/80 p-2.5 rounded-lg border border-surface-800">
										<span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 float-right">Space: {rule.space_id}</span>
										<p>{rule.rule_text || rule}</p>
									</li>
								{/each}
							</ul>
						</div>
					</div>
				</div>
			</div>

		{:else if activeTab === 'agents'}
			<!-- TAB 3: General vs Specialized Agents Portal -->
			<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
				<!-- General Personas -->
				<div class="bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl space-y-4">
					<div class="border-b border-surface-800 pb-3">
						<h2 class="text-base font-bold text-white flex items-center gap-2">
							<span class="h-2.5 w-2.5 rounded-full bg-blue-500"></span>
							{$t('shell.hub_general_agents_title', 'General Persona Agents (Laya Pipeline)')}
						</h2>
						<p class="text-xs text-surface-400 mt-0.5">
							{$t('shell.hub_general_agents_desc', 'Powered by your local Ollama to analyze and draft quick replies.')}
						</p>
					</div>

					<div class="grid grid-cols-2 gap-3 text-xs">
						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl">
							<strong class="text-blue-400 block font-semibold">Engineer Worker</strong>
							<p class="text-surface-400 text-[11px] mt-1">{$t('shell.hub_worker_engineer_desc', 'Bug analysis, PR reviews, and error diagnostics.')}</p>
						</div>
						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl">
							<strong class="text-emerald-400 block font-semibold">Comms Worker</strong>
							<p class="text-surface-400 text-[11px] mt-1">{$t('shell.hub_worker_comms_desc', 'Email drafts, Slack replies, and conversation summaries.')}</p>
						</div>
						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl">
							<strong class="text-amber-400 block font-semibold">Ops Worker</strong>
							<p class="text-surface-400 text-[11px] mt-1">{$t('shell.hub_worker_ops_desc', 'Infrastructure monitoring, pipeline alerts, and logs.')}</p>
						</div>
						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl">
							<strong class="text-purple-400 block font-semibold">{$t('shell.hub_worker_other', 'Sales / HR / Finance')}</strong>
							<p class="text-surface-400 text-[11px] mt-1">{$t('shell.hub_worker_other_desc', 'Meeting triage, budgets, and client reports.')}</p>
						</div>
					</div>
				</div>

				<!-- Specialized CLI Coding Agents -->
				<div class="bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl space-y-4">
					<div class="border-b border-surface-800 pb-3">
						<h2 class="text-base font-bold text-white flex items-center gap-2">
							<span class="h-2.5 w-2.5 rounded-full bg-orange-500"></span>
							{$t('shell.hub_specialized_title', 'Project-Specialized Agents (Card Workspaces)')}
						</h2>
						<p class="text-xs text-surface-400 mt-0.5">
							{$t('shell.hub_specialized_desc', 'Interactive coding and deep-audit agents that operate in your project directory.')}
						</p>
					</div>

					<div class="space-y-2.5 text-xs">
						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl flex items-center justify-between">
							<div>
								<strong class="text-orange-400 block font-semibold">Claude Code / Gemini CLI / Codex / Pi</strong>
								<p class="text-surface-400 text-[11px]">{$t('shell.hub_cli_agents_desc', 'Installed CLI agents used as an inference backend with their own quota.')}</p>
							</div>
							<span class="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-mono text-[10px]">{$t('common.active', 'Active')}</span>
						</div>

						<div class="p-3 bg-surface-950 border border-surface-800 rounded-xl flex items-center justify-between">
							<div>
								<strong class="text-amber-400 block font-semibold">Ollama Local Agent (DeepSeek 16B / Llama 3.2)</strong>
								<p class="text-surface-400 text-[11px]">{$t('shell.hub_ollama_agent_desc', '100% private, offline execution for confidential projects.')}</p>
							</div>
							<span class="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 font-mono text-[10px]">{$t('shell.connected', 'Connected')}</span>
						</div>
					</div>
				</div>
			</div>

		{:else if activeTab === 'mcp'}
			<!-- TAB 4: MCP Integration Guide -->
			<div class="bg-surface-900 border border-surface-800/80 rounded-2xl p-6 shadow-xl space-y-6">
				<div class="border-b border-surface-800 pb-4">
					<h2 class="text-lg font-bold text-white flex items-center gap-2">
						<svg class="h-5 w-5 text-orange-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
						</svg>
						{$t('shell.hub_mcp_title', 'Built-in HTTP/SSE MCP Server (Model Context Protocol)')}
					</h2>
					<p class="text-xs text-surface-400 mt-1">
						{$t('shell.hub_mcp_desc', "Laya runs a native MCP server on port 8420. Connect your IDEs so your external assistants can access Laya's context.")}
					</p>
				</div>

				<div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
					<div class="bg-surface-950 p-4 rounded-xl border border-surface-800 space-y-2">
						<h3 class="font-bold text-white text-sm">1. Cursor IDE</h3>
						<p class="text-surface-400">{$t('shell.hub_mcp_cursor_desc', 'In Settings → MCP Servers, add a new server with the SSE URL:')}</p>
						<code class="block bg-surface-900 p-2 rounded text-[11px] font-mono text-orange-300">http://localhost:8420/mcp</code>
					</div>

					<div class="bg-surface-950 p-4 rounded-xl border border-surface-800 space-y-2">
						<h3 class="font-bold text-white text-sm">2. Claude Code</h3>
						<p class="text-surface-400">{$t('shell.hub_mcp_claude_desc', 'Run in your terminal inside any project:')}</p>
						<code class="block bg-surface-900 p-2 rounded text-[11px] font-mono text-orange-300">claude mcp add laya http://localhost:8420/mcp</code>
					</div>

					<div class="bg-surface-950 p-4 rounded-xl border border-surface-800 space-y-2">
						<h3 class="font-bold text-white text-sm">3. VS Code (Continue/Cline)</h3>
						<p class="text-surface-400">{$t('shell.hub_mcp_vscode_desc', 'Add the HTTP SSE endpoint to the mcpServers tools configuration.')}</p>
						<code class="block bg-surface-900 p-2 rounded text-[11px] font-mono text-orange-300">http://localhost:8420/mcp</code>
					</div>
				</div>
			</div>
		{/if}
	</main>
</div>
