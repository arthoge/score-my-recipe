/** Prepared-weight display values, pending documented yields from the analysis API. */
import { isIngredientNotEmpty, type Ingredient } from '$lib/types/ingredient';
import { isPositiveAmount } from './ingredientEditor';

/** Preserve measured overrides; reuse quantities only when no conversion is needed. */
export function getPreparedWeight(ingredient: Ingredient): number | null {
	if (ingredient.measuredPreparedWeightG != null) return ingredient.measuredPreparedWeightG;
	if (!isPositiveAmount(ingredient.weight)) return null;
	if (
		ingredient.state === 'cooked' ||
		ingredient.state === 'drained' ||
		!ingredient.preparationProfile ||
		ingredient.preparationProfile === 'none'
	)
		return ingredient.weight;
	// Cooking coefficients depend on the exact food and process; do not guess them.
	return null;
}

/** Show a total only when every populated ingredient has a usable prepared weight. */
export function getFinalPreparedWeight(ingredients: Ingredient[]): number | null {
	const rows = ingredients.filter(isIngredientNotEmpty);
	if (!rows.length) return null;
	const weights = rows.map(getPreparedWeight);
	if (weights.some((weight) => !isPositiveAmount(weight))) return null;
	return weights.reduce<number>((total, weight) => total + weight!, 0);
}
