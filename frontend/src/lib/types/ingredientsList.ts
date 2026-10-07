import type { Ingredient } from './ingredient';
import { createEmptyIngredient, isIngredientNotEmpty } from './ingredient';

/**
 * Types and utility functions for managing a list of ingredients in the recipe scoring application.
 */
export type IngredientsList = Ingredient[];

/**
 * Remove an ingredient from a list by ID
 * @param ingredients - The current list of ingredients
 * @param id - The ID of the ingredient to remove
 * @returns A new list with the ingredient removed, which may be empty
 */
export function removeIngredientFromList(
	ingredients: IngredientsList,
	id: string
): IngredientsList {
	return ingredients.filter((ingredient) => ingredient.id !== id);
}

/**
 * Add a new empty ingredient to the list if the last ingredient has content
 * @param ingredients - The current list of ingredients
 * @returns A new list with a new empty ingredient added if needed
 */
export function addEmptyIngredientIfNeeded(ingredients: IngredientsList): IngredientsList {
	const lastIngredient = ingredients[ingredients.length - 1];

	// Only add a new line if the last line has content
	if (lastIngredient && isIngredientNotEmpty(lastIngredient)) {
		return [...ingredients, createEmptyIngredient()];
	}

	return ingredients;
}

/**
 * Count non-empty ingredients in a list
 * @param ingredients - The list of ingredients to count
 * @returns The number of ingredients that have content
 */
export function countNonEmptyIngredients(ingredients: IngredientsList): number {
	return ingredients.filter(isIngredientNotEmpty).length;
}
