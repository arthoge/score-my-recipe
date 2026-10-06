import { afterEach, describe, expect, it, vi } from 'vitest';
vi.mock('$lib/i18n', () => ({ getLocale: () => 'fr-FR' }));
import { searchCiqualFoods, searchOffProducts } from './nutrition';

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
