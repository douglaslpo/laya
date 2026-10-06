<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { t } from '$lib/i18n';
	import PlatformIcon from './PlatformIcon.svelte';
	import SmtpSetupForm from './SmtpSetupForm.svelte';
	import TagInput from './TagInput.svelte';
	import type { FieldDef } from '$lib/api/types';

	let {
		platform,
		platformLabel,
		isOAuth = false,
		fields = [],
		onClose,
		onConnected
	}: {
		platform: string;
		platformLabel: string;
		isOAuth?: boolean;
		fields?: FieldDef[];
		onClose: () => void;
		onConnected: () => void;
	} = $props();

	// Connection name (for additional accounts)
	let connectionName = $state('');
	let existingNames = $state<string[]>([]);
	let nameError = $state<string | null>(null);

	// API-key form state (checkbox fields hold booleans, everything else strings)
	let fieldValues = $state<Record<string, string | boolean>>({});
	let submitting = $state(false);
	let error = $state<string | null>(null);

	// Load existing names for uniqueness validation
	$effect(() => {
		engineApi.getConnectionNames(platform).then(r => {
			existingNames = r.names;
		}).catch(() => {});
	});

	// Slack channel selection
	let slackChannels = $state<string[]>([]);

	// OAuth state
	let oauthPolling = $state(false);
	let oauthError = $state<string | null>(null);
	let showOAuthSetup = $state(false);
	let oauthClientId = $state('');
	let oauthClientSecret = $state('');

	// Initialize field values
	$effect(() => {
		const vals: Record<string, string | boolean> = {};
		for (const f of fields) {
			vals[f.key] = f.type === 'checkbox' ? false : '';
		}
		fieldValues = vals;
	});

	async function handleApiKeySubmit() {
		if (!connectionName.trim()) {
			nameError = $t('settingsModels.name_required', 'Please provide a name for this account');
			return;
		}
		if (connectionName && existingNames.includes(connectionName.trim())) {
			nameError = $t('settingsModels.name_in_use', 'This name is already in use');
			return;
		}
		nameError = null;
		submitting = true;
		error = null;
		try {
			await engineApi.createEgressConnection({
				platform,
				name: connectionName.trim() || undefined,
				credentials: fieldValues
			});
			onConnected();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('settingsModels.connection_failed', 'Connection failed');
		} finally {
			submitting = false;
		}
	}

	async function handleSmtpSubmit(credentials: Record<string, string>) {
		submitting = true;
		error = null;
		try {
			await engineApi.createEgressConnection({
				platform: 'smtp',
				name: connectionName.trim() || `Email (${credentials.email})`,
				credentials
			});
			onConnected();
		} catch (e) {
			error = e instanceof Error ? e.message : $t('settingsModels.connection_failed', 'Connection failed');
		} finally {
			submitting = false;
		}
	}

	async function handleOAuthConnect() {
		if (!connectionName.trim()) {
			nameError = $t('settingsModels.name_required', 'Please provide a name for this account');
			return;
		}
		if (connectionName && existingNames.includes(connectionName.trim())) {
			nameError = $t('settingsModels.name_in_use', 'This name is already in use');
			return;
		}
		if (platform === 'slack' && slackChannels.length === 0) {
			oauthError = $t('settingsModels.slack_channel_required', 'Please specify at least one channel to monitor.');
			return;
		}
		nameError = null;
		oauthError = null;
		try {
			const result = await engineApi.startOAuthFlow(
				platform,
				connectionName.trim() || undefined,
				undefined,
				platform === 'slack' ? slackChannels : undefined
			);
			// Open in system browser (works in Tauri and dev).
			// Tauri's shell plugin opens the default browser; in dev/web
			// we fall back to window.open.
			try {
				const { open } = await import('@tauri-apps/plugin-shell');
				await open(result.auth_url);
			} catch {
				window.open(result.auth_url, '_blank', 'width=600,height=700');
			}
			// Capture current connection count before polling
			try {
				const current = await engineApi.listEgressConnections();
				initialConnectionCount = current.connections.filter(c => c.platform === platform).length;
			} catch { initialConnectionCount = 0; }
			// Start polling for completion
			oauthPolling = true;
			pollForOAuthCompletion();
		} catch (e) {
			const msg = e instanceof Error ? e.message : $t('settingsModels.oauth_failed', 'OAuth failed');
			if (msg.includes('not configured') || msg.includes('client')) {
				showOAuthSetup = true;
				oauthError = null;
			} else {
				oauthError = msg;
			}
		}
	}

	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let pollCount = 0;
	let initialConnectionCount = 0;

	function pollForOAuthCompletion() {
		pollCount = 0;
		pollInterval = setInterval(async () => {
			pollCount++;
			if (pollCount > 30) {
				// 60 seconds timeout
				stopPolling();
				oauthPolling = false;
				oauthError = $t('settingsModels.oauth_timeout', 'OAuth flow timed out. Please try again.');
				return;
			}
			try {
				const conns = await engineApi.listEgressConnections();
				const platformConns = conns.connections.filter((c) => c.platform === platform);
				// Detect a new connection (count increased) rather than matching an existing one
				if (platformConns.length > initialConnectionCount) {
					stopPolling();
					oauthPolling = false;
					onConnected();
				}
			} catch {
				// ignore polling errors
			}
		}, 2000);
	}

	function stopPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	}

	async function handleOAuthSetup() {
		if (!oauthClientId.trim() || !oauthClientSecret.trim()) return;
		submitting = true;
		oauthError = null;
		try {
			await engineApi.setupOAuthClient({
				platform,
				client_id: oauthClientId.trim(),
				client_secret: oauthClientSecret.trim()
			});
			showOAuthSetup = false;
			// Now try the OAuth flow again
			await handleOAuthConnect();
		} catch (e) {
			oauthError = e instanceof Error ? e.message : $t('settingsModels.setup_failed', 'Setup failed');
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			stopPolling();
			onClose();
		}
	}

	// Cleanup on unmount
	$effect(() => {
		return () => stopPolling();
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Overlay -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onclick={onClose} onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}>
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="w-full max-w-md rounded-xl border shadow-2xl {$glassTheme ? 'glass-dropdown border-white/[0.12]' : 'border-surface-700 bg-surface-900'}"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center gap-3 border-b {$glassTheme ? 'border-white/[0.08]' : 'border-surface-700'} px-6 py-4">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg {$glassTheme ? 'bg-white/[0.06]' : 'bg-surface-800'} text-surface-300">
				<PlatformIcon platform={platform} size={18} />
			</div>
			<div>
				<h3 class="text-laya-base font-semibold text-surface-100">{$t('settingsModels.connect_platform', 'Connect {platform}', { platform: platformLabel })}</h3>
				<p class="text-laya-secondary text-surface-500">
					{#if isOAuth}
						{$t('settingsModels.auth_via_oauth', 'Authenticate via OAuth')}
					{:else if platform === 'smtp'}
						{$t('settingsModels.configure_email_server', 'Configure email server settings')}
					{:else}
						{$t('settingsModels.enter_api_credentials', 'Enter your API credentials')}
					{/if}
				</p>
			</div>
			<button
				aria-label={$t('common.close', 'Close')}
				onclick={() => { stopPolling(); onClose(); }}
				class="ml-auto text-surface-500 hover:text-surface-200 transition-colors"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>

		<!-- Body -->
		<div class="px-6 py-5">
			{#if error}
				<div class="mb-4 rounded-md border border-red-800/50 bg-red-900/20 px-3 py-2 text-laya-secondary text-red-300">
					{error}
				</div>
			{/if}

			<!-- Account name input -->
			<div class="mb-4">
				<label for="connection-name" class="mb-1 block text-laya-secondary font-medium text-surface-400">{$t('settingsModels.account_name', 'Account Name')}</label>
				<input
					id="connection-name"
					type="text"
					bind:value={connectionName}
					placeholder={$t('settingsModels.account_name_placeholder', 'e.g., Personal, Work')}
					class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
				/>
				{#if nameError}
					<p class="mt-1 text-laya-secondary text-red-400">{nameError}</p>
				{:else if connectionName && existingNames.includes(connectionName.trim())}
					<p class="mt-1 text-laya-secondary text-red-400">{$t('settingsModels.name_in_use', 'This name is already in use')}</p>
				{:else}
					<p class="mt-1 text-laya-secondary text-surface-500">{$t('settingsModels.account_name_hint', 'A label to identify this account')}</p>
				{/if}
			</div>

			{#if platform === 'slack' && isOAuth}
				<div class="mb-4">
					<span class="mb-1 block text-laya-secondary font-medium text-surface-400">{$t('settingsModels.channels_to_monitor', 'Channels to Monitor')}</span>
					<TagInput
						bind:tags={slackChannels}
						placeholder={$t('settingsModels.channels_placeholder', 'e.g., general, dev, team-standup')}
					/>
					<p class="mt-1 text-laya-secondary text-surface-500">
						{$t('settingsModels.channels_hint', 'Type channel names separated by commas. Only these channels will be monitored.')}
					</p>
				</div>
			{/if}

			{#if platform === 'smtp'}
				<!-- SMTP setup form -->
				<SmtpSetupForm onSubmit={handleSmtpSubmit} {submitting} />

			{:else if isOAuth}
				<!-- OAuth flow -->
				{#if showOAuthSetup}
					<div class="space-y-4">
						<p class="text-laya-secondary text-surface-400">
							{$t('settingsModels.oauth_setup_intro', 'To connect {platform}, first configure your OAuth application credentials.', { platform: platformLabel })}
						</p>
						<div>
							<label for="oauth-client-id" class="mb-1 block text-laya-secondary font-medium text-surface-400">{$t('settingsModels.client_id', 'Client ID')}</label>
							<input
								id="oauth-client-id"
								type="text"
								bind:value={oauthClientId}
								placeholder={$t('settingsModels.client_id_placeholder', 'Your OAuth client ID')}
								class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
							/>
						</div>
						<div>
							<label for="oauth-client-secret" class="mb-1 block text-laya-secondary font-medium text-surface-400">{$t('settingsModels.client_secret', 'Client Secret')}</label>
							<input
								id="oauth-client-secret"
								type="password"
								bind:value={oauthClientSecret}
								placeholder={$t('settingsModels.client_secret_placeholder', 'Your OAuth client secret')}
								class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
							/>
						</div>
						{#if oauthError}
							<div class="rounded-md border border-red-800/50 bg-red-900/20 px-3 py-2 text-laya-secondary text-red-300">
								{oauthError}
							</div>
						{/if}
						<button
							onclick={handleOAuthSetup}
							disabled={submitting || !oauthClientId.trim() || !oauthClientSecret.trim()}
							class="w-full rounded-md bg-laya-orange px-4 py-2 text-laya-base font-medium text-white transition-colors hover:bg-laya-gold disabled:opacity-50"
						>
							{submitting ? $t('settingsModels.saving', 'Saving…') : $t('settingsModels.save_continue', 'Save & Continue')}
						</button>
					</div>
				{:else if oauthPolling}
					<div class="flex flex-col items-center gap-3 py-6">
						<div class="h-8 w-8 animate-spin rounded-full border-2 border-surface-600 border-t-laya-orange"></div>
						<p class="text-laya-base text-surface-300">{$t('settingsModels.waiting_authorization', 'Waiting for authorization...')}</p>
						<p class="text-laya-secondary text-surface-500">{$t('settingsModels.complete_signin', 'Complete the sign-in in the opened window')}</p>
					</div>
				{:else}
					<div class="flex flex-col items-center gap-4 py-4">
						<p class="text-center text-laya-base text-surface-400">
							{$t('settingsModels.oauth_signin_intro', 'Click below to sign in with {platform}. A new window will open for authorization.', { platform: platformLabel })}
						</p>
						{#if oauthError}
							<div class="w-full rounded-md border border-red-800/50 bg-red-900/20 px-3 py-2 text-laya-secondary text-red-300">
								{oauthError}
							</div>
						{/if}
						<button
							onclick={handleOAuthConnect}
							class="flex items-center gap-2 rounded-md bg-laya-orange px-6 py-2.5 text-laya-base font-medium text-white transition-colors hover:bg-laya-gold"
						>
							<PlatformIcon platform={platform} size={16} />
							{$t('settingsModels.connect_platform', 'Connect {platform}', { platform: platformLabel })}
						</button>
						<button
							onclick={() => { showOAuthSetup = true; oauthError = null; }}
							class="text-laya-secondary text-surface-500 hover:text-surface-300 transition-colors"
						>
							{$t('settingsModels.change_oauth_credentials', 'Change OAuth credentials')}
						</button>
					</div>
				{/if}

			{:else}
				<!-- API-key form -->
				<div class="space-y-4">
					{#each fields as field}
						<div>
							{#if field.type === 'checkbox'}
								<label for="field-{field.key}" class="flex items-center gap-2 text-laya-secondary font-medium text-surface-400">
									<input
										id="field-{field.key}"
										type="checkbox"
										checked={fieldValues[field.key] === true}
										onchange={(e) => (fieldValues[field.key] = e.currentTarget.checked)}
										class="h-4 w-4 rounded border-surface-600 bg-surface-700 accent-laya-orange"
									/>
									{field.label}
								</label>
							{:else if field.type === 'password'}
								<label for="field-{field.key}" class="mb-1 block text-laya-secondary font-medium text-surface-400">{field.label}</label>
								<input
									id="field-{field.key}"
									type="password"
									bind:value={fieldValues[field.key]}
									placeholder={field.placeholder ?? ''}
									class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
								/>
							{:else}
								<label for="field-{field.key}" class="mb-1 block text-laya-secondary font-medium text-surface-400">{field.label}</label>
								<input
									id="field-{field.key}"
									type="text"
									bind:value={fieldValues[field.key]}
									placeholder={field.placeholder ?? ''}
									class="w-full rounded-md border border-surface-600 bg-surface-700 px-3 py-2 text-laya-base text-surface-100 placeholder:text-surface-500"
								/>
							{/if}
							{#if field.help}
								<p class="mt-1 text-laya-secondary text-surface-500">{field.help}</p>
							{/if}
						</div>
					{/each}

					<button
						onclick={handleApiKeySubmit}
						disabled={submitting || fields.some((f) => f.type !== 'checkbox' && !String(fieldValues[f.key] ?? '').trim())}
						class="w-full rounded-md bg-laya-orange px-4 py-2 text-laya-base font-medium text-white transition-colors hover:bg-laya-gold disabled:opacity-50"
					>
						{submitting ? $t('settingsModels.connecting', 'Connecting...') : $t('settingsModels.connect', 'Connect')}
					</button>
				</div>
			{/if}
		</div>
	</div>
</div>
