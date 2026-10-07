import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
	apiIngredientToIngredient,
	apiIngredientsToIngredients,
	ingredientToGreenScoreInput,
	parseRecipeText,
	computeGreenScore,
	getOrigins,
	type RecipeIngredient
} from './recipe';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import type { IngredientsList } from '$lib/types/ingredientsList';

/** Build a fully-populated RecipeIngredient as returned by the parse endpoint. */
function apiIngredient(overrides: Partial<RecipeIngredient> = {}): RecipeIngredient {
	return {
		taxonomy_id: 'en:apple',
		is_in_taxonomy: true,
		codified_ingredient: 'apple',
		quantity_g: 150,
		origins: { id: 'en:france', label: 'France', isInTaxonomy: true },
		labels: [{ id: 'en:organic', label: 'organic', isInTaxonomy: true }],
		...overrides
	};
}

describe('apiIngredientToIngredient', () => {
	it('maps the codified ingredient name and quantity', () => {
		const result = apiIngredientToIngredient(apiIngredient());
		expect(result.name).toBe('apple');
		expect(result.weight).toBe(150);
	});

	it('generates a new ingredient id', () => {
		const result = apiIngredientToIngredient(apiIngredient());
		expect(result.id).toMatch(/^ingredient-/);
		expect(result.id).not.toBe('en:apple');
	});

	it('builds the codified ingredient from taxonomy_id and is_in_taxonomy', () => {
		expect(apiIngredientToIngredient(apiIngredient()).codifiedIngredient).toEqual({
			id: 'en:apple',
			label: 'apple',
			isInTaxonomy: true
		});
	});

	it('falls back to codified_ingredient for the id when taxonomy_id is null', () => {
		const result = apiIngredientToIngredient(
			apiIngredient({ taxonomy_id: null, codified_ingredient: 'apple' })
		);
		expect(result.codifiedIngredient?.id).toBe('apple');
		expect(result.codifiedIngredient?.label).toBe('apple');
	});

	it('falls back to codified_ingredient for the id when taxonomy_id is undefined', () => {
		const result = apiIngredientToIngredient(apiIngredient({ taxonomy_id: undefined }));
		expect(result.codifiedIngredient?.id).toBe('apple');
	});

	it('maps origins to a single origin (or null)', () => {
		expect(apiIngredientToIngredient(apiIngredient()).origin).toEqual({
			id: 'en:france',
			label: 'France',
			isInTaxonomy: true
		});
		expect(apiIngredientToIngredient(apiIngredient({ origins: null })).origin).toBeNull();
	});

	it('defaults labels to an empty array when absent', () => {
		expect(apiIngredientToIngredient(apiIngredient({ labels: null })).labels).toEqual([]);
	});

	it('defaults weight to null when quantity_g is absent', () => {
		expect(apiIngredientToIngredient(apiIngredient({ quantity_g: null })).weight).toBeNull();
	});

	it('keeps a zero quantity as zero (not null)', () => {
		expect(apiIngredientToIngredient(apiIngredient({ quantity_g: 0 })).weight).toBe(0);
	});

	it('initializes isFreshPlant and isInSeason to false', () => {
		const result = apiIngredientToIngredient(apiIngredient());
		expect(result.isFreshPlant).toBe(false);
		expect(result.isInSeason).toBe(false);
	});
});

describe('apiIngredientsToIngredients', () => {
	it('maps each api ingredient and preserves order', () => {
		const result = apiIngredientsToIngredients([
			apiIngredient({ codified_ingredient: 'apple', taxonomy_id: 'en:apple' }),
			apiIngredient({ codified_ingredient: 'flour', taxonomy_id: 'en:wheat-flour' })
		]);
		expect(result).toHaveLength(2);
		expect(result.map((i) => i.name)).toEqual(['apple', 'flour']);
		expect(result.map((i) => i.codifiedIngredient?.id)).toEqual(['en:apple', 'en:wheat-flour']);
		// Each gets a distinct generated id.
		expect(result[0].id).not.toBe(result[1].id);
	});

	it('returns an empty list for no ingredients', () => {
		expect(apiIngredientsToIngredients([])).toEqual([]);
	});
});

describe('ingredientToGreenScoreInput', () => {
	/** Build a frontend Ingredient. */
	function ingredient(overrides: Partial<Ingredient> = {}): Ingredient {
		return {
			id: 'i1',
			name: 'apple',
			weight: 150,
			codifiedIngredient: { id: 'en:apple', label: 'Apple', isInTaxonomy: true },
			labels: [{ id: 'en:organic', label: 'organic', isInTaxonomy: true }],
			isFreshPlant: false,
			isInSeason: false,
			origin: { id: 'en:france', label: 'France', isInTaxonomy: true },
			...overrides
		};
	}

	it('maps all fields through to the API payload', () => {
		expect(ingredientToGreenScoreInput(ingredient())).toEqual({
			id: 'i1',
			name: 'apple',
			weight: 150,
			codifiedIngredient: { id: 'en:apple', label: 'Apple', isInTaxonomy: true },
			labels: [{ id: 'en:organic', label: 'organic', isInTaxonomy: true }],
			isFreshPlant: false,
			isInSeason: false,
			origin: { id: 'en:france', label: 'France', isInTaxonomy: true }
		});
	});

	it('keeps the codifiedIngredient when present', () => {
		const codified = { id: 'en:apple', label: 'Apple', isInTaxonomy: true };
		expect(
			ingredientToGreenScoreInput(ingredient({ codifiedIngredient: codified })).codifiedIngredient
		).toBe(codified);
	});

	it('synthesizes a non-taxonomy codifiedIngredient from the name when absent', () => {
		expect(
			ingredientToGreenScoreInput(ingredient({ codifiedIngredient: null, name: 'custom thing' }))
				.codifiedIngredient
		).toEqual({ id: 'custom thing', label: 'custom thing', isInTaxonomy: false });
	});

	it("defaults a null weight to 0 to satisfy the API's non-null weight schema", () => {
		expect(ingredientToGreenScoreInput(ingredient({ weight: null })).weight).toBe(0);
	});

	it('preserves an explicit zero weight', () => {
		expect(ingredientToGreenScoreInput(ingredient({ weight: 0 })).weight).toBe(0);
	});

	it('passes labels and origin through by reference', () => {
		const labels = [{ id: 'en:organic', label: 'organic', isInTaxonomy: true }];
		const origin = { id: 'en:france', label: 'France', isInTaxonomy: true };
		const result = ingredientToGreenScoreInput(ingredient({ labels, origin }));
		expect(result.labels).toBe(labels);
		expect(result.origin).toBe(origin);
	});
});

// ---------------------------------------------------------------------------
// Fetcher tests: parseRecipeText, computeGreenScore, getOrigins
// ---------------------------------------------------------------------------

/** Build a non-empty frontend Ingredient suitable for the green-score payload. */
function namedIngredient(
	id: string,
	name: string,
	overrides: Partial<Ingredient> = {}
): Ingredient {
	return {
		id,
		name,
		weight: 100,
		codifiedIngredient: { id: `en:${name}`, label: name, isInTaxonomy: true },
		labels: [],
		isFreshPlant: false,
		isInSeason: false,
		origin: null,
		...overrides
	};
}

/** Minimal fetch Response stub for successful requests. */
function okResponse(body: unknown) {
	return {
		ok: true,
		status: 200,
		statusText: 'OK',
		json: async () => body
	};
}

/** Minimal fetch Response stub for error responses. */
function errorResponse(status: number, statusText: string) {
	return {
		ok: false,
		status,
		statusText
	};
}

describe('parseRecipeText', () => {
	beforeEach(() => {
		vi.stubGlobal('fetch', vi.fn());
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('sends a POST with text and lang as the JSON body', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ ingredients: [] }) as Response);

		await parseRecipeText('200g apple', 'fr');

		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toContain('/v1/parse_text');
		expect(init?.method).toBe('POST');
		expect(init?.headers).toEqual({ 'Content-Type': 'application/json' });
		expect(JSON.parse(init?.body as string)).toEqual({ text: '200g apple', lang: 'fr' });
	});

	it('returns the parsed ingredients from the response', async () => {
		const parsed = { ingredients: [apiIngredient()] };
		vi.mocked(fetch).mockResolvedValue(okResponse(parsed) as Response);

		const result = await parseRecipeText('apple', 'en');
		expect(result).toEqual(parsed);
	});

	it('throws an Error including status and statusText on a non-ok response', async () => {
		vi.mocked(fetch).mockResolvedValue(errorResponse(422, 'Unprocessable Entity') as Response);

		await expect(parseRecipeText('bad', 'en')).rejects.toThrow('Error 422: Unprocessable Entity');
	});
});

describe('computeGreenScore', () => {
	beforeEach(() => {
		vi.stubGlobal('fetch', vi.fn());
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('returns the green-score response on success', async () => {
		const scoreResponse = {
			numericScore: 76.38,
			letterGrade: 'A',
			missingIngredientIds: []
		};
		vi.mocked(fetch).mockResolvedValue(okResponse(scoreResponse) as Response);

		const result = await computeGreenScore([namedIngredient('i1', 'apple')]);
		expect(result).toEqual(scoreResponse);
	});

	it('filters out empty ingredients before sending them', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		const ingredients: IngredientsList = [namedIngredient('i1', 'apple'), createEmptyIngredient()];
		await computeGreenScore(ingredients);

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
		expect(body.ingredients).toHaveLength(1);
		expect(body.ingredients[0].id).toBe('i1');
	});

	it('sends no ingredients when the list contains only empty lines', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		await computeGreenScore([createEmptyIngredient(), createEmptyIngredient()]);

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
		expect(body.ingredients).toEqual([]);
	});

	it('always sets accountedWeights to "scorable"', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		await computeGreenScore([namedIngredient('i1', 'apple')]);

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
		expect(body.accountedWeights).toBe('scorable');
	});

	it('sends country as null when no country is provided', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		await computeGreenScore([namedIngredient('i1', 'apple')]);

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
		expect(body.country).toBeNull();
	});

	it('sends the country code when provided', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		await computeGreenScore([namedIngredient('i1', 'apple')], { country: 'FR' });

		const body = JSON.parse(fetchMock.mock.calls[0][1]?.body as string);
		expect(body.country).toBe('FR');
	});

	it('passes the abort signal through to fetch', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ missingIngredientIds: [] }) as Response);

		const controller = new AbortController();
		await computeGreenScore([namedIngredient('i1', 'apple')], { signal: controller.signal });

		expect(fetchMock.mock.calls[0][1]?.signal).toBe(controller.signal);
	});

	it('throws an Error including status and statusText on a non-ok response', async () => {
		vi.mocked(fetch).mockResolvedValue(errorResponse(500, 'Internal Server Error') as Response);

		await expect(computeGreenScore([namedIngredient('i1', 'apple')])).rejects.toThrow(
			'Error 500: Internal Server Error'
		);
	});
});

describe('getOrigins', () => {
	beforeEach(() => {
		vi.stubGlobal('fetch', vi.fn());
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('returns the origins array from the response', async () => {
		const origins = [
			{ id: 'en:france', label: 'France' },
			{ id: 'en:spain', label: 'Spain' }
		];
		vi.mocked(fetch).mockResolvedValue(okResponse({ origins }) as Response);

		const result = await getOrigins('en');
		expect(result).toEqual(origins);
	});

	it('encodes the lang parameter in the URL', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ origins: [] }) as Response);

		await getOrigins('en-US');

		expect(fetchMock.mock.calls[0][0]).toContain('/v1/origins?lang=en-US');
	});

	it('URL-encodes special characters in the lang parameter', async () => {
		const fetchMock = vi.mocked(fetch);
		fetchMock.mockResolvedValue(okResponse({ origins: [] }) as Response);

		await getOrigins('zh CN');

		// A space must be percent-encoded as %20.
		expect(fetchMock.mock.calls[0][0]).toContain('/v1/origins?lang=zh%20CN');
	});

	it('throws an Error including status and statusText on a non-ok response', async () => {
		vi.mocked(fetch).mockResolvedValue(errorResponse(503, 'Service Unavailable') as Response);

		await expect(getOrigins('en')).rejects.toThrow('Error 503: Service Unavailable');
	});
});

it('does not reuse taxonomy environmental data after a manual correspondence is cleared', () => {
	const ingredient = {
		...createEmptyIngredient(),
		name: 'Tomatoes',
		weight: 100,
		codifiedIngredient: { id: 'en:tomato', label: 'Tomatoes', isInTaxonomy: true },
		referenceSource: 'manual'
	};
	expect(ingredientToGreenScoreInput(ingredient).codifiedIngredient).toEqual({
		id: null,
		label: 'Tomatoes',
		isInTaxonomy: false
	});
	expect(ingredientToGreenScoreInput(ingredient)).not.toHaveProperty('agribalyseCode');
});
