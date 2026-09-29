/**
 * Exact-match helpers for the tag autocomplete.
 *
 * Used by the tag editor's free-typed save path: a value that exactly matches a
 * proposed suggestion (by label or synonym) is registered as if the user had
 * clicked it, keeping the taxonomy id in sync instead of resetting it to null.
 */
import type { TaxonomyItem } from '$lib/types/ingredient';

/**
 * Normalize a string for exact (case- and accent-insensitive) comparison.
 *
 * Trims, lowercases, and strips combining diacritics (NFD decomposition), so a
 * free-typed value matches a suggestion the same way the Fuse search surfaces
 * it (which runs with `ignoreDiacritics: true`).
 *
 * @param value - The string to normalize.
 * @returns The normalized string.
 */
export function normalizeForMatch(value: string): string {
	return value
		.trim()
		.toLowerCase()
		.normalize('NFD')
		.replace(/[\u0300-\u036f]/g, '');
}

/**
 * Find a suggestion whose label (first) or synonym (then) exactly matches the
 * given value, ignoring case and diacritics.
 *
 * Label matches take priority over synonym matches so the canonical item wins
 * when a value is both an item's label and another item's synonym.
 *
 * @param value - The free-typed value to match.
 * @param suggestions - The currently proposed taxonomy items.
 * @returns The matching item, or `undefined` when no suggestion matches.
 */
export function findMatchingSuggestion(
	value: string,
	suggestions: TaxonomyItem[]
): TaxonomyItem | undefined {
	const needle = normalizeForMatch(value);
	if (needle === '') return undefined;
	const byLabel = suggestions.find((item) => normalizeForMatch(item.label) === needle);
	if (byLabel) return byLabel;
	return suggestions.find((item) =>
		item.synonyms?.some((synonym) => normalizeForMatch(synonym) === needle)
	);
}
