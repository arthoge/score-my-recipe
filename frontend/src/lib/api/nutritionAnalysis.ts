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
	for (let attempt = 0; ; attempt++) {
		signal.throwIfAborted();
		let response: Response;
		try {
			response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/nutrition/analyze`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(inputs),
				signal
			});
		} catch (error) {
			if (attempt === 0 && !signal.aborted && error instanceof TypeError) continue;
			throw error;
		}
		// A cold or temporarily unavailable dependency gets one retry. Invalid inputs
		// and incomplete food data need correction rather than another identical call.
		if (!response.ok) {
			if (attempt === 0 && [502, 503, 504].includes(response.status)) continue;
			throw new Error(`Nutrition analysis failed: ${response.status}`);
		}
		const result = (await response.json()) as NutritionAnalysis;
		if (attempt === 0 && result.status === 'dependency_error') continue;
		return result;
	}
}
