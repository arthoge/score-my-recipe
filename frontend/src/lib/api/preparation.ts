/** Backend estimates of prepared mass; cooking coefficients stay in the API. */
import { env } from '$env/dynamic/public';
import type { Ingredient } from '$lib/types/ingredient';

export type PreparedWeightResponse = {
	status: 'unchanged' | 'estimated' | 'unsupported';
	prepared_weight_g: number | null;
	yield_factor: number | null;
	source: NonNullable<Ingredient['preparedWeightSuggestion']>['source'];
};

/** Ask for the selected generic food's documented preparation yield. */
export async function estimatePreparedWeight(ingredient: Ingredient, signal?: AbortSignal) {
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/prepared-weight`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			quantity_g: ingredient.weight,
			state: ingredient.state ?? 'raw',
			preparation: ingredient.preparationProfile ?? 'none',
			ciqual_code: ingredient.ciqualCode || null,
			barcode: ingredient.barcode || null
		}),
		signal
	});
	if (!response.ok) throw new Error(`Prepared weight estimate failed: ${response.status}`);
	return (await response.json()) as PreparedWeightResponse;
}
