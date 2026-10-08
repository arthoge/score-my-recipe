/** Cooking-aware nutrition analysis, independent of environmental scoring. */
import { env } from '$env/dynamic/public';
import type { Ingredient } from '$lib/types/ingredient';
import { isIngredientNotEmpty } from '$lib/types/ingredient';

import type { components } from '../../api-schema';

export type NutritionDiagnostic = components['schemas']['Diagnostic'];
export type NutritionAnalysis = Required<components['schemas']['NutritionResponse']>;
export type NutritionCategory = NonNullable<components['schemas']['NutritionRequest']['category']>;

/** Preserve exact references and measured weights; cooking rules belong to the backend. */
export function nutritionInputs(
	ingredients: Ingredient[],
	portions: number | null | undefined,
	category: NutritionCategory = 'en:meals'
) {
	return {
		category,
		portions: portions ?? 1,
		ingredients: ingredients.filter(isIngredientNotEmpty).map((row) => ({
			id: row.id,
			name: row.name,
			quantity_g: row.weight,
			state: row.state ?? 'raw',
			preparation: row.preparationProfile ?? 'none',
			ciqual_code: row.ciqualCode || null,
			barcode: row.barcode || null,
			// Zero-quantity rows are excluded by the backend regardless of a manual mass.
			prepared_weight_g: row.weight === 0 ? null : (row.measuredPreparedWeightG ?? null)
		}))
	};
}

/** Fetch recipe totals and the 2023 grade with cancellation for stale edits. */
export async function analyzeNutrition(
	inputs: ReturnType<typeof nutritionInputs>,
	signal: AbortSignal
) {
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/nutrition/analyze`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(inputs),
		signal
	});
	if (!response.ok) throw new Error(`Nutrition analysis failed: ${response.status}`);
	return (await response.json()) as NutritionAnalysis;
}
