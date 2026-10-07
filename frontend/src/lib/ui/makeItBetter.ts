import type { Ingredient } from '$lib/types/ingredient';
import type { MakeItBetterSuggestion } from '$lib/api/recipe';

export function replaceSelectedRecipeProducts(
	ingredients: Ingredient[],
	suggestions: MakeItBetterSuggestion[]
): void {
	for (const suggestion of suggestions) {
		const target = ingredients.find(
			(i) => {
				let matchStr = i.name;
				if (i.codifiedIngredient?.id) {
					matchStr = i.codifiedIngredient.id.split(':').pop()?.replace(/-/g, ' ') || i.name;
				}
				return matchStr === suggestion.ingredient;
			}
		);
		if (target) {
			target.name = suggestion.suggested.name;
			if (target.codifiedIngredient) {
				target.codifiedIngredient.id = suggestion.suggested.id;
				target.codifiedIngredient.label = suggestion.suggested.name;
				target.codifiedIngredient.isInTaxonomy = true;
			} else {
				target.codifiedIngredient = {
					id: suggestion.suggested.id,
					label: suggestion.suggested.name,
					isInTaxonomy: true
				};
			}
		}
	}
}
