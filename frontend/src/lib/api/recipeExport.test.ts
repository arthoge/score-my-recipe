/** Export input contracts keep environmental and nutritional data aligned. */
import { afterEach, expect, it, vi } from 'vitest';
import { locale, waitLocale } from '$lib/i18n';
import { createEmptyIngredient } from '$lib/types/ingredient';
import { recipeExportInputs, exportRecipes } from './recipeExport';

const recipes = [
	{
		id: 'recipe',
		name: 'Rice',
		country: 'FR',
		portions: 2,
		ingredients: [
			{
				...createEmptyIngredient(),
				name: 'Rice',
				weight: 100,
				ciqualCode: '9119',
				agribalyseCode: '9119',
				barcode: '123',
				measuredPreparedWeightG: 250
			},
			createEmptyIngredient()
		]
	}
];
afterEach(async () => {
	vi.unstubAllGlobals();
	locale.set('en-US');
	await waitLocale();
});

it('exports current inputs without browser scores and insertion rows', () => {
	const payload = recipeExportInputs(recipes);
	expect(payload.recipes[0]).toMatchObject({ name: 'Rice', country: 'FR', portions: 2 });
	expect(payload.recipes[0].ingredients).toHaveLength(1);
	expect(payload.recipes[0].ingredients[0]).toMatchObject({
		quantity_g: 100,
		ciqual_code: '9119',
		agribalyse_code: '9119',
		barcode: '123',
		prepared_weight_g: 250
	});
	expect(payload.recipes[0]).not.toHaveProperty('nutri_score');
	expect(payload.recipes[0]).not.toHaveProperty('green_score');
});

it('accepts PDF downloads and rejects validation errors or non-PDF responses', async () => {
	const fetch = vi
		.fn()
		.mockResolvedValue(
			new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf' } })
		);
	vi.stubGlobal('fetch', fetch);
	expect(await (await exportRecipes(recipes)).text()).toBe('%PDF-test');
	fetch.mockResolvedValue(new Response('{}', { status: 422 }));
	await expect(exportRecipes(recipes)).rejects.toThrow('422');
	fetch.mockResolvedValue(new Response('<html>error</html>'));
	await expect(exportRecipes(recipes)).rejects.toThrow();
});

it('exports the selected website language and follows later selector changes', async () => {
	const fetch = vi
		.fn()
		.mockImplementation(
			async () => new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf' } })
		);
	vi.stubGlobal('fetch', fetch);
	await waitLocale('fr-FR');
	locale.set('fr-FR');
	await exportRecipes(recipes);
	const french = JSON.parse(fetch.mock.calls[0][1].body).translations;
	expect(french).toMatchObject({
		ingredients: 'Ingrédients',
		nutrition: 'Valeurs nutritionnelles',
		per_100g: 'Pour 100 g',
		fat: 'Matières grasses'
	});
	expect(french.exclusions).toContain('{count}');
	expect(french.exclusions).toContain('{percent}');
	locale.set('en-US');
	await exportRecipes(recipes);
	expect(JSON.parse(fetch.mock.calls[1][1].body).translations.ingredients).toBe('Ingredients');
});
