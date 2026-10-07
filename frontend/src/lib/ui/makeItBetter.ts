/** Utilities that apply explicitly selected Make it better recommendations. */

import type { MakeItBetterSuggestion } from '$lib/api/recipe';

/**
 * Replace one occurrence of each selected product while preserving every
 * unselected product and the rest of the recipe text.
 */
export function replaceSelectedRecipeProducts(
	recipeText: string,
	suggestions: MakeItBetterSuggestion[]
): string {
	return suggestions.reduce(
		(updatedRecipe, suggestion) =>
			updatedRecipe.replace(suggestion.ingredient, suggestion.suggested.name),
		recipeText
	);
}
