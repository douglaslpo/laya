<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { reducedMotion } from '$lib/stores/reducedMotion';
	import type { ProviderModels, CustomProvider, CustomProviderTestResult, DiscoveredModel, PipelineSettings, BudgetConfig, MonthlyCostEntry, AgentBackend, AgentBudgetStatus } from '$lib/api/types';
	import { parseBackendDate } from '$lib/utils/datetime';
	import { budgetPaused, loadBudgetStatus, loadAgentBudgetStatus, fmtTokens } from '$lib/stores/budget';
	import { portal } from '$lib/actions/portal';
	import { CODING_AGENTS } from '$lib/config';
	import { t, locale } from '$lib/i18n';
	import ModelSelect from './ModelSelect.svelte';

	let guideTooltip = $state<{ text: string; top: number; left: number } | null>(null);

	function showGuide(e: MouseEvent, text: string) {
		const el = e.currentTarget as HTMLElement;
		const r = el.getBoundingClientRect();
		guideTooltip = { text, top: r.bottom + 8, left: r.left + r.width / 2 };
	}
	function hideGuide() { guideTooltip = null; }

	const roles = $derived([
		{ id: 'router', label: $t('settingsModels.role_router', 'Router'), hint: $t('settingsModels.role_router_hint', 'Classifies incoming events'),
			guide: $t('settingsModels.role_router_guide', 'Classifies each incoming event by persona (Engineer/Comms/Ops) and priority. Output is structured JSON, not prose. A small, fast model works well here.') },
		{ id: 'stager', label: $t('settingsModels.role_stager', 'Stager'), hint: $t('settingsModels.role_stager_hint', 'Synthesises action cards'),
			guide: $t('settingsModels.role_stager_guide', 'Reads the classified event and writes the action card: headline, summary, suggested actions, and draft replies. Quality of card content scales directly with model capability — use a stronger model if you want richer summaries.') },
		{ id: 'chat', label: $t('common.chat', 'Chat'), hint: $t('settingsModels.role_chat_hint', 'Conversational responses'),
			guide: $t('settingsModels.role_chat_guide', 'Powers the chat panel where you ask questions about your cards, events, and workspace. A capable model gives better conversational and reasoning quality.') },
		{ id: 'trace', label: $t('nav.coherence', 'Coherence'), hint: $t('settingsModels.role_trace_hint', 'Generates trace narratives'),
			guide: $t('settingsModels.role_trace_guide', 'Generates narrative summaries when you search for related activity across platforms. The heavy lifting is semantic search — the model just synthesises results into prose. A smaller model is usually sufficient.') },
		{ id: 'omni', label: 'Omni', hint: $t('settingsModels.role_omni_hint', 'Resynthesises rolling summaries'),
			guide: $t('settingsModels.role_omni_guide', 'Periodically compresses your rolling cross-platform summary into a concise digest. Needs to merge and deduplicate information across many events. A mid-tier model balances cost and coherence well.') }
	]);

	const cloudProviders = [
		{ id: 'anthropic', label: 'Anthropic', envVar: 'ANTHROPIC_API_KEY' },
		{ id: 'openai', label: 'OpenAI', envVar: 'OPENAI_API_KEY' },
		{ id: 'google', label: 'Google', envVar: 'GOOGLE_API_KEY' },
		{ id: 'openrouter', label: 'OpenRouter', envVar: 'OPENROUTER_API_KEY' }
	];

	const providerTypes = $derived([
		{ id: 'lmstudio', label: 'LM Studio', defaultUrl: 'http://localhost:1234' },
		{ id: 'ollama', label: 'Ollama', defaultUrl: 'http://localhost:11434' },
		{ id: 'openai_compatible', label: $t('settingsModels.provider_type_openai_compatible', 'OpenAI Compatible'), defaultUrl: 'http://localhost:8080' }
	]);

	let models = $state({
		router: 'claude-haiku-4-5',
		stager: 'claude-sonnet-4-6',
		chat: 'claude-sonnet-4-6',
		trace: 'claude-sonnet-4-6',
		omni: 'claude-sonnet-4-6',
		local: 'ollama/llama3'
	});

	// --- Agent inference backend (use an installed CLI agent as the LLM) ---
	// Only the structured, non-streaming roles can run on an agent. Chat + Coherence need
	// a streaming tool-loop the agents can't run for us, so they stay on a model/local
	// provider (keep their dropdowns) even when the agent backend is selected.
	const AGENT_ROLES = ['router', 'stager', 'omni'];
	const DEFAULT_MODELS: Record<string, string> = {
		router: 'claude-haiku-4-5', stager: 'claude-sonnet-4-6', omni: 'claude-sonnet-4-6'
	};
	const AGENT_LABELS: Record<string, string> = Object.fromEntries(
		CODING_AGENTS.filter((a) => a.value !== 'none').map((a) => [a.value, a.label])
	);
	const AGENT_MODEL_EXAMPLES: Record<string, { model: string; agent: string }> = {
		claude_code: { model: 'claude-sonnet-4-6', agent: 'Claude Code' },
		codex_cli: { model: 'gpt-5-codex', agent: 'Codex' },
		gemini_cli: { model: 'gemini-2.5-pro', agent: 'Gemini' },
		pi_cli: { model: 'lmstudio/qwen3.6-35b-a3b', agent: 'Pi' }
	};

	let agentMode = $state(false);
	let selectedAgent = $state('claude_code');
	const agentModelPlaceholder = $derived(
		AGENT_MODEL_EXAMPLES[selectedAgent]
			? $t('settingsModels.agent_model_placeholder', 'e.g. {model} — blank uses {agent}’s default', AGENT_MODEL_EXAMPLES[selectedAgent])
			: $t('settingsModels.agent_model_placeholder_fallback', 'Model string (blank = agent default)')
	);
	let agentBackends = $state<AgentBackend[]>([]);
	let providerBackup = $state<Record<string, string>>({});
	let selectedBackend = $derived(agentBackends.find((b) => b.agent_id === selectedAgent));

	// --- Agent usage-limit budget (window-based, auto-resume) ---
	let agentBudgetEnabled = $state(false);
	let agentBudgetAgents = $state<Record<string, { window_token_limit: number | null; window_hours: number; pause_at_percent: number }>>({});
	let agentBudgetStatus = $state<AgentBudgetStatus | null>(null);
	let savingAgentBudget = $state(false);
	let resumingAgentBudget = $state(false);
	let agentBudgetTimer: ReturnType<typeof setTimeout> | null = null;

	// Seed a default config row for every available agent so the inputs can bind.
	$effect(() => {
		for (const b of agentBackends) {
			if (b.available && !agentBudgetAgents[b.agent_id]) {
				agentBudgetAgents[b.agent_id] = { window_token_limit: null, window_hours: 5, pause_at_percent: 85 };
			}
		}
	});

	function agentStatusFor(agentId: string) {
		return agentBudgetStatus?.agents.find((a) => a.agent_id === agentId) ?? null;
	}
	function fmtTokensShort(n: number): string {
		if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + 'M';
		if (n >= 1_000) return Math.round(n / 1_000) + 'K';
		return '' + n;
	}

	async function loadAgentBudget() {
		try {
			const data = await engineApi.getAgentBudget();
			agentBudgetStatus = data;
			agentBudgetEnabled = data.enabled;
			for (const a of data.agents) {
				agentBudgetAgents[a.agent_id] = {
					window_token_limit: a.window_token_limit || null,
					window_hours: a.window_hours,
					pause_at_percent: a.pause_at_percent,
				};
			}
		} catch (e) {
			console.error('Failed to load agent budget:', e);
		}
	}

	async function saveAgentBudget() {
		savingAgentBudget = true;
		try {
			const agents: Record<string, { window_token_limit: number; window_hours: number; pause_at_percent: number }> = {};
			for (const [id, c] of Object.entries(agentBudgetAgents)) {
				if (c.window_token_limit && c.window_token_limit > 0) {
					agents[id] = {
						window_token_limit: Math.round(c.window_token_limit),
						window_hours: c.window_hours || 5,
						pause_at_percent: c.pause_at_percent || 85,
					};
				}
			}
			await engineApi.updateAgentBudget({ enabled: agentBudgetEnabled, agents });
			await loadAgentBudget();
			loadAgentBudgetStatus();
		} catch (e) {
			console.error('Failed to save agent budget:', e);
		} finally {
			savingAgentBudget = false;
		}
	}

	function debounceSaveAgentBudget() {
		if (agentBudgetTimer) clearTimeout(agentBudgetTimer);
		agentBudgetTimer = setTimeout(saveAgentBudget, 600);
	}

	async function handleResumeAgent() {
		resumingAgentBudget = true;
		try {
			await engineApi.resumeAgentBudget();
			await loadAgentBudget();
			loadAgentBudgetStatus();
		} catch (e) {
			console.error('Failed to resume agent budget:', e);
		} finally {
			resumingAgentBudget = false;
		}
	}

	let apiKeys = $state<Record<string, boolean>>({
		anthropic: false,
		openai: false,
		google: false,
		openrouter: false
	});

	let keyInputs = $state<Record<string, string>>({
		anthropic: '',
		openai: '',
		google: '',
		openrouter: ''
	});

	let saving = $state(false);
	let savingKey = $state<string | null>(null);
	let loaded = $state(false);
	let availableModels = $state<ProviderModels[]>([]);
	let modelsLoading = $state(false);

	// Local providers state
	let customProviders = $state<CustomProvider[]>([]);
	let showAddProvider = $state(false);
	let newProvider = $state({ name: '', base_url: '', provider_type: 'lmstudio', api_key: '' });
	let addingProvider = $state(false);
	let addError = $state('');

	// Per-provider state
	let testingProvider = $state<string | null>(null);
	let testResults = $state<Record<string, CustomProviderTestResult>>({});
	let providerModels = $state<Record<string, DiscoveredModel[]>>({});
	let expandedProvider = $state<string | null>(null);
	let deletingProvider = $state<string | null>(null);

	// Edit state
	let editingProvider = $state<string | null>(null);
	let editForm = $state({ name: '', base_url: '', api_key: '' });
	let editSaving = $state(false);

	// Advanced pipeline settings
	let showAdvanced = $state(false);
	let pipeline = $state<PipelineSettings>({
		model_timeout: 120,
		llm_retries: 3,
		max_retry_attempts: 5,
		max_concurrent_events: 5,
		queue_poll_interval: 2
	});
	let savingPipeline = $state(false);
	let pipelineSaveTimer: ReturnType<typeof setTimeout> | null = null;

	// Budget / Cost Control state
	let budgetEnabled = $state(false);
	let budgetLimit = $state<number | null>(null);
	let budgetLimitInput = $state<number | null>(null);
	let currentMonthCost = $state(0);
	let currentMonth = $state('');
	let budgetByModel = $state<Record<string, number>>({});
	let budgetTokensByModel = $state<Record<string, number>>({});
	let budgetIsPaused = $state(false);
	let pausedWorkflowCount = $state(0);
	let savingBudget = $state(false);
	let resumingBudget = $state(false);
	let showHistory = $state(false);
	let budgetHistory = $state<MonthlyCostEntry[]>([]);
	let historyLoading = $state(false);

	const budgetPercent = $derived(
		budgetLimit && budgetLimit > 0 ? Math.min((currentMonthCost / budgetLimit) * 100, 100) : 0
	);
	const budgetBarColor = $derived(
		budgetPercent >= 100 ? 'bg-red-500' : budgetPercent >= 75 ? 'bg-amber-500' : 'bg-green-500'
	);

	async function loadBudget() {
		try {
			const data = await engineApi.getBudget();
			budgetEnabled = data.enabled;
			budgetLimit = data.monthly_limit_usd;
			budgetLimitInput = data.monthly_limit_usd;
			currentMonthCost = data.current_month_cost;
			currentMonth = data.current_month;
			budgetByModel = data.by_model;
			budgetTokensByModel = data.tokens_by_model;
			budgetIsPaused = data.is_paused;
			pausedWorkflowCount = data.paused_workflow_count;
			budgetPaused.set(data.is_paused);
		} catch (e) {
			console.error('Failed to load budget:', e);
		}
	}

	async function saveBudget() {
		savingBudget = true;
		try {
			const limit = budgetLimitInput != null && budgetLimitInput > 0 ? budgetLimitInput : null;
			await engineApi.updateBudget({ monthly_limit_usd: limit, enabled: budgetEnabled });
			budgetLimit = limit;
			// Re-fetch to confirm server state
			await loadBudget();
			// Update the global budget store so the footer cost widget refreshes
			loadBudgetStatus();
		} catch (e) {
			console.error('Failed to save budget:', e);
		} finally {
			savingBudget = false;
		}
	}

	let budgetSaveTimer: ReturnType<typeof setTimeout> | null = null;
	function debounceSaveBudget() {
		if (budgetSaveTimer) clearTimeout(budgetSaveTimer);
		budgetSaveTimer = setTimeout(saveBudget, 600);
	}

	async function handleResume() {
		resumingBudget = true;
		try {
			await engineApi.resumeBudget();
			await loadBudget();
		} catch (e) {
			console.error('Failed to resume:', e);
		} finally {
			resumingBudget = false;
		}
	}

	async function loadHistory() {
		if (budgetHistory.length > 0) return; // already loaded
		historyLoading = true;
		try {
			const data = await engineApi.getBudgetHistory();
			budgetHistory = data.months;
		} catch (e) {
			console.error('Failed to load budget history:', e);
		} finally {
			historyLoading = false;
		}
	}

	function formatMonth(ym: string): string {
		const [y, m] = ym.split('-');
		const date = new Date(parseInt(y), parseInt(m) - 1);
		return date.toLocaleDateString($locale, { month: 'long', year: 'numeric' });
	}

	onMount(async () => {
		try {
			const [settings, providersResp] = await Promise.all([
				engineApi.getSettings(),
				engineApi.getCustomProviders()
			]);
			models = { ...models, ...settings.models };
			apiKeys = { ...apiKeys, ...settings.api_keys };
			if (settings.pipeline) pipeline = { ...pipeline, ...settings.pipeline };
			customProviders = providersResp.providers;
			loaded = true;
			// Infer agent-backend mode from the saved structured-role values.
			const inferred = AGENT_ROLES
				.map((r) => parseAgentModel(models[r as keyof typeof models]))
				.find((p) => p);
			if (inferred) {
				agentMode = true;
				if (inferred.agentId) selectedAgent = inferred.agentId;
			}
			try {
				const backendsResp = await engineApi.getAgentBackends();
				agentBackends = backendsResp.backends;
			} catch (e) {
				console.error('Failed to load agent backends:', e);
			}
			await Promise.all([fetchModels(), loadBudget(), loadAgentBudget()]);
		} catch (e) {
			console.error('Failed to load settings:', e);
		}
	});

	async function fetchModels(refresh = false) {
		modelsLoading = true;
		try {
			const resp = await engineApi.getAvailableModels(refresh);
			availableModels = resp.providers;
		} catch (e) {
			console.error('Failed to fetch available models:', e);
		} finally {
			modelsLoading = false;
		}
	}

	async function saveModels() {
		saving = true;
		try {
			await engineApi.updateSettings({ models } as any);
		} catch (e) {
			console.error('Failed to save models:', e);
		} finally {
			saving = false;
		}
	}

	function handleModelChange(role: string) {
		return (value: string) => {
			models[role as keyof typeof models] = value;
			saveModels();
		};
	}

	// --- Agent backend helpers ---
	// A stage's stored value is `agent/<agentId>/<modelString>` (or `agent/<agentId>` for the
	// agent's default model). Splitting keeps slugs with their own slashes (lmstudio/…) intact.
	function parseAgentModel(v: string): { agentId: string; modelString: string } | null {
		if (!v || !v.startsWith('agent/')) return null;
		const parts = v.split('/');
		return { agentId: parts[1] || '', modelString: parts.slice(2).join('/') };
	}

	function agentModelString(role: string): string {
		const p = parseAgentModel(models[role as keyof typeof models]);
		return p ? p.modelString : '';
	}

	function setAgentMode(on: boolean) {
		if (on === agentMode) return;
		agentMode = on;
		if (on) {
			// Switch structured roles to the agent; stash their provider model so we can restore it.
			for (const r of AGENT_ROLES) {
				if (!parseAgentModel(models[r as keyof typeof models])) {
					providerBackup[r] = models[r as keyof typeof models];
					models[r as keyof typeof models] = `agent/${selectedAgent}`;
				}
			}
		} else {
			for (const r of AGENT_ROLES) {
				if (parseAgentModel(models[r as keyof typeof models])) {
					models[r as keyof typeof models] = providerBackup[r] || DEFAULT_MODELS[r];
				}
			}
		}
		saveModels();
	}

	function selectAgent(agentId: string) {
		selectedAgent = agentId;
		// Re-point every structured role at the new agent, preserving each typed model string.
		for (const r of AGENT_ROLES) {
			const ms = agentModelString(r);
			models[r as keyof typeof models] = ms ? `agent/${agentId}/${ms}` : `agent/${agentId}`;
		}
		saveModels();
	}

	function handleAgentModelInput(role: string) {
		return (e: Event) => {
			const typed = (e.target as HTMLInputElement).value.trim();
			models[role as keyof typeof models] = typed
				? `agent/${selectedAgent}/${typed}`
				: `agent/${selectedAgent}`;
			saveModels();
		};
	}

	async function saveApiKey(provider: string) {
		const key = keyInputs[provider];
		if (!key.trim()) return;
		savingKey = provider;
		try {
			await engineApi.setApiKey(provider, key.trim());
			apiKeys[provider] = true;
			keyInputs[provider] = '';
			await fetchModels();
		} catch (e) {
			console.error('Failed to save API key:', e);
		} finally {
			savingKey = null;
		}
	}

	async function removeApiKey(provider: string) {
		try {
			await engineApi.deleteApiKey(provider);
			apiKeys[provider] = false;
			await fetchModels();
		} catch (e) {
			console.error('Failed to remove API key:', e);
		}
	}

	// --- Local provider management ---

	function handleProviderTypeChange(type: string) {
		newProvider.provider_type = type;
		const preset = providerTypes.find(p => p.id === type);
		if (preset && !newProvider.base_url) {
			newProvider.base_url = preset.defaultUrl;
		}
	}

	async function addProvider() {
		if (!newProvider.name.trim() || !newProvider.base_url.trim()) return;
		addingProvider = true;
		addError = '';
		try {
			const resp = await engineApi.addCustomProvider({
				name: newProvider.name.trim(),
				base_url: newProvider.base_url.trim(),
				provider_type: newProvider.provider_type,
				api_key: newProvider.api_key.trim() || undefined
			});
			customProviders = [...customProviders, resp.provider];
			newProvider = { name: '', base_url: '', provider_type: 'lmstudio', api_key: '' };
			showAddProvider = false;
			// Refresh models to include models from new provider
			await fetchModels(true);
		} catch (e: any) {
			addError = e.message || $t('settingsModels.add_provider_failed', 'Failed to add provider');
		} finally {
			addingProvider = false;
		}
	}

	async function deleteProvider(providerId: string) {
		deletingProvider = providerId;
		try {
			await engineApi.deleteCustomProvider(providerId);
			customProviders = customProviders.filter(p => p.id !== providerId);
			delete testResults[providerId];
			delete providerModels[providerId];
			if (expandedProvider === providerId) expandedProvider = null;
			await fetchModels(true);
		} catch (e) {
			console.error('Failed to delete provider:', e);
		} finally {
			deletingProvider = null;
		}
	}

	async function testProvider(providerId: string) {
		testingProvider = providerId;
		try {
			const result = await engineApi.testCustomProvider(providerId);
			testResults[providerId] = result;
		} catch (e: any) {
			testResults[providerId] = {
				provider_id: providerId,
				reachable: false,
				models_count: 0,
				llm_count: 0,
				embedding_count: 0,
				inference_ok: false,
				latency_ms: 0,
				error: e.message || $t('settingsModels.connection_failed', 'Connection failed')
			};
		} finally {
			testingProvider = null;
		}
	}

	async function toggleExpand(providerId: string) {
		if (expandedProvider === providerId) {
			expandedProvider = null;
			return;
		}
		expandedProvider = providerId;
		if (!providerModels[providerId]) {
			try {
				const resp = await engineApi.getProviderModels(providerId);
				providerModels[providerId] = resp.models;
			} catch (e) {
				console.error('Failed to fetch provider models:', e);
				providerModels[providerId] = [];
			}
		}
	}

	function startEdit(provider: CustomProvider) {
		editingProvider = provider.id;
		editForm = { name: provider.name, base_url: provider.base_url, api_key: '' };
	}

	async function saveEdit(providerId: string) {
		editSaving = true;
		try {
			const updates: Record<string, any> = {};
			if (editForm.name.trim()) updates.name = editForm.name.trim();
			if (editForm.base_url.trim()) updates.base_url = editForm.base_url.trim();
			if (editForm.api_key.trim()) updates.api_key = editForm.api_key.trim();
			const resp = await engineApi.updateCustomProvider(providerId, updates);
			customProviders = customProviders.map(p => p.id === providerId ? resp.provider : p);
			editingProvider = null;
			// Clear cached models for this provider and refresh
			delete providerModels[providerId];
			delete testResults[providerId];
			await fetchModels(true);
		} catch (e) {
			console.error('Failed to update provider:', e);
		} finally {
			editSaving = false;
		}
	}

	function getTypeLabel(type: string) {
		return providerTypes.find(p => p.id === type)?.label ?? type;
	}

	function debounceSavePipeline() {
		if (pipelineSaveTimer) clearTimeout(pipelineSaveTimer);
		pipelineSaveTimer = setTimeout(savePipeline, 600);
	}

	async function savePipeline() {
		savingPipeline = true;
		try {
			await engineApi.updateSettings({ pipeline } as any);
		} catch (e) {
			console.error('Failed to save pipeline settings:', e);
		} finally {
			savingPipeline = false;
		}
	}
</script>

{#if !loaded}
	<div class="flex items-center justify-center py-12 text-surface-400">{$t('settingsModels.loading_settings', 'Loading settings...')}</div>
{:else}
	<div class="space-y-8">
		<!-- API Keys -->
		<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
			<h3 class="mb-4 text-laya-heading font-medium">{$t('settingsModels.api_keys_title', 'API Keys')}</h3>
			<p class="mb-4 text-laya-base text-surface-400">
				{$t('settingsModels.api_keys_desc', 'Keys are stored securely in your OS keychain. They are never sent to the UI.')}
			</p>
			<div class="space-y-4">
				{#each cloudProviders as provider}
					<div class="flex items-center gap-3">
						<div class="flex w-28 items-center gap-2">
							<span
								class="h-2 w-2 rounded-full {apiKeys[provider.id]
									? 'bg-green-500'
									: 'bg-surface-500'}"
							></span>
							<span class="text-laya-base text-surface-300">{provider.label}</span>
						</div>

						{#if apiKeys[provider.id]}
							<span class="text-laya-base text-green-400">{$t('settingsModels.configured', 'Configured')}</span>
							<button
								onclick={() => removeApiKey(provider.id)}
								class="ml-auto text-laya-base text-red-400 transition-colors hover:text-red-300"
							>
								{$t('settingsModels.remove', 'Remove')}
							</button>
						{:else}
							<input
								type="password"
								bind:value={keyInputs[provider.id]}
								placeholder={$t('settingsModels.enter_api_key', 'Enter API key...')}
								class="flex-1 rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-laya-base text-surface-100 placeholder:text-surface-500"
							/>
							<button
								onclick={() => saveApiKey(provider.id)}
								disabled={!keyInputs[provider.id].trim() || savingKey === provider.id}
								class="rounded-md bg-primary-600 px-3 py-1.5 text-laya-base font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50"
							>
								{savingKey === provider.id ? $t('settingsModels.saving', 'Saving…') : $t('common.save', 'Save')}
							</button>
						{/if}
					</div>
				{/each}
			</div>
		</div>

		<!-- Local Providers -->
		<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
			<div class="mb-4 flex items-center justify-between">
				<div>
					<h3 class="mb-1 text-laya-heading font-medium">{$t('settingsModels.local_providers_title', 'Local Providers')}</h3>
					<p class="text-laya-secondary text-surface-500">{$t('settingsModels.local_providers_desc', 'Connect to LM Studio, Ollama, or any OpenAI-compatible server running on your machine.')}</p>
				</div>
				<button
					onclick={() => { showAddProvider = !showAddProvider; addError = ''; }}
					class="rounded-md border border-surface-600 px-3 py-1.5 text-laya-base text-surface-400 transition-colors hover:border-surface-500 hover:text-surface-300"
				>
					{showAddProvider ? $t('common.cancel', 'Cancel') : $t('settingsModels.add_provider_toggle', '+ Add Provider')}
				</button>
			</div>

			<!-- Add Provider Form -->
			{#if showAddProvider}
				<div transition:slide={{ duration: $reducedMotion ? 0 : 200 }} class="mb-5 rounded-md border border-surface-600 bg-surface-700/50 p-4 space-y-3">
					<div class="grid grid-cols-3 gap-3">
						{#each providerTypes as pt}
							<button
								onclick={() => handleProviderTypeChange(pt.id)}
								class="rounded-md border px-3 py-2 text-laya-base transition-colors
									{newProvider.provider_type === pt.id
										? 'border-laya-orange/50 bg-laya-orange/10 text-laya-orange'
										: 'border-surface-600 text-surface-400 hover:border-surface-500 hover:text-surface-300'}"
							>
								{pt.label}
							</button>
						{/each}
					</div>
					<div class="grid grid-cols-2 gap-3">
						<input
							type="text"
							bind:value={newProvider.name}
							placeholder={$t('settingsModels.display_name_example', 'Display name (e.g. My LM Studio)')}
							class="rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
						/>
						<input
							type="text"
							bind:value={newProvider.base_url}
							placeholder={providerTypes.find(p => p.id === newProvider.provider_type)?.defaultUrl ?? 'http://localhost:1234'}
							class="rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
						/>
					</div>
										<input
						type="password"
						bind:value={newProvider.api_key}
						placeholder={$t('settingsModels.api_key_optional', 'API key (optional — leave blank if not required)')}
						class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
					/>
					{#if addError}
						<p class="text-laya-base text-red-400">{addError}</p>
					{/if}
					<div class="flex justify-end">
						<button
							onclick={addProvider}
							disabled={!newProvider.name.trim() || !newProvider.base_url.trim() || addingProvider}
							class="rounded-md bg-laya-orange px-4 py-2 text-laya-base font-medium text-surface-900 transition-colors hover:bg-laya-gold disabled:opacity-50"
						>
							{addingProvider ? $t('settingsModels.adding', 'Adding...') : $t('settingsModels.add_provider', 'Add Provider')}
						</button>
					</div>
				</div>
			{/if}

			<!-- Provider List -->
			{#if customProviders.length === 0 && !showAddProvider}
				<div class="rounded-md border border-dashed border-surface-600 py-8 text-center">
					<p class="text-laya-base text-surface-500">{$t('settingsModels.no_local_providers', 'No local providers configured')}</p>
					<p class="mt-1 text-laya-secondary text-surface-600">{$t('settingsModels.no_local_providers_hint', 'Add LM Studio, Ollama, or another local server to use local models')}</p>
				</div>
			{:else}
				<div class="space-y-3">
					{#each customProviders as provider (provider.id)}
						<div class="rounded-md border border-surface-600 bg-surface-700/30">
							<!-- Provider header -->
							<div class="flex items-center gap-3 px-4 py-3">
								<button
									onclick={() => toggleExpand(provider.id)}
									class="flex flex-1 items-center gap-3 text-left"
								>
									<svg
										class="h-4 w-4 shrink-0 text-surface-400 transition-transform {expandedProvider === provider.id ? 'rotate-90' : ''}"
										fill="none" stroke="currentColor" viewBox="0 0 24 24"
									>
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
									</svg>
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<span class="text-laya-base font-medium text-surface-200">{provider.name}</span>
											<span class="rounded-full bg-surface-600 px-2 py-0.5 text-laya-micro text-surface-400">
												{getTypeLabel(provider.provider_type)}
											</span>
											{#if testResults[provider.id]}
												{@const tr = testResults[provider.id]}
												<span class="h-2 w-2 rounded-full {tr.reachable ? (tr.inference_ok ? 'bg-green-500' : 'bg-yellow-500') : 'bg-red-500'}"></span>
											{/if}
										</div>
										<p class="mt-0.5 truncate text-laya-secondary text-surface-500">{provider.base_url}</p>
									</div>
								</button>

								<div class="flex items-center gap-1.5">
									<button
										onclick={() => testProvider(provider.id)}
										disabled={testingProvider === provider.id}
										class="rounded px-2 py-1 text-laya-secondary text-surface-400 transition-colors hover:bg-surface-600 hover:text-surface-300 disabled:opacity-50"
										title={$t('settingsModels.test_connection', 'Test connection')}
									>
										{#if testingProvider === provider.id}
											<svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
												<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
												<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
											</svg>
										{:else}
											{$t('settingsModels.test', 'Test')}
										{/if}
									</button>
									<button
										onclick={() => startEdit(provider)}
										class="rounded px-2 py-1 text-laya-secondary text-surface-400 transition-colors hover:bg-surface-600 hover:text-surface-300"
									>
										{$t('common.edit', 'Edit')}
									</button>
									<button
										onclick={() => deleteProvider(provider.id)}
										disabled={deletingProvider === provider.id}
										class="rounded px-2 py-1 text-laya-secondary text-red-400/70 transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
									>
										{deletingProvider === provider.id ? '...' : $t('settingsModels.remove', 'Remove')}
									</button>
								</div>
							</div>

							<!-- Test result -->
							{#if testResults[provider.id]}
								{@const tr = testResults[provider.id]}
								<div class="border-t border-surface-600/50 px-4 py-2 text-laya-secondary">
									{#if tr.reachable}
										<div class="flex items-center gap-4 text-surface-400">
											<span class="text-green-400">{$t('settingsModels.connected', 'Connected')}</span>
											<span>{tr.models_count === 1
												? $t('settingsModels.models_count_one', '{count} model', { count: tr.models_count })
												: $t('settingsModels.models_count_other', '{count} models', { count: tr.models_count })}</span>
											<span>{$t('settingsModels.inference_label', 'Inference:')} <span class="{tr.inference_ok ? 'text-green-400' : 'text-yellow-400'}">{tr.inference_ok ? $t('settingsModels.inference_ok', 'OK') : $t('settingsModels.inference_failed', 'failed')}</span></span>
											<span>{tr.latency_ms}ms</span>
										</div>
									{:else}
										<span class="text-red-400">{tr.error || $t('settingsModels.unreachable', 'Unreachable')}</span>
									{/if}
								</div>
							{/if}

							<!-- Edit form -->
							{#if editingProvider === provider.id}
								<div class="border-t border-surface-600/50 px-4 py-3 space-y-3">
									<div class="grid grid-cols-2 gap-3">
										<input
											type="text"
											bind:value={editForm.name}
											placeholder={$t('settingsModels.display_name', 'Display name')}
											class="rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-laya-base text-surface-100 placeholder:text-surface-500"
										/>
										<input
											type="text"
											bind:value={editForm.base_url}
											placeholder={$t('settingsModels.base_url', 'Base URL')}
											class="rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-laya-base text-surface-100 placeholder:text-surface-500"
										/>
									</div>
									<input
										type="password"
										bind:value={editForm.api_key}
										placeholder={$t('settingsModels.new_api_key', 'New API key (leave blank to keep current)')}
										class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-laya-base text-surface-100 placeholder:text-surface-500"
									/>
									<div class="flex justify-end gap-2">
										<button
											onclick={() => { editingProvider = null; }}
											class="rounded-md px-3 py-1.5 text-laya-base text-surface-400 hover:text-surface-300"
										>
											{$t('common.cancel', 'Cancel')}
										</button>
										<button
											onclick={() => saveEdit(provider.id)}
											disabled={editSaving}
											class="rounded-md bg-laya-orange px-3 py-1.5 text-laya-base font-medium text-surface-900 transition-colors hover:bg-laya-gold disabled:opacity-50"
										>
											{editSaving ? $t('settingsModels.saving', 'Saving…') : $t('common.save', 'Save')}
										</button>
									</div>
								</div>
							{/if}

							<!-- Expanded model list -->
							{#if expandedProvider === provider.id}
								<div transition:slide={{ duration: $reducedMotion ? 0 : 200 }} class="border-t border-surface-600/50 px-4 py-3">
									{#if !providerModels[provider.id]}
										<p class="text-laya-secondary text-surface-500">{$t('settingsModels.loading_models', 'Loading models...')}</p>
									{:else if providerModels[provider.id].length === 0}
										<p class="text-laya-secondary text-surface-500">{$t('settingsModels.no_models_found', 'No models found. Is the server running?')}</p>
									{:else}
										<div class="space-y-1.5">
											{#each providerModels[provider.id] as model}
												<div class="flex items-center gap-3 rounded px-2 py-1.5 text-laya-secondary hover:bg-surface-700/50">
													<div class="flex items-center gap-1.5 min-w-0 flex-1">
														{#if model.loaded}
															<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-green-500" title={$t('settingsModels.model_loaded', 'Loaded')}></span>
														{:else}
															<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-surface-500" title={$t('settingsModels.model_not_loaded', 'Not loaded')}></span>
														{/if}
														<span class="truncate text-surface-200">{model.name}</span>
													</div>
													<div class="flex items-center gap-2 shrink-0 text-surface-500">
														{#if model.params}
															<span>{model.params}</span>
														{/if}
														{#if model.quantization}
															<span class="rounded bg-surface-600 px-1.5 py-0.5">{model.quantization}</span>
														{/if}
														{#if model.max_context_length}
															<span>{$t('settingsModels.context_size', '{size}K ctx', { size: Math.round(model.max_context_length / 1024) })}</span>
														{/if}
														{#if model.supports_tool_calling}
															<span class="rounded bg-blue-500/15 px-1.5 py-0.5 text-blue-400" title={$t('settingsModels.supports_tools', 'Supports tool calling')}>{$t('settingsModels.tools_badge', 'tools')}</span>
														{/if}
														{#if model.supports_vision}
															<span class="rounded bg-purple-500/15 px-1.5 py-0.5 text-purple-400" title={$t('settingsModels.supports_vision', 'Supports vision')}>{$t('settingsModels.vision_badge', 'vision')}</span>
														{/if}
													</div>
												</div>
											{/each}
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Model Selection -->
		<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
			<div class="mb-4 flex items-center justify-between">
				<div>
					<h3 class="mb-1 text-laya-heading font-medium">{$t('settingsModels.model_selection_title', 'Model Selection')}</h3>
					<p class="text-laya-secondary text-surface-500">{$t('settingsModels.model_selection_desc', 'Choose a model for each pipeline stage, or switch the backend to an installed CLI agent.')}</p>
				</div>
				<div class="flex items-center gap-3">
					{#if saving}
						<span class="text-laya-micro text-laya-orange">{$t('settingsModels.saving', 'Saving…')}</span>
					{/if}
				<button
					onclick={() => fetchModels(true)}
					disabled={modelsLoading}
					class="rounded-md border border-surface-600 px-2.5 py-1.5 text-laya-secondary text-surface-400 transition-colors hover:border-surface-500 hover:text-surface-300 disabled:opacity-50"
					title={$t('settingsModels.refresh_models', 'Refresh model list')}
				>
					{#if modelsLoading}
						<svg class="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
							<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
							<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
						</svg>
					{:else}
						{$t('settingsModels.refresh', 'Refresh')}
					{/if}
				</button>
				</div>
			</div>
			<!-- Inference backend: model provider (dropdowns) vs installed agent (typed model strings) -->
			<div class="mb-4 rounded-lg border {$glassTheme ? 'border-white/10' : 'border-surface-700'} p-3">
				<div class="inline-flex rounded-md border {$glassTheme ? 'border-white/15' : 'border-surface-600'} p-0.5">
					<button
						type="button"
						onclick={() => setAgentMode(false)}
						class="rounded px-3 py-1.5 text-laya-base transition-colors {!agentMode ? 'bg-laya-orange/15 text-laya-orange' : 'text-surface-400 hover:text-surface-300'}"
					>{$t('settingsModels.backend_model_provider', 'Model provider')}</button>
					<button
						type="button"
						onclick={() => setAgentMode(true)}
						class="flex items-center gap-1.5 rounded px-3 py-1.5 text-laya-base transition-colors {agentMode ? 'bg-laya-orange/15 text-laya-orange' : 'text-surface-400 hover:text-surface-300'}"
					>{$t('settingsModels.backend_installed_agent', 'Installed agent')}
						<span class="rounded bg-laya-gold/25 px-1 text-laya-micro font-semibold uppercase tracking-wide text-laya-amber">{$t('settingsModels.beta', 'Beta')}</span>
					</button>
				</div>
				<p class="mt-2 text-laya-micro text-surface-500">
					{#if agentMode}
						{$t('settingsModels.backend_agent_desc', 'Structured stages run through an installed CLI agent on its own subscription — no API key or local VRAM. Chat & Coherence keep using a model provider.')}
					{:else}
						{$t('settingsModels.backend_provider_desc', 'Use cloud or local-provider models for every stage.')}
					{/if}
				</p>

				{#if agentMode}
					<div class="mt-3 flex flex-wrap gap-2">
						{#each agentBackends as b}
							<button
								type="button"
								onclick={() => b.available && selectAgent(b.agent_id)}
								disabled={!b.available}
								title={b.hint}
								class="flex items-center gap-2 rounded-md border px-3 py-1.5 text-laya-base transition-colors {selectedAgent === b.agent_id ? 'border-laya-orange/40 bg-laya-orange/10 text-laya-orange' : 'border-surface-600 text-surface-300 hover:border-surface-500'} {!b.available ? 'cursor-not-allowed opacity-50' : ''}"
							>
								{AGENT_LABELS[b.agent_id] || b.agent_id}
								<span class="rounded px-1.5 py-0.5 text-laya-micro {b.tier === 'native' ? 'bg-laya-gold/25 text-laya-amber' : 'bg-surface-700 text-surface-400'}">
									{b.tier === 'native' ? $t('settingsModels.tier_native', 'native schema') : $t('settingsModels.tier_best_effort', 'best-effort')}
								</span>
								{#if !b.available}
									<span class="text-laya-micro text-surface-500">{$t('settingsModels.not_detected', 'not detected')}</span>
								{/if}
							</button>
						{/each}
					</div>
					{#if selectedBackend?.hint}
						<p class="mt-2 text-laya-micro text-surface-500">{selectedBackend.hint}</p>
					{/if}
				{/if}
			</div>

			<div class="space-y-4">
				{#each roles as role}
					<div class="grid grid-cols-[140px_auto_1fr] items-center gap-2">
						<div>
							<label for="{role.id}-model" class="text-laya-base text-surface-400">{role.label}</label>
							<p class="text-laya-micro text-surface-500">{role.hint}</p>
						</div>
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							class="cursor-help"
							onmouseenter={(e) => showGuide(e, role.guide)}
							onmouseleave={hideGuide}
						>
							<svg class="h-3.5 w-3.5 shrink-0 text-surface-600 transition-colors hover:text-laya-orange" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01" />
								<circle cx="12" cy="12" r="10" stroke-width="2" />
							</svg>
						</div>
						{#if agentMode && AGENT_ROLES.includes(role.id)}
							<input
								id="{role.id}-model"
								type="text"
								value={agentModelString(role.id)}
								onchange={handleAgentModelInput(role.id)}
								placeholder={agentModelPlaceholder}
								spellcheck="false"
								autocapitalize="off"
								class="w-full rounded-md border px-3 py-2 font-mono text-laya-base text-surface-100 placeholder:text-surface-500 focus:outline-none {$glassTheme ? 'glass-input' : 'border-surface-600 bg-surface-700 focus:border-surface-500'}"
							/>
						{:else}
							<ModelSelect
								id="{role.id}-model"
								bind:value={models[role.id as keyof typeof models]}
								providers={availableModels}
								onchange={handleModelChange(role.id)}
							/>
						{/if}
					</div>
				{/each}
			</div>
		</div>

		<!-- Agent Usage Limits (shown when an installed agent is the inference backend) -->
		{#if agentMode}
			<div id="agent-usage" class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
				<div class="mb-4">
					<div class="mb-1 flex items-center gap-2">
						<h3 class="text-laya-heading font-medium">{$t('settingsModels.agent_usage_title', 'Agent Usage Limits')}</h3>
						<span class="rounded bg-laya-gold/25 px-1 text-laya-micro font-semibold uppercase tracking-wide text-laya-amber">{$t('settingsModels.beta', 'Beta')}</span>
						{#if savingAgentBudget}<span class="ml-auto text-laya-micro text-laya-orange">{$t('settingsModels.saving', 'Saving…')}</span>{/if}
					</div>
					<p class="text-laya-secondary text-surface-500">{$t('settingsModels.agent_usage_desc', 'Agents bill against usage limits, not dollars. Set a token budget per rolling window — Laya pauses ingestion when reached and auto-resumes when the window resets.')}</p>
				</div>

				{#if agentBudgetStatus?.is_paused}
					<div class="mb-4 flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
						<div class="flex items-center gap-2">
							<svg class="h-4 w-4 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
							<span class="text-laya-base text-red-300">
								{#if agentBudgetStatus.paused_until}
									{$t('settingsModels.usage_limit_paused_until', 'Usage limit reached — ingestion paused until {date}', { date: parseBackendDate(agentBudgetStatus.paused_until)?.toLocaleString($locale) ?? '' })}
								{:else}
									{$t('settingsModels.usage_limit_paused', 'Usage limit reached — ingestion paused')}
								{/if}
							</span>
						</div>
						<button
							onclick={handleResumeAgent}
							disabled={resumingAgentBudget}
							class="rounded-md bg-red-500/20 px-3 py-1.5 text-laya-secondary font-medium text-red-300 transition-colors hover:bg-red-500/30 disabled:opacity-50"
						>
							{resumingAgentBudget ? $t('settingsModels.resuming', 'Resuming…') : $t('settingsModels.resume_now', 'Resume Now')}
						</button>
					</div>
				{/if}

				<div class="space-y-4">
					<div class="flex items-center gap-3">
						<button
							aria-label={$t('settingsModels.toggle_agent_limits', 'Toggle agent usage limits')}
							onclick={() => { agentBudgetEnabled = !agentBudgetEnabled; debounceSaveAgentBudget(); }}
							class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors {agentBudgetEnabled ? 'bg-laya-orange' : 'bg-surface-600'}"
						>
							<span class="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform {agentBudgetEnabled ? 'translate-x-4' : 'translate-x-0.5'}"></span>
						</button>
						<span class="text-laya-base text-surface-300">{$t('settingsModels.enable_agent_limits', 'Enable agent usage limits')}</span>
					</div>

					{#if agentBudgetEnabled}
						{#each agentBackends.filter((b) => b.available) as b}
							{@const c = agentBudgetAgents[b.agent_id]}
							{@const st = agentStatusFor(b.agent_id)}
							{#if c}
								<div class="rounded-lg border border-surface-700 bg-surface-900/50 p-4">
									<div class="mb-2 flex items-center justify-between">
										<span class="text-laya-base text-surface-200">{AGENT_LABELS[b.agent_id] || b.agent_id}</span>
										{#if st?.rate_limit?.status}
											<span class="text-laya-micro text-surface-500">
												{#if st.rate_limit.resets_at}
													{$t('settingsModels.live_limit_resets', 'live limit: {status} · resets {time}', { status: st.rate_limit.status, time: new Date(st.rate_limit.resets_at * 1000).toLocaleTimeString($locale) })}
												{:else}
													{$t('settingsModels.live_limit', 'live limit: {status}', { status: st.rate_limit.status })}
												{/if}
											</span>
										{/if}
									</div>
									<div class="grid grid-cols-3 gap-3">
										<label class="text-laya-micro text-surface-500">
											{$t('settingsModels.token_budget', 'Token budget')}
											<input type="number" min="0" step="100000" placeholder={$t('settingsModels.example_tokens', 'e.g. 5000000')}
												bind:value={c.window_token_limit} oninput={debounceSaveAgentBudget}
												class="mt-1 w-full rounded-md border border-surface-600 bg-surface-700 px-2 py-1.5 text-laya-base text-surface-200 placeholder:text-surface-500" />
										</label>
										<label class="text-laya-micro text-surface-500">
											{$t('settingsModels.window_hours', 'Window (hours)')}
											<input type="number" min="1" step="1"
												bind:value={c.window_hours} oninput={debounceSaveAgentBudget}
												class="mt-1 w-full rounded-md border border-surface-600 bg-surface-700 px-2 py-1.5 text-laya-base text-surface-200" />
										</label>
										<label class="text-laya-micro text-surface-500">
											{$t('settingsModels.pause_at_percent', 'Pause at %')}
											<input type="number" min="1" max="100"
												bind:value={c.pause_at_percent} oninput={debounceSaveAgentBudget}
												class="mt-1 w-full rounded-md border border-surface-600 bg-surface-700 px-2 py-1.5 text-laya-base text-surface-200" />
										</label>
									</div>
									{#if st && st.window_token_limit > 0}
										<div class="mt-3">
											<div class="mb-1 flex justify-between text-laya-micro text-surface-500">
												<span>{$t('settingsModels.tokens_window', '{used} / {limit} tokens · last {hours}h', { used: fmtTokensShort(st.tokens_used), limit: fmtTokensShort(st.window_token_limit), hours: st.window_hours })}</span>
												<span>{st.percent != null ? st.percent.toFixed(0) : 0}%</span>
											</div>
											<div class="h-2 w-full overflow-hidden rounded-full bg-surface-700">
												<div
													class="h-full rounded-full transition-all duration-500 {(st.percent ?? 0) >= 100 ? 'bg-red-500' : (st.percent ?? 0) >= 75 ? 'bg-amber-500' : 'bg-green-500'}"
													style="width: {Math.min(st.percent ?? 0, 100)}%"
												></div>
											</div>
										</div>
									{/if}
								</div>
							{/if}
						{/each}
						<p class="text-laya-micro text-surface-500">{$t('settingsModels.agent_limits_tip', 'Tip: set the token budget to match your plan’s window (e.g. Claude Code’s 5-hour window). Claude Code also reports its live limit above and resumes exactly at its reset.')}</p>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Cost Control -->
		<div id="cost-control" class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
			<div class="mb-4">
				<div class="mb-1 flex items-center justify-between">
					<h3 class="text-laya-heading font-medium">{$t('settingsModels.cost_control_title', 'Cost Control')}</h3>
					{#if savingBudget}
						<span class="text-laya-micro text-laya-orange">{$t('settingsModels.saving', 'Saving…')}</span>
					{/if}
				</div>
				<p class="text-laya-secondary text-surface-500">{$t('settingsModels.cost_control_desc', 'Set a monthly budget to automatically pause workflows when the limit is reached.')}</p>
			</div>

			<!-- Budget paused alert -->
			{#if budgetIsPaused}
				<div class="mb-4 flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
					<div class="flex items-center gap-2">
						<svg class="h-4 w-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
						</svg>
						<span class="text-laya-base text-red-300">
							{pausedWorkflowCount === 1
								? $t('settingsModels.budget_exceeded_one', 'Budget exceeded — {count} workflow paused', { count: pausedWorkflowCount })
								: $t('settingsModels.budget_exceeded_other', 'Budget exceeded — {count} workflows paused', { count: pausedWorkflowCount })}
						</span>
					</div>
					<button
						onclick={handleResume}
						disabled={resumingBudget}
						class="rounded-md bg-red-500/20 px-3 py-1.5 text-laya-secondary font-medium text-red-300 transition-colors hover:bg-red-500/30 disabled:opacity-50"
					>
						{resumingBudget ? $t('settingsModels.resuming', 'Resuming…') : $t('settingsModels.resume_workflows', 'Resume Workflows')}
					</button>
				</div>
			{/if}

			<!-- Enable toggle + limit input -->
			<div class="space-y-4">
				<div class="flex items-center gap-3">
					<button
						aria-label={$t('settingsModels.toggle_budget', 'Toggle monthly budget limit')}
						onclick={() => { budgetEnabled = !budgetEnabled; debounceSaveBudget(); }}
						class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors {budgetEnabled ? 'bg-laya-orange' : 'bg-surface-600'}"
					>
						<span class="inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform {budgetEnabled ? 'translate-x-4' : 'translate-x-0.5'}"></span>
					</button>
					<span class="text-laya-base text-surface-300">{$t('settingsModels.enable_budget', 'Enable monthly budget limit')}</span>
				</div>

				{#if budgetEnabled}
					<div class="grid grid-cols-[200px_1fr] items-center gap-4">
						<div>
							<label for="budget-limit" class="text-laya-base text-surface-300">{$t('settingsModels.monthly_limit', 'Monthly Limit')}</label>
							<p class="text-laya-micro text-surface-500">{$t('settingsModels.monthly_limit_desc', 'Workflows pause when this amount is reached.')}</p>
						</div>
						<div class="flex items-center gap-2">
							<span class="text-laya-base text-surface-400">$</span>
							<input
								id="budget-limit"
								type="number"
								min="0.01"
								step="0.50"
								placeholder={$t('settingsModels.example_amount', 'e.g. 10.00')}
								bind:value={budgetLimitInput}
								oninput={debounceSaveBudget}
								class="w-32 rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-laya-base text-surface-200 placeholder:text-surface-500"
							/>
							<span class="text-laya-secondary text-surface-500">{$t('settingsModels.usd_per_month', 'USD / month')}</span>
						</div>
					</div>

					<!-- Current month progress -->
					<div class="rounded-lg border border-surface-700 bg-surface-900/50 p-4">
						<div class="mb-2 flex items-center justify-between">
							<span class="text-[13px] leading-5 text-surface-400">
								{currentMonth ? formatMonth(currentMonth) : $t('settingsModels.current_month', 'Current Month')}
							</span>
							<span class="text-[13px] leading-5">
								<span class="font-semibold {budgetPercent >= 100 ? 'text-red-400' : budgetPercent >= 75 ? 'text-amber-400' : 'text-green-400'}">
									${currentMonthCost.toFixed(2)}
								</span>
								{#if budgetLimit}
									<span class="text-surface-500"> / ${budgetLimit.toFixed(2)}</span>
								{/if}
							</span>
						</div>
						<!-- Progress bar -->
						{#if budgetLimit}
							<div class="h-2 w-full overflow-hidden rounded-full bg-surface-700">
								<div
									class="h-full rounded-full transition-all duration-500 {budgetBarColor}"
									style="width: {budgetPercent}%"
								></div>
							</div>
							<div class="mt-1.5 text-right text-laya-micro text-surface-500">
								{$t('settingsModels.percent_used', '{percent}% used', { percent: budgetPercent.toFixed(0) })}
							</div>
						{/if}

						<!-- Per-model breakdown: name | tokens | cost. The token column
						     keeps this meaningful on a local-model setup, where every
						     per-model cost is $0. Sort by tokens so the heaviest model
						     leads even when all costs are $0. -->
						{#if Object.keys(budgetByModel).length > 0}
							<div class="mt-3 space-y-1">
								{#each Object.entries(budgetByModel).sort((a, b) => (budgetTokensByModel[b[0]] ?? 0) - (budgetTokensByModel[a[0]] ?? 0)) as [model, cost]}
									<div class="flex items-center gap-3 text-laya-secondary">
										<span class="flex-1 truncate text-surface-400">{model}</span>
										<span class="w-16 shrink-0 text-right tabular-nums text-surface-500">{fmtTokens(budgetTokensByModel[model] ?? 0)}</span>
										<span class="w-20 shrink-0 text-right tabular-nums text-surface-300">${cost.toFixed(4)}</span>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/if}

				<!-- History accordion -->
				<div>
					<button
						onclick={() => { showHistory = !showHistory; if (showHistory) loadHistory(); }}
						class="flex items-center gap-1.5 text-laya-secondary text-surface-400 transition-colors hover:text-surface-300"
					>
						<svg
							class="h-3.5 w-3.5 transition-transform {showHistory ? 'rotate-90' : ''}"
							fill="none" stroke="currentColor" viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
						</svg>
						{$t('settingsModels.monthly_history', 'Monthly History')}
					</button>
					{#if showHistory}
						<div class="mt-2 space-y-1.5">
							{#if historyLoading}
								<p class="text-laya-secondary text-surface-500">{$t('common.loading', 'Loading...')}</p>
							{:else if budgetHistory.length === 0}
								<p class="text-laya-secondary text-surface-500">{$t('settingsModels.no_cost_history', 'No cost history yet. History is recorded at the end of each month.')}</p>
							{:else}
								{#each budgetHistory as entry}
									<div class="flex items-center justify-between rounded-md border border-surface-700 bg-surface-900/30 px-3 py-2">
										<span class="text-laya-secondary text-surface-400">{formatMonth(entry.year_month)}</span>
										<span class="text-laya-secondary font-medium text-surface-200">${entry.total_cost_usd.toFixed(2)}</span>
									</div>
								{/each}
							{/if}
						</div>
					{/if}
				</div>
			</div>
		</div>

		<!-- Advanced Pipeline Settings -->
		<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'}">
			<button
				onclick={() => { showAdvanced = !showAdvanced; }}
				class="flex w-full items-center justify-between p-5 text-left"
			>
				<div>
					<h3 class="text-laya-heading font-medium">{$t('settingsModels.advanced_title', 'Advanced')}</h3>
					<p class="text-laya-secondary text-surface-500">{$t('settingsModels.advanced_desc', 'Model timeout, retry attempts, and request concurrency')}</p>
				</div>
				{#if savingPipeline}
					<span class="text-laya-micro text-laya-orange">{$t('settingsModels.saving', 'Saving…')}</span>
				{/if}
				<svg
					class="h-5 w-5 shrink-0 text-surface-400 transition-transform {showAdvanced ? 'rotate-180' : ''}"
					fill="none" stroke="currentColor" viewBox="0 0 24 24"
				>
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
				</svg>
			</button>

			{#if showAdvanced}
				<div transition:slide={{ duration: $reducedMotion ? 0 : 200 }} class="border-t border-surface-700 p-5 space-y-5">
					<!-- Model Timeout -->
					<div class="grid grid-cols-[200px_1fr_auto] items-center gap-4">
						<div>
							<label for="model-timeout" class="text-laya-base text-surface-300">{$t('settingsModels.model_timeout', 'Model Timeout')}</label>
							<p class="text-laya-micro text-surface-500">{$t('settingsModels.model_timeout_desc', 'Max seconds to wait for an LLM response. Increase for slow local models.')}</p>
						</div>
						<input
							id="model-timeout"
							type="range"
							min="30"
							max="900"
							step="30"
							bind:value={pipeline.model_timeout}
							oninput={debounceSavePipeline}
							class="w-full accent-laya-orange"
						/>
						<div class="flex items-center gap-1.5">
							<input
								type="number"
								min="30"
								max="900"
								bind:value={pipeline.model_timeout}
								oninput={debounceSavePipeline}
								class="w-16 rounded-md border border-surface-600 bg-surface-700 px-2 py-1 text-center text-laya-base text-surface-200"
							/>
							<span class="text-laya-secondary text-surface-500">{$t('settingsModels.unit_sec', 'sec')}</span>
						</div>
					</div>

					<!-- LLM Retries (per call) -->
					<div class="grid grid-cols-[200px_1fr_auto] items-center gap-4">
						<div>
							<label for="llm-retries" class="text-laya-base text-surface-300">{$t('settingsModels.llm_retries', 'LLM Retries')}</label>
							<p class="text-laya-micro text-surface-500">{$t('settingsModels.llm_retries_desc', 'Retries per LLM call on timeout or transient error (fast, seconds apart).')}</p>
						</div>
						<input
							id="llm-retries"
							type="range"
							min="1"
							max="5"
							step="1"
							bind:value={pipeline.llm_retries}
							oninput={debounceSavePipeline}
							class="w-full accent-laya-orange"
						/>
						<div class="flex items-center gap-1.5">
							<input
								type="number"
								min="1"
								max="5"
								bind:value={pipeline.llm_retries}
								oninput={debounceSavePipeline}
								class="w-16 rounded-md border border-surface-600 bg-surface-700 px-2 py-1 text-center text-laya-base text-surface-200"
							/>
							<span class="text-laya-secondary text-surface-500">{$t('settingsModels.unit_tries', 'tries')}</span>
						</div>
					</div>

					<!-- Event Queue Retries -->
					<div class="grid grid-cols-[200px_1fr_auto] items-center gap-4">
						<div>
							<label for="max-retries" class="text-laya-base text-surface-300">{$t('settingsModels.queue_retries', 'Event Queue Retries')}</label>
							<p class="text-laya-micro text-surface-500">{$t('settingsModels.queue_retries_desc', 'Times a failed event is re-queued with exponential backoff (slow, minutes apart).')}</p>
						</div>
						<input
							id="max-retries"
							type="range"
							min="1"
							max="10"
							step="1"
							bind:value={pipeline.max_retry_attempts}
							oninput={debounceSavePipeline}
							class="w-full accent-laya-orange"
						/>
						<div class="flex items-center gap-1.5">
							<input
								type="number"
								min="1"
								max="10"
								bind:value={pipeline.max_retry_attempts}
								oninput={debounceSavePipeline}
								class="w-16 rounded-md border border-surface-600 bg-surface-700 px-2 py-1 text-center text-laya-base text-surface-200"
							/>
							<span class="text-laya-secondary text-surface-500">{$t('settingsModels.unit_tries', 'tries')}</span>
						</div>
					</div>

					<!-- Request Concurrency -->
					<div class="grid grid-cols-[200px_1fr_auto] items-center gap-4">
						<div>
							<label for="max-concurrent" class="text-laya-base text-surface-300">{$t('settingsModels.concurrency', 'Request Concurrency')}</label>
							<p class="text-laya-micro text-surface-500">{$t('settingsModels.concurrency_desc', 'Max events processed in parallel. Lower for local GPU models.')}</p>
						</div>
						<input
							id="max-concurrent"
							type="range"
							min="1"
							max="20"
							step="1"
							bind:value={pipeline.max_concurrent_events}
							oninput={debounceSavePipeline}
							class="w-full accent-laya-orange"
						/>
						<div class="flex items-center gap-1.5">
							<input
								type="number"
								min="1"
								max="20"
								bind:value={pipeline.max_concurrent_events}
								oninput={debounceSavePipeline}
								class="w-16 rounded-md border border-surface-600 bg-surface-700 px-2 py-1 text-center text-laya-base text-surface-200"
							/>
							<span class="text-laya-secondary text-surface-500">{$t('settingsModels.unit_events', 'events')}</span>
						</div>
					</div>

				</div>
			{/if}
		</div>
	</div>

	{#if guideTooltip}
		<div
			use:portal
			class="pointer-events-none fixed z-[100] w-64 -translate-x-1/2 rounded-lg border border-transparent glass-tooltip px-3 py-2.5 text-laya-secondary leading-relaxed shadow-lg"
			style="top: {guideTooltip.top}px; left: {guideTooltip.left}px;"
		>
			{guideTooltip.text}
		</div>
	{/if}
{/if}
