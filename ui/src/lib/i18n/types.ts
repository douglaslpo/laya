// Copyright 2026 Aayush Chawla
// SPDX-License-Identifier: Apache-2.0

export type SupportedLocale = 'pt-BR' | 'en' | 'es';

export const SUPPORTED_LOCALES: SupportedLocale[] = ['pt-BR', 'en', 'es'];

/** One dictionary per locale; every locale must carry the same keys. */
export type LocaleDict = Record<SupportedLocale, Record<string, string>>;
