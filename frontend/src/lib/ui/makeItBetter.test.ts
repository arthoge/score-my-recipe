import { describe, expect, it } from 'vitest';
import { applyOptimizedRecipe, formatImprovementPercent } from './makeItBetter';
import { createEmptyIngredient } from '$lib/types/ingredient';
import { syncNutritionSearches } from './nutritionSearch';
import type { ImprovementSuggestion, OptimizeResponse } from '$lib/api/improvements';

/** Model a replacement with resolved references, never a catalog slug. */
function fixture() {
	const ingredients = ['first', 'second'].map((id) => ({
		...createEmptyIngredient(),
		id,
		name: 'Yogurt',
		weight: 100,
		ciqualCode: 'old',
		ciqualName: 'Old yogurt',
		agribalyseCode: 'old-green',
		barcode: '123',
		productName: 'Old product',
		measuredPreparedWeightG: 150
	}));
	const after = {
		id: 'second',
		name: 'Plain yogurt',
		quantity_g: 100,
		ciqual_code: '19593',
		agribalyse_code: 'resolved-green',
		labels: []
	};
	const suggestion: ImprovementSuggestion = {
		id: 'second:ciqual:19593',
		ingredient_id: 'second',
		category: 'ingredient',
		before: { id: 'second', name: 'Yogurt', quantity_g: 100 },
		after,
		ciqual_name: 'Plain yogurt',
		agribalyse_name: 'Yaourt nature',
		green_score: null,
		nutri_score: null
	};
	const result: OptimizeResponse = { recipe: { name: 'Recipe', ingredients: [after] } };
	return { ingredients, suggestion, result };
}

describe('confirmed recipe improvements', () => {
	it('applies the selected duplicate row and preserves unselected row identity', () => {
		const { ingredients, suggestion, result } = fixture();
		const updated = applyOptimizedRecipe(ingredients, result, [suggestion]);
		expect(updated[0]).toBe(ingredients[0]);
		expect(updated[1]).toMatchObject({
			name: 'Plain yogurt',
			ciqualCode: '19593',
			agribalyseCode: 'resolved-green',
			weight: 100,
			labels: [],
			measuredPreparedWeightG: null
		});
		expect(updated[1].barcode).toBeUndefined();
		expect(updated[1].productName).toBe('');
		expect(updated[1].codifiedIngredient).toBeNull();
		expect(ingredients[1].name).toBe('Yogurt');
	});

	it('does not clear newly resolved references when the row reacts to its changed name', () => {
		const { ingredients, suggestion, result } = fixture();
		const updated = applyOptimizedRecipe(ingredients, result, [suggestion]);
		syncNutritionSearches(updated[1], 'Yogurt');
		expect(updated[1].ciqualCode).toBe('19593');
		expect(updated[1].agribalyseCode).toBe('resolved-green');
		updated[1].name = 'Rice';
		syncNutritionSearches(updated[1], 'Plain yogurt');
		expect(updated[1].ciqualCode).toBeUndefined();
		expect(updated[1].agribalyseCode).toBeUndefined();
	});

	it('leaves every row unchanged for an empty selection', () => {
		const { ingredients, result } = fixture();
		expect(applyOptimizedRecipe(ingredients, result, [])).toEqual(ingredients);
	});

	it('shows unavailable percentages explicitly and formats computed gains', () => {
		expect(formatImprovementPercent(null)).toBe('—');
		expect(formatImprovementPercent(undefined)).toBe('—');
		expect(formatImprovementPercent(20)).toBe('+20.0%');
		expect(formatImprovementPercent(0)).toBe('0.0%');
		expect(formatImprovementPercent(0.01)).toBe('+<0.1%');
		expect(formatImprovementPercent(-0.01)).toBe('−<0.1%');
		expect(formatImprovementPercent(1.5)).toBe('+1.5%');
		expect(formatImprovementPercent(-1)).toBe('-1.0%');
	});
});

it('recognizes a trade-off even when the percentage baseline is zero', async () => {
	const { hasScoreRegression } = await import('./makeItBetter');
	const { suggestion } = fixture();
	suggestion.green_score = {
		before: 0,
		after: 10,
		before_grade: 'F',
		after_grade: 'E',
		percent: null
	};
	suggestion.nutri_score = {
		before: 0,
		after: 1,
		before_grade: 'B',
		after_grade: 'B',
		percent: null
	};
	expect(hasScoreRegression(suggestion)).toBe(true);
	suggestion.nutri_score.after = -1;
	expect(hasScoreRegression(suggestion)).toBe(false);
});

it('preserves quantities and selected product identity for same-name replacements', () => {
	const { ingredients, suggestion, result } = fixture();
	const after = {
		...result.recipe.ingredients[0],
		name: ingredients[1].name,
		quantity_g: 100,
		barcode: ingredients[1].barcode,
		ciqual_code: ingredients[1].ciqualCode,
		agribalyse_code: ingredients[1].agribalyseCode
	};
	suggestion.after = after;
	suggestion.product_name = null;
	result.recipe.ingredients = [after];
	const updated = applyOptimizedRecipe(ingredients, result, [suggestion]);
	expect(updated[1].weight).toBe(100);
	expect(updated[1].barcode).toBe('123');
	expect(updated[1].productName).toBe('Old product');
	expect(updated[0]).toBe(ingredients[0]);
});

it('clears unselected draft text and restarts lookup for same-name replacements', () => {
	const { ingredients, suggestion, result } = fixture();
	Object.assign(ingredients[1], { barcode: undefined });
	ingredients[1].productName = 'Unselected draft';
	result.recipe.ingredients[0].name = ingredients[1].name;
	const updated = applyOptimizedRecipe(ingredients, result, [suggestion]);
	expect(updated[1].productName).toBe('');
	expect(updated[1].referenceRevision).toBe(1);
	expect(applyOptimizedRecipe(updated, result, [suggestion])[1].referenceRevision).toBe(2);
});

it('ignores suggestion labels without confirmed codes so automatic lookup can fill the row', async () => {
	const { ingredients, suggestion, result } = fixture();
	const { suggestOffProduct } = await import('./nutritionSearch');
	Object.assign(result.recipe.ingredients[0], {
		barcode: null,
		ciqual_code: null,
		agribalyse_code: null
	});
	suggestion.product_name = 'Stale suggestion label';
	const updated = applyOptimizedRecipe(ingredients, result, [suggestion])[1];
	expect(updated.ciqualName).toBe('');
	expect(updated.agribalyseName).toBe('');
	suggestOffProduct(updated, [
		{ id: 'verified', label: 'Matched product', isInTaxonomy: true, automaticMatch: true }
	]);
	expect(updated.barcode).toBe('verified');
});

it('tracks certifications from optimized products and clears them on the next product change', async () => {
	const { ingredients, suggestion, result } = fixture();
	const { selectOffProduct } = await import('./nutritionSearch');
	const label = { id: 'en:eu-organic', label: 'Organic', isInTaxonomy: true };
	result.recipe.ingredients[0].barcode = '456';
	result.recipe.ingredients[0].labels = [label];
	result.recipe.ingredients[0].origin = { id: 'en:france', label: 'France', isInTaxonomy: true };
	const updated = applyOptimizedRecipe(ingredients, result, [suggestion]);
	expect(updated[1].labels).toEqual([label]);
	expect(updated[1].origin?.id).toBe('en:france');
	expect(updated[0]).toBe(ingredients[0]);
	selectOffProduct(updated[1], { id: '789', label: 'Another product', isInTaxonomy: true });
	expect(updated[1].labels).toEqual([]);
	expect(updated[1].origin).toBeNull();
	expect(updated[1].ciqualCode).toBe('19593');
	expect(updated[1].agribalyseCode).toBe('resolved-green');
});
