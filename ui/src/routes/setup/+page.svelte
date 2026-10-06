<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { invoke } from '@tauri-apps/api/core';
	import { engineApi } from '$lib/api/engine';
	import type { CustomProvider, DiscoveredModel } from '$lib/api/types';
	import { CODING_AGENTS } from '$lib/config';
	import { t } from '$lib/i18n';

	interface RepoDetection {
		path: string;
		name: string;
		platform: string;
		remote_id: string;
	}

	$effect(() => {
		if (step === 3 && n8nStatus === 'checking') {
			checkN8n();
		}
	});

	let step = $state(1);
	const totalSteps = 6;

	// Step 1: API Key
	let provider = $state('anthropic');
	let apiKey = $state('');
	let keyStatus = $state('');
	let savedKeys = $state<Array<{ provider: string; label: string }>>([]);
	let useSelfHosted = $state(false);

	const providerLabels: Record<string, string> = {
		anthropic: 'Anthropic (Claude)',
		openai: 'OpenAI',
		google: 'Google (Gemini)',
		ollama: 'Ollama (Local Servidor)'
	};

	// Provider-to-model defaults: small model for router, large model for stager/chat/trace
	const providerModelDefaults: Record<string, Record<string, string>> = {
		anthropic: { router: 'claude-haiku-4-5', stager: 'claude-sonnet-4-6', chat: 'claude-sonnet-4-6', trace: 'claude-sonnet-4-6', omni: 'claude-sonnet-4-6' },
		openai: { router: 'gpt-4o-mini', stager: 'gpt-4o', chat: 'gpt-4o', trace: 'gpt-4o', omni: 'gpt-4o' },
		google: { router: 'gemini-2.0-flash', stager: 'gemini-2.5-pro', chat: 'gemini-2.5-pro', trace: 'gemini-2.5-pro', omni: 'gemini-2.5-pro' }
	};

	// Step 2: Model defaults
	let defaultProvider = $state('');
	let settingDefaults = $state(false);

	// Self-hosted provider config (step 2)
	let selfHostedProviderType = $state('lmstudio');
	let selfHostedName = $state('');
	let selfHostedUrl = $state('http://localhost:1234');
	let selfHostedApiKey = $state('');
	let addingSelfHosted = $state(false);
	let selfHostedError = $state('');
	let selfHostedProvider = $state<CustomProvider | null>(null);
	let selfHostedEditing = $state(false);
	let selfHostedTesting = $state(false);
	let selfHostedTestOk = $state<boolean | null>(null);
	let selfHostedModels = $state<DiscoveredModel[]>([]);
	let selfHostedModelsLoading = $state(false);
	let selfHostedModelSelections = $state<Record<string, string>>({ router: '', stager: '', chat: '', trace: '', omni: '' });

	const selfHostedProviderTypes = [
		{ id: 'lmstudio', label: 'LM Studio', defaultUrl: 'http://localhost:1234' },
		{ id: 'ollama', label: 'Ollama', defaultUrl: 'http://localhost:11434' },
		{ id: 'openai_compatible', label: 'OpenAI Compatible', defaultUrl: 'http://localhost:8080' }
	];

	const roles = $derived([
		{ id: 'router', label: $t('settingsModels.role_router', 'Router'), hint: $t('setupLegal.role_router_hint', 'Classifies incoming events (use a fast/cheap model)') },
		{ id: 'stager', label: $t('settingsModels.role_stager', 'Stager'), hint: $t('setupLegal.role_stager_hint', 'Synthesises action cards (use a capable model)') },
		{ id: 'chat', label: $t('common.chat', 'Chat'), hint: $t('setupLegal.role_chat_hint', 'Conversational responses') },
		{ id: 'trace', label: $t('nav.coherence', 'Coherence'), hint: $t('setupLegal.role_trace_hint', 'Generates trace narratives') },
		{ id: 'omni', label: 'Omni', hint: $t('setupLegal.role_omni_hint', 'Resynthesises rolling summaries') }
	]);

	function providerDisplayLabel(key: { provider: string; label: string }): string {
		return key.provider === 'ollama' ? $t('setup.ollama_option', 'Ollama (Local Server)') : key.label;
	}

	// Derived: whether step 2 needs to show provider picker
	const needsProviderChoice = $derived(
		(savedKeys.length > 1 && !useSelfHosted) ||
		(savedKeys.length >= 1 && useSelfHosted)
	);
	const singleCloudProvider = $derived(savedKeys.length === 1 && !useSelfHosted);
	const selfHostedOnly = $derived(savedKeys.length === 0 && useSelfHosted);

	// Whether self-hosted is fully configured (provider added + all roles selected)
	const selfHostedConfigured = $derived(
		selfHostedProvider !== null &&
		selfHostedModelSelections.router !== '' &&
		selfHostedModelSelections.stager !== '' &&
		selfHostedModelSelections.chat !== '' &&
		selfHostedModelSelections.trace !== '' &&
		selfHostedModelSelections.omni !== ''
	);

	// Whether step 2 can proceed
	const step2CanProceed = $derived(() => {
		if (selfHostedOnly) {
			return selfHostedConfigured;
		}
		if (needsProviderChoice) {
			if (defaultProvider === 'self-hosted') {
				return selfHostedConfigured;
			}
			return defaultProvider !== '';
		}
		// Single cloud provider — auto-set, always can proceed
		return true;
	});

	// Step 4: Coding Agent + Repo
	let codingAgent = $state('claude_code');
	let repoName = $state('');
	let repoPath = $state('');
	let repoPlatform = $state('');
	let repoRemoteId = $state('');
	let repoBrowseStatus = $state<{ ok: boolean; msg: string } | null>(null);
	let browsing = $state(false);
	let savedRepos = $state<Array<{ name: string; path: string; platform: string; remote_id: string }>>([]);
	let showManualRepo = $state(false);

	// Step 5: Team
	let members = $state<Array<{ name: string; email: string; role: 'self' | 'manager' | 'teammate' | 'external' | 'bot' }>>([
		{ name: '', email: '', role: 'teammate' }
	]);

	// Step 3: n8n
	let n8nStatus = $state<'checking' | 'running' | 'not_running' | 'configured'>('checking');
	let bootstrapping = $state(false);
	let bootstrapMessage = $state('');

	// Step 6: Filters
	let ignoreBots = $state(true);
	let muteRandom = $state(false);

	async function saveApiKey() {
		if (provider === 'ollama') {
			useSelfHosted = true;
			selfHostedProviderType = 'ollama';
			selfHostedName = 'Ollama Local';
			selfHostedUrl = 'http://localhost:11434';
			await addSelfHostedProvider();
			savedKeys = [...savedKeys.filter((k) => k.provider !== 'ollama'), { provider: 'ollama', label: 'Ollama (Local Servidor)' }];
			keyStatus = 'saved';
			return;
		}

		if (!apiKey.trim()) return;
		try {
			await engineApi.setApiKey(provider, apiKey.trim());
			savedKeys = [...savedKeys.filter((k) => k.provider !== provider), { provider, label: providerLabels[provider] || provider }];
			apiKey = '';
			keyStatus = '';
		} catch {
			keyStatus = 'error';
		}
	}

	async function applyModelDefaults(providerKey: string) {
		const defaults = providerModelDefaults[providerKey];
		if (!defaults) return;
		settingDefaults = true;
		try {
			await engineApi.updateSettings({ models: defaults } as any);
		} catch (e) {
			console.error('Failed to set model defaults:', e);
		} finally {
			settingDefaults = false;
		}
	}

	async function applySelfHostedModels() {
		settingDefaults = true;
		try {
			await engineApi.updateSettings({
				models: {
					router: selfHostedModelSelections.router,
					stager: selfHostedModelSelections.stager,
					chat: selfHostedModelSelections.chat,
					trace: selfHostedModelSelections.trace,
					omni: selfHostedModelSelections.omni
				}
			} as any);
		} catch (e) {
			console.error('Failed to set self-hosted model defaults:', e);
		} finally {
			settingDefaults = false;
		}
	}

	function handleSelfHostedTypeChange(type: string) {
		selfHostedProviderType = type;
		const preset = selfHostedProviderTypes.find(p => p.id === type);
		if (preset) {
			selfHostedUrl = preset.defaultUrl;
		}
	}

	async function addSelfHostedProvider() {
		if (!selfHostedName.trim() || !selfHostedUrl.trim()) return;
		addingSelfHosted = true;
		selfHostedError = '';
		try {
			const payload = {
				name: selfHostedName.trim(),
				base_url: selfHostedUrl.trim(),
				provider_type: selfHostedProviderType,
				api_key: selfHostedApiKey.trim() || undefined
			};
			// Editing an existing provider (e.g. correcting a wrong URL): update in place
			// so we don't orphan the bad record that was created on the first attempt.
			const resp = selfHostedProvider
				? await engineApi.updateCustomProvider(selfHostedProvider.id, payload)
				: await engineApi.addCustomProvider(payload);
			selfHostedProvider = resp.provider;
			selfHostedEditing = false;
			// Reset prior test/model state before re-testing the (possibly new) URL
			selfHostedTestOk = null;
			selfHostedModels = [];
			// Auto-test and discover models
			await testAndDiscoverModels(resp.provider.id);
		} catch (e: any) {
			selfHostedError = e.message || $t('setupLegal.add_provider_failed', 'Failed to add provider');
		} finally {
			addingSelfHosted = false;
		}
	}

	function editSelfHostedProvider() {
		// Re-show the form (pre-filled from retained state) so the user can fix the URL.
		selfHostedEditing = true;
		selfHostedError = '';
	}

	function cancelEditSelfHosted() {
		selfHostedEditing = false;
		selfHostedError = '';
	}

	async function testAndDiscoverModels(providerId: string) {
		selfHostedTesting = true;
		selfHostedTestOk = null;
		try {
			const result = await engineApi.testCustomProvider(providerId);
			selfHostedTestOk = result.reachable;
			if (result.reachable) {
				selfHostedModelsLoading = true;
				const modelsResp = await engineApi.getProviderModels(providerId);
				selfHostedModels = modelsResp.models.filter(m => m.type === 'llm');
				selfHostedModelsLoading = false;
			}
		} catch (e) {
			selfHostedTestOk = false;
			console.error('Failed to test provider:', e);
		} finally {
			selfHostedTesting = false;
		}
	}

	async function goToStep2() {
		// If single cloud provider and no self-hosted, auto-set defaults and skip to step 3
		if (singleCloudProvider) {
			await applyModelDefaults(savedKeys[0].provider);
			step = 3;
			return;
		}
		// If no keys and no self-hosted, skip model config entirely
		if (savedKeys.length === 0 && !useSelfHosted) {
			step = 3;
			return;
		}
		// Pre-select default provider if only one cloud key (with self-hosted also available)
		if (savedKeys.length === 1 && useSelfHosted) {
			defaultProvider = '';
		} else if (savedKeys.length > 1) {
			defaultProvider = '';
		}
		step = 2;
	}

	async function finishStep2() {
		if (selfHostedOnly || defaultProvider === 'self-hosted') {
			await applySelfHostedModels();
		} else if (defaultProvider) {
			await applyModelDefaults(defaultProvider);
		}
		step = 3;
	}

	async function checkN8n() {
		n8nStatus = 'checking';
		try {
			const result = await engineApi.testN8nConnection();
			if (result.health === 'healthy') {
				const settings = await engineApi.getSettings();
				n8nStatus = settings.api_keys?.n8n ? 'configured' : 'running';
				if (n8nStatus === 'running') {
					await doBootstrap();
				}
			} else {
				n8nStatus = 'not_running';
			}
		} catch {
			n8nStatus = 'not_running';
		}
	}

	async function doBootstrap() {
		bootstrapping = true;
		bootstrapMessage = '';
		try {
			const result = await engineApi.bootstrapN8n();
			bootstrapMessage = result.message;
			n8nStatus = result.has_api_key ? 'configured' : 'running';
		} catch {
			bootstrapMessage = $t('setupLegal.n8n_bootstrap_failed', 'Failed to auto-configure n8n');
		} finally {
			bootstrapping = false;
		}
	}

	async function browseRepo() {
		browsing = true;
		repoBrowseStatus = null;
		try {
			const result = await invoke<RepoDetection>('pick_repo_folder');
			savedRepos = [...savedRepos, {
				name: result.name,
				path: result.path,
				platform: result.platform || 'github',
				remote_id: result.remote_id
			}];
		} catch (err: unknown) {
			const msg = String(err);
			if (!msg.includes('cancelled')) {
				repoBrowseStatus = { ok: false, msg: msg.replace(/^Error: /, '') };
			}
		} finally {
			browsing = false;
		}
	}

	function addRepo() {
		if (!repoName.trim() || !repoPath.trim()) return;
		savedRepos = [...savedRepos, {
			name: repoName.trim(),
			path: repoPath.trim(),
			platform: repoPlatform || 'github',
			remote_id: repoRemoteId
		}];
		repoName = '';
		repoPath = '';
		repoPlatform = '';
		repoRemoteId = '';
		repoBrowseStatus = null;
	}

	function removeRepo(index: number) {
		savedRepos = savedRepos.filter((_, i) => i !== index);
	}

	function addMember() {
		members = [...members, { name: '', email: '', role: 'teammate' }];
	}

	function removeMember(index: number) {
		members = members.filter((_, i) => i !== index);
	}

	async function finish() {
		// Step 4: Save agent + repos
		await engineApi.updateSettings({ coding_agent: codingAgent });
		const allRepos = [...savedRepos];
		if (repoName.trim() && repoPath.trim()) {
			allRepos.push({ name: repoName.trim(), path: repoPath.trim(), platform: repoPlatform || 'github', remote_id: repoRemoteId });
		}
		if (allRepos.length > 0) {
			await engineApi.updateRepos({ repos: allRepos });
		}

		// Step 5: Save team
		const validMembers = members.filter((m) => m.name.trim() && m.email.trim());
		if (validMembers.length > 0) {
			await engineApi.updateTeam({
				members: validMembers.map((m) => ({
					name: m.name.trim(),
					email: m.email.trim(),
					role: m.role,
					notes: '',
					aliases: [],
					accounts: []
				}))
			});
		}

		// Step 6: Save filter rules
		const rules: Array<import('$lib/api/types').Rule> = [];
		if (ignoreBots) {
			rules.push({
				name: 'Ignore bot messages',
				enabled: true,
				condition: { field: 'actor.email', operator: 'contains', value: 'bot' },
				action: 'drop'
			});
		}
		if (muteRandom) {
			rules.push({
				name: 'Mute #random',
				enabled: true,
				condition: {
					all: [
						{ field: 'source.platform', operator: 'equals', value: 'slack' },
						{
							field: 'content.metadata.slack_channel',
							operator: 'equals',
							value: 'random'
						}
					]
				},
				action: 'drop'
			});
		}
		if (rules.length > 0) {
			await engineApi.updateRules({ rules });
		}

		await engineApi.updateSettings({ setup_complete: true });
		goto('/');
	}

	function handleNext() {
		if (step === 1) {
			goToStep2();
		} else if (step === 2) {
			finishStep2();
		} else {
			step += 1;
		}
	}
</script>

<div class="max-h-[calc(100vh-4rem)] overflow-y-auto space-y-6 rounded-xl border border-surface-700 bg-surface-800 p-8">
	<!-- Step indicator -->
	<div class="flex items-center justify-center gap-2">
		{#each Array(totalSteps) as _, i}
			<div
				class="h-2 w-8 rounded-full transition-colors
					{i + 1 <= step ? 'bg-primary-500' : 'bg-surface-600'}"
			></div>
		{/each}
	</div>

	<!-- Step 1: Welcome + API Key -->
	{#if step === 1}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setup.welcome', 'Welcome to Laya')}</h2>
			<p class="text-sm text-surface-400">
				{$t('setupLegal.intro', "Let's get you set up. First, add an API key for your LLM provider.")}
			</p>

			<!-- Saved keys -->
			{#if savedKeys.length > 0}
				<div class="space-y-1.5">
					{#each savedKeys as key}
						<div class="flex items-center gap-2 rounded-md border border-green-500/20 bg-green-500/5 px-3 py-2">
							<span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>
							<span class="text-sm text-surface-200">{providerDisplayLabel(key)}</span>
							<span class="text-xs text-green-400">{$t('setupLegal.saved', 'saved')}</span>
						</div>
					{/each}
				</div>
			{/if}

			<div class="space-y-3">
				<label class="block text-sm font-medium">
					{$t('setup.provider', 'AI Provider')}
					<select
						class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
						bind:value={provider}
					>
						<option value="anthropic">Anthropic (Claude)</option>
						<option value="openai">OpenAI</option>
						<option value="google">Google (Gemini)</option>
						<option value="ollama">{$t('setup.ollama_option', 'Ollama (Local Server)')}</option>
					</select>
				</label>

				{#if provider === 'ollama'}
					<div class="rounded-lg border border-laya-orange/30 bg-laya-orange/10 p-3 space-y-2 text-xs">
						<div class="font-semibold text-laya-orange flex items-center gap-2">
							<span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
							{$t('setupLegal.ollama_server_title', 'Ollama Local Server ({url})', { url: 'http://localhost:11434' })}
						</div>
						<div class="text-surface-300">
							{$t('setupLegal.ollama_inline_desc', 'Connects directly to your local Ollama to list and select which installed model you want to use (e.g. llama3.2, deepseek-coder-v2). No paid API key is required.')}
						</div>
					</div>

					<button
						class="rounded-md bg-laya-orange px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-laya-orange/90 disabled:opacity-50 flex items-center gap-2"
						onclick={saveApiKey}
						disabled={addingSelfHosted}
					>
						{#if addingSelfHosted}
							<span class="animate-spin h-3.5 w-3.5 border-2 border-white border-t-transparent rounded-full"></span>
							{$t('setupLegal.connecting_ollama', 'Connecting to Ollama...')}
						{:else}
							{$t('setup.connect_ollama', 'Connect Ollama & Discover Models')}
						{/if}
					</button>
				{:else}
					<label class="block text-sm font-medium">
						{$t('setup.api_key', 'API Key')}
						<input
							type="password"
							class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
							placeholder="sk-..."
							bind:value={apiKey}
						/>
					</label>

					<button
						class="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50"
						onclick={saveApiKey}
						disabled={!apiKey.trim()}
					>
						{$t('setup.save_key', 'Save Key')}
					</button>
				{/if}

				{#if keyStatus === 'error'}
					<p class="text-sm text-red-400">{$t('setupLegal.key_error', 'Failed to save key / connect provider')}</p>
				{/if}
			</div>

			<!-- Self-hosted toggle -->
			<div class="border-t border-surface-700 pt-4">
				<label class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors
					{useSelfHosted
					? 'border-laya-orange bg-laya-orange/10'
					: 'border-surface-600 bg-surface-800 hover:border-surface-500'}">
					<input type="checkbox" class="accent-laya-orange" bind:checked={useSelfHosted} />
					<div>
						<div class="text-sm font-medium">{$t('setup.self_hosted_checkbox', 'I want to use a self-hosted model')}</div>
						<div class="text-xs text-surface-400">{$t('setup.self_hosted_desc', 'Configure a local provider like Ollama, LM Studio, or any OpenAI-compatible server')}</div>
					</div>
				</label>
			</div>
		</div>

	<!-- Step 2: Configure Default Models -->
	{:else if step === 2}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setupLegal.models_title', 'Configure Default Models')}</h2>

			<!-- Provider choice (when multiple options exist) -->
			{#if needsProviderChoice}
				<p class="text-sm text-surface-400">
					{$t('setupLegal.multiple_providers', "You have multiple providers available. Choose which one to use as the default for Laya's pipeline.")}
				</p>

				<div class="space-y-2">
					{#each savedKeys as key}
						<label
							class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors
								{defaultProvider === key.provider
								? 'border-laya-orange bg-laya-orange/10'
								: 'border-surface-600 bg-surface-800 hover:border-surface-500'}"
						>
							<input type="radio" bind:group={defaultProvider} value={key.provider} class="accent-laya-orange" />
							<div>
								<div class="text-sm font-medium">{providerDisplayLabel(key)}</div>
								<div class="text-xs text-surface-400">
									{#if providerModelDefaults[key.provider]}
										{$t('setupLegal.provider_defaults', 'Router: {router} / Others: {others}', { router: providerModelDefaults[key.provider].router, others: providerModelDefaults[key.provider].stager })}
									{/if}
								</div>
							</div>
						</label>
					{/each}

					{#if useSelfHosted}
						<label
							class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors
								{defaultProvider === 'self-hosted'
								? 'border-laya-orange bg-laya-orange/10'
								: 'border-surface-600 bg-surface-800 hover:border-surface-500'}"
						>
							<input type="radio" bind:group={defaultProvider} value="self-hosted" class="accent-laya-orange" />
							<div>
								<div class="text-sm font-medium">{$t('setupLegal.self_hosted_model', 'Self-hosted model')}</div>
								<div class="text-xs text-surface-400">{$t('setupLegal.self_hosted_model_desc', 'Use a locally running model server')}</div>
							</div>
						</label>
					{/if}
				</div>
			{:else if selfHostedOnly}
				<p class="text-sm text-surface-400">
					{$t('setupLegal.self_hosted_only_intro', 'Set up your self-hosted model provider and select models for each pipeline role.')}
				</p>
			{/if}

			<!-- Self-hosted provider setup (shown when self-hosted is the choice) -->
			{#if selfHostedOnly || defaultProvider === 'self-hosted'}
				<div class="space-y-4 rounded-lg border border-surface-600 bg-surface-900/50 p-4">
					{#if !selfHostedProvider || selfHostedEditing}
						<h3 class="text-sm font-semibold text-surface-200">
							{selfHostedProvider ? $t('setupLegal.edit_local_provider', 'Edit Local Provider') : $t('setupLegal.add_local_provider', 'Add Local Provider')}
						</h3>

						<div class="space-y-3">
							<label class="block text-sm font-medium">
								{$t('setupLegal.provider_type', 'Provider Type')}
								<select
									class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
									value={selfHostedProviderType}
									onchange={(e) => handleSelfHostedTypeChange((e.target as HTMLSelectElement).value)}
								>
									{#each selfHostedProviderTypes as pt}
										<option value={pt.id}>{pt.id === 'openai_compatible' ? $t('setupLegal.provider_type_openai_compatible', pt.label) : pt.label}</option>
									{/each}
								</select>
							</label>

							<label class="block text-sm font-medium">
								{$t('setupLegal.name', 'Name')}
								<input
									type="text"
									class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
									placeholder={$t('setupLegal.name_placeholder', 'My Local Server')}
									bind:value={selfHostedName}
								/>
							</label>

							<label class="block text-sm font-medium">
								{$t('setupLegal.base_url', 'Base URL')}
								<input
									type="text"
									class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
									bind:value={selfHostedUrl}
								/>
							</label>

							<label class="block text-sm font-medium">
								{$t('setup.api_key', 'API Key')} <span class="text-xs text-surface-500">{$t('setupLegal.optional', '(optional)')}</span>
								<input
									type="password"
									class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
									placeholder={$t('setupLegal.api_key_placeholder', 'Leave blank if not required')}
									bind:value={selfHostedApiKey}
								/>
							</label>

							<div class="flex items-center gap-3">
								<button
									class="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50"
									onclick={addSelfHostedProvider}
									disabled={!selfHostedName.trim() || !selfHostedUrl.trim() || addingSelfHosted}
								>
									{#if addingSelfHosted}
										{selfHostedProvider ? $t('setupLegal.updating', 'Updating...') : $t('setupLegal.adding', 'Adding...')}
									{:else}
										{selfHostedProvider ? $t('setupLegal.update_discover', 'Update & Discover Models') : $t('setupLegal.add_discover', 'Add & Discover Models')}
									{/if}
								</button>
								{#if selfHostedProvider}
									<button
										class="text-xs text-surface-400 hover:text-surface-200"
										onclick={cancelEditSelfHosted}
									>
										{$t('common.cancel', 'Cancel')}
									</button>
								{/if}
							</div>

							{#if selfHostedError}
								<p class="text-sm text-red-400">{selfHostedError}</p>
							{/if}
						</div>
					{:else}
						<!-- Provider added — show status and model selection -->
						<div class="flex items-center gap-3">
							<span class="h-2.5 w-2.5 rounded-full {selfHostedTestOk ? 'bg-green-500' : selfHostedTestOk === false ? 'bg-red-500' : 'bg-surface-500 animate-pulse'}"></span>
							<div>
								<span class="text-sm font-medium">{selfHostedProvider.name}</span>
								<span class="ml-2 text-xs text-surface-400">{selfHostedProvider.base_url}</span>
							</div>
							{#if selfHostedTesting}
								<span class="text-xs text-surface-400">{$t('setupLegal.testing', 'Testing...')}</span>
							{:else}
								<div class="ml-auto flex items-center gap-3">
									{#if selfHostedTestOk === false}
										<button
											class="text-xs text-primary-400 hover:text-primary-300"
											onclick={() => selfHostedProvider && testAndDiscoverModels(selfHostedProvider.id)}
										>
											{$t('common.retry', 'Retry')}
										</button>
									{/if}
									<button
										class="text-xs text-surface-400 hover:text-surface-200"
										onclick={editSelfHostedProvider}
									>
										{$t('setupLegal.change_url', 'Change URL')}
									</button>
								</div>
							{/if}
						</div>

						{#if selfHostedTestOk === false}
							<p class="text-sm text-red-400">
								{$t('setupLegal.connect_failed', 'Could not connect to provider. Check the Base URL is correct and the server is running, then use "{changeUrl}" to fix it or "{retry}".', { changeUrl: $t('setupLegal.change_url', 'Change URL'), retry: $t('common.retry', 'Retry') })}
							</p>
						{/if}

						{#if selfHostedModelsLoading}
							<p class="text-sm text-surface-400">{$t('setupLegal.discovering_models', 'Discovering models from Ollama...')}</p>
						{:else if selfHostedModels.length > 0}
							<div class="pt-2 space-y-3">
								<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-surface-950 p-3 rounded-lg border border-laya-orange/30">
									<span class="text-xs font-semibold text-laya-orange">{$t('setup.quick_picker', 'Quick Model Picker (Apply model to all roles):')}</span>
									<select
										class="rounded-md border border-surface-600 bg-surface-800 px-2.5 py-1 text-xs text-surface-200"
										onchange={(e) => {
											const selected = (e.target as HTMLSelectElement).value;
											if (selected) {
												selfHostedModelSelections = {
													router: selected,
													stager: selected,
													chat: selected,
													trace: selected,
													omni: selected
												};
											}
										}}
									>
										<option value="">{$t('setupLegal.select_ollama_model', 'Select an Ollama model...')}</option>
										{#each selfHostedModels as model}
											<option value={model.id}>{model.name} {model.params ? `(${model.params})` : ''}</option>
										{/each}
									</select>
								</div>

								<h3 class="text-sm font-semibold text-surface-200 pt-1">{$t('setup.select_role_models', 'Select models for each pipeline role')}</h3>
							</div>

							<div class="space-y-3">
								{#each roles as role}
									<label class="block text-sm font-medium">
										{role.label}
										<span class="text-xs font-normal text-surface-400 ml-1">— {role.hint}</span>
										<select
											class="mt-1 block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
											bind:value={selfHostedModelSelections[role.id]}
										>
											<option value="">{$t('setupLegal.select_model', 'Select a model...')}</option>
											{#each selfHostedModels as model}
												<option value={model.id}>{model.name}{model.params ? ` (${model.params})` : ''}{model.quantization ? ` [${model.quantization}]` : ''}</option>
											{/each}
										</select>
									</label>
								{/each}
							</div>
						{:else if selfHostedTestOk}
							<p class="text-sm text-yellow-400">{$t('setupLegal.no_models', 'No LLM models found on this provider. Make sure you have models loaded.')}</p>
						{/if}
					{/if}
				</div>
			{/if}

			<!-- Single cloud provider confirmation -->
			{#if !needsProviderChoice && !selfHostedOnly && savedKeys.length === 1}
				{@const [beforeProvider, afterProvider = ''] = $t('setupLegal.setting_defaults', 'Setting up defaults for {provider}...').split('{provider}')}
				<p class="text-sm text-surface-400">
					{beforeProvider}<strong class="text-surface-200">{providerDisplayLabel(savedKeys[0])}</strong>{afterProvider}
				</p>
			{/if}
		</div>

	<!-- Step 3: Connect Tools -->
	{:else if step === 3}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setupLegal.tools_title', 'Connect Tools')}</h2>
			<p class="text-sm text-surface-400">
				{$t('setupLegal.tools_intro', "Laya uses n8n to connect to your tools (Jira, Slack, GitHub, etc.). Let's make sure it's ready.")}
			</p>

			<div class="rounded-md border border-surface-600 bg-surface-700 p-4">
				<div class="flex items-center gap-3">
					<span
						class="h-3 w-3 rounded-full
							{n8nStatus === 'configured'
							? 'bg-green-500'
							: n8nStatus === 'running'
								? 'bg-yellow-500'
								: n8nStatus === 'not_running'
									? 'bg-red-500'
									: 'bg-surface-500 animate-pulse'}"
					></span>
					<span class="text-sm font-medium">
						{#if n8nStatus === 'configured'}
							{$t('setupLegal.n8n_configured', 'n8n is connected and ready')}
						{:else if n8nStatus === 'running'}
							{$t('setupLegal.n8n_running', 'n8n is running')}
						{:else if n8nStatus === 'not_running'}
							{$t('setupLegal.n8n_not_running', 'n8n is not running')}
						{:else}
							{$t('setupLegal.n8n_checking', 'Checking n8n...')}
						{/if}
					</span>
				</div>

				{#if bootstrapMessage}
					<p
						class="mt-2 text-sm
							{n8nStatus === 'configured' ? 'text-green-400' : 'text-yellow-400'}"
					>
						{bootstrapMessage}
					</p>
				{/if}

				{#if n8nStatus === 'not_running'}
					<p class="mt-3 text-sm text-surface-400">
						{$t('setupLegal.n8n_autostart', 'n8n will start automatically when the app launches. Click retry to check again.')}
					</p>
					<button
						onclick={checkN8n}
						class="mt-2 rounded-md bg-surface-600 px-4 py-2 text-sm font-medium transition-colors hover:bg-surface-500"
					>
						{$t('common.retry', 'Retry')}
					</button>
				{:else if n8nStatus === 'running' && !bootstrapping}
					<button
						onclick={doBootstrap}
						class="mt-3 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500"
					>
						{$t('setupLegal.auto_configure', 'Auto-configure')}
					</button>
				{:else if bootstrapping}
					<p class="mt-3 text-sm text-surface-400">{$t('setupLegal.n8n_setting_up', 'Setting up n8n...')}</p>
				{/if}
			</div>

			<p class="text-xs text-surface-500">
				{$t('setupLegal.tools_skip', 'You can skip this and configure integrations later in Settings.')}
			</p>
		</div>

	<!-- Step 4: Coding Agent + Repo -->
	{:else if step === 4}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setupLegal.agent_title', 'Coding Agent (optional)')}</h2>
			<p class="text-sm text-surface-400">{$t('setupLegal.agent_intro', "Choose a coding agent for automated code tasks, or skip if you don't need one.")}</p>

			<div class="space-y-2">
				{#each CODING_AGENTS as option}
					<label
						class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors
							{codingAgent === option.value
							? 'border-laya-orange bg-laya-orange/10'
							: 'border-surface-600 bg-surface-800 hover:border-surface-500'}"
					>
						<input type="radio" bind:group={codingAgent} value={option.value} class="accent-laya-orange" />
						<div>
							<div class="text-sm font-medium">{option.value === 'none' ? $t('settingsRules.agent_label_none', option.label) : option.label}</div>
							<div class="text-xs text-surface-400">{$t(`settingsRules.agent_desc_${option.value}`, option.description)}</div>
						</div>
					</label>
				{/each}
			</div>

			<div class="space-y-3 pt-2">
				<p class="text-sm font-medium">{$t('setupLegal.repos_title', 'Repositories (optional)')}</p>

				{#if savedRepos.length > 0}
					<div class="max-h-32 space-y-1.5 overflow-y-auto pr-1">
						{#each savedRepos as repo, i}
							<div class="flex items-center gap-2 rounded-md border border-green-500/20 bg-green-500/5 px-3 py-1.5">
								<span class="h-1.5 w-1.5 rounded-full bg-green-500 shrink-0"></span>
								<span class="flex-1 min-w-0 truncate text-sm text-surface-200">{repo.name}</span>
								<span class="text-xs text-surface-500">{repo.platform}</span>
								<button
									class="shrink-0 text-xs text-red-400 hover:text-red-300"
									onclick={() => removeRepo(i)}
								>
									{$t('setupLegal.remove', 'Remove')}
								</button>
							</div>
						{/each}
					</div>
				{/if}

				<div class="flex items-center gap-3">
					<button
						class="rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-600 disabled:opacity-50"
						onclick={browseRepo}
						disabled={browsing}
					>
						{browsing ? $t('setupLegal.opening', 'Opening...') : $t('setupLegal.browse', 'Browse...')}
					</button>
					{#if repoBrowseStatus && !repoBrowseStatus.ok}
						<span class="text-sm text-red-400">{repoBrowseStatus.msg}</span>
					{/if}
					{#if !showManualRepo}
						<button
							class="text-xs text-surface-500 hover:text-surface-300"
							onclick={() => showManualRepo = true}
						>
							{$t('setupLegal.add_manually', 'or add manually')}
						</button>
					{/if}
				</div>

				{#if showManualRepo}
					<div class="space-y-2 rounded-md border border-surface-700 bg-surface-800/50 p-3">
						<input
							type="text"
							class="block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
							placeholder={$t('setupLegal.repo_name_placeholder', 'Repository name')}
							bind:value={repoName}
						/>
						<input
							type="text"
							class="block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-sm"
							placeholder={$t('setupLegal.repo_path_placeholder', '/path/to/repo')}
							bind:value={repoPath}
						/>
						<div class="flex items-center gap-2">
							<button
								class="rounded-md bg-surface-600 px-3 py-1.5 text-sm font-medium text-surface-200 transition-colors hover:bg-surface-500 disabled:opacity-50"
								onclick={addRepo}
								disabled={!repoName.trim() || !repoPath.trim()}
							>
								{$t('setupLegal.add', 'Add')}
							</button>
							<button
								class="text-xs text-surface-500 hover:text-surface-300"
								onclick={() => { showManualRepo = false; repoName = ''; repoPath = ''; }}
							>
								{$t('common.cancel', 'Cancel')}
							</button>
						</div>
					</div>
				{/if}
			</div>
		</div>

	<!-- Step 5: Team Members -->
	{:else if step === 5}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setupLegal.team_title', 'Team Members')}</h2>
			<p class="text-sm text-surface-400">{$t('setupLegal.team_intro', 'Add people Laya should recognize in events.')}</p>

			<div class="space-y-3">
				{#each members as member, i}
					<div class="flex items-start gap-2">
						<div class="flex-1 space-y-1">
							<input
								type="text"
								class="block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-sm"
								placeholder={$t('setupLegal.name', 'Name')}
								bind:value={member.name}
							/>
							<input
								type="email"
								class="block w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-1.5 text-sm"
								placeholder={$t('setupLegal.email', 'Email')}
								bind:value={member.email}
							/>
						</div>
						<select
							class="rounded-md border border-surface-600 bg-surface-700 px-2 py-1.5 text-sm"
							bind:value={member.role}
						>
							<option value="teammate">{$t('setupLegal.role_teammate', 'Teammate')}</option>
							<option value="manager">{$t('setupLegal.role_manager', 'Manager')}</option>
							<option value="stakeholder">{$t('setupLegal.role_stakeholder', 'Stakeholder')}</option>
							<option value="bot">{$t('setupLegal.role_bot', 'Bot')}</option>
						</select>
						{#if members.length > 1}
							<button
								class="rounded-md px-2 py-1.5 text-sm text-red-400 hover:text-red-300"
								onclick={() => removeMember(i)}
								aria-label={$t('setupLegal.remove_member', 'Remove member')}
							>
								X
							</button>
						{/if}
					</div>
				{/each}
			</div>

			<button
				class="text-sm text-primary-400 hover:text-primary-300"
				onclick={addMember}
			>
				{$t('setupLegal.add_member', '+ Add member')}
			</button>
		</div>

	<!-- Step 6: Filter Presets -->
	{:else if step === 6}
		<div class="space-y-4">
			<h2 class="text-xl font-semibold">{$t('setupLegal.filters_title', 'Filters')}</h2>
			<p class="text-sm text-surface-400">{$t('setupLegal.filters_intro', 'Choose which events to filter out automatically.')}</p>

			<div class="space-y-3">
				<label class="flex items-center gap-3 rounded-md border border-surface-600 p-3">
					<input type="checkbox" class="accent-laya-orange" bind:checked={ignoreBots} />
					<div>
						<div class="text-sm font-medium">{$t('setupLegal.ignore_bots', 'Ignore bot messages')}</div>
						<div class="text-xs text-surface-400">{$t('setupLegal.ignore_bots_desc', 'Filter events from CI bots, webhooks, etc.')}</div>
					</div>
				</label>

				<label class="flex items-center gap-3 rounded-md border border-surface-600 p-3">
					<input type="checkbox" class="accent-laya-orange" bind:checked={muteRandom} />
					<div>
						<div class="text-sm font-medium">{$t('setupLegal.mute_random', 'Mute #random')}</div>
						<div class="text-xs text-surface-400">{$t('setupLegal.mute_random_desc', 'Filter Slack messages from #random channel')}</div>
					</div>
				</label>
			</div>
		</div>
	{/if}

	<!-- Navigation -->
	<div class="flex justify-between pt-2">
		{#if step > 1}
			<button
				class="rounded-md bg-surface-600 px-4 py-2 text-sm font-medium text-surface-200 transition-colors hover:bg-surface-500"
				onclick={() => (step -= 1)}
			>
				{$t('common.back', 'Back')}
			</button>
		{:else}
			<div></div>
		{/if}

		{#if step < totalSteps}
			<button
				class="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50"
				onclick={handleNext}
				disabled={step === 2 && !step2CanProceed()}
			>
				{#if step === 1 && savedKeys.length === 0 && !useSelfHosted}
					{$t('setupLegal.skip', 'Skip')}
				{:else if step === 2 && settingDefaults}
					{$t('setupLegal.saving', 'Saving...')}
				{:else}
					{$t('common.next', 'Next')}
				{/if}
			</button>
		{:else}
			<button
				class="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-500"
				onclick={finish}
			>
				{$t('setupLegal.finish', 'Finish Setup')}
			</button>
		{/if}
	</div>
</div>
