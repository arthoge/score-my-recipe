import { describe, expect, it } from 'vitest';
import { replaceSelectedRecipeProducts } from './makeItBetter';
import type { MakeItBetterSuggestion } from '$lib/api/recipe';

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

const plainYogurt: MakeItBetterSuggestion = {
	ingredient: 'Plain yogurt',
	original: { id: 'plain-yogurt', name: 'Plain yogurt', nutriScore: 'B', greenScore: 'B' },
	suggested: {
		id: 'organic-plain-yogurt',
		name: 'Organic plain yogurt',
		nutriScore: 'A',
		greenScore: 'A'
	},
	improvements: []
};

describe('replaceSelectedRecipeProducts', () => {
	it('leaves the recipe unchanged when no products are selected', () => {
		const recipe = 'Chocolate yogurt\nPlain yogurt\nTomato';

		expect(replaceSelectedRecipeProducts(recipe, [])).toBe(recipe);
	});

	it('replaces only the explicitly selected products', () => {
		const recipe = 'Chocolate yogurt\nPlain yogurt\nTomato';

		expect(replaceSelectedRecipeProducts(recipe, [chocolateYogurt])).toBe(
			'Organic plain yogurt\nPlain yogurt\nTomato'
		);
	});

	it('can apply more than one selected replacement', () => {
		const recipe = 'Chocolate yogurt\nPlain yogurt\nTomato';

		expect(replaceSelectedRecipeProducts(recipe, [chocolateYogurt, plainYogurt])).toBe(
			'Organic plain yogurt\nOrganic plain yogurt\nTomato'
		);
	});
});
