// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

// The Edit → Polish → Execute machinery for the item page's expanded evidence
// detail, preserved verbatim from the old insight page.
//
// State stays in the route (one WebSocket effect, one polish-seeding effect) and
// is handed to every row through this bag rather than duplicated per row — the
// `_polishing` flags arrive as page-level WS messages, not per-component ones.

import type { ActionCard, SuggestedAction } from '$lib/api/types';
import { tr } from '$lib/i18n';

export interface EvidenceActionContext {
	executingActionId: string | null;
	editingActionId: string | null;
	editedPayload: Record<string, string>;
	savingPayload: boolean;
	polishingActionIds: Set<string>;
	polishErrors: Record<string, string>;
	executeError: string | null;
	startEditing: (action: SuggestedAction, fallbackBody?: string) => void;
	cancelEditing: () => void;
	savePayload: (card: ActionCard, action: SuggestedAction) => void;
	polishDraft: (card: ActionCard, action: SuggestedAction) => void;
	executeAction: (card: ActionCard, actionId: string) => void;
	showInPulse: (cardId: string) => void;
}

/** Statuses where the card is finished and its actions are no longer offered. */
export const TERMINAL_CARD_STATUSES = new Set(['done', 'failed', 'dismissed', 'archived']);

/**
 * The field in an action payload that holds the editable draft body. Order
 * matters — `body` wins over `comment` when a payload carries both.
 */
export function getEditableTextField(payload: Record<string, unknown>): string | null {
	for (const key of ['body', 'comment', 'message', 'description']) {
		if (typeof payload[key] === 'string' && (payload[key] as string).length > 0) return key;
	}
	return null;
}

/** Human labels for staged_output.type. */
export const OUTPUT_TYPE_LABELS: Record<string, string> = {
	get draft_reply() { return tr('omniTrace.output_draft_reply', 'Draft Reply'); },
	get code_fix() { return tr('omniTrace.output_code_fix', 'Code Fix'); },
	get briefing() { return tr('omniTrace.output_briefing', 'Briefing'); },
	get summary() { return tr('omniTrace.output_summary', 'Summary'); },
	get agent_result() { return tr('omniTrace.output_agent_result', 'Agent Result'); },
	get agent_plan() { return tr('omniTrace.output_agent_plan', 'Agent Plan'); }
};

/** Platform key for the "Open on <platform>" link — same derivation as before. */
export function cardPlatform(card: ActionCard & { platform?: string }): string {
	if (card.platform) return card.platform;
	if (card.entity_id) return card.entity_id.split(':')[0];
	return 'unknown';
}
