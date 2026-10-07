import { describe, expect, it } from 'vitest';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import {
	getPreparedWeight,
	getFinalPreparedWeight,
	preparedWeightInputKey
} from './preparedWeight';

/** A populated ingredient ready for editing preparation weights. */
function food(overrides: Partial<Ingredient> = {}): Ingredient {
	return { ...createEmptyIngredient(), name: 'Rice', weight: 100, ...overrides };
}

describe('prepared weight display', () => {
	it('uses a current API suggestion, preserves measured weights, and rejects stale suggestions', () => {
		const ingredient = food({ ciqualCode: '9119', preparationProfile: 'boiled' });
		ingredient.preparedWeightSuggestion = {
			inputKey: preparedWeightInputKey(ingredient),
			weightG: 298,
			yieldFactor: 2.98,
			source: null
		};
		expect(getPreparedWeight(ingredient)).toBe(298);
		expect(getFinalPreparedWeight([ingredient])).toBe(298);
		expect(getPreparedWeight({ ...ingredient, measuredPreparedWeightG: 275 })).toBe(275);
		for (const change of [
			{ weight: 200 },
			{ ciqualCode: '9102' },
			{ preparationProfile: 'steamed' as const },
			{ barcode: '123' },
			{ name: 'Different ingredient' }
		]) {
			expect(getPreparedWeight({ ...ingredient, ...change })).toBe(change.weight ?? 100);
		}
		expect(getPreparedWeight({ ...ingredient, state: 'cooked' })).toBe(100);
	});
	it('tracks quantity when no preparation conversion is needed', () => {
		expect(getPreparedWeight(food())).toBe(100);
		expect(getPreparedWeight(food({ weight: 200 }))).toBe(200);
		for (const state of ['cooked', 'drained'] as const) {
			expect(getPreparedWeight(food({ state, preparationProfile: 'boiled' }))).toBe(100);
		}
	});

	it('falls back to quantity when no cooking yield is available', () => {
		expect(getPreparedWeight(food({ preparationProfile: 'boiled' }))).toBe(100);
	});

	it('preserves measured overrides and restores suggestions when cleared', () => {
		expect(getPreparedWeight(food({ weight: 200, measuredPreparedWeightG: 150 }))).toBe(150);
		expect(getPreparedWeight(food({ measuredPreparedWeightG: null }))).toBe(100);
	});

	it('sums complete rows and ignores the empty insertion row', () => {
		expect(
			getFinalPreparedWeight([
				food(),
				food({ measuredPreparedWeightG: 250 }),
				createEmptyIngredient()
			])
		).toBe(350);
	});

	it('does not show a partial or invalid total', () => {
		expect(getFinalPreparedWeight([createEmptyIngredient()])).toBeNull();
		expect(getFinalPreparedWeight([food(), food({ weight: null })])).toBeNull();
		for (const measuredPreparedWeightG of [0, -1, NaN, Infinity]) {
			expect(getFinalPreparedWeight([food({ measuredPreparedWeightG })])).toBeNull();
		}
	});
});
