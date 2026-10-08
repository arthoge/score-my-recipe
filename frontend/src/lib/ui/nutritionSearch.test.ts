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

it('finds an OFF product for a verified replacement while preserving its food references', async () => {
	const ingredient = {
		...createEmptyIngredient(),
		name: 'Reduced-fat butter',
		resolvedReferenceName: 'Reduced-fat butter',
		ciqualCode: '16410',
		ciqualName: 'Reduced-fat butter',
		agribalyseCode: 'butter-green',
		agribalyseName: 'Reduced-fat butter'
	};
	suggestOffProduct(ingredient, [{ id: '123', label: 'Butter — Brand', isInTaxonomy: true }]);
	expect(ingredient.barcode).toBe('123');
	expect(ingredient.productName).toBe('Butter — Brand');
	expect(ingredient.ciqualCode).toBe('16410');
	expect(ingredient.agribalyseCode).toBe('butter-green');
	ingredient.name = 'Rice';
	syncNutritionSearches(ingredient, 'Reduced-fat butter');
	suggestOffProduct(ingredient, [{ id: '456', label: 'Rice — Brand', isInTaxonomy: true }]);
	expect(ingredient.barcode).toBe('456');
});

it('completes missing CIQUAL and Agribalyse names on imported and optimized rows', async () => {
	const { applyIngredientReferences } = await import('./nutritionSearch');
	for (const resolvedReferenceName of [undefined, 'Butter']) {
		const ingredient = {
			...createEmptyIngredient(),
			name: 'Butter',
			resolvedReferenceName,
			ciqualCode: '16400',
			agribalyseCode: 'butter-green',
			referenceSource: 'manual'
		};
		applyIngredientReferences(ingredient, {
			ciqual: { code: '16400', name: 'Butter, unsalted' },
			agribalyse: { code: 'butter-green', name: 'Beurre doux' },
			source: 'catalog'
		});
		expect(ingredient.ciqualName).toBe('Butter, unsalted');
		expect(ingredient.agribalyseName).toBe('Beurre doux');
		expect(ingredient.referenceSource).toBe('manual');
	}
});

it('fills one absent reference independently without overwriting another choice', async () => {
	const { applyIngredientReferences } = await import('./nutritionSearch');
	const ingredient = { ...createEmptyIngredient(), ciqualCode: 'chosen', ciqualName: 'My food' };
	applyIngredientReferences(ingredient, {
		ciqual: { code: 'other', name: 'Other food' },
		agribalyse: { code: 'linked-green', name: 'Linked environmental food' },
		source: 'catalog'
	});
	expect(ingredient.ciqualCode).toBe('chosen');
	expect(ingredient.ciqualName).toBe('My food');
	expect(ingredient.agribalyseCode).toBe('linked-green');
});

it('preserves a manually cleared environmental field and unresolved search drafts', async () => {
	const { applyIngredientReferences } = await import('./nutritionSearch');
	const ingredient = {
		...createEmptyIngredient(),
		ciqualName: 'My search',
		referenceSource: 'manual'
	};
	applyIngredientReferences(ingredient, {
		ciqual: { code: '123', name: 'Food' },
		agribalyse: { code: '456', name: 'Environmental food' },
		source: 'catalog'
	});
	expect(ingredient.ciqualName).toBe('My search');
	expect(ingredient.ciqualCode).toBeUndefined();
	expect(ingredient.agribalyseCode).toBeUndefined();
});

it('does not automatically select products rejected by backend matching', () => {
	const ingredient = { ...createEmptyIngredient(), name: 'truffe' };
	const chocolate = {
		id: '123',
		label: 'Truffes fantaisie — Favorina',
		isInTaxonomy: true,
		automaticMatch: false
	};
	suggestOffProduct(ingredient, [chocolate]);
	expect(ingredient.barcode).toBeUndefined();
	suggestOffProduct(ingredient, [
		chocolate,
		{ id: '456', label: 'Truffes noires', isInTaxonomy: true, automaticMatch: true }
	]);
	expect(ingredient.barcode).toBe('456');
});

it('keeps rejected environmental proxies out of score requests', async () => {
	const { applyIngredientReferences } = await import('./nutritionSearch');
	const { ingredientToGreenScoreInput } = await import('$lib/api/recipe');
	const ingredient = {
		...createEmptyIngredient(),
		name: 'truffe',
		codifiedIngredient: { id: 'en:truffle', label: 'truffe', isInTaxonomy: true }
	};
	applyIngredientReferences(ingredient, {
		ciqual: { code: '20106', name: 'Champignon, truffe noire, crue' },
		agribalyse: null,
		source: 'unmatched'
	});
	expect(ingredient.ciqualCode).toBe('20106');
	expect(ingredientToGreenScoreInput(ingredient).codifiedIngredient.id).toBeNull();
});
