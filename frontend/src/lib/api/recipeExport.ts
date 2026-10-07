/** Generate printable recipe reports from inputs; scores are calculated by the backend. */
import { env } from '$env/dynamic/public';
import type { components } from '../../api-schema';
import type { RecipeDraft } from '$lib/types/recipeDraft';
import { isIngredientNotEmpty } from '$lib/types/ingredient';
import { ingredientToGreenScoreInput } from './recipe';
import { nutritionInputs } from './nutritionAnalysis';

/** Preserve editor references, quantities, portions and country in a canonical export payload. */
export function recipeExportInputs(recipes: RecipeDraft[]): components['schemas']['ExportRequest'] {
	return {
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

/** Request the server PDF and verify its content before triggering a browser download. */
export async function exportRecipes(recipes: RecipeDraft[]): Promise<Blob> {
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/recipes/export`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(recipeExportInputs(recipes))
	});
	if (!response.ok || !response.headers.get('content-type')?.includes('application/pdf')) {
		throw new Error(`Recipe export failed: ${response.status}`);
	}
	return response.blob();
}
