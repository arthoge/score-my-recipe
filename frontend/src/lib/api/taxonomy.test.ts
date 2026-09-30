import { describe, it, expect, beforeEach, vi } from 'vitest';

// --- Module mocks (hoisted before the import of ./taxonomy) ---------------
// Mocking $lib/i18n avoids the real svelte-i18n initialization, and mocking
// $lib/offLink skips its top-level `await` so the taxonomy module loads
// synchronously and deterministically in the test runner.
vi.mock('$lib/i18n', () => ({
	getLocale: () => 'en-US'
}));

vi.mock('$lib/offLink', () => ({
	offLinks: { website: 'https://world-en.openfoodfacts.org' }
}));

// The OFF client is constructed at module load; stub it so the synonym-search
// fallback can be asserted without any network call.
const offMocks = vi.hoisted(() => ({
	getTaxonomySuggestions: vi.fn()
}));

vi.mock('@openfoodfacts/openfoodfacts-nodejs', () => ({
	OpenFoodFacts: class {
		apiv3 = { getTaxonomySuggestions: offMocks.getTaxonomySuggestions };
	}
}));

import { getMatchingTags } from './taxonomy';

/** Ingredients taxonomy returned by the (mocked) backend. */
const ingredientsBody = {
	ingredients: [
		{ id: 'en:apple', label: 'Apple', synonyms: ['pommes'], has_ef_score: true },
		{ id: 'en:tomato', label: 'Tomato', synonyms: [], has_ef_score: true },
		{ id: 'en:potato', label: 'Potato', synonyms: [], has_ef_score: false }
	]
};

/** Labels taxonomy returned by the (mocked) backend. */
const labelsBody = {
	labels: [
		{ id: 'en:organic', label: 'organic', synonyms: ['bio'] },
		{ id: 'en:vegan', label: 'vegan', synonyms: [] }
	]
};

/** Build a fake ok Response for the given JSON body. */
function jsonResponse(body: unknown) {
	return {
		ok: true,
		status: 200,
		statusText: 'OK',
		json: async () => body
	};
}

beforeEach(() => {
	offMocks.getTaxonomySuggestions.mockReset();

	// Route the taxonomy fetches to controlled JSON payloads.
	vi.stubGlobal(
		'fetch',
		vi.fn(async (url: string) => {
			if (url.includes('/v1/ingredients')) return jsonResponse(ingredientsBody);
			if (url.includes('/v1/labels')) return jsonResponse(labelsBody);
			if (url.includes('/v1/origins')) return jsonResponse({ origins: [] });
			throw new Error(`Unexpected fetch: ${url}`);
		})
	);
});

describe('getMatchingTags (known tagtypes)', () => {
	it('fetches the ingredients taxonomy with lang and synonyms', async () => {
		await getMatchingTags('ingredients', 'apple');
		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining('/v1/ingredients?lang=en&include_synonyms=true')
		);
	});

	it('returns suggestions whose label matches the query', async () => {
		const { suggestions } = await getMatchingTags('ingredients', 'apple');
		expect(suggestions.map((s) => s.id)).toContain('en:apple');
	});

	it('preserves the hasEfScore flag on ingredient suggestions', async () => {
		const { suggestions } = await getMatchingTags('ingredients', 'apple');
		expect(suggestions.find((s) => s.id === 'en:apple')?.hasEfScore).toBe(true);
	});

	it('does not populate matched_synonyms for a label-only match', async () => {
		// "apple" matches the label; none of the synonyms match -> nothing recorded.
		const { matched_synonyms } = await getMatchingTags('ingredients', 'apple');
		expect(matched_synonyms['en:apple']).toBeUndefined();
	});

	it('records the matched synonym under matched_synonyms', async () => {
		const { suggestions, matched_synonyms } = await getMatchingTags('ingredients', 'pommes');
		expect(suggestions.map((s) => s.id)).toContain('en:apple');
		expect(matched_synonyms['en:apple']).toEqual(['pommes']);
	});

	it('returns no suggestions for a non-matching query', async () => {
		const { suggestions, matched_synonyms } = await getMatchingTags('ingredients', 'zzz');
		expect(suggestions).toEqual([]);
		expect(matched_synonyms).toEqual({});
	});

	it('caps the number of suggestions to the limit', async () => {
		// "ato" matches both Tomato and Potato via their label.
		expect((await getMatchingTags('ingredients', 'ato', 30)).suggestions).toHaveLength(2);
		expect((await getMatchingTags('ingredients', 'ato', 1)).suggestions).toHaveLength(1);
	});

	it('routes the labels tagtype to the labels endpoint', async () => {
		const { suggestions } = await getMatchingTags('labels', 'bio');
		expect(suggestions.map((s) => s.id)).toContain('en:organic');
		expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/v1/labels'));
	});
});

describe('getMatchingTags (unknown tagtype fallback)', () => {
	it('falls back to the OpenFoodFacts suggestions API for unknown tagtypes', async () => {
		const fake = {
			suggestions: [{ id: 'en:beverage', label: 'Beverage', isInTaxonomy: true }],
			matched_synonyms: { 'en:beverage': ['drink'] }
		};
		offMocks.getTaxonomySuggestions.mockResolvedValue(fake);

		const result = await getMatchingTags('categories', 'drink', 5);

		expect(result).toBe(fake);
		expect(offMocks.getTaxonomySuggestions).toHaveBeenCalledWith({
			tagtype: 'categories',
			term: 'drink',
			lc: 'en',
			limit: '5',
			get_synonyms: '1'
		});
	});

	it('uses the default limit (30) when none is provided', async () => {
		offMocks.getTaxonomySuggestions.mockResolvedValue({ suggestions: [], matched_synonyms: {} });
		await getMatchingTags('categories', 'x');
		expect(offMocks.getTaxonomySuggestions).toHaveBeenCalledWith(
			expect.objectContaining({ limit: '30' })
		);
	});
});
