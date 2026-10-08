/** Name searches for generic CIQUAL foods and identified Open Food Facts products. */
import { env } from '$env/dynamic/public';
import { getLocale } from '$lib/i18n';
import type { TaxonomyItem } from '$lib/types/ingredient';

/** Official CIQUAL food identities; composition data is separate. */
type FoodSearchResponse = {
	foods: {
		code?: string;
		ciqual_code: string;
		name: string;
		synonyms?: string[];
		missing_data?: string[];
		no_data?: boolean;
	}[];
};

/** Search the bundled ANSES CIQUAL 2025 food catalog by its official names. */
export async function searchCiqualFoods(query: string, limit = 8, signal?: AbortSignal) {
	const params = new URLSearchParams({
		q: query.trim(),
		lang: getLocale().split('-')[0],
		limit: String(limit)
	});
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/nutrition/foods?${params}`, {
		signal
	});
	if (!response.ok) throw new Error(`CIQUAL search failed: ${response.status}`);
	const data: FoodSearchResponse = await response.json();
	return data.foods.slice(0, limit).map(
		(food): TaxonomyItem => ({
			id: String(food.ciqual_code),
			label: food.name,
			isInTaxonomy: true,
			synonyms: food.synonyms,
			missingData: food.missing_data,
			noData: food.no_data
		})
	);
}

/** Search actual Agribalyse food rows for an environmental reference override. */
export async function searchAgribalyseFoods(query: string, limit = 8, signal?: AbortSignal) {
	const params = new URLSearchParams({ q: query.trim(), limit: String(limit) });
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/agribalyse/foods?${params}`, {
		signal
	});
	if (!response.ok) throw new Error(`Agribalyse search failed: ${response.status}`);
	const data: {
		foods: { code: string; name: string; missing_data?: string[]; no_data?: boolean }[];
	} = await response.json();
	return data.foods.map(
		(food): TaxonomyItem => ({
			id: food.code,
			label: food.name,
			isInTaxonomy: true,
			missingData: food.missing_data,
			noData: food.no_data
		})
	);
}

/** Resolve selected codes and conservative catalogue/taxonomy name correspondences. */
export async function getIngredientReferences(
	taxonomyId: string | undefined,
	signal?: AbortSignal,
	input?: { name: string; ciqualCode?: string; agribalyseCode?: string }
) {
	const params = new URLSearchParams({ lang: getLocale().split('-')[0] });
	if (taxonomyId) params.set('taxonomy_id', taxonomyId);
	if (input?.name) params.set('q', input.name);
	if (input?.ciqualCode) params.set('ciqual_code', input.ciqualCode);
	if (input?.agribalyseCode) params.set('agribalyse_code', input.agribalyseCode);
	const response = await fetch(
		`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/ingredient-references?${params}`,
		{ signal }
	);
	if (!response.ok) throw new Error(`Reference matching failed: ${response.status}`);
	return (await response.json()) as {
		agribalyse: { code: string; name: string } | null;
		ciqual: { code: string; name: string } | null;
		source: string | null;
	};
}

/** Search OFF through our backend to avoid cross-origin browser failures. */
export async function searchOffProducts(query: string, limit = 8, signal?: AbortSignal) {
	const params = new URLSearchParams({
		q: query.trim(),
		lang: getLocale().split('-')[0],
		limit: String(limit)
	});
	const response = await fetch(
		`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/nutrition/products?${params}`,
		{ signal }
	);
	if (!response.ok) throw new Error(`Product search failed: ${response.status}`);
	const data: {
		foods: {
			code: string;
			name: string;
			missing_data?: string[];
			no_data?: boolean;
			automatic_match?: boolean;
			label_ids?: string[];
			origin_id?: string | null;
		}[];
	} = await response.json();
	return data.foods.slice(0, limit).map(
		(food): TaxonomyItem => ({
			id: food.code,
			label: food.name,
			isInTaxonomy: true,
			missingData: food.missing_data,
			noData: food.no_data,
			automaticMatch: food.automatic_match,
			productLabelIds: food.label_ids,
			productOriginId: food.origin_id
		})
	);
}
