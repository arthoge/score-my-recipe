import { describe, expect, it } from 'vitest';
import { replaceSelectedRecipeProducts } from './makeItBetter';
import type { MakeItBetterSuggestion } from '$lib/api/recipe';
import type { Ingredient } from '$lib/types/ingredient';

const chocolateYogurt: MakeItBetterSuggestion = {
	ingredient: 'Chocolate yogurt',
	original: { id: 'chocolate-yogurt', name: 'Chocolate yogurt', nutriScore: 'D', greenScore: 'D' },
	suggested: {
		id: 'organic-plain-yogurt',
		name: 'Organic plain yogurt',
		nutriScore: 'A',
		greenScore: 'A'
	},
	improvements: []
};

function makeIngredient(name: string): Ingredient {
	return {
		id: name,
		name: name,
		weight: null,
		codifiedIngredient: null,
		labels: [],
		isFreshPlant: false,
		isInSeason: false,
		origin: null,
		state: 'raw',
		preparationProfile: 'none'
	};
}

describe('replaceSelectedRecipeProducts', () => {
	it('leaves the recipe unchanged when no products are selected', () => {
		const ingredients = [makeIngredient('Chocolate yogurt'), makeIngredient('Tomato')];
		replaceSelectedRecipeProducts(ingredients, []);
		expect(ingredients[0].name).toBe('Chocolate yogurt');
	});

	it('replaces only the explicitly selected products', () => {
		const ingredients = [makeIngredient('Chocolate yogurt'), makeIngredient('Tomato')];
		replaceSelectedRecipeProducts(ingredients, [chocolateYogurt]);
		expect(ingredients[0].name).toBe('Organic plain yogurt');
		expect(ingredients[1].name).toBe('Tomato');
	});
});
