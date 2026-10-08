import { describe, expect, it } from 'vitest';
import { createEmptyIngredient, type Ingredient } from '$lib/types/ingredient';
import { canAutoScore, ingredientCellErrors, ingredientCalculationCells } from './ingredientEditor';

/** An editable ingredient with a selected environmental database reference. */
function validIngredient(): Ingredient {
	return {
		...createEmptyIngredient(),
		name: 'Tomatoes',
		weight: 400,
		codifiedIngredient: { id: 'en:tomato', label: 'Tomatoes', isInTaxonomy: true }
	};
}

describe('automatic score form validation', () => {
	it('does not score when the only reference lacks environmental impact data', () => {
		const reference = { id: 'en:unknown', label: 'Unknown', isInTaxonomy: true, hasEfScore: false };
		expect(canAutoScore([{ ...validIngredient(), codifiedIngredient: reference }])).toBe(false);
	});
	it('scores valid recipes without treating the trailing insertion row as an error', () => {
		expect(canAutoScore([validIngredient(), createEmptyIngredient()])).toBe(true);
		expect(Object.values(ingredientCellErrors(createEmptyIngredient())).some(Boolean)).toBe(false);
		expect(canAutoScore([createEmptyIngredient()])).toBe(false);
	});

	it.each([null, 0, -1, Number.NaN, Number.POSITIVE_INFINITY])(
		'does not send an invalid quantity (%s) to the score API',
		(weight) => {
			expect(canAutoScore([{ ...validIngredient(), weight }])).toBe(false);
		}
	);

	it('allows incomplete rows to be excluded without blocking other ingredients', () => {
		expect(canAutoScore([validIngredient(), { ...validIngredient(), name: '' }])).toBe(true);
		expect(
			canAutoScore([validIngredient(), { ...validIngredient(), codifiedIngredient: null }])
		).toBe(true);
		expect(
			canAutoScore([
				{
					...validIngredient(),
					codifiedIngredient: { id: null, label: 'Unknown', isInTaxonomy: false }
				}
			])
		).toBe(false);
	});

	it.each(['manual', 'unmatched'])(
		'does not reuse %s correspondences unless another usable row remains',
		(referenceSource) => {
			const cleared = { ...validIngredient(), referenceSource };
			expect(canAutoScore([cleared])).toBe(false);
			expect(canAutoScore([{ ...validIngredient(), name: '' }])).toBe(false);
			expect(canAutoScore([{ ...validIngredient(), codifiedIngredient: null }])).toBe(false);
			expect(canAutoScore([cleared, validIngredient()])).toBe(true);
			expect(canAutoScore([{ ...cleared, agribalyseCode: '123' }])).toBe(true);
			expect(canAutoScore([])).toBe(false);
		}
	);

	it('keeps preparation fields optional and validates portions', () => {
		expect(canAutoScore([{ ...validIngredient(), state: 'raw', ciqualCode: '1234' }], 4)).toBe(
			true
		);
		expect(canAutoScore([validIngredient()], 2.5)).toBe(false);
	});

	it('treats preparation-only rows as incomplete drafts rather than ignoring them', () => {
		expect(canAutoScore([validIngredient(), { ...createEmptyIngredient(), state: 'cooked' }])).toBe(
			true
		);
	});
});

describe('calculation cell feedback', () => {
	it('marks an empty required nutrition source red while leaving optional OFF neutral', () => {
		const cells = ingredientCalculationCells(validIngredient(), false, [
			{ code: 'nutrition_reference_missing' }
		]);
		expect(cells.ciqual).toBe('error');
		expect(cells.product).toBeNull();
		expect(ingredientCalculationCells(createEmptyIngredient(), false, []).ciqual).toBeNull();
	});
	it('warns on the active OFF reference without blaming an unused Ciqual reference', () => {
		const ingredient = { ...validIngredient(), barcode: '123', productName: 'Tomato sauce' };
		const cells = ingredientCalculationCells(ingredient, false, [
			{ code: 'nutrients_missing', fields: ['fiber'] }
		]);
		expect(cells.product).toBe('warning');
		expect(cells.ciqual).toBeNull();
	});
	it('warns on a filled Ciqual source with missing calculation data', () => {
		const ingredient = { ...validIngredient(), ciqualCode: '123', ciqualName: 'Tomatoes' };
		expect(
			ingredientCalculationCells(ingredient, false, [{ code: 'plant_proportion_missing' }]).ciqual
		).toBe('warning');
		expect(ingredientCalculationCells(ingredient, false, []).ciqual).toBeNull();
	});
	it('distinguishes an empty environmental reference from a filled unusable reference', () => {
		expect(ingredientCalculationCells(validIngredient(), true, []).agribalyse).toBe('error');
		expect(
			ingredientCalculationCells({ ...validIngredient(), agribalyseName: 'Tomatoes' }, true, [])
				.agribalyse
		).toBe('warning');
	});
	it('attaches cooking issues to preparation or state rather than the food source', () => {
		const ingredient = { ...validIngredient(), ciqualCode: '123', ciqualName: 'Tomatoes' };
		const cells = ingredientCalculationCells(ingredient, false, [
			{ code: 'unsupported_preparation' },
			{ code: 'prepared_reference_required' }
		]);
		expect(cells.preparation).toBe('warning');
		expect(cells.state).toBe('warning');
		expect(cells.ciqual).toBeNull();
	});
});

it('warns when the backend confirms a usable Ciqual fallback', () => {
	const ingredient = {
		...validIngredient(),
		barcode: '123',
		productName: 'Tomato sauce',
		ciqualCode: '456',
		ciqualName: 'Tomatoes'
	};
	const cells = ingredientCalculationCells(ingredient, false, [], true);
	expect(cells.product).toBe('warning');
	expect(cells.ciqual).toBeNull();
	expect(
		ingredientCalculationCells(ingredient, false, [{ code: 'nutrients_missing' }]).product
	).toBe('warning');
});

it('allows zero-weight exclusions when another ingredient has a positive quantity', () => {
	const zero = { ...validIngredient(), weight: 0 };
	expect(canAutoScore([validIngredient(), zero])).toBe(true);
	expect(canAutoScore([zero])).toBe(false);
	expect(ingredientCellErrors(zero).weight).toBe(true);
	expect(ingredientCalculationCells(zero, true, [{ code: 'zero_quantity' }]).agribalyse).toBeNull();
});

it('keeps scoring when a newly populated row has no quantity yet', () => {
	const draft = { ...createEmptyIngredient(), name: 'New ingredient' };
	expect(canAutoScore([validIngredient(), draft])).toBe(true);
	expect(canAutoScore([draft])).toBe(false);
	expect(ingredientCellErrors(draft).weight).toBe(true);
});

it('attaches incomplete generic fallback data to Ciqual rather than the OFF product', () => {
	const ingredient = {
		...validIngredient(),
		barcode: '123',
		productName: 'Lardons',
		ciqualCode: '28501',
		ciqualName: 'Lardoons, plain, raw'
	};
	const cells = ingredientCalculationCells(
		ingredient,
		false,
		[{ code: 'red_meat_proportion_missing' }],
		false,
		'CIQUAL-2025'
	);
	expect(cells.ciqual).toBe('warning');
	expect(cells.product).toBeNull();
});

it('shows only a warning for an OFF issue even without a product label', () => {
	const cells = ingredientCalculationCells({ ...validIngredient(), barcode: '123' }, false, [
		{ code: 'product_missing' }
	]);
	expect(cells.product).toBe('warning');
});
