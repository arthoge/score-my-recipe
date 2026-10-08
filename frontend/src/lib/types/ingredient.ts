/**
 * Ingredient type definitions for recipe management
 *
 * This module contains all type definitions and factory functions
 * for ingredient-related data structures.
 */

/**
 * A taxonomy item with id and localized label
 */
export interface TaxonomyItem {
	/**
	 * Taxonomy identifier, or `null` when the value is not in the taxonomy.
	 */
	id: string | null;
	/** Display label in the current language */
	label: string;
	/** Whether this item comes from the taxonomy (true) or is a custom user entry (false) */
	isInTaxonomy: boolean;
	/** Synonyms in the current language (used for matching; may be empty) */
	synonyms?: string[];
	/** Required data absent from this reference, as reported by the search API. */
	missingData?: string[];
	/** The reference has no usable measurements for its score. */
	noData?: boolean;
}

/**
 * Represents a label/certification (e.g., organic, fair-trade)
 */
export type Label = TaxonomyItem;

/**
 * Represents an origin/country
 */
export type Origin = TaxonomyItem;

/**
 * Represents a codified ingredient from taxonomy
 */
export type IngredientType = TaxonomyItem;

/**
 * An ingredient suggestion returned by the autocomplete API (`/v1/ingredients`),
 * extending a TaxonomyItem with the EF-score presence flag.
 *
 * `hasEfScore` is true when the ingredient resolves (through its taxonomy node
 * and its parents) to an Agribalyse row carrying an EF score — i.e. it can be
 * counted in the green-score computation.
 */
export interface IngredientSuggestion extends TaxonomyItem {
	/** Whether the ingredient has an EF score (is scorable in the green-score). */
	hasEfScore: boolean;
}

/** Preparation choices shared by the editor and its typed draft values. */
export const PREPARATION_OPTIONS = [
	{ value: 'none', label: 'No preparation' },
	{ value: 'boiled', label: 'Boiled' },
	{ value: 'steamed', label: 'Steamed' },
	{ value: 'baked_roasted', label: 'Baked / roasted' },
	{ value: 'grilled', label: 'Grilled' },
	{ value: 'pan_fried', label: 'Pan-fried' },
	{ value: 'deep_fried', label: 'Deep-fried' }
] as const;

export type PreparationProfile = (typeof PREPARATION_OPTIONS)[number]['value'];

/**
 * Represents a single ingredient in a recipe
 */
export interface Ingredient {
	/** Unique identifier for the ingredient */
	id: string;
	/** Display name of the ingredient */
	name: string;
	/** Name whose references were resolved together by a confirmed server replacement. */
	resolvedReferenceName?: string;
	/** Weight in grams (null if not specified) */
	weight: number | null;
	/** Codified ingredient from taxonomy */
	codifiedIngredient: IngredientType | null;
	/** List of labels (e.g., organic, fair-trade) */
	labels: Label[];
	/** Whether the ingredient is a fresh fruit or vegetable (gates `isInSeason`) */
	isFreshPlant: boolean;
	/** Whether the ingredient is in season (only meaningful when `isFreshPlant` is true) */
	isInSeason: boolean;
	/** Origin countries/regions */
	origin: Origin | null;
	/** Preparation and nutrition fields used by the analysis API. */
	state?: 'raw' | 'cooked' | 'drained' | null;
	ciqualCode?: string;
	/** Visible food search text; a code is stored only after selecting a result. */
	ciqualName?: string;
	/** Actual environmental food row, separate from the OFF ingredient taxonomy. */
	agribalyseCode?: string;
	agribalyseName?: string;
	/** Mapping provenance may describe an inherited or proxy correspondence. */
	referenceSource?: string;
	barcode?: string;
	/** Visible product name and brand, separate from the internally stored barcode. */
	productName?: string;
	preparationProfile?: PreparationProfile;
	/** User-entered prepared weight; null or absent keeps the automatic suggestion. */
	measuredPreparedWeightG?: number | null;
	/** Backend suggestion keyed to its inputs so stale estimates are never displayed. */
	preparedWeightSuggestion?: {
		inputKey: string;
		weightG: number | null;
		yieldFactor: number | null;
		source: {
			version: string;
			url: string;
			table: string;
			food: string;
			conditions: string;
		} | null;
	};
}

/**
 * Generate a unique ID for ingredients
 * @returns A unique string identifier
 */
export function generateIngredientId(): string {
	return `ingredient-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Create a new empty ingredient with default values
 * @returns A new Ingredient object with empty/default values
 */
export function createEmptyIngredient(): Ingredient {
	return {
		id: generateIngredientId(),
		name: '',
		weight: null,
		codifiedIngredient: null,
		labels: [],
		isFreshPlant: false,
		isInSeason: false,
		origin: null,
		state: 'raw',
		preparationProfile: 'none'
	};
}

/**
 * Check if an ingredient is empty
 * @param ingredient - The ingredient to check
 * @returns True if the ingredient has no name
 */
export function isIngredientEmpty(ingredient: Ingredient): boolean {
	// Default flags, raw state and no preparation do not populate the insertion row.
	return (
		ingredient.name.trim() === '' &&
		ingredient.weight === null &&
		ingredient.codifiedIngredient === null &&
		ingredient.labels.length === 0 &&
		ingredient.origin === null &&
		(!ingredient.state || ingredient.state === 'raw') &&
		!ingredient.ciqualCode?.trim() &&
		!ingredient.ciqualName?.trim() &&
		!ingredient.agribalyseName?.trim() &&
		!ingredient.agribalyseCode &&
		!ingredient.barcode?.trim() &&
		!ingredient.productName?.trim() &&
		(!ingredient.preparationProfile || ingredient.preparationProfile === 'none') &&
		ingredient.measuredPreparedWeightG == null
	);
}

/**
 * Check if an ingredient has content (has a name)
 * @param ingredient - The ingredient to check
 * @returns True if the ingredient has a name
 */
export function isIngredientNotEmpty(ingredient: Ingredient): boolean {
	return !isIngredientEmpty(ingredient);
}

/**
 * Compute a signature string for an ingredient's relevant fields.
 *
 * Used to detect changes and reset inactivity timers (e.g. before recomputing
 * the green-score). Only the fields that affect the score are included.
 *
 * @param ingredient - The ingredient to sign.
 * @returns A string uniquely identifying the ingredient's relevant content.
 */
export function ingredientSignature(ingredient: Ingredient): string {
	return `${ingredient.id}:${ingredient.name}:${ingredient.weight ?? ''}:${ingredient.codifiedIngredient?.id ?? ''}:${ingredient.isFreshPlant}:${ingredient.isInSeason}:${ingredient.origin?.id ?? ''}:${ingredient.labels.map((l) => l.id).join(',')}`;
}
