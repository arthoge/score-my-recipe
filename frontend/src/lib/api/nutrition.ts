/** Name searches for generic CIQUAL foods and identified Open Food Facts products. */
import { env } from '$env/dynamic/public';
import { getLocale } from '$lib/i18n';
import type { TaxonomyItem } from '$lib/types/ingredient';

/** Official CIQUAL food identities; composition data is separate. */
type FoodSearchResponse = {
	foods: { code?: string; ciqual_code: string; name: string; synonyms?: string[] }[];
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
			synonyms: food.synonyms
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
	const data: { foods: { code: string; name: string }[] } = await response.json();
	return data.foods.map(
		(food): TaxonomyItem => ({ id: food.code, label: food.name, isInTaxonomy: true })
	);
}

/** Fetch the same taxonomy correspondences used by the backend's Green Score matching. */
export async function getIngredientReferences(taxonomyId: string, signal?: AbortSignal) {
	const params = new URLSearchParams({ taxonomy_id: taxonomyId, lang: getLocale().split('-')[0] });
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
	const data: { foods: { code: string; name: string }[] } = await response.json();
	return data.foods
		.slice(0, limit)
		.map((food): TaxonomyItem => ({ id: food.code, label: food.name, isInTaxonomy: true }));
}
