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

it('retries a transient calculation failure once with the same inputs', async () => {
	const success = { status: 'complete', nutri_score: { grade: 'B' } };
	const fetch = vi
		.fn()
		.mockResolvedValueOnce(new Response(JSON.stringify({ status: 'dependency_error' })))
		.mockResolvedValueOnce(new Response(JSON.stringify(success)));
	vi.stubGlobal('fetch', fetch);
	const payload = nutritionInputs([], 1);
	expect(await analyzeNutrition(payload, new AbortController().signal)).toEqual(success);
	expect(fetch).toHaveBeenCalledTimes(2);
	expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
});

it('bounds dependency retries and does not retry incomplete data', async () => {
	for (const status of ['dependency_error', 'incomplete']) {
		const fetch = vi
			.fn()
			.mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ status }))));
		vi.stubGlobal('fetch', fetch);
		await analyzeNutrition(nutritionInputs([], 1), new AbortController().signal);
		expect(fetch).toHaveBeenCalledTimes(status === 'dependency_error' ? 2 : 1);
	}
});

it('does not retry an aborted calculation or invalid inputs', async () => {
	const controller = new AbortController();
	const fetch = vi.fn().mockImplementation(() => {
		controller.abort();
		return Promise.reject(new TypeError('Network error'));
	});
	vi.stubGlobal('fetch', fetch);
	await expect(analyzeNutrition(nutritionInputs([], 1), controller.signal)).rejects.toThrow();
	expect(fetch).toHaveBeenCalledTimes(1);
	fetch.mockReset().mockResolvedValue(new Response('', { status: 422 }));
	await expect(
		analyzeNutrition(nutritionInputs([], 1), new AbortController().signal)
	).rejects.toThrow('422');
	expect(fetch).toHaveBeenCalledTimes(1);
});
