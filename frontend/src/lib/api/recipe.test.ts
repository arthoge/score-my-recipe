import { describe, it, expect } from 'vitest';
import {
	apiIngredientToIngredient,
	apiIngredientsToIngredients,
	ingredientToGreenScoreInput,
	type RecipeIngredient
} from './recipe';
import type { Ingredient } from '$lib/types/ingredient';

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

	it('defaults a null weight to 0 (the backend treats 0 as missing)', () => {
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
