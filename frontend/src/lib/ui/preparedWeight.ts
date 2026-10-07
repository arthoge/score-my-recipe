/** Prepared-weight display values, using current API suggestions and quantity fallbacks. */
import { isIngredientNotEmpty, type Ingredient } from '$lib/types/ingredient';
import { isPositiveAmount } from './ingredientEditor';

/** Identify the inputs used by a backend estimate, including food identity changes. */
export function preparedWeightInputKey(ingredient: Ingredient): string {
	return JSON.stringify([
		ingredient.name,
		ingredient.weight,
		ingredient.state ?? 'raw',
		ingredient.preparationProfile ?? 'none',
		ingredient.ciqualCode ?? '',
		ingredient.barcode ?? ''
	]);
}

/** Display manual edits or a current estimate, falling back to the entered quantity. */
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
	const suggestion = ingredient.preparedWeightSuggestion;
	if (suggestion?.inputKey === preparedWeightInputKey(ingredient))
		return suggestion.weightG ?? ingredient.weight;
	return ingredient.weight;
}

/** Show a total only when every populated ingredient has a usable prepared weight. */
export function getFinalPreparedWeight(ingredients: Ingredient[]): number | null {
	const rows = ingredients.filter(isIngredientNotEmpty);
	if (!rows.length) return null;
	const weights = rows.map(getPreparedWeight);
	if (weights.some((weight) => !isPositiveAmount(weight))) return null;
	return weights.reduce<number>((total, weight) => total + weight!, 0);
}
