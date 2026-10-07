/** Form validation shared by cell highlighting and automatic scoring. */
import { isIngredientNotEmpty, type Ingredient } from '$lib/types/ingredient';

/** A weight or portion value is usable only when finite and strictly positive. */
export function isPositiveAmount(value: number | null | undefined): boolean {
	return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

/** Zero quantities can be excluded; negative, missing and non-finite values remain invalid. */
export function isNonNegativeAmount(value: number | null | undefined): boolean {
	return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

/** Validate visible inputs without guessing missing quantities or database references. */
export function ingredientCellErrors(ingredient: Ingredient) {
	const populated = isIngredientNotEmpty(ingredient);
	const reference = ingredient.codifiedIngredient;
	return {
		name: populated && !ingredient.name.trim(),
		weight: populated && !isNonNegativeAmount(ingredient.weight),
		preparedWeight:
			ingredient.measuredPreparedWeightG != null &&
			!isPositiveAmount(ingredient.measuredPreparedWeightG),
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

/** Allow incomplete drafts to be excluded while at least one usable environmental row remains. */
export function canAutoScore(ingredients: Ingredient[], portions?: number | null): boolean {
	const rows = ingredients.filter(isIngredientNotEmpty);
	return (
		rows.some(
			(row) =>
				isPositiveAmount(row.weight) &&
				!ingredientCellErrors(row).name &&
				!ingredientCellErrors(row).environmentalReference
		) &&
		(portions == null || (isPositiveAmount(portions) && Number.isInteger(portions))) &&
		rows.every(
			(ingredient) =>
				(ingredient.weight == null || isNonNegativeAmount(ingredient.weight)) &&
				!ingredientCellErrors(ingredient).preparedWeight
		)
	);
}

/** Map calculation diagnostics to the source cells, keeping optional unused sources neutral. */
export function ingredientCalculationCells(
	ingredient: Ingredient,
	environmentalMissing: boolean,
	diagnostics: { code: string; fields?: string[] }[],
	usesCiqualFallback = false
) {
	if (ingredient.weight == null || ingredient.weight === 0)
		return { agribalyse: null, ciqual: null, product: null, preparation: null, state: null };
	const populated = isIngredientNotEmpty(ingredient);
	const usesProduct = !!ingredient.barcode;
	const sourceIssues = diagnostics.filter(
		(issue) => !['unsupported_preparation', 'prepared_reference_required'].includes(issue.code)
	);
	const severity = (hasValue: boolean): 'error' | 'warning' => (hasValue ? 'warning' : 'error');
	return {
		agribalyse:
			environmentalMissing || ingredientCellErrors(ingredient).environmentalReference
				? severity(!!ingredient.agribalyseName?.trim())
				: null,
		ciqual:
			!usesProduct && (sourceIssues.length > 0 || (populated && !ingredient.ciqualCode))
				? severity(!!ingredient.ciqualName?.trim())
				: null,
		product: usesCiqualFallback
			? 'info'
			: usesProduct && sourceIssues.length > 0
				? severity(!!ingredient.productName?.trim())
				: null,
		preparation: diagnostics.some((issue) => issue.code === 'unsupported_preparation')
			? 'warning'
			: null,
		state: diagnostics.some((issue) => issue.code === 'prepared_reference_required')
			? 'warning'
			: null
	};
}
