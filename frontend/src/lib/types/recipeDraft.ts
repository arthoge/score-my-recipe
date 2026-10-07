/** Editable frontend recipes passed from an import flow to the score page. */
import { createEmptyIngredient, type Ingredient } from './ingredient';

/** Keep displayed recipe names compact for page and printed PDF headings. */
export const RECIPE_NAME_MAX_LENGTH = 80;

export type RecipeDraft = {
	id: string;
	name: string;
	ingredients: Ingredient[];
	portions?: number | null;
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
		name: recipe.name.trim().slice(0, RECIPE_NAME_MAX_LENGTH),
		// Bindable Svelte props with defaults require explicit values during hydration.
		portions: recipe.portions ?? 1,
		// Copy drafts before editing: navigation state should remain an import snapshot.
		ingredients: recipe.ingredients.length
			? structuredClone(recipe.ingredients).map((ingredient) => ({
					...ingredient,
					state: ingredient.state ?? 'raw',
					preparationProfile: ingredient.preparationProfile ?? 'none'
				}))
			: [createEmptyIngredient()]
	}));
}
