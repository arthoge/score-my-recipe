import { describe, expect, it } from 'vitest';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import { canAutoScore, ingredientCellErrors } from './ingredientEditor';

/** An editable ingredient with a selected environmental database reference. */
function validIngredient(): Ingredient {
	return {
		...createEmptyIngredient(),
		name: 'Tomatoes',
		weight: 400,
		codifiedIngredient: { id: 'en:tomato', label: 'Tomatoes', isInTaxonomy: true }
	};
}

describe('automatic score form validation', () => {
	it('blocks a reference explicitly marked as lacking environmental impact data', () => {
		const reference = { id: 'en:unknown', label: 'Unknown', isInTaxonomy: true, hasEfScore: false };
		expect(canAutoScore([{ ...validIngredient(), codifiedIngredient: reference }])).toBe(false);
	});
	it('scores valid recipes without treating the trailing insertion row as an error', () => {
		expect(canAutoScore([validIngredient(), createEmptyIngredient()])).toBe(true);
		expect(Object.values(ingredientCellErrors(createEmptyIngredient())).some(Boolean)).toBe(false);
		expect(canAutoScore([createEmptyIngredient()])).toBe(false);
	});

	it.each([null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY])(
		'does not send an invalid quantity (%s) to the score API',
		(weight) => {
			expect(canAutoScore([{ ...validIngredient(), weight }])).toBe(false);
		}
	);

	it('blocks the whole recipe when any populated row lacks its name or reference', () => {
		expect(canAutoScore([validIngredient(), { ...validIngredient(), name: '' }])).toBe(false);
		expect(
			canAutoScore([validIngredient(), { ...validIngredient(), codifiedIngredient: null }])
		).toBe(false);
		expect(
			canAutoScore([
				{
					...validIngredient(),
					codifiedIngredient: { id: null, label: 'Unknown', isInTaxonomy: false }
				}
			])
		).toBe(false);
	});

	it('keeps planned preparation fields optional, but validates entered weights', () => {
		expect(
			canAutoScore([{ ...validIngredient(), state: 'raw', ciqualCode: '1234' }], 4, 1200)
		).toBe(true);
		expect(canAutoScore([{ ...validIngredient(), measuredPreparedWeightG: -1 }])).toBe(false);
		expect(canAutoScore([validIngredient()], 2.5)).toBe(false);
		expect(canAutoScore([validIngredient()], 4, 0)).toBe(false);
	});

	it('treats preparation-only rows as incomplete drafts rather than ignoring them', () => {
		expect(canAutoScore([validIngredient(), { ...createEmptyIngredient(), state: 'cooked' }])).toBe(
			false
		);
	});
});
