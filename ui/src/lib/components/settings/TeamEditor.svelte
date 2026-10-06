<!-- Copyright 2026 Aayush Chawla -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { engineApi } from '$lib/api/engine';
	import { glassTheme } from '$lib/stores/glassTheme';
	import type { TeamMember } from '$lib/api/types';
	import { t } from '$lib/i18n';

	const roles: TeamMember['role'][] = ['self', 'manager', 'teammate', 'external', 'bot'];
	const roleLabels: Record<TeamMember['role'], string> = {
		self: 'You',
		manager: 'manager',
		teammate: 'teammate',
		external: 'external',
		bot: 'bot',
	};

	function roleLabel(role: TeamMember['role']): string {
		return $t(`settingsRules.role_${role}`, roleLabels[role] ?? role);
	}

	let members = $state<TeamMember[]>([]);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let editingIndex = $state<number | null>(null);
	let showAddForm = $state(false);

	// Form fields
	let formName = $state('');
	let formEmail = $state('');
	let formRole = $state<TeamMember['role']>('teammate');
	let formNotes = $state('');
	let formAliases = $state('');
	let formAccounts = $state('');

	let hasSelf = $derived(members.some((m) => m.role === 'self'));

	/** Roles available in the current form context */
	let availableRoles = $derived.by(() => {
		if (editingIndex !== null && members[editingIndex]?.role === 'self') {
			return roles;
		}
		return hasSelf ? roles.filter((r) => r !== 'self') : roles;
	});

	/** Whether the current form is for the 'self' role */
	let isSelfForm = $derived(formRole === 'self');

	function parseList(raw: string): string[] {
		return raw.split(',').map((s) => s.trim()).filter(Boolean);
	}

	function joinList(arr: string[]): string {
		return arr.join(', ');
	}

	onMount(async () => {
		try {
			const data = await engineApi.getTeam();
			members = data.members;
		} catch {
			error = $t('settingsRules.err_load_team', 'Failed to load team configuration');
		} finally {
			loading = false;
		}
	});

	async function save() {
		saving = true;
		error = null;
		try {
			await engineApi.updateTeam({ members });
		} catch {
			error = $t('settingsRules.err_save_team', 'Failed to save team');
		} finally {
			saving = false;
		}
	}

	function resetForm() {
		formName = '';
		formEmail = '';
		formRole = 'teammate';
		formNotes = '';
		formAliases = '';
		formAccounts = '';
		showAddForm = false;
		editingIndex = null;
	}

	function buildMember(): TeamMember {
		return {
			name: formName,
			email: formEmail,
			role: formRole,
			notes: formNotes,
			aliases: parseList(formAliases),
			accounts: parseList(formAccounts),
		};
	}

	async function addMember() {
		members.push(buildMember());
		resetForm();
		await save();
	}

	function startEdit(index: number) {
		const m = members[index];
		formName = m.name;
		formEmail = m.email;
		formRole = m.role;
		formNotes = m.notes;
		formAliases = joinList(m.aliases ?? []);
		formAccounts = joinList(m.accounts ?? []);
		editingIndex = index;
		showAddForm = false;
	}

	async function saveEdit() {
		if (editingIndex !== null) {
			members[editingIndex] = buildMember();
			resetForm();
			await save();
		}
	}

	async function removeMember(index: number) {
		members.splice(index, 1);
		await save();
	}
</script>

{#if loading}
	<div class="text-surface-400">{$t('settingsRules.loading_team', 'Loading team...')}</div>
{:else}
	{#if error}
		<div class="rounded-lg border border-red-800 bg-red-900/30 px-4 py-2 text-laya-base text-red-300">{error}</div>
	{/if}

	<!-- Self-identification prompt (if no 'self' member exists) -->
	{#if !hasSelf && !showAddForm && editingIndex === null}
		<button
			class="mb-4 w-full rounded-xl border border-dashed border-laya-orange/40 bg-laya-orange/5 px-4 py-3 text-left transition-colors hover:border-laya-orange/60 hover:bg-laya-orange/10"
			onclick={() => { formRole = 'self'; showAddForm = true; }}
		>
			<span class="text-laya-base font-medium text-laya-orange">{$t('settingsRules.identify_prompt', 'Identify yourself')}</span>
			<span class="mt-0.5 block text-laya-secondary text-surface-400">{$t('settingsRules.identify_prompt_desc', 'Add your name, emails, and platform accounts so Laya can personalise cards and avoid drafting messages to yourself.')}</span>
		</button>
	{/if}

	<!-- Member table -->
	<div class="overflow-hidden {$glassTheme ? 'glass-section' : 'rounded-xl border border-surface-700'}">
		<table class="w-full text-laya-base">
			<thead class="{$glassTheme ? 'bg-white/[0.03]' : 'bg-surface-800'} text-left text-laya-secondary uppercase tracking-wider text-surface-400">
				<tr>
					<th class="px-4 py-3">{$t('settingsRules.col_name', 'Name')}</th>
					<th class="px-4 py-3">{$t('settingsRules.col_email', 'Email')}</th>
					<th class="px-4 py-3">{$t('settingsRules.col_role', 'Role')}</th>
					<th class="px-4 py-3">{$t('settingsRules.col_notes', 'Notes')}</th>
					<th class="px-4 py-3 text-right">{$t('settingsRules.col_actions', 'Actions')}</th>
				</tr>
			</thead>
			<tbody class="divide-y {$glassTheme ? 'divide-white/[0.05]' : 'divide-surface-700'}">
				{#each members as member, i}
					<tr class={member.role === 'self' ? 'bg-laya-orange/5 hover:bg-laya-orange/10' : $glassTheme ? 'bg-white/[0.02] hover:bg-white/[0.05]' : 'bg-surface-900 hover:bg-surface-800'}>
						<td class="px-4 py-3 font-medium">{member.name}</td>
						<td class="px-4 py-3 text-surface-300">
							{member.email}
							{#if member.aliases?.length}
								<span class="ml-1 text-surface-500">+{member.aliases.length}</span>
							{/if}
						</td>
						<td class="px-4 py-3">
							{#if member.role === 'self'}
								<span class="rounded-full bg-laya-orange/20 px-2 py-0.5 text-laya-secondary text-laya-orange">{roleLabel('self')}</span>
							{:else}
								<span class="rounded-full bg-surface-700 px-2 py-0.5 text-laya-secondary">{roleLabel(member.role)}</span>
							{/if}
						</td>
						<td class="px-4 py-3 text-surface-400">
							{#if member.role === 'self' && member.accounts?.length}
								<span class="text-surface-500">{member.accounts.join(', ')}</span>
							{:else}
								{member.notes}
							{/if}
						</td>
						<td class="px-4 py-3 text-right">
							<button class="text-surface-400 hover:text-surface-100" onclick={() => startEdit(i)}>{$t('common.edit', 'Edit')}</button>
							<button class="ml-2 text-red-400 hover:text-red-300" onclick={() => removeMember(i)}>{$t('settingsRules.remove', 'Remove')}</button>
						</td>
					</tr>
				{/each}
				{#if members.length === 0}
					<tr><td colspan="5" class="px-4 py-6 text-center text-surface-500">{$t('settingsRules.no_members', 'No team members configured')}</td></tr>
				{/if}
			</tbody>
		</table>
	</div>

	<!-- Add/Edit form -->
	{#if showAddForm || editingIndex !== null}
		<div class="mt-4 {$glassTheme ? 'glass-section' : 'rounded-xl border border-surface-700 bg-surface-800'} p-4">
			<h3 class="mb-3 text-laya-base font-medium">
				{#if editingIndex !== null}
					{isSelfForm ? $t('settingsRules.edit_identity', 'Edit Your Identity') : $t('settingsRules.edit_member', 'Edit Member')}
				{:else if isSelfForm}
					{$t('settingsRules.identify_title', 'Identify Yourself')}
				{:else}
					{$t('settingsRules.add_member_title', 'Add Member')}
				{/if}
			</h3>
			{#if isSelfForm && editingIndex === null}
				<p class="mb-3 text-laya-secondary text-surface-400">{$t('settingsRules.self_form_desc', 'Laya will use this to personalise your cards — referring to your actions in first person and avoiding drafting messages to yourself.')}</p>
			{/if}
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<input bind:value={formName} placeholder={$t('settingsRules.col_name', 'Name')} class="rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50 placeholder-surface-500" />
				<input bind:value={formEmail} placeholder={isSelfForm ? $t('settingsRules.primary_email', 'Primary email') : $t('settingsRules.col_email', 'Email')} class="rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50 placeholder-surface-500" />
				<select bind:value={formRole} class="rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50">
					{#each availableRoles as role}
						<option value={role}>{roleLabel(role)}</option>
					{/each}
				</select>
				{#if isSelfForm}
					<input bind:value={formAliases} placeholder={$t('settingsRules.other_emails_placeholder', 'Other emails (comma-separated)')} class="rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50 placeholder-surface-500" />
					<input bind:value={formAccounts} placeholder={$t('settingsRules.accounts_placeholder', 'Platform accounts, e.g. jdoe, jane.doe (comma-separated)')} class="col-span-full rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50 placeholder-surface-500" />
				{/if}
				<input bind:value={formNotes} placeholder={$t('settingsRules.notes_placeholder', 'Notes (optional)')} class="rounded-lg border border-surface-600 bg-surface-900 px-3 py-2 text-laya-base text-surface-50 placeholder-surface-500" />
			</div>
			<div class="mt-3 flex gap-2">
				<button
					class="rounded-lg bg-surface-600 px-4 py-2 text-laya-base font-medium hover:bg-surface-500"
					onclick={editingIndex !== null ? saveEdit : addMember}
					disabled={!formName || !formEmail}
				>
					{saving ? $t('settingsRules.saving', 'Saving...') : editingIndex !== null ? $t('common.save', 'Save') : isSelfForm ? $t('common.save', 'Save') : $t('settingsRules.add', 'Add')}
				</button>
				<button class="rounded-lg px-4 py-2 text-laya-base text-surface-400 hover:text-surface-200" onclick={resetForm}>
					{$t('common.cancel', 'Cancel')}
				</button>
			</div>
		</div>
	{:else}
		<button
			class="mt-4 rounded-lg border border-dashed border-surface-600 px-4 py-2 text-laya-base text-surface-400 transition-colors hover:border-surface-400 hover:text-surface-200"
			onclick={() => (showAddForm = true)}
		>
			{$t('settingsRules.add_member', '+ Add Member')}
		</button>
	{/if}
{/if}
