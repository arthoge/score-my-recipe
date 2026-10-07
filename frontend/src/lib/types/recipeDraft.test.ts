import { describe, expect, it } from 'vitest';
import { createEmptyIngredient } from './ingredient';
import { getEditorRecipes, RECIPE_NAME_MAX_LENGTH } from './recipeDraft';

describe('getEditorRecipes', () => {
	it('bounds imported names for display without changing the import snapshot', () => {
		const name = `  ${'a'.repeat(RECIPE_NAME_MAX_LENGTH + 20)}  `;
		const imported = { id: 'long-name', name, ingredients: [] };
		const [recipe] = getEditorRecipes({ recipes: [imported] });
		expect(recipe.name).toBe('a'.repeat(RECIPE_NAME_MAX_LENGTH));
		expect(imported.name).toBe(name);
	});

	it('keeps the existing single-recipe navigation working', () => {
		const ingredient = { ...createEmptyIngredient(), name: 'Tomatoes', weight: 400 };
		const recipes = getEditorRecipes({ ingredients: [ingredient] });
		expect(recipes).toHaveLength(1);
		expect(recipes[0].portions).toBe(1);
		expect(recipes[0].ingredients[0]).toEqual(ingredient);
		expect(recipes[0].ingredients).toHaveLength(1);
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
		expect(recipes[0].ingredients[0]).not.toBe(recipes[1].ingredients[0]);
	});

	it('defaults imported ingredients to raw while preserving explicit cooked and drained states', () => {
		const ingredients = ['raw', 'cooked', 'drained'].map((name) => ({
			...createEmptyIngredient(),
			name
		}));
		ingredients[0].state = undefined;
		ingredients[1].state = 'cooked';
		ingredients[2].state = 'drained';
		const result = getEditorRecipes({ ingredients })[0].ingredients;
		expect(result.map((ingredient) => ingredient.state)).toEqual(['raw', 'cooked', 'drained']);
		expect(ingredients[0].state).toBeUndefined();
	});

	it('defaults imported preparation without replacing an explicit choice', () => {
		const ingredients = [createEmptyIngredient(), createEmptyIngredient()];
		ingredients[0].name = 'Tomatoes';
		ingredients[0].preparationProfile = undefined;
		ingredients[1].name = 'Rice';
		ingredients[1].preparationProfile = 'boiled';
		const result = getEditorRecipes({ ingredients })[0].ingredients;
		expect(result.map((ingredient) => ingredient.preparationProfile)).toEqual(['none', 'boiled']);
		expect(ingredients[0].preparationProfile).toBeUndefined();
	});

	it('keeps direct entry and empty imported recipes free of blank ingredient rows', () => {
		expect(getEditorRecipes({})[0].ingredients).toHaveLength(0);
		expect(getEditorRecipes({ recipes: [] })[0].ingredients).toHaveLength(0);
		expect(
			getEditorRecipes({ recipes: [{ id: 'empty', name: 'Empty', ingredients: [] }] })[0]
				.ingredients
		).toHaveLength(0);
	});
});
