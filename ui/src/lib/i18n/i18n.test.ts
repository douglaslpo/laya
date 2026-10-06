// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

import { describe, expect, it } from 'vitest';
import { areaDictionaries, translate, translations } from './index';
import { SUPPORTED_LOCALES } from './types';

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('i18n dictionaries', () => {
	const sources = { core: translations, ...areaDictionaries };

	for (const [name, dict] of Object.entries(sources)) {
		describe(name, () => {
			const base = Object.keys(dict.en).sort();

			for (const loc of SUPPORTED_LOCALES) {
				it(`${loc} has the same keys as en`, () => {
					expect(Object.keys(dict[loc]).sort()).toEqual(base);
				});

				it(`${loc} has no empty strings`, () => {
					const empty = Object.entries(dict[loc]).filter(([, v]) => !v.trim());
					expect(empty).toEqual([]);
				});

				it(`${loc} keeps the en placeholders`, () => {
					const mismatched = base.filter(
						(key) =>
							placeholders(dict[loc][key] ?? '').join() !== placeholders(dict.en[key]).join()
					);
					expect(mismatched).toEqual([]);
				});
			}
		});
	}

	it('area files do not redefine keys from another area', () => {
		const seen = new Map<string, string>();
		const clashes: string[] = [];
		for (const [name, dict] of Object.entries(areaDictionaries)) {
			for (const key of Object.keys(dict.en)) {
				const prev = seen.get(key);
				if (prev && prev !== name) clashes.push(`${key} (${prev}, ${name})`);
				seen.set(key, name);
			}
		}
		expect(clashes).toEqual([]);
	});
});

describe('translate', () => {
	it('interpolates params', () => {
		expect(translate('en', '__missing__', '{count} cards', { count: 3 })).toBe('3 cards');
	});

	it('falls back to en, then to the fallback text', () => {
		expect(translate('pt-BR', '__missing__', 'Fallback')).toBe('Fallback');
	});
});
