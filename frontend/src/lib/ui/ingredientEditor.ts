/** Form validation shared by cell highlighting and automatic scoring. */
import { isIngredientNotEmpty, type Ingredient } from '$lib/types/ingredient';

/** A weight or portion value is usable only when finite and strictly positive. */
export function isPositiveAmount(value: number | null | undefined): boolean {
	return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

/** Validate visible inputs without guessing missing quantities or database references. */
export function ingredientCellErrors(ingredient: Ingredient) {
	const populated = isIngredientNotEmpty(ingredient);
	const reference = ingredient.codifiedIngredient;
	return {
		name: populated && !ingredient.name.trim(),
		weight: populated && !isPositiveAmount(ingredient.weight),
		environmentalReference:
			populated &&
			!ingredient.agribalyseCode &&
			(ingredient.referenceSource === 'manual' ||
				!(
					reference?.id &&
					reference.isInTaxonomy &&
					!('hasEfScore' in reference && reference.hasEfScore === false)
				))
	};
}

/** Ignore the blank insertion row and block scoring until every populated row is valid. */
export function canAutoScore(ingredients: Ingredient[], portions?: number | null): boolean {
	const rows = ingredients.filter(isIngredientNotEmpty);
	return (
		rows.length > 0 &&
		(portions == null || (isPositiveAmount(portions) && Number.isInteger(portions))) &&
		rows.every((ingredient) => !Object.values(ingredientCellErrors(ingredient)).some(Boolean))
	);
}
