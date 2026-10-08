/** Keep nutrition search drafts synchronized with the chef's ingredient description. */
import type { Ingredient, TaxonomyItem } from '$lib/types/ingredient';

/** Suggest the first real OFF result without replacing a choice or edit made by the chef. */
export function suggestOffProduct(ingredient: Ingredient, suggestions: TaxonomyItem[]) {
	const match = suggestions.find((item) => item.id && item.isInTaxonomy);
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
