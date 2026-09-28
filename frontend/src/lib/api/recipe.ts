/**
 * @fileoverview Recipe API client
 *
 * This module wraps the calls to the Score My Recipe backend
 * (see `server/api/api.py`) so that Svelte components don't have
 * to deal with raw `fetch` calls and URL building.
 */

import type { components } from '../../api-schema';
import type { Ingredient, IngredientType } from '$lib/types/ingredient';
import { generateIngredientId, isIngredientNotEmpty } from '$lib/types/ingredient';
import { env } from '$env/dynamic/public';
import type { IngredientsList } from '$lib/types/ingredientsList';

/** Response schema for the `parse_text` endpoint, generated from the OpenAPI schema. */
export type RecipeParseResponse = components['schemas']['RecipeParseResponse'];

/** Single ingredient schema from the `parse_text` endpoint. */
export type RecipeIngredient = components['schemas']['RecipeIngredient'];

/** Request body schema for the green-score computation endpoint. */
export type GreenScoreRequest = components['schemas']['GreenScoreRequest'];

/** Response schema for the green-score computation endpoint. */
export type GreenScoreResponse = components['schemas']['GreenScoreResponse'];

/** Single origin schema from the `get_origins` endpoint. */
export type Origin = components['schemas']['Origin'];

/** Response schema for the `get_origins` endpoint. */
export type OriginsResponse = components['schemas']['OriginsResponse'];

/** Base URL of the Score My Recipe backend. */
const API_BASE_URL = env.PUBLIC_RECIPE_API_URL ?? '';
/**
 * Parse a free-form recipe text and return the list of detected ingredients
 * with their quantities and taxonomy information.
 *
 * @param text - The raw recipe text to parse.
 * @param lang - The language code of the recipe text (e.g. `"fr"`).
 * @returns The parsed recipe response from the backend.
 * @throws {Error} If the backend responds with a non-2xx status code.
 */
export async function parseRecipeText(text: string, lang: string): Promise<RecipeParseResponse> {
	const response = await fetch(`${API_BASE_URL}/v1/parse_text`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ text, lang })
	});

	if (!response.ok) {
		throw new Error(`Error ${response.status}: ${response.statusText}`);
	}

	return (await response.json()) as RecipeParseResponse;
}

/**
 * Convert a single API `RecipeIngredient` into the frontend `Ingredient` shape
 * used by the recipe editor.
 *
 * @param apiIngredient - The ingredient as returned by the backend.
 * @returns An `Ingredient` ready to be displayed in an `IngredientLine`.
 */
export function apiIngredientToIngredient(apiIngredient: RecipeIngredient): Ingredient {
	const taxonomyItem: IngredientType = {
		id: apiIngredient.taxonomy_id ?? apiIngredient.codified_ingredient,
		label: apiIngredient.codified_ingredient,
		isInTaxonomy: apiIngredient.is_in_taxonomy
	};
	return {
		id: generateIngredientId(),
		name: apiIngredient.codified_ingredient,
		weight: apiIngredient.quantity_g ?? null,
		codifiedIngredient: taxonomyItem,
		labels: [],
		isFreshPlant: false,
		isInSeason: false,
		origin: null
	};
}

/**
 * Convert a list of API `RecipeIngredient` into frontend `Ingredient` objects.
 *
 * @param apiIngredients - The list of ingredients as returned by the backend.
 * @returns A list of `Ingredient` ready to be displayed in the recipe editor.
 */
export function apiIngredientsToIngredients(apiIngredients: RecipeIngredient[]): Ingredient[] {
	return apiIngredients.map(apiIngredientToIngredient);
}

/**
 * Convert the frontend `Ingredient` shape into the API `RecipeIngredientInput`
 * payload expected by the green-score endpoint.
 *
 * The API requires a non-null `weight` (in grams); ingredients without a
 * weight are sent with a weight of 0 so the backend can flag them as missing.
 *
 * @param ingredient - The frontend ingredient to convert.
 * @returns The ingredient payload ready to be sent to the backend.
 */
export function ingredientToGreenScoreInput(
	ingredient: Ingredient
): components['schemas']['RecipeIngredientInput'] {
	const codifiedIngredient: IngredientType = ingredient.codifiedIngredient ?? {
		id: ingredient.name,
		label: ingredient.name,
		isInTaxonomy: false
	};
	return {
		id: ingredient.id,
		name: ingredient.name,
		weight: ingredient.weight ?? 0,
		codifiedIngredient,
		labels: ingredient.labels,
		isFreshPlant: ingredient.isFreshPlant,
		isInSeason: ingredient.isInSeason,
		origin: ingredient.origin
	};
}

/**
 * Optional parameters for the green-score computation.
 */
export type ComputeGreenScoreOptions = {
	/**
	 * ISO 3166-1 alpha-2 country code (e.g. `"FR"`) of the country the recipe is
	 * being cooked in. Used by the backend to compute the distance modifier.
	 * When omitted, the distance defaults to "world".
	 */
	country?: string;
	/** Optional abort signal to cancel the in-flight request. */
	signal?: AbortSignal;
};

/**
 * Compute the green-score of a recipe by calling the backend endpoint.
 *
 * Only non-empty ingredients are sent, as empty lines are just placeholders for
 * the editor and carry no meaningful data.
 *
 * @param ingredients - The current list of ingredients in the editor.
 * @param options - Optional parameters (country code and abort signal).
 * @returns The green-score response from the backend.
 * @throws {Error} If the backend responds with a non-2xx status code.
 */
export async function computeGreenScore(
	ingredients: IngredientsList,
	options: ComputeGreenScoreOptions = {}
): Promise<GreenScoreResponse> {
	const { country, signal } = options;
	const payload: GreenScoreRequest = {
		ingredients: ingredients.filter(isIngredientNotEmpty).map(ingredientToGreenScoreInput),
		accountedWeights: 'scorable',
		country: country ?? null
	};
	const response = await fetch(`${API_BASE_URL}/v1/green-score`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload),
		signal
	});

	if (!response.ok) {
		throw new Error(`Error ${response.status}: ${response.statusText}`);
	}

	return (await response.json()) as GreenScoreResponse;
}

/**
 * Fetch the list of available origins (countries) from the backend.
 *
 * @param lang - The language code for the origin labels (e.g. `"fr"`).
 * @returns The list of origins from the backend.
 * @throws {Error} If the backend responds with a non-2xx status code.
 */
export async function getOrigins(lang: string): Promise<Origin[]> {
	const response = await fetch(`${API_BASE_URL}/v1/origins?lang=${encodeURIComponent(lang)}`);

	if (!response.ok) {
		throw new Error(`Error ${response.status}: ${response.statusText}`);
	}

	const data = (await response.json()) as OriginsResponse;
	return data.origins;
}
