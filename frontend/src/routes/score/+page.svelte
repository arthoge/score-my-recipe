<!-- Render one independently editable table per imported recipe. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { page } from '$app/state';
	import RecipeEditor from '$lib/ui/RecipeEditor.svelte';
	import { getEditorRecipes, type RecipeEditorState } from '$lib/types/recipeDraft';

	let recipes = $state(getEditorRecipes(page.state as RecipeEditorState));
</script>

<svelte:head>
	<title>{$_('recipe.title', { default: 'Recipe Editor' })}</title>
</svelte:head>

<div class="w-full px-4 py-8">
	<div class="mb-8">
		<h1 class="text-3xl font-bold">{$_('recipe.title', { default: 'Recipe Editor' })}</h1>
		<p class="text-base-content/70 mt-2">
			{$_('recipe.review_description', {
				default: 'Review your ingredients and quantities before calculating each recipe’s score.'
			})}
		</p>
	</div>
	<div class="space-y-8">
		{#each recipes as recipe, index (recipe.id)}
			<RecipeEditor
				id={recipe.id}
				title={recipe.name ||
					$_('recipe.untitled', { default: 'Recipe {number}', values: { number: index + 1 } })}
				bind:ingredients={recipes[index].ingredients}
				bind:portions={recipes[index].portions}
			/>
		{/each}
	</div>
</div>
