/** Generate printable recipe reports from inputs; scores are calculated by the backend. */
import { get } from 'svelte/store';
import { _, waitLocale } from '$lib/i18n';
import { env } from '$env/dynamic/public';
import type { components } from '../../api-schema';
import type { RecipeDraft } from '$lib/types/recipeDraft';
import { isIngredientNotEmpty } from '$lib/types/ingredient';
import { ingredientToGreenScoreInput } from './recipe';
import { nutritionInputs } from './nutritionAnalysis';

/** Preserve editor references, quantities, portions and country in a canonical export payload. */
export function recipeExportInputs(
	recipes: RecipeDraft[],
	translations?: components['schemas']['ReportTranslations']
): components['schemas']['ExportRequest'] {
	return {
		...(translations ? { translations } : {}),
		recipes: recipes.map((recipe) => {
			const rows = recipe.ingredients.filter(isIngredientNotEmpty);
			const nutrition = nutritionInputs(rows, recipe.portions);
			return {
				name: recipe.name,
				country: recipe.country ?? null,
				portions: nutrition.portions,
				category: nutrition.category,
				ingredients: rows.map((row, index) => {
					const green = ingredientToGreenScoreInput(row);
					return {
						...nutrition.ingredients[index],
						codified_ingredient: green.codifiedIngredient,
						agribalyse_code: green.agribalyseCode ?? null,
						labels: green.labels ?? [],
						origin: green.origin ?? null,
						is_fresh_plant: green.isFreshPlant ?? false,
						is_in_season: green.isInSeason ?? false
					};
				})
			};
		})
	};
}

/** Reuse the active website dictionary for PDF text, preserving substitution tokens. */
export function reportTranslations(): components['schemas']['ReportTranslations'] {
	const translate = get(_);
	return {
		title: translate('pdf.title', { default: 'Recipes' }),
		subtitle: translate('pdf.subtitle', {
			default:
				'Based on available ingredient and product data. Information may be missing or inaccurate.'
		}),
		ingredients: translate('pdf.ingredients', { default: 'Ingredients' }),
		unnamed_ingredient: translate('pdf.unnamed_ingredient', { default: 'Unnamed ingredient' }),
		nutrition: translate('pdf.nutrition', { default: 'Nutrition' }),
		per_100g: translate('nutrition.per_100g', { default: 'Per 100 g' }),
		per_portion: translate('nutrition.per_portion', { default: 'Per portion' }),
		additives: translate('nutrition.additives', { default: 'Additives' }),
		allergens: translate('nutrition.allergens', { default: 'Allergens' }),
		no_information: translate('nutrition.no_product_information', {
			default: 'No information available'
		}),
		exclusions: translate('recipe.excluded_summary', {
			default: '{count} ingredient(s) excluded ({percent}% of recipe weight).',
			values: { count: '{count}', percent: '{percent}' }
		}),
		energy_kj: translate('nutrition.nutrients.energy_kj', { default: 'Energy' }),
		fat: translate('nutrition.nutrients.fat', { default: 'Fat' }),
		saturated_fat: translate('nutrition.nutrients.saturated_fat', { default: 'Saturated fat' }),
		carbohydrates: translate('nutrition.nutrients.carbohydrates', { default: 'Carbohydrates' }),
		sugars: translate('nutrition.nutrients.sugars', { default: 'Sugars' }),
		fiber: translate('nutrition.nutrients.fiber', { default: 'Fibre' }),
		proteins: translate('nutrition.nutrients.proteins', { default: 'Proteins' }),
		salt: translate('nutrition.nutrients.salt', { default: 'Salt' })
	};
}

/** Request the server PDF and verify its content before triggering a browser download. */
export async function exportRecipes(recipes: RecipeDraft[]): Promise<Blob> {
	await waitLocale();
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/recipes/export`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(recipeExportInputs(recipes, reportTranslations()))
	});
	if (!response.ok || !response.headers.get('content-type')?.includes('application/pdf')) {
		throw new Error(`Recipe export failed: ${response.status}`);
	}
	return response.blob();
}
