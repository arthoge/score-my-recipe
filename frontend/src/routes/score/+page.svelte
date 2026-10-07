<!-- Render one independently editable table per imported recipe. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { page } from '$app/state';
	import RecipeEditor from '$lib/ui/RecipeEditor.svelte';
	import RecipeExportDialog from '$lib/ui/RecipeExportDialog.svelte';
	import AddIngredientsDialog from '$lib/ui/AddIngredientsDialog.svelte';
	import type { Ingredient } from '$lib/types/ingredient';
	import { getEditorRecipes, type RecipeEditorState } from '$lib/types/recipeDraft';

	let recipes = $state(getEditorRecipes(page.state as RecipeEditorState));

	/** Append a parsed recipe after the existing editors. */
	function addRecipe(ingredients: Ingredient[]) {
		recipes.push({
			id: crypto.randomUUID(),
			name: '',
			ingredients,
			portions: 1,
			country: null
		});
	}

	/** Remove a recipe while retaining at least one editor. */
	function deleteRecipe(id: string) {
		if (recipes.length <= 1) return;
		recipes = recipes.filter((recipe) => recipe.id !== id);
	}
</script>

<svelte:head>
	<title>{$_('recipe.title', { default: 'Recipe Editor' })}</title>
</svelte:head>

<div class="w-full px-4 py-8">
	<div class="mb-8 flex flex-wrap items-center justify-between gap-4">
		<div class="min-w-0 basis-full md:flex-1 md:basis-96">
			<h1 class="text-3xl font-bold">{$_('recipe.title', { default: 'Recipe Editor' })}</h1>
			<p class="text-base-content/70 mt-2">
				{$_('recipe.review_description', {
					default: 'Review your ingredients and quantities before calculating each recipe’s score.'
				})}
			</p>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<AddIngredientsDialog mode="recipe" onadd={addRecipe} />
			<RecipeExportDialog {recipes} />
		</div>
	</div>
	<div class="space-y-16">
		{#each recipes as recipe, index (recipe.id)}
			<RecipeEditor
				id={recipe.id}
				ondelete={() => deleteRecipe(recipe.id)}
				deleteDisabled={recipes.length <= 1}
				bind:name={recipes[index].name}
				fallbackTitle={$_('recipe.untitled', {
					default: 'Recipe {number}',
					values: { number: index + 1 }
				})}
				bind:ingredients={recipes[index].ingredients}
				bind:portions={recipes[index].portions}
				bind:country={recipes[index].country}
			/>
		{/each}
	</div>
</div>
