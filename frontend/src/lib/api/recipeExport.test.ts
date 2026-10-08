/** Export input contracts keep environmental and nutritional data aligned. */
import { afterEach, expect, it, vi } from 'vitest';
import { _, locale, waitLocale } from '$lib/i18n';
import { get } from 'svelte/store';
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

it.each([
	['en-US', 'Open Food Facts product', 'Recipes', 'Ingredients', 'No information available'],
	['en-GB', 'Open Food Facts product', 'Recipes', 'Ingredients', 'No information available'],
	['en-AU', 'Open Food Facts product', 'Recipes', 'Ingredients', 'No information available'],
	['fr-FR', 'Produit Open Food Facts', 'Recettes', 'Ingrédients', 'Aucune information disponible'],
	['de-DE', 'Open Food Facts-Produkt', 'Rezepte', 'Zutaten', 'Keine Informationen verfügbar'],
	[
		'es-ES',
		'Producto de Open Food Facts',
		'Recetas',
		'Ingredientes',
		'No hay información disponible'
	],
	[
		'it-IT',
		'Prodotto Open Food Facts',
		'Ricette',
		'Ingredienti',
		'Nessuna informazione disponibile'
	],
	[
		'ca-ES',
		'Producte d’Open Food Facts',
		'Receptes',
		'Ingredients',
		'No hi ha informació disponible'
	],
	['nl-NL', 'Open Food Facts-product', 'Recepten', 'Ingrediënten', 'Geen informatie beschikbaar'],
	['nl-BE', 'Open Food Facts-product', 'Recepten', 'Ingrediënten', 'Geen informatie beschikbaar'],
	['pt-PT', 'Produto Open Food Facts', 'Receitas', 'Ingredientes', 'Nenhuma informação disponível'],
	['pt-BR', 'Produto Open Food Facts', 'Receitas', 'Ingredientes', 'Nenhuma informação disponível']
])(
	'localizes product labels and PDF downloads in %s',
	async (code, product, title, ingredients, noInformation) => {
		const fetch = vi
			.fn()
			.mockImplementation(
				async () => new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf' } })
			);
		vi.stubGlobal('fetch', fetch);
		await locale.set(code);
		await exportRecipes(recipes);
		expect(get(_)('recipe.off_product', { default: 'Open Food Facts product' })).toBe(product);
		const payload = JSON.parse(fetch.mock.calls[0][1].body);
		expect(payload.translations).toMatchObject({
			title,
			ingredients,
			no_information: noInformation
		});
		if (!code.startsWith('en')) {
			expect(payload.translations.subtitle).not.toContain('Based on available');
			expect(payload.translations.unnamed_ingredient).not.toBe('Unnamed ingredient');
			expect(payload.translations.nutrition).not.toBe('Nutrition');
			expect(payload.translations.additives).not.toBe('Additives');
			expect(payload.translations.allergens).not.toBe('Allergens');
		}
	}
);
