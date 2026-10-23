// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';
import {
	addConfirmation,
	expireConfirmations,
	isPendingConfirmation,
	mergeConfirmations,
	replaceConfirmations,
	resolveConfirmation,
	secondsLeft,
	type PendingEgressConfirmation
} from './pendingConfirmations';

function item(id: string, expiresAt: string): PendingEgressConfirmation {
	return {
		request_id: id,
		origin: 'mcp',
		platform: 'gmail',
		action_type: 'send_email',
		space_id: null,
		connection_id: null,
		preview: { summary: `s-${id}`, details: {}, warnings: [], estimated_impact: 'low' },
		created_at: '2026-09-29T12:00:00Z',
		expires_at: expiresAt
	};
}

describe('pendingConfirmations', () => {
	it('adds and sorts by expires_at', () => {
		let q = addConfirmation([], item('b', '2026-09-29T12:05:00Z'));
		q = addConfirmation(q, item('a', '2026-09-29T12:03:00Z'));
		expect(q.map((i) => i.request_id)).toEqual(['a', 'b']);
	});

	it('dedupes by request_id, keeping the latest payload', () => {
		let q = addConfirmation([], item('a', '2026-09-29T12:03:00Z'));
		const updated = { ...item('a', '2026-09-29T12:03:00Z'), platform: 'slack' };
		q = addConfirmation(q, updated);
		expect(q).toHaveLength(1);
		expect(q[0].platform).toBe('slack');
	});

	it('resolves by request_id', () => {
		const q = [item('a', '2026-09-29T12:03:00Z'), item('b', '2026-09-29T12:04:00Z')];
		expect(resolveConfirmation(q, 'a').map((i) => i.request_id)).toEqual(['b']);
		expect(resolveConfirmation(q, 'missing')).toHaveLength(2);
	});

	it('expires items at or before now', () => {
		const now = Date.parse('2026-09-29T12:04:00Z');
		const q = [item('a', '2026-09-29T12:03:00Z'), item('b', '2026-09-29T12:04:00Z'), item('c', '2026-09-29T12:05:00Z')];
		expect(expireConfirmations(q, now).map((i) => i.request_id)).toEqual(['c']);
	});

	it('shows both requests created while disconnected after reconnect (CA-07)', () => {
		const snapshot = [item('x', '2026-09-29T12:05:00Z'), item('y', '2026-09-29T12:02:00Z')];
		const q = replaceConfirmations(snapshot);
		expect(q.map((i) => i.request_id)).toEqual(['y', 'x']);
	});

	it('merge keeps existing items and dedupes snapshot entries', () => {
		const q = mergeConfirmations([item('a', '2026-09-29T12:03:00Z')], [
			item('a', '2026-09-29T12:03:00Z'),
			item('b', '2026-09-29T12:01:00Z')
		]);
		expect(q.map((i) => i.request_id)).toEqual(['b', 'a']);
	});

	it('computes seconds left, never negative', () => {
		const it0 = item('a', '2026-09-29T12:05:00Z');
		expect(secondsLeft(it0, Date.parse('2026-09-29T12:04:30Z'))).toBe(30);
		expect(secondsLeft(it0, Date.parse('2026-09-29T12:06:00Z'))).toBe(0);
	});

	it('validates payload shape', () => {
		expect(isPendingConfirmation(item('a', '2026-09-29T12:05:00Z'))).toBe(true);
		expect(isPendingConfirmation({ request_id: '' })).toBe(false);
		expect(isPendingConfirmation(null)).toBe(false);
	});
});
