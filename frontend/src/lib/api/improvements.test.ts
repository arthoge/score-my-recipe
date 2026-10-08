import { afterEach, expect, it, vi } from 'vitest';
import { checkImprovements, ImprovementError, optimizeRecipe } from './improvements';

const payload = { recipe: { name: 'Recipe', ingredients: [] }, lang: 'fr' };
afterEach(() => vi.unstubAllGlobals());

it('sends the original snapshot and exact selection with cancellation', async () => {
	const response = { recipe: payload.recipe };
	const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(response)));
	vi.stubGlobal('fetch', fetch);
	const signal = new AbortController().signal;
	expect(await optimizeRecipe(payload, ['butter:ciqual:16410'], signal)).toEqual(response);
	expect(fetch.mock.calls[0][0]).toContain('/v1/make-it-better/optimize');
	expect(fetch.mock.calls[0][1].signal).toBe(signal);
	expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
		...payload,
		selected_ids: ['butter:ciqual:16410']
	});
});

it.each([
	['Selected suggestions are no longer available', 'selection_unavailable'],
	['Selected changes do not improve the combined recipe scores', 'no_combined_gain'],
	['Selected changes could not be verified with available score data', 'failed']
])('preserves validation reason %s for the dialog', async (detail, reason) => {
	vi.stubGlobal(
		'fetch',
		vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail }), { status: 409 }))
	);
	await expect(
		optimizeRecipe(payload, ['swap'], new AbortController().signal)
	).rejects.toMatchObject({
		reason
	});
});

it('handles non-JSON service failures without misclassifying them as selection conflicts', async () => {
	vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Unavailable', { status: 503 })));
	await expect(checkImprovements(payload, new AbortController().signal)).rejects.toEqual(
		new ImprovementError('failed')
	);
});
