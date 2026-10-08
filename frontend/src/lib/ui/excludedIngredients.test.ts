import { describe, expect, it } from 'vitest';
import type { NutritionAnalysis } from '$lib/api/nutritionAnalysis';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import {
	greenExclusionReasons,
	nutritionExclusionReasons,
	exclusionTarget
} from './excludedIngredients';

/** An ingredient with both a product and a generic reference to exercise source selection. */
function ingredient(changes: Partial<Ingredient> = {}): Ingredient {
	return {
		...createEmptyIngredient(),
		id: 'cheese',
		name: 'Cheese',
		weight: 100,
		ciqualCode: '12118',
		ciqualName: 'Emmental cheese, grated, from cow’s milk',
		barcode: '123',
		productName: 'Grated Emmental',
		...changes
	};
}

/** Supply only the API fields used by the exclusion explanation. */
function analysis(code = 'nutrients_missing', source?: string): NutritionAnalysis {
	return {
		excluded_ingredients: [
			{ ingredient_id: 'cheese', ingredient_name: 'Cheese', prepared_weight_g: 100 }
		],
		diagnostics: [{ ingredient_id: 'cheese', code, fields: ['sugars'] }],
		ingredients: source ? [{ ingredient_id: 'cheese', source }] : []
	} as NutritionAnalysis;
}

describe('excluded-reference explanations', () => {
	it('names the Ciqual fallback actually missing data rather than the selected product', () => {
		expect(
			nutritionExclusionReasons([ingredient()], analysis('nutrients_missing', 'CIQUAL-2025'))
		).toEqual([
			{ kind: 'ciqual', name: 'Emmental cheese, grated, from cow’s milk', ingredientId: 'cheese' }
		]);
	});

	it('directs OFF failures to the product in the table', () => {
		expect(nutritionExclusionReasons([ingredient()], analysis())).toEqual([
			{ kind: 'off', name: 'Grated Emmental', ingredientId: 'cheese' }
		]);
		expect(nutritionExclusionReasons([ingredient()], analysis('product_unavailable'))).toEqual([
			{ kind: 'off_unavailable', name: 'Grated Emmental', ingredientId: 'cheese' }
		]);
	});

	it('asks for a reference when none was selected rather than claiming it lacks data', () => {
		const row = ingredient({ barcode: undefined, ciqualCode: undefined });
		expect(nutritionExclusionReasons([row], analysis('nutrition_reference_missing'))).toEqual([
			{ kind: 'select_ciqual', name: 'Cheese', ingredientId: 'cheese' }
		]);
		expect(greenExclusionReasons([row], ['cheese'])).toEqual([
			{ kind: 'select_agribalyse', name: 'Cheese', ingredientId: 'cheese' }
		]);
	});

	it.each([
		['zero_quantity', 'quantity'],
		['quantity_missing', 'quantity'],
		['unsupported_preparation', 'preparation'],
		['prepared_reference_required', 'state']
	])('gives the appropriate action for %s', (code, kind) => {
		expect(nutritionExclusionReasons([ingredient()], analysis(code))).toEqual([
			{ kind, name: 'Cheese', ingredientId: 'cheese' }
		]);
	});

	it('keeps separate navigation targets for repeated references and ignores included ingredients', () => {
		const row = ingredient({ agribalyseCode: '123', agribalyseName: 'Emmental' });
		expect(
			greenExclusionReasons(
				[
					row,
					{ ...row, id: 'second' },
					ingredient({ id: 'included', agribalyseName: 'Other cheese' })
				],
				['cheese', 'second']
			)
		).toEqual([
			{ kind: 'agribalyse', name: 'Emmental', ingredientId: 'cheese' },
			{ kind: 'agribalyse', name: 'Emmental', ingredientId: 'second' }
		]);
	});

	it('uses the reported ingredient name if an excluded row is unavailable', () => {
		expect(nutritionExclusionReasons([], analysis('zero_quantity'))).toEqual([
			{ kind: 'quantity', name: 'Cheese', ingredientId: 'cheese' }
		]);
		expect(nutritionExclusionReasons([ingredient()], null)).toEqual([]);
	});
});

it('opens the right details modal and reference input in a recipe with repeated ingredient ids', () => {
	const reason = { kind: 'ciqual' as const, name: 'Emmental', ingredientId: 'cheese' };
	expect(exclusionTarget('second-recipe', reason)).toEqual({
		inputId: 'ingredient-ciqual-second-recipe-cheese',
		dialogId: 'ingredient-details-dialog-second-recipe-cheese'
	});
	expect(exclusionTarget('second-recipe', { ...reason, kind: 'agribalyse' })).toEqual({
		inputId: 'ingredient-reference-second-recipe-cheese',
		dialogId: 'ingredient-details-dialog-second-recipe-cheese'
	});
});

it('focuses product, quantity and preparation controls directly in the table', () => {
	for (const [kind, field] of [
		['off', 'product'],
		['quantity', 'weight'],
		['preparation', 'preparation']
	] as const) {
		expect(exclusionTarget('recipe', { kind, name: 'Cheese', ingredientId: 'cheese' })).toEqual({
			inputId: `ingredient-${field}-recipe-cheese`,
			dialogId: null
		});
	}
});
