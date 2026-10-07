import { describe, expect, it } from 'vitest';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import { getPreparedWeight, getFinalPreparedWeight } from './preparedWeight';

/** A populated ingredient ready for editing preparation weights. */
function food(overrides: Partial<Ingredient> = {}): Ingredient {
	return { ...createEmptyIngredient(), name: 'Rice', weight: 100, ...overrides };
}

describe('prepared weight display', () => {
	it('tracks quantity when no preparation conversion is needed', () => {
		expect(getPreparedWeight(food())).toBe(100);
		expect(getPreparedWeight(food({ weight: 200 }))).toBe(200);
		for (const state of ['cooked', 'drained'] as const) {
			expect(getPreparedWeight(food({ state, preparationProfile: 'boiled' }))).toBe(100);
		}
	});

	it('does not invent cooking yields for raw ingredients', () => {
		expect(getPreparedWeight(food({ preparationProfile: 'boiled' }))).toBeNull();
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
		expect(getFinalPreparedWeight([food(), food({ preparationProfile: 'boiled' })])).toBeNull();
		for (const measuredPreparedWeightG of [0, -1, NaN, Infinity]) {
			expect(getFinalPreparedWeight([food({ measuredPreparedWeightG })])).toBeNull();
		}
	});
});
