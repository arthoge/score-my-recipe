/**
 * Taxonomy related API functions
 */
import Fuse from 'fuse.js';
import type { TaxonomySuggestionsQuery } from '@openfoodfacts/openfoodfacts-nodejs';
import { OpenFoodFacts } from '@openfoodfacts/openfoodfacts-nodejs';
import { getLocale } from '$lib/i18n';
import { offLinks } from '$lib/offLink';
import type { TaxonomyItem, IngredientSuggestion } from '$lib/types/ingredient';
import type { components } from '../../api-schema';
import { env } from '$env/dynamic/public';

type Label = components['schemas']['Label'];
type Origin = components['schemas']['Origin'];
type SuggestedIngredient = components['schemas']['SuggestedIngredient'];
type Country = components['schemas']['Country'];
type CountriesResponse = components['schemas']['CountriesResponse'];
type UnitsResponse = components['schemas']['UnitsResponse'];

const API_BASE_URL = env.PUBLIC_RECIPE_API_URL ?? '';

type TaxonomySuggestionResponse = {
	suggestions: TaxonomyItem[];
	matched_synonyms: Record<string, string[]>;
};

const offAPIv3 = new OpenFoodFacts(fetch, { host: offLinks.website });

/**
 * wrapper for taxonomy API calls
 * @param tagtype taxonomy type to match against (e.g. 'ingredients', 'labels', 'countries')
 * @param query search term used to filter taxonomy items by label
 * @param limit maximum number of suggestions to return (defaults to 30)
 */
export async function getMatchingTags(
	tagtype: string,
	query: string,
	limit = 30
): Promise<TaxonomySuggestionResponse> {
	// temporary simulation
	const values = {
		ingredients: getIngredientsTaxonomy(),
		labels: getLabelsTaxonomy(),
		countries: getCountriesTaxonomy(),
		units: getUnitsTaxonomy()
	};
	if (Object.hasOwn(values, tagtype)) {
		const list = await values[tagtype as keyof typeof values];
		// Empty query: return all items (up to limit). Used by short-value
		// taxonomies like units (minChars=0) to show every option on focus.
		if (query.trim() === '') {
			return { suggestions: list.slice(0, limit), matched_synonyms: {} };
		}
		// Units have short labels/synonyms (e.g. "g", "kg", "l"), so a lower
		// minimum match length is needed than for ingredients/labels/countries.
		const minMatchCharLength = tagtype === 'units' ? 1 : 3;
		const fuse = new Fuse(list, {
			// search both the canonical label and the synonyms so that
			// alternative names also yield a match
			keys: ['label', 'synonyms'],
			includeScore: true,
			includeMatches: true,
			minMatchCharLength,
			ignoreDiacritics: true
		});
		const results = fuse
			.search(query)
			.sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
			.slice(0, limit);
		const suggestions = results.map((result) => result.item);
		// for each suggestion, collect the synonyms that actually matched the query
		// (matches on the 'synonyms' key carry the matched synonym string as value)
		const matched_synonyms: Record<string, string[]> = {};
		for (const result of results) {
			const matched = (result.matches ?? [])
				.filter((m) => m.key === 'synonyms' && typeof m.value === 'string')
				.map((m) => m.value as string);
			// The condition on item.id avoids type problems because it can be null.
			if (matched.length > 0 && result.item.id !== null) {
				matched_synonyms[result.item.id] = [...new Set(matched)];
			}
		}
		return {
			suggestions,
			matched_synonyms
		};
	}

	const suggestionQuery: TaxonomySuggestionsQuery = {
		tagtype: tagtype,
		term: query,
		lc: getLocaleKey(),
		limit: limit.toString(),
		get_synonyms: '1'
	};
	const response = await offAPIv3.apiv3.getTaxonomySuggestions(suggestionQuery);
	// we know the structure of the response from the API
	return response as unknown as TaxonomySuggestionResponse;
}

/**
 * Labels taxonomy - certification and quality labels with English and French translations
 */
export const LABELS_TAXONOMY: Record<string, TaxonomyItem[]> = {
	en: [
		{ id: 'en:organic', label: 'organic', isInTaxonomy: true },
		{ id: 'en:fair_trade', label: 'fair trade', isInTaxonomy: true },
		{ id: 'en:local', label: 'local', isInTaxonomy: true },
		{ id: 'en:seasonal', label: 'seasonal', isInTaxonomy: true },
		{ id: 'en:vegetarian', label: 'vegetarian', isInTaxonomy: true },
		{ id: 'en:vegan', label: 'vegan', isInTaxonomy: true },
		{ id: 'en:gluten_free', label: 'gluten free', isInTaxonomy: true },
		{ id: 'en:palm_oil_free', label: 'palm oil free', isInTaxonomy: true },
		{ id: 'en:recyclable', label: 'recyclable', isInTaxonomy: true },
		{ id: 'en:eco_friendly', label: 'eco friendly', isInTaxonomy: true },
		{ id: 'en:grass_fed', label: 'grass fed', isInTaxonomy: true },
		{ id: 'en:wild_caught', label: 'wild caught', isInTaxonomy: true },
		{ id: 'en:farm_raised', label: 'farm raised', isInTaxonomy: true },
		{ id: 'en:non_gmo', label: 'non GMO', isInTaxonomy: true },
		{ id: 'en:rainforest_alliance', label: 'rainforest alliance', isInTaxonomy: true },
		{ id: 'en:sustainable', label: 'sustainable', isInTaxonomy: true }
	],
	fr: [
		{ id: 'en:organic', label: 'bio', isInTaxonomy: true },
		{ id: 'en:fair_trade', label: 'commerce équitable', isInTaxonomy: true },
		{ id: 'en:local', label: 'local', isInTaxonomy: true },
		{ id: 'en:seasonal', label: 'de saison', isInTaxonomy: true },
		{ id: 'en:vegetarian', label: 'végétarien', isInTaxonomy: true },
		{ id: 'en:vegan', label: 'végan', isInTaxonomy: true },
		{ id: 'en:gluten_free', label: 'sans gluten', isInTaxonomy: true },
		{ id: 'en:palm_oil_free', label: 'sans huile de palme', isInTaxonomy: true },
		{ id: 'en:recyclable', label: 'recyclable', isInTaxonomy: true },
		{ id: 'en:eco_friendly', label: 'écologique', isInTaxonomy: true },
		{ id: 'en:grass_fed', label: 'herbe nourri', isInTaxonomy: true },
		{ id: 'en:wild_caught', label: 'pêché sauvage', isInTaxonomy: true },
		{ id: 'en:farm_raised', label: 'élevé à la ferme', isInTaxonomy: true },
		{ id: 'en:non_gmo', label: 'non OGM', isInTaxonomy: true },
		{ id: 'en:rainforest_alliance', label: 'alliance pour la forêt tropicale', isInTaxonomy: true },
		{ id: 'en:sustainable', label: 'durable', isInTaxonomy: true }
	]
};

/**
 * Countries taxonomy - list of countries for origin tracking with English and French translations
 */
export const COUNTRIES_TAXONOMY: Record<string, TaxonomyItem[]> = {
	en: [
		{ id: 'en:france', label: 'France', isInTaxonomy: true },
		{ id: 'en:italy', label: 'Italy', isInTaxonomy: true },
		{ id: 'en:spain', label: 'Spain', isInTaxonomy: true },
		{ id: 'en:germany', label: 'Germany', isInTaxonomy: true },
		{ id: 'en:united_kingdom', label: 'United Kingdom', isInTaxonomy: true },
		{ id: 'en:united_states', label: 'United States', isInTaxonomy: true },
		{ id: 'en:canada', label: 'Canada', isInTaxonomy: true },
		{ id: 'en:japan', label: 'Japan', isInTaxonomy: true },
		{ id: 'en:china', label: 'China', isInTaxonomy: true },
		{ id: 'en:india', label: 'India', isInTaxonomy: true },
		{ id: 'en:brazil', label: 'Brazil', isInTaxonomy: true },
		{ id: 'en:argentina', label: 'Argentina', isInTaxonomy: true },
		{ id: 'en:australia', label: 'Australia', isInTaxonomy: true },
		{ id: 'en:new_zealand', label: 'New Zealand', isInTaxonomy: true },
		{ id: 'en:south_africa', label: 'South Africa', isInTaxonomy: true },
		{ id: 'en:morocco', label: 'Morocco', isInTaxonomy: true },
		{ id: 'en:egypt', label: 'Egypt', isInTaxonomy: true },
		{ id: 'en:turkey', label: 'Turkey', isInTaxonomy: true },
		{ id: 'en:greece', label: 'Greece', isInTaxonomy: true },
		{ id: 'en:portugal', label: 'Portugal', isInTaxonomy: true },
		{ id: 'en:netherlands', label: 'Netherlands', isInTaxonomy: true },
		{ id: 'en:belgium', label: 'Belgium', isInTaxonomy: true },
		{ id: 'en:switzerland', label: 'Switzerland', isInTaxonomy: true },
		{ id: 'en:austria', label: 'Austria', isInTaxonomy: true },
		{ id: 'en:poland', label: 'Poland', isInTaxonomy: true },
		{ id: 'en:sweden', label: 'Sweden', isInTaxonomy: true },
		{ id: 'en:norway', label: 'Norway', isInTaxonomy: true },
		{ id: 'en:denmark', label: 'Denmark', isInTaxonomy: true },
		{ id: 'en:finland', label: 'Finland', isInTaxonomy: true },
		{ id: 'en:ireland', label: 'Ireland', isInTaxonomy: true },
		{ id: 'en:scotland', label: 'Scotland', isInTaxonomy: true },
		{ id: 'en:mexico', label: 'Mexico', isInTaxonomy: true },
		{ id: 'en:peru', label: 'Peru', isInTaxonomy: true },
		{ id: 'en:chile', label: 'Chile', isInTaxonomy: true },
		{ id: 'en:colombia', label: 'Colombia', isInTaxonomy: true },
		{ id: 'en:vietnam', label: 'Vietnam', isInTaxonomy: true },
		{ id: 'en:thailand', label: 'Thailand', isInTaxonomy: true },
		{ id: 'en:indonesia', label: 'Indonesia', isInTaxonomy: true },
		{ id: 'en:malaysia', label: 'Malaysia', isInTaxonomy: true },
		{ id: 'en:philippines', label: 'Philippines', isInTaxonomy: true },
		{ id: 'en:south_korea', label: 'South Korea', isInTaxonomy: true },
		{ id: 'en:taiwan', label: 'Taiwan', isInTaxonomy: true }
	],
	fr: [
		{ id: 'en:france', label: 'France', isInTaxonomy: true },
		{ id: 'en:italy', label: 'Italie', isInTaxonomy: true },
		{ id: 'en:spain', label: 'Espagne', isInTaxonomy: true },
		{ id: 'en:germany', label: 'Allemagne', isInTaxonomy: true },
		{ id: 'en:united_kingdom', label: 'Royaume-Uni', isInTaxonomy: true },
		{ id: 'en:united_states', label: 'États-Unis', isInTaxonomy: true },
		{ id: 'en:canada', label: 'Canada', isInTaxonomy: true },
		{ id: 'en:japan', label: 'Japon', isInTaxonomy: true },
		{ id: 'en:china', label: 'Chine', isInTaxonomy: true },
		{ id: 'en:india', label: 'Inde', isInTaxonomy: true },
		{ id: 'en:brazil', label: 'Brésil', isInTaxonomy: true },
		{ id: 'en:argentina', label: 'Argentine', isInTaxonomy: true },
		{ id: 'en:australia', label: 'Australie', isInTaxonomy: true },
		{ id: 'en:new_zealand', label: 'Nouvelle-Zélande', isInTaxonomy: true },
		{ id: 'en:south_africa', label: 'Afrique du Sud', isInTaxonomy: true },
		{ id: 'en:morocco', label: 'Maroc', isInTaxonomy: true },
		{ id: 'en:egypt', label: 'Égypte', isInTaxonomy: true },
		{ id: 'en:turkey', label: 'Turquie', isInTaxonomy: true },
		{ id: 'en:greece', label: 'Grèce', isInTaxonomy: true },
		{ id: 'en:portugal', label: 'Portugal', isInTaxonomy: true },
		{ id: 'en:netherlands', label: 'Pays-Bas', isInTaxonomy: true },
		{ id: 'en:belgium', label: 'Belgique', isInTaxonomy: true },
		{ id: 'en:switzerland', label: 'Suisse', isInTaxonomy: true },
		{ id: 'en:austria', label: 'Autriche', isInTaxonomy: true },
		{ id: 'en:poland', label: 'Pologne', isInTaxonomy: true },
		{ id: 'en:sweden', label: 'Suède', isInTaxonomy: true },
		{ id: 'en:norway', label: 'Norvège', isInTaxonomy: true },
		{ id: 'en:denmark', label: 'Danemark', isInTaxonomy: true },
		{ id: 'en:finland', label: 'Finlande', isInTaxonomy: true },
		{ id: 'en:ireland', label: 'Irlande', isInTaxonomy: true },
		{ id: 'en:scotland', label: 'Écosse', isInTaxonomy: true },
		{ id: 'en:mexico', label: 'Mexique', isInTaxonomy: true },
		{ id: 'en:peru', label: 'Pérou', isInTaxonomy: true },
		{ id: 'en:chile', label: 'Chili', isInTaxonomy: true },
		{ id: 'en:colombia', label: 'Colombie', isInTaxonomy: true },
		{ id: 'en:vietnam', label: 'Vietnam', isInTaxonomy: true },
		{ id: 'en:thailand', label: 'Thaïlande', isInTaxonomy: true },
		{ id: 'en:indonesia', label: 'Indonésie', isInTaxonomy: true },
		{ id: 'en:malaysia', label: 'Malaisie', isInTaxonomy: true },
		{ id: 'en:philippines', label: 'Philippines', isInTaxonomy: true },
		{ id: 'en:south_korea', label: 'Corée du Sud', isInTaxonomy: true },
		{ id: 'en:taiwan', label: 'Taïwan', isInTaxonomy: true }
	]
};

/**
 * Get the current locale key ('en' or 'fr')
 */
function getLocaleKey(): 'en' | 'fr' {
	const locale = getLocale();
	return locale.startsWith('fr') ? 'fr' : 'en';
}

/**
 * Fetch the ingredients taxonomy from the backend API.
 *
 * Each returned item carries `hasEfScore`, telling whether the ingredient
 * resolves to an Agribalyse row with an EF score (i.e. whether it can be
 * counted in the green-score computation).
 *
 * @param includeSynonyms whether to also fetch synonyms (defaults to true, used for matching)
 * @returns Promise resolving to the list of ingredient suggestions (with EF-score flag)
 */
export async function getIngredientsTaxonomy(
	includeSynonyms = true
): Promise<IngredientSuggestion[]> {
	const lang = getLocaleKey();
	const params = new URLSearchParams({ lang });
	if (includeSynonyms) {
		params.set('include_synonyms', 'true');
	}
	const response = await fetch(`${API_BASE_URL}/v1/ingredients?${params.toString()}`);
	if (!response.ok) {
		throw new Error(`Failed to fetch ingredients: ${response.statusText}`);
	}
	const data = (await response.json()) as { ingredients: SuggestedIngredient[] };
	return data.ingredients.map((ingredient) => ({
		id: ingredient.id,
		label: ingredient.label,
		isInTaxonomy: true,
		synonyms: ingredient.synonyms ?? [],
		hasEfScore: ingredient.has_ef_score
	}));
}

/**
 * Fetch the labels taxonomy from the backend API
 * @param includeSynonyms whether to also fetch synonyms (defaults to true, used for matching)
 * @returns Promise resolving to the list of label taxonomy items
 */
export async function getLabelsTaxonomy(includeSynonyms = true): Promise<TaxonomyItem[]> {
	const lang = getLocaleKey();
	const params = new URLSearchParams({ lang });
	if (includeSynonyms) {
		params.set('include_synonyms', 'true');
	}
	const response = await fetch(`${API_BASE_URL}/v1/labels?${params.toString()}`);
	if (!response.ok) {
		throw new Error(`Failed to fetch labels: ${response.statusText}`);
	}
	const data = (await response.json()) as { labels: Label[] };
	return data.labels.map((label) => ({
		id: label.id,
		label: label.label,
		isInTaxonomy: true,
		synonyms: label.synonyms ?? []
	}));
}

/**
 * Fetch the countries taxonomy from the backend API
 * @param includeSynonyms whether to also fetch synonyms (defaults to true, used for matching)
 * @returns Promise resolving to the list of country taxonomy items
 */
export async function getCountriesTaxonomy(includeSynonyms = true): Promise<TaxonomyItem[]> {
	const lang = getLocaleKey();
	const params = new URLSearchParams({ lang });
	if (includeSynonyms) {
		params.set('include_synonyms', 'true');
	}
	const response = await fetch(`${API_BASE_URL}/v1/origins?${params.toString()}`);
	if (!response.ok) {
		throw new Error(`Failed to fetch origins: ${response.statusText}`);
	}
	const data = (await response.json()) as { origins: Origin[] };
	return data.origins.map((origin) => ({
		id: origin.id,
		label: origin.label,
		isInTaxonomy: true,
		synonyms: origin.synonyms ?? []
	}));
}

/**
 * Fetch the list of countries relevant for the green-score computation.
 *
 * Only countries with a usable ISO 3166-1 alpha-2 country code are returned,
 * since the green-score `country` parameter expects such a code. Countries
 * without a code cannot influence the distance modifier and would mislead the
 * user if offered as a choice.
 *
 * @param lang - The language code for the country labels (e.g. `"en"`).
 * @returns The list of countries (with a non-null country code) from the backend.
 * @throws {Error} If the backend responds with a non-2xx status code.
 */
export async function getCountries(lang: string): Promise<Country[]> {
	const response = await fetch(`${API_BASE_URL}/v1/countries?lang=${encodeURIComponent(lang)}`);

	if (!response.ok) {
		throw new Error(`Error ${response.status}: ${response.statusText}`);
	}

	const data = (await response.json()) as CountriesResponse;
	return data.countries.filter((country) => country.country_code != null);
}

/**
 * The id of the synthetic ``item`` unit, used for countable ingredients
 * (e.g. "3 eggs"). Mirrors the backend ``types.ITEM_UNIT`` sentinel.
 */
export const ITEM_UNIT_ID = 'item';

/**
 * Cache for the units taxonomy, keyed by language code.
 *
 * The units list is small and changes rarely, so it is fetched once per
 * language and reused across all ingredient lines.
 */
const unitsCache: Record<string, TaxonomyItem[]> = {};

/**
 * Fetch the list of units (mass and volume) from the backend, with synonyms
 * for client-side matching.
 *
 * The synthetic ``item`` unit (for countable ingredients) is appended
 * client-side because its label is context-dependent (it should read as the
 * ingredient name, handled by the Tags ``formatLabel`` prop).
 *
 * @returns The list of unit TaxonomyItems (taxonomy units + the ``item`` sentinel).
 * @throws {Error} If the backend responds with a non-2xx status code.
 */
export async function getUnitsTaxonomy(): Promise<TaxonomyItem[]> {
	const lang = getLocaleKey();
	if (unitsCache[lang]) {
		return unitsCache[lang];
	}
	const params = new URLSearchParams({ lang, include_synonyms: 'true' });
	const response = await fetch(`${API_BASE_URL}/v1/units?${params.toString()}`);
	if (!response.ok) {
		throw new Error(`Failed to fetch units: ${response.statusText}`);
	}
	const data = (await response.json()) as UnitsResponse;
	// Map the backend Unit to the frontend TaxonomyItem shape.
	const units: TaxonomyItem[] = data.units.map((unit) => ({
		id: unit.id,
		label: unit.label,
		isInTaxonomy: true,
		synonyms: unit.synonyms ?? []
	}));
	// Append the synthetic 'item' unit for countable ingredients.
	// Its label is substituted at render time (see IngredientLine) so it
	// displays as the ingredient name instead of the literal 'item'.
	units.push({ id: ITEM_UNIT_ID, label: ITEM_UNIT_ID, isInTaxonomy: true, synonyms: [] });
	unitsCache[lang] = units;
	return units;
}
