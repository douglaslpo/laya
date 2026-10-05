<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import { t, locale } from '$lib/i18n';

	/** Splits a translated string into plain and [[highlighted]] segments. */
	function rich(text: string): { text: string; hl: boolean }[] {
		return text
			.split(/\[\[(.*?)\]\]/)
			.map((s, i) => ({ text: s, hl: i % 2 === 1 }))
			.filter((s) => s.text);
	}

	type Section = 'card' | 'chat' | 'audit' | 'omni' | 'ingestion' | 'firings' | 'logging';
	type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

	let retentionDays = $state(90);
	let chatRetentionDays = $state(90);
	let auditRetentionDays = $state(90);
	let omniRetentionDays = $state(30);
	let ingestionErrorsRetentionDays = $state(30);
	let firingLogRetentionDays = $state(90);
	let logLevel = $state<LogLevel>('INFO');
	let loading = $state(true);
	let savingSection = $state<Section | null>(null);
	let savedSection = $state<Section | null>(null);
	let errorSection = $state<Section | null>(null);
	let error = $state('');

	let saveTimer: ReturnType<typeof setTimeout> | null = null;
	let savedClearTimer: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		engineApi.getSettings().then((s) => {
			retentionDays = s.retention?.card_retention_days ?? 90;
			chatRetentionDays = s.retention?.chat_retention_days ?? 90;
			auditRetentionDays = s.retention?.audit_retention_days ?? 90;
			omniRetentionDays = s.retention?.omni_retention_days ?? 30;
			ingestionErrorsRetentionDays = s.retention?.ingestion_errors_retention_days ?? 30;
			firingLogRetentionDays = s.retention?.firing_log_retention_days ?? 90;
			logLevel = s.logging?.level ?? 'INFO';
			loading = false;
		});
	});

	function debouncedSave(section: Section) {
		if (saveTimer) clearTimeout(saveTimer);
		if (savedClearTimer) clearTimeout(savedClearTimer);
		savingSection = section;
		savedSection = null;
		errorSection = null;
		error = '';
		saveTimer = setTimeout(() => save(section), 800);
	}

	async function save(section: Section) {
		try {
			await engineApi.updateSettings({
				retention: {
					card_retention_days: retentionDays,
					chat_retention_days: chatRetentionDays,
					audit_retention_days: auditRetentionDays,
					omni_retention_days: omniRetentionDays,
					ingestion_errors_retention_days: ingestionErrorsRetentionDays,
					firing_log_retention_days: firingLogRetentionDays
				}
			} as never);
			savedSection = section;
			savedClearTimer = setTimeout(() => (savedSection = null), 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : $t('settingsData.save_failed', 'Save failed');
			errorSection = section;
		} finally {
			if (savingSection === section) savingSection = null;
		}
	}

	// Log level is a discrete <select>, so save immediately on change (no debounce).
	// The engine applies the new level to the running process right away — no restart.
	async function saveLogLevel() {
		if (savedClearTimer) clearTimeout(savedClearTimer);
		savingSection = 'logging';
		savedSection = null;
		errorSection = null;
		error = '';
		try {
			await engineApi.updateSettings({ logging: { level: logLevel } } as never);
			savedSection = 'logging';
			savedClearTimer = setTimeout(() => (savedSection = null), 2000);
		} catch (e) {
			error = e instanceof Error ? e.message : $t('settingsData.save_failed', 'Save failed');
			errorSection = 'logging';
		} finally {
			if (savingSection === 'logging') savingSection = null;
		}
	}
</script>

<div class="space-y-6">
	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.log_level_title', 'Engine Log Level')}</h3>
			{#if savingSection === 'logging'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'logging'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{#each rich($t('settingsData.log_level_desc', 'Controls how much detail the engine writes to [[{path}]]. Lower the level to reduce log volume. Applies immediately — no restart needed.', { path: '~/.laya/logs/engine.log' })) as seg}{#if seg.hl}<span class="text-surface-300">{seg.text}</span>{:else}{seg.text}{/if}{/each}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="log-level">
					{$t('settingsData.log_level', 'Log level')}
				</label>
				<select
					id="log-level"
					bind:value={logLevel}
					onchange={() => saveLogLevel()}
					class="h-9 w-36 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				>
					<option value="DEBUG">Debug</option>
					<option value="INFO">Info</option>
					<option value="WARNING">Warning</option>
					<option value="ERROR">Error</option>
				</select>
			</div>

			{#if errorSection === 'logging' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{#each rich($t('settingsData.log_level_hint', 'Default: [[Info]]. Choose [[Warning]] or [[Error]] to record only problems and keep logs small. The log file is size-capped and rotated automatically (10\u00a0MB × 5 files).')) as seg}{#if seg.hl}<span class="text-surface-300">{seg.text}</span>{:else}{seg.text}{/if}{/each}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.card_retention_title', 'Card Retention')}</h3>
			{#if savingSection === 'card'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'card'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.card_retention_desc', 'Cards in archived, dismissed, completed, or failed states that are older than the retention period are automatically deleted each day. Active cards are never auto-deleted.')}
		</p>

		{#if loading}
			<p class="text-laya-base text-surface-500">{$t('common.loading', 'Loading...')}</p>
		{:else}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="retention-days"
					type="number"
					min="1"
					max="3650"
					bind:value={retentionDays}
					oninput={() => debouncedSave('card')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'card' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{#each rich($t('settingsData.card_retention_hint', 'Default: 90 days. Cards created before [[{date}]] would be eligible for deletion.', { date: new Date(Date.now() - retentionDays * 86400000).toLocaleDateString($locale) })) as seg}{#if seg.hl}<span class="text-surface-300">{seg.text}</span>{:else}{seg.text}{/if}{/each}
			</p>

			<p class="mt-3 text-laya-secondary text-surface-500">
				{#each rich($t('settingsData.card_delete_hint', 'To delete a card manually, first [[archive]] it — a trash icon will appear on the card. Clicking it opens a confirmation before permanently removing the card and all its related data.')) as seg}{#if seg.hl}<span class="text-surface-300">{seg.text}</span>{:else}{seg.text}{/if}{/each}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.chat_retention_title', 'Chat Retention')}</h3>
			{#if savingSection === 'chat'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'chat'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.chat_retention_desc', 'Conversations that have been idle for longer than the retention period are automatically deleted each day, along with all their messages.')}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="chat-retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="chat-retention-days"
					type="number"
					min="1"
					max="3650"
					bind:value={chatRetentionDays}
					oninput={() => debouncedSave('chat')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'chat' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{#each rich($t('settingsData.chat_retention_hint', 'Default: 90 days. Conversations last active before [[{date}]] would be eligible for deletion.', { date: new Date(Date.now() - chatRetentionDays * 86400000).toLocaleDateString($locale) })) as seg}{#if seg.hl}<span class="text-surface-300">{seg.text}</span>{:else}{seg.text}{/if}{/each}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.audit_retention_title', 'Audit Log Retention')}</h3>
			{#if savingSection === 'audit'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'audit'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.audit_retention_desc', 'LLM call audit logs older than the retention period are automatically deleted each day.')}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="audit-retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="audit-retention-days"
					type="number"
					min="1"
					max="3650"
					bind:value={auditRetentionDays}
					oninput={() => debouncedSave('audit')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'audit' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{$t('settingsData.default_days', 'Default: {count} days.', { count: 90 })}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.omni_retention_title', 'Omni Retention')}</h3>
			{#if savingSection === 'omni'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'omni'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.omni_retention_desc', 'Omni timeline snapshots older than the retention period are automatically deleted each day. The latest snapshot per space is always preserved.')}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="omni-retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="omni-retention-days"
					type="number"
					min="1"
					max="365"
					bind:value={omniRetentionDays}
					oninput={() => debouncedSave('omni')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'omni' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{$t('settingsData.default_days', 'Default: {count} days.', { count: 30 })}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.ingestion_retention_title', 'Ingestion Errors Retention')}</h3>
			{#if savingSection === 'ingestion'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'ingestion'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.ingestion_retention_desc', 'Captured n8n ingestion failures older than the retention period are automatically deleted each day. Cleared errors are also subject to this retention.')}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="ingestion-retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="ingestion-retention-days"
					type="number"
					min="1"
					max="365"
					bind:value={ingestionErrorsRetentionDays}
					oninput={() => debouncedSave('ingestion')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'ingestion' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{$t('settingsData.default_days', 'Default: {count} days.', { count: 30 })}
			</p>
		{/if}
	</div>

	<div class="{$glassTheme ? 'glass-section' : 'rounded-lg border border-surface-700 bg-surface-800'} p-5">
		<div class="mb-1 flex items-center justify-between">
			<h3 class="text-laya-heading font-medium">{$t('settingsData.firing_retention_title', 'Rule Firing Log Retention')}</h3>
			{#if savingSection === 'firings'}
				<span class="text-laya-micro text-laya-orange">{$t('settingsData.saving', 'Saving…')}</span>
			{:else if savedSection === 'firings'}
				<span class="text-laya-micro text-green-400">{$t('settingsData.saved', 'Saved')}</span>
			{/if}
		</div>
		<p class="mb-4 text-laya-base text-surface-400">
			{$t('settingsData.firing_retention_desc', 'Processing-rule firing history (shown under Rules → Activity) older than the retention period is automatically deleted each day.')}
		</p>

		{#if !loading}
			<div class="flex flex-col gap-1">
				<label class="text-laya-secondary font-medium text-surface-300" for="firing-retention-days">
					{$t('settingsData.retention_period', 'Retention period (days)')}
				</label>
				<input
					id="firing-retention-days"
					type="number"
					min="1"
					max="3650"
					bind:value={firingLogRetentionDays}
					oninput={() => debouncedSave('firings')}
					class="h-9 w-32 rounded-md border border-surface-600 bg-surface-700 px-3 text-laya-base text-surface-50 focus:border-laya-orange/50 focus:outline-none"
				/>
			</div>

			{#if errorSection === 'firings' && error}
				<p class="mt-2 text-laya-secondary text-red-400">{error}</p>
			{/if}

			<p class="mt-3 text-laya-secondary text-surface-500">
				{$t('settingsData.default_days', 'Default: {count} days.', { count: 90 })}
			</p>
		{/if}
	</div>

</div>
