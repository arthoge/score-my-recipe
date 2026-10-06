import { describe, expect, it } from 'vitest';
import { createEmptyIngredient } from './ingredient';
import { getEditorRecipes } from './recipeDraft';

describe('getEditorRecipes', () => {
	it('keeps the existing single-recipe navigation working', () => {
		const ingredient = { ...createEmptyIngredient(), name: 'Tomatoes', weight: 400 };
		const recipes = getEditorRecipes({ ingredients: [ingredient] });
		expect(recipes).toHaveLength(1);
		expect(recipes[0].portions).toBeNull();
		expect(recipes[0].finalWeightG).toBeNull();
		expect(recipes[0].ingredients[0]).toEqual(ingredient);
		expect(recipes[0].ingredients).toHaveLength(2);
	});

	it('preserves batch order and prevents edits leaking between recipes or back into imports', () => {
		const ingredient = { ...createEmptyIngredient(), name: 'Tomatoes', weight: null };
		const imported = [
			{ id: 'salad', name: 'Tomato salad', ingredients: [ingredient] },
			{ id: 'soup', name: 'Tomato soup', ingredients: [ingredient] }
		];
		const recipes = getEditorRecipes({ recipes: imported });
		expect(recipes.map((recipe) => recipe.name)).toEqual(['Tomato salad', 'Tomato soup']);
		recipes[0].ingredients[0].weight = 200;
		expect(recipes[1].ingredients[0].weight).toBeNull();
		expect(imported[0].ingredients[0].weight).toBeNull();
		expect(recipes[0].ingredients.at(-1)?.id).not.toBe(recipes[1].ingredients.at(-1)?.id);
	});

	it('provides an empty editable row for direct entry and empty imported recipes', () => {
		expect(getEditorRecipes({})[0].ingredients).toHaveLength(1);
		expect(getEditorRecipes({ recipes: [] })[0].ingredients).toHaveLength(1);
		expect(
			getEditorRecipes({ recipes: [{ id: 'empty', name: 'Empty', ingredients: [] }] })[0]
				.ingredients
		).toHaveLength(1);
	});
});
