import { describe, it, expect } from 'vitest';
import {
	removeIngredientFromList,
	addEmptyIngredientIfNeeded,
	countNonEmptyIngredients
} from './ingredientsList';
import { createEmptyIngredient, isIngredientNotEmpty, type Ingredient } from './ingredient';

/** Build a non-empty ingredient with the given id and name. */
function named(id: string, name: string, overrides: Partial<Ingredient> = {}): Ingredient {
	return {
		id,
		name,
		weight: null,
		codifiedIngredient: null,
		labels: [],
		isFreshPlant: false,
		isInSeason: false,
		origin: null,
		...overrides
	};
}

describe('removeIngredientFromList', () => {
	it('removes the ingredient with the matching id', () => {
		const list = [named('i1', 'apple'), named('i2', 'flour')];
		expect(removeIngredientFromList(list, 'i1').map((i) => i.id)).toEqual(['i2']);
	});

	it('returns a new array and does not mutate the input', () => {
		const list = [named('i1', 'apple'), named('i2', 'flour')];
		const result = removeIngredientFromList(list, 'i1');
		expect(result).not.toBe(list);
		expect(list.map((i) => i.id)).toEqual(['i1', 'i2']);
	});

	it('leaves the list content unchanged when no id matches', () => {
		const list = [named('i1', 'apple'), named('i2', 'flour')];
		expect(removeIngredientFromList(list, 'missing').map((i) => i.id)).toEqual(['i1', 'i2']);
	});

	it('replaces an emptied list with a single fresh empty ingredient', () => {
		const result = removeIngredientFromList([named('i1', 'apple')], 'i1');
		expect(result).toHaveLength(1);
		expect(isIngredientNotEmpty(result[0])).toBe(false);
		// The new line is fresh: it does not reuse the removed id.
		expect(result[0].id).not.toBe('i1');
	});
});

describe('addEmptyIngredientIfNeeded', () => {
	it('appends a new empty ingredient when the last one is non-empty', () => {
		const result = addEmptyIngredientIfNeeded([named('i1', 'apple')]);
		expect(result).toHaveLength(2);
		expect(isIngredientNotEmpty(result[0])).toBe(true);
		expect(isIngredientNotEmpty(result[1])).toBe(false);
	});

	it('returns the same array when the last ingredient is already empty', () => {
		const list = [named('i1', 'apple'), createEmptyIngredient()];
		expect(addEmptyIngredientIfNeeded(list)).toBe(list);
	});

	it('returns the same array when the list is empty', () => {
		const list: Ingredient[] = [];
		expect(addEmptyIngredientIfNeeded(list)).toBe(list);
		expect(addEmptyIngredientIfNeeded(list)).toHaveLength(0);
	});

	it('does not mutate the input when appending', () => {
		const list = [named('i1', 'apple')];
		addEmptyIngredientIfNeeded(list);
		expect(list).toHaveLength(1);
	});
});

describe('countNonEmptyIngredients', () => {
	it('counts only ingredients with content', () => {
		const list = [named('i1', 'apple'), createEmptyIngredient(), named('i2', 'flour')];
		expect(countNonEmptyIngredients(list)).toBe(2);
	});

	it('returns 0 for a list with only empty ingredients', () => {
		expect(countNonEmptyIngredients([createEmptyIngredient()])).toBe(0);
	});

	it('returns 0 for an empty list', () => {
		expect(countNonEmptyIngredients([])).toBe(0);
	});
});
