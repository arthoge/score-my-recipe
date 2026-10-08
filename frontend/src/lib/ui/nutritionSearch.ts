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
	selectOffProduct(ingredient, match);
}

/** Product changes invalidate all previous claims, including manually entered values. */
function clearOffMetadata(ingredient: Ingredient) {
	ingredient.labels = [];
	ingredient.origin = null;
	ingredient.offProductOriginId = undefined;
	ingredient.offProductLabelIds = undefined;
}

/** Select a product atomically with its pending certifications, without a new lookup. */
export function selectOffProduct(ingredient: Ingredient, product?: TaxonomyItem) {
	const code = product?.isInTaxonomy ? (product.id ?? undefined) : undefined;
	if (code !== ingredient.barcode) {
		clearOffMetadata(ingredient);
		if (code) {
			ingredient.offProductLabelIds = product?.productLabelIds;
			ingredient.offProductOriginId = product?.productOriginId;
		}
	}
	ingredient.barcode = code;
	ingredient.productName = product?.label ?? '';
}

/** Consume declared labels once; later manual removals must not be automatically undone. */
export function applyProductCertifications(ingredient: Ingredient, options: TaxonomyItem[]) {
	if (!ingredient.barcode || !ingredient.offProductLabelIds) return;
	const declared = new Set(ingredient.offProductLabelIds);
	const existing = new Set(ingredient.labels.map((label) => label.id));
	const additions = options.filter(
		(label) => label.id && declared.has(label.id) && !existing.has(label.id)
	);
	ingredient.labels = [...ingredient.labels, ...additions];
	ingredient.offProductLabelIds = undefined;
}

/** Resolve a declared origin once; manual edits afterward remain until the product changes. */
export function applyProductOrigin(ingredient: Ingredient, options: TaxonomyItem[]) {
	if (!ingredient.barcode || ingredient.offProductOriginId === undefined) return;
	ingredient.origin = options.find((origin) => origin.id === ingredient.offProductOriginId) ?? null;
	ingredient.offProductOriginId = undefined;
}

/** Seed empty searches on load; changing ingredients invalidates previous references. */
export function syncNutritionSearches(ingredient: Ingredient, previousName?: string) {
	const changed = previousName !== undefined && previousName !== ingredient.name;
	if (changed && ingredient.resolvedReferenceName !== ingredient.name) {
		clearOffMetadata(ingredient);
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
