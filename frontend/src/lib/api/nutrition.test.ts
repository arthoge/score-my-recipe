import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('$lib/i18n', () => ({ getLocale: () => 'fr-FR' }));
import { searchAgribalyseFoods, searchCiqualFoods, searchOffProducts } from './nutrition';

afterEach(() => vi.unstubAllGlobals());

describe('nutrition reference searches', () => {
	it('keeps CIQUAL names visible and codes internal, passing locale and cancellation', async () => {
		const request = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					foods: [{ ciqual_code: '123', name: 'Tomate, crue', synonyms: ['Tomate'] }]
				})
			)
		);
		vi.stubGlobal('fetch', request);
		const signal = new AbortController().signal;
		expect(await searchCiqualFoods(' tomate ', 8, signal)).toEqual([
			{ id: '123', label: 'Tomate, crue', synonyms: ['Tomate'], isInTaxonomy: true }
		]);
		const url = new URL(request.mock.calls[0][0], 'http://localhost');
		expect(url.pathname).toBe('/v1/nutrition/foods');
		expect(url.searchParams.get('q')).toBe('tomate');
		expect(url.searchParams.get('lang')).toBe('fr');
		expect(request.mock.calls[0][1].signal).toBe(signal);
	});

	it('searches OFF through the backend with locale and cancellation', async () => {
		const request = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					foods: [{ code: '456', name: 'Tomates — Brand' }]
				})
			)
		);
		vi.stubGlobal('fetch', request);
		const signal = new AbortController().signal;
		expect(await searchOffProducts(' tomates ', 8, signal)).toEqual([
			{ id: '456', label: 'Tomates — Brand', isInTaxonomy: true }
		]);
		const url = new URL(request.mock.calls[0][0], 'http://localhost');
		expect(url.pathname).toBe('/v1/nutrition/products');
		expect(url.searchParams.get('q')).toBe('tomates');
		expect(url.searchParams.get('lang')).toBe('fr');
		expect(request.mock.calls[0][1].signal).toBe(signal);
	});

	it('does not substitute invented references when a service fails', async () => {
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 404 })));
		await expect(searchCiqualFoods('Rice')).rejects.toThrow('CIQUAL search failed');
		await expect(searchOffProducts('Rice')).rejects.toThrow('Product search failed');
	});
});

it.each([searchCiqualFoods, searchAgribalyseFoods, searchOffProducts])(
	'preserves missing-data metadata for reference dropdowns',
	async (search) => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(
					JSON.stringify({
						foods: [
							{
								code: '123',
								ciqual_code: '123',
								name: 'Food',
								missing_data: ['sugars'],
								no_data: false
							}
						]
					})
				)
			)
		);
		const result = (await search('Food'))[0];
		expect(result.missingData).toEqual(['sugars']);
		expect(result.noData).toBe(false);
	}
);

it.each([searchCiqualFoods, searchAgribalyseFoods, searchOffProducts])(
	'preserves the no-data status for red dropdown warnings',
	async (search) => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockResolvedValue(
				new Response(
					JSON.stringify({
						foods: [
							{
								code: '123',
								ciqual_code: '123',
								name: 'Empty',
								no_data: true,
								missing_data: ['sugars']
							}
						]
					})
				)
			)
		);
		expect((await search('Empty'))[0].noData).toBe(true);
	}
);

it('resolves references from a recipe row without requiring a taxonomy ID', async () => {
	const { getIngredientReferences } = await import('./nutrition');
	const fetch = vi
		.fn()
		.mockResolvedValue(
			new Response(JSON.stringify({ ciqual: null, agribalyse: null, source: null }))
		);
	vi.stubGlobal('fetch', fetch);
	const signal = new AbortController().signal;
	await getIngredientReferences(undefined, signal, {
		name: 'Butter',
		ciqualCode: '16400',
		agribalyseCode: 'green'
	});
	const url = new URL(fetch.mock.calls[0][0], 'http://localhost');
	expect(url.pathname).toBe('/v1/ingredient-references');
	expect(url.searchParams.get('ciqual_code')).toBe('16400');
	expect(url.searchParams.get('agribalyse_code')).toBe('green');
	expect(url.searchParams.get('q')).toBe('Butter');
	expect(url.searchParams.get('lang')).toBe('fr');
	expect(url.searchParams.has('taxonomy_id')).toBe(false);
	expect(fetch.mock.calls[0][1].signal).toBe(signal);
});

it('carries backend automatic product eligibility to the editor', async () => {
	vi.stubGlobal(
		'fetch',
		vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					foods: [{ code: '123', name: 'Truffes fantaisie', automatic_match: false }]
				})
			)
		)
	);
	expect((await searchOffProducts('truffe'))[0].automaticMatch).toBe(false);
});

it('carries declared OFF label IDs alongside the selected product without another request', async () => {
	const fetch = vi.fn().mockResolvedValue(
		new Response(
			JSON.stringify({
				foods: [{ code: '123', name: 'Milk', label_ids: ['en:eu-organic'], origin_id: 'en:france' }]
			})
		)
	);
	vi.stubGlobal('fetch', fetch);
	const product = (await searchOffProducts('Milk'))[0];
	expect(product.productLabelIds).toEqual(['en:eu-organic']);
	expect(product.productOriginId).toBe('en:france');
	expect(fetch).toHaveBeenCalledTimes(1);
});
