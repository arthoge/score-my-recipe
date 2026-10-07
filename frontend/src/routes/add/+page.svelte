<script lang="ts">
	import { tick } from 'svelte';
	import { _, getLocale } from '$lib/i18n';
	import { goto } from '$app/navigation';
	import {
		parseRecipeText,
		apiIngredientsToIngredients,
		getMakeItBetterSuggestions,
		type MakeItBetterSuggestion
	} from '$lib/api/recipe';
	import OnboardingBanner from '$lib/ui/OnboardingBanner.svelte';
	import HelperTooltip from '$lib/ui/HelperTooltip.svelte';
	import RecipeExamples from '$lib/ui/RecipeExamples.svelte';
	import type { RecipeDraft } from '$lib/types/recipeDraft';
	import MakeItBetterDialog from '$lib/ui/MakeItBetterDialog.svelte';
	import { replaceSelectedRecipeProducts } from '$lib/ui/makeItBetter';

	let recipeInputs = $state([{ id: 0, text: '' }]);
	let nextRecipeId = 1;
	const nonEmptyRecipes = $derived(recipeInputs.filter((recipe) => recipe.text.trim()));
	let isLoading = $state(false);
	let error = $state<string | null>(null);
	let isCheckingImprovements = $state(false);
	let improvementError = $state<string | null>(null);
	let improvementSuggestions = $state<MakeItBetterSuggestion[]>([]);
	let isImprovementDialogOpen = $state(false);
	let currentMakeItBetterIndex = $state(0);

	let onboardingRef = $state<ReturnType<typeof OnboardingBanner> | null>(null);
	let isOnboardingDismissed = $state(true);

	/** Add an independent recipe input and focus it once it is rendered. */
	async function addRecipe() {
		const id = nextRecipeId++;
		recipeInputs.push({ id, text: '' });
		await tick();
		document.getElementById(`recipe-text-${id}`)?.focus();
	}

	/** Parse each non-empty input into its own recipe editor, preserving input order. */
	async function handleSubmit(event: Event) {
		event.preventDefault();
		if (isLoading || !nonEmptyRecipes.length) return;
		isLoading = true;
		error = null;

		try {
			// the recipe text is most likely written in the language of the
			// interface, the API expects a 2-letter language code (eg. "fr")
			const lang = getLocale().split('-')[0];
			const recipes: RecipeDraft[] = await Promise.all(
				nonEmptyRecipes.map(async (recipe) => {
					const result = await parseRecipeText(recipe.text, lang);
					return {
						id: `recipe-${recipe.id}`,
						name: '',
						ingredients: apiIngredientsToIngredients(result.ingredients)
					};
				})
			);
			await goto('/score', { state: { recipes } });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Une erreur est survenue';
			isLoading = false;
		}
	}

	/** Parse the recipe first, then request only catalog-backed replacements. */
	async function openMakeItBetter(index: number = 0) {
		currentMakeItBetterIndex = index;
		isCheckingImprovements = true;
		improvementError = null;
		try {
			const lang = getLocale().split('-')[0];
			const parsedRecipe = await parseRecipeText(recipeInputs[index].text, lang);
			const names = parsedRecipe.ingredients.map((ingredient) => ingredient.codified_ingredient);
			const result = await getMakeItBetterSuggestions(names);
			improvementSuggestions = result.suggestions;
			if (result.suggestions.length === 0) {
				improvementError = 'No catalogued improvements are available for this recipe.';
				return;
			}
			isImprovementDialogOpen = true;
		} catch (e) {
			improvementError = e instanceof Error ? e.message : 'Could not check recipe improvements.';
		} finally {
			isCheckingImprovements = false;
		}
	}

	/** Replace one occurrence per selected recommendation and preserve all other text. */
	function applySelectedImprovements(suggestions: MakeItBetterSuggestion[]) {
		recipeInputs[currentMakeItBetterIndex].text = replaceSelectedRecipeProducts(recipeInputs[currentMakeItBetterIndex].text, suggestions);
	}
</script>

<svelte:head>
	<title>{$_('add.title', { default: 'Ajouter une recette' })}</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8">
	<!-- Onboarding Callout -->
	<OnboardingBanner bind:this={onboardingRef} bind:isDismissed={isOnboardingDismissed} />

	<!-- Header -->
	<div class="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
		<div>
			<h1 class="text-3xl font-bold">{$_('add.title', { default: 'Ajouter une recette' })}</h1>
			<p class="text-base-content/70 mt-2">
				{$_('add.description', { default: 'Entrez votre recette ci-dessous' })}
				{$_('add.or', { default: 'ou utilisez la' })}
				<a href="/score" class="link link-primary"
					>{$_('add.guided_entry', { default: 'saisie guidée' })}</a
				>.
			</p>
		</div>

		{#if isOnboardingDismissed}
			<button
				type="button"
				class="btn btn-ghost btn-sm text-primary gap-1.5 self-start sm:self-auto"
				onclick={() => onboardingRef?.show()}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-4 w-4"
				>
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
						clip-rule="evenodd"
					/>
				</svg>
				<span>{$_('onboarding.help_button', { default: 'How does it work?' })}</span>
			</button>
		{/if}
	</div>

	<!-- Recipe Form -->
	<form onsubmit={handleSubmit} class="space-y-6">
		<div class="form-control w-full space-y-2">
			<!-- Field label -->
			<label class="label justify-start p-0" for="recipe-text-0">
				<span class="flex items-center gap-2 text-sm font-medium sm:text-base">
					<span>{$_('add.recipe_label', { default: 'Votre recette' })}</span>
					<HelperTooltip
						tip={$_('helpers.recipe_text', {
							default:
								'Enter each ingredient on a new line with its quantity (e.g. 200g flour, 3 eggs, 100g sugar).'
						})}
						ariaLabel={$_('helpers.more_info', { default: 'More information' })}
					/>
				</span>
			</label>

			<!-- Example recipe shortcuts (honors UI language) -->
			<div class="flex flex-wrap items-center gap-2 py-1">
				<RecipeExamples onselect={(text) => (recipeInputs[0].text = text)} />
				<button
					type="button"
					class="btn btn-outline btn-xs hover:btn-primary rounded-full font-normal"
					disabled={isCheckingImprovements || recipeInputs[0].text.trim().length === 0}
					onclick={() => openMakeItBetter(0)}
				>
					{#if isCheckingImprovements}<span class="loading loading-spinner loading-xs"></span>{/if}
					{$_('make_it_better.button', { default: 'Make it better' })}
				</button>
			</div>

			{#each recipeInputs as recipe, index (recipe.id)}
				<div class="relative">
					<textarea
						id={`recipe-text-${recipe.id}`}
						bind:value={recipe.text}
						class="textarea textarea-bordered block min-h-64 w-full text-base"
						class:pr-12={index > 0}
						aria-label={$_('recipe.untitled', {
							default: 'Recipe {number}',
							values: { number: index + 1 }
						})}
						placeholder={$_('add.recipe_placeholder', {
							default:
								'Entrez votre recette ici...\n\nExemple:\n200g de farine\n3 œufs\n100g de sucre'
						})}
						disabled={isLoading}
					></textarea>
					{#if index > 0}
						<button
							type="button"
							class="btn btn-ghost btn-square btn-sm text-base-content/50 hover:text-error absolute top-2 right-2"
							aria-label={$_('add.remove_recipe', {
								default: 'Remove recipe {number}',
								values: { number: index + 1 }
							})}
							disabled={isLoading}
							onclick={() =>
								(recipeInputs = recipeInputs.filter((input) => input.id !== recipe.id))}
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								class="h-5 w-5"
								aria-hidden="true"
							>
								<path stroke-linecap="round" d="m6 6 12 12M6 18 18 6" />
							</svg>
						</button>
					{/if}
				</div>
			{/each}

			<button
				type="button"
				class="btn btn-outline border-base-content/30 text-base-content/60 hover:border-primary hover:bg-base-200 hover:text-primary w-full border-dashed"
				aria-label={$_('add.add_recipe', { default: 'Add another recipe' })}
				disabled={isLoading}
				onclick={addRecipe}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					class="h-6 w-6"
					aria-hidden="true"
				>
					<path stroke-linecap="round" d="M12 5v14M5 12h14" />
				</svg>
			</button>
		</div>

		<button
			type="submit"
			class="btn btn-primary btn-lg"
			disabled={isLoading || !nonEmptyRecipes.length}
		>
			{#if isLoading}
				<span class="loading loading-spinner"></span>
				{$_('add.loading', { default: 'Calcul en cours...' })}
			{:else}
				{$_('add.score_button', { default: 'Score' })}
			{/if}
		</button>
	</form>

	<!-- Error Display -->
	{#if error}
		<div class="alert alert-error mt-6">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-6 w-6 shrink-0 stroke-current"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<span>{error}</span>
		</div>
	{/if}

	{#if improvementError}
		<div class="alert alert-info mt-6" role="status">
			<span>{improvementError}</span>
		</div>
	{/if}
</div>

<MakeItBetterDialog
	bind:open={isImprovementDialogOpen}
	suggestions={improvementSuggestions}
	onapply={applySelectedImprovements}
/>
