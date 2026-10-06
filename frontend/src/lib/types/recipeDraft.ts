/** Editable frontend recipes passed from an import flow to the score page. */
import { createEmptyIngredient, type Ingredient } from './ingredient';
import { addEmptyIngredientIfNeeded } from './ingredientsList';

export type RecipeDraft = {
	id: string;
	name: string;
	ingredients: Ingredient[];
	portions?: number | null;
	finalWeightG?: number | null;
};

export type RecipeEditorState = {
	recipes?: RecipeDraft[];
	/** Existing single-recipe navigation from `/add`. */
	ingredients?: Ingredient[];
};

/** Prepare independent recipe editors, preserving imported names and recipe order. */
export function getEditorRecipes(state: RecipeEditorState): RecipeDraft[] {
	const recipes = state.recipes?.length
		? state.recipes
		: [{ id: 'single-recipe', name: '', ingredients: state.ingredients ?? [] }];

	return recipes.map((recipe) => ({
		...recipe,
		// Bindable Svelte props with defaults require explicit values during hydration.
		portions: recipe.portions ?? null,
		finalWeightG: recipe.finalWeightG ?? null,
		// Copy drafts before editing: navigation state should remain an import snapshot.
		ingredients: addEmptyIngredientIfNeeded(
			recipe.ingredients.length ? structuredClone(recipe.ingredients) : [createEmptyIngredient()]
		)
	}));
}
