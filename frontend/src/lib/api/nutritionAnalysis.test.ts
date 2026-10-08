import { afterEach, describe, expect, it, vi } from 'vitest';
import { createEmptyIngredient } from '$lib/types/ingredient';
import { analyzeNutrition, nutritionInputs } from './nutritionAnalysis';

afterEach(() => vi.unstubAllGlobals());

describe('independent recipe nutrition requests', () => {
	it('clears manual prepared masses for zero quantities so they cannot block scoring', () => {
		for (const measuredPreparedWeightG of [null, 0, 500]) {
			const payload = nutritionInputs(
				[
					{ ...createEmptyIngredient(), name: 'Rice', weight: 100, ciqualCode: '9119' },
					{ ...createEmptyIngredient(), name: 'Unused', weight: 0, measuredPreparedWeightG }
				],
				1
			);
			expect(payload.ingredients[0].quantity_g).toBe(100);
			expect(payload.ingredients[1]).toMatchObject({ quantity_g: 0, prepared_weight_g: null });
		}
	});

	it('keeps references and measured masses without sending stale display estimates', () => {
		const row = {
			...createEmptyIngredient(),
			name: 'Rice',
			weight: 100,
			ciqualCode: '9119',
			barcode: '123',
			measuredPreparedWeightG: 250,
			preparedWeightSuggestion: { inputKey: 'stale', weightG: 500, yieldFactor: 5, source: null }
		};
		const payload = nutritionInputs([row, createEmptyIngredient()], 2);
		expect(payload.ingredients).toHaveLength(1);
		expect(payload.ingredients[0]).toMatchObject({
			quantity_g: 100,
			ciqual_code: '9119',
			barcode: '123',
			prepared_weight_g: 250
		});
		expect(payload.portions).toBe(2);
		expect(payload.category).toBe('en:meals');
		expect(nutritionInputs([row], 2, 'en:cheeses').category).toBe('en:cheeses');
	});

	it('sends invalid or missing references to analysis without environmental dependencies', async () => {
		const signal = new AbortController().signal;
		const result = { status: 'incomplete', nutri_score: null, diagnostics: [] };
		const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(result)));
		vi.stubGlobal('fetch', fetch);
		const payload = nutritionInputs(
			[{ ...createEmptyIngredient(), name: 'Custom food', weight: 100 }],
			1
		);
		expect(await analyzeNutrition(payload, signal)).toEqual(result);
		expect(fetch).toHaveBeenCalledWith(
			expect.stringContaining('/v1/nutrition/analyze'),
			expect.objectContaining({ signal, body: JSON.stringify(payload), method: 'POST' })
		);
	});
});
