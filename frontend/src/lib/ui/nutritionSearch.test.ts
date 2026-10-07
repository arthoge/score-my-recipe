import { describe, expect, it } from 'vitest';
import { createEmptyIngredient, isIngredientEmpty } from '$lib/types/ingredient';
import { suggestOffProduct, syncNutritionSearches } from './nutritionSearch';

describe('nutrition search drafts', () => {
	it('does not represent an ingredient name as a matched database food', () => {
		const ingredient = { ...createEmptyIngredient(), name: 'Tomatoes' };
		syncNutritionSearches(ingredient);
		expect('ciqualName' in ingredient).toBe(false);
		expect('productName' in ingredient).toBe(false);
	});

	it('preserves explicitly selected references during initialization', () => {
		const ingredient = {
			...createEmptyIngredient(),
			name: 'Rice',
			ciqualCode: '123',
			ciqualName: 'Rice, cooked',
			productName: 'My rice search'
		};
		syncNutritionSearches(ingredient);
		expect(ingredient.ciqualCode).toBe('123');
		expect(ingredient.ciqualName).toBe('Rice, cooked');
		expect(ingredient.productName).toBe('My rice search');
	});

	it('invalidates old identifiers when the ingredient changes', () => {
		const ingredient = {
			...createEmptyIngredient(),
			name: 'Lentils',
			ciqualCode: '123',
			barcode: '456',
			ciqualName: 'Rice',
			productName: 'Rice — Brand'
		};
		syncNutritionSearches(ingredient, 'Rice');
		expect(ingredient).toMatchObject({
			ciqualName: '',
			productName: ''
		});
		expect(ingredient.ciqualCode).toBeUndefined();
		expect(ingredient.barcode).toBeUndefined();
	});

	it('preserves cleared search fields and treats standalone search drafts as populated rows', () => {
		const ingredient = { ...createEmptyIngredient(), ciqualName: '', productName: 'Rice' };
		syncNutritionSearches(ingredient);
		expect(ingredient.ciqualName).toBe('');
		expect(isIngredientEmpty(ingredient)).toBe(false);
	});
});

describe('automatic OFF selection', () => {
	const suggestions = [
		{ label: 'Unidentified result', isInTaxonomy: false },
		{ id: '123', label: 'Tomatoes — Brand', isInTaxonomy: true },
		{ id: '456', label: 'Another product', isInTaxonomy: true }
	];
	it('selects the first identified product', () => {
		const ingredient = createEmptyIngredient();
		suggestOffProduct(ingredient, suggestions);
		expect(ingredient).toMatchObject({
			barcode: '123',
			productName: 'Tomatoes — Brand'
		});
	});
	it('preserves a manual selection or an ongoing search', () => {
		for (const edit of [
			{ barcode: '999', productName: 'My product' },
			{ productName: 'My search' }
		]) {
			const ingredient = { ...createEmptyIngredient(), ...edit };
			const before = { ...ingredient };
			suggestOffProduct(ingredient, suggestions);
			expect(ingredient).toEqual(before);
		}
	});
	it('leaves the reference empty when no real result exists', () => {
		const ingredient = createEmptyIngredient();
		const before = { ...ingredient };
		suggestOffProduct(ingredient, suggestions.slice(0, 1));
		expect(ingredient).toEqual(before);
	});
});
