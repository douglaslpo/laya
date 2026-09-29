// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

// Pure queue logic for egress actions requested over MCP that await the user's
// confirmation in the UI (WS `egress_confirmation_request` / `_resolved`, and
// GET /egress/pending on (re)connect). No Svelte or network imports so it stays
// unit-testable in node.

export interface PendingEgressPreview {
	summary: string;
	details: Record<string, unknown>;
	warnings: string[];
	estimated_impact: string;
}

export interface PendingEgressConfirmation {
	request_id: string;
	origin: 'mcp' | 'chat';
	platform: string;
	action_type: string;
	space_id: string | null;
	connection_id: string | null;
	preview: PendingEgressPreview;
	created_at: string;
	expires_at: string;
}

export type ResolvedStatus = 'done' | 'failed' | 'rejected';

function expiresMs(item: PendingEgressConfirmation): number {
	const t = Date.parse(item.expires_at);
	return Number.isNaN(t) ? Number.POSITIVE_INFINITY : t;
}

function sortByExpiry(queue: PendingEgressConfirmation[]): PendingEgressConfirmation[] {
	return [...queue].sort((a, b) => expiresMs(a) - expiresMs(b));
}

export function isPendingConfirmation(value: unknown): value is PendingEgressConfirmation {
	if (!value || typeof value !== 'object') return false;
	const v = value as Record<string, unknown>;
	return (
		typeof v.request_id === 'string' &&
		v.request_id.length > 0 &&
		typeof v.expires_at === 'string' &&
		!!v.preview &&
		typeof v.preview === 'object'
	);
}

/** Add (or replace, deduped by request_id) one confirmation; keeps expiry order. */
export function addConfirmation(
	queue: PendingEgressConfirmation[],
	item: PendingEgressConfirmation
): PendingEgressConfirmation[] {
	return sortByExpiry([...queue.filter((q) => q.request_id !== item.request_id), item]);
}

/** Merge a server snapshot (GET /egress/pending) into the queue. */
export function mergeConfirmations(
	queue: PendingEgressConfirmation[],
	items: PendingEgressConfirmation[]
): PendingEgressConfirmation[] {
	return items.reduce((acc, item) => addConfirmation(acc, item), queue);
}

/** Replace the queue with the authoritative server snapshot (after reconnect). */
export function replaceConfirmations(
	items: PendingEgressConfirmation[]
): PendingEgressConfirmation[] {
	return mergeConfirmations([], items);
}

export function resolveConfirmation(
	queue: PendingEgressConfirmation[],
	requestId: string
): PendingEgressConfirmation[] {
	return queue.filter((q) => q.request_id !== requestId);
}

/** Drop confirmations whose expiry is at or before `nowMs`. */
export function expireConfirmations(
	queue: PendingEgressConfirmation[],
	nowMs: number
): PendingEgressConfirmation[] {
	return queue.filter((q) => expiresMs(q) > nowMs);
}

export function secondsLeft(item: PendingEgressConfirmation, nowMs: number): number {
	const ms = expiresMs(item) - nowMs;
	if (!Number.isFinite(ms)) return 0;
	return Math.max(0, Math.floor(ms / 1000));
}
