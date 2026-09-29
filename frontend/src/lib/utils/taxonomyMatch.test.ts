import { describe, it, expect } from 'vitest';
import { normalizeForMatch, findMatchingSuggestion } from './taxonomyMatch';
import type { TaxonomyItem } from '$lib/types/ingredient';

/** Build a taxonomy item with the given id, label and optional synonyms. */
function item(id: string, label: string, synonyms: string[] = []): TaxonomyItem {
	return { id, label, isInTaxonomy: true, synonyms };
}

describe('normalizeForMatch', () => {
	it('trims, lowercases and strips diacritics', () => {
		expect(normalizeForMatch('  Apple ')).toBe('apple');
		expect(normalizeForMatch('Crème')).toBe('creme');
		expect(normalizeForMatch('Élève')).toBe('eleve');
		expect(normalizeForMatch('façade')).toBe('facade');
	});

	it('returns an empty string for whitespace-only input', () => {
		expect(normalizeForMatch('   ')).toBe('');
	});
});

describe('findMatchingSuggestion', () => {
	const suggestions: TaxonomyItem[] = [
		item('en:apple', 'Apple', ['apples', 'pommes']),
		item('en:pear', 'Pear')
	];

	it('matches by label (case- and accent-insensitive)', () => {
		expect(findMatchingSuggestion('apple', suggestions)?.id).toBe('en:apple');
		expect(findMatchingSuggestion('APPLE', suggestions)?.id).toBe('en:apple');
	});

	it('matches by synonym', () => {
		expect(findMatchingSuggestion('pommes', suggestions)?.id).toBe('en:apple');
		expect(findMatchingSuggestion('apples', suggestions)?.id).toBe('en:apple');
	});

	it('matches an accented label typed without the accent', () => {
		const items = [item('en:creme-fraiche', 'Crème fraîche')];
		expect(findMatchingSuggestion('creme fraiche', items)?.id).toBe('en:creme-fraiche');
	});

	it('prefers a label match over a synonym match, regardless of order', () => {
		// 'apple' is a synonym of en:fake but the label of en:apple (listed last).
		const items = [item('en:fake', 'Fake', ['apple']), item('en:apple', 'Apple')];
		expect(findMatchingSuggestion('apple', items)?.id).toBe('en:apple');
	});

	it('returns undefined when no suggestion matches', () => {
		expect(findMatchingSuggestion('banana', suggestions)).toBeUndefined();
	});

	it('returns undefined for empty input', () => {
		expect(findMatchingSuggestion('  ', suggestions)).toBeUndefined();
	});
});
