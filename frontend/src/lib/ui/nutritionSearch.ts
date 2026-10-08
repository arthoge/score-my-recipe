/** Keep nutrition search drafts synchronized with the chef's ingredient description. */
import type { Ingredient, TaxonomyItem } from '$lib/types/ingredient';
import type { getIngredientReferences } from '$lib/api/nutrition';

/** Complete absent codes and names independently, preserving choices and search drafts. */
export function applyIngredientReferences(
	ingredient: Ingredient,
	result: Awaited<ReturnType<typeof getIngredientReferences>>
) {
	const environmental = result.agribalyse;
	if (!environmental && !ingredient.agribalyseCode && ingredient.referenceSource !== 'manual')
		ingredient.referenceSource = result.source ?? undefined;
	if (
		environmental &&
		!ingredient.agribalyseName &&
		(ingredient.agribalyseCode === environmental.code ||
			(!ingredient.agribalyseCode && ingredient.referenceSource !== 'manual'))
	) {
		ingredient.agribalyseCode = environmental.code;
		ingredient.agribalyseName = environmental.name;
		if (ingredient.referenceSource !== 'manual')
			ingredient.referenceSource = result.source ?? undefined;
	}
	const food = result.ciqual;
	if (
		food &&
		!ingredient.ciqualName &&
		(!ingredient.ciqualCode || ingredient.ciqualCode === food.code)
	) {
		ingredient.ciqualCode = food.code;
		ingredient.ciqualName = food.name;
	}
}

/** Suggest the first eligible OFF result without replacing a choice or edit made by the chef. */
export function suggestOffProduct(ingredient: Ingredient, suggestions: TaxonomyItem[]) {
	const match = suggestions.find(
		(item) => item.id && item.isInTaxonomy && item.automaticMatch !== false
	);
	if (ingredient.barcode || ingredient.productName || !match) return;
	ingredient.barcode = match.id ?? undefined;
	ingredient.productName = match.label;
}

/** Seed empty searches on load; changing ingredients invalidates previous references. */
export function syncNutritionSearches(ingredient: Ingredient, previousName?: string) {
	const changed = previousName !== undefined && previousName !== ingredient.name;
	if (changed && ingredient.resolvedReferenceName !== ingredient.name) {
		ingredient.ciqualCode = undefined;
		ingredient.agribalyseCode = undefined;
		ingredient.agribalyseName = '';
		ingredient.referenceSource = undefined;
		ingredient.barcode = undefined;
		ingredient.resolvedReferenceName = undefined;
		ingredient.ciqualName = '';
		ingredient.productName = '';
	}
}
