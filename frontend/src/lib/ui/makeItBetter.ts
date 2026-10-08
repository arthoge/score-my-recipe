/** Apply complete server replacements by row ID, preserving untouched editor drafts. */
import type { Ingredient } from '$lib/types/ingredient';
import type { ImprovementSuggestion, OptimizeResponse } from '$lib/api/improvements';

/** Keep selected rows consistent with the exact recipe validated by the backend. */
export function applyOptimizedRecipe(
	ingredients: Ingredient[],
	result: OptimizeResponse,
	suggestions: ImprovementSuggestion[]
): Ingredient[] {
	const selected = new Map(suggestions.map((suggestion) => [suggestion.ingredient_id, suggestion]));
	const replacements = new Map(result.recipe.ingredients.map((row) => [row.id, row]));
	return ingredients.map((ingredient) => {
		const suggestion = selected.get(ingredient.id);
		const row = replacements.get(ingredient.id);
		if (!suggestion || !row) return ingredient;
		return {
			...ingredient,
			name: row.name ?? '',
			resolvedReferenceName: row.name ?? '',
			weight: row.quantity_g ?? null,
			codifiedIngredient: row.codified_ingredient ?? null,
			ciqualCode: row.ciqual_code ?? undefined,
			ciqualName:
				suggestion.ciqual_name ??
				(row.ciqual_code === ingredient.ciqualCode ? ingredient.ciqualName : ''),
			agribalyseCode: row.agribalyse_code ?? undefined,
			agribalyseName:
				suggestion.agribalyse_name ??
				(row.agribalyse_code === ingredient.agribalyseCode ? ingredient.agribalyseName : ''),
			referenceSource: row.agribalyse_code ? 'manual' : undefined,
			barcode: row.barcode ?? undefined,
			productName:
				suggestion.product_name ??
				(row.barcode === ingredient.barcode ? ingredient.productName : ''),
			labels: row.labels ?? [],
			origin: row.origin ?? null,
			isFreshPlant: row.is_fresh_plant ?? false,
			isInSeason: row.is_in_season ?? false,
			state: row.state ?? 'raw',
			preparationProfile: row.preparation ?? 'none',
			measuredPreparedWeightG: row.prepared_weight_g ?? null,
			preparedWeightSuggestion: undefined
		};
	});
}

/** Percentages describe directional numeric score changes, not distances between letter grades. */
export function formatImprovementPercent(percent: number | null | undefined): string {
	if (percent == null) return '—';
	const rounded = percent.toFixed(1);
	if (Number(rounded) === 0) return '0.0%';
	return `${percent > 0 ? '+' : ''}${rounded}%`;
}

/** Keep suggestions with a displayed regression unchecked until explicitly selected. */
export function hasScoreRegression(suggestion: ImprovementSuggestion): boolean {
	return !!(
		(suggestion.green_score && suggestion.green_score.after < suggestion.green_score.before) ||
		(suggestion.nutri_score && suggestion.nutri_score.after > suggestion.nutri_score.before)
	);
}
