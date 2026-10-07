<script lang="ts">
	import { _, getLocale } from '$lib/i18n';
	import { apiIngredientsToIngredients, parseRecipeText } from '$lib/api/recipe';
	import type { Ingredient } from '$lib/types/ingredient';
	import HelperTooltip from './HelperTooltip.svelte';
	import IconMdiPlus from '@iconify-svelte/mdi/plus';

	let {
		onadd,
		mode = 'ingredients'
	}: {
		onadd: (ingredients: Ingredient[]) => void;
		mode?: 'ingredients' | 'recipe';
	} = $props();
	const buttonText = $derived(
		mode === 'recipe'
			? $_('recipe.add_recipe', { default: 'Add a recipe' })
			: $_('recipe.add_ingredients', { default: 'Add ingredients' })
	);
	const id = $props.id();
	let dialog: HTMLDialogElement;
	let textarea: HTMLTextAreaElement;
	let text = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	/** Open a fresh recipe or ingredient input and focus it for immediate typing. */
	function openDialog() {
		text = '';
		error = null;
		dialog.showModal();
		textarea.focus();
	}

	/** Parse the input using the add-page API and pass it to the recipe list or ingredient table. */
	async function addIngredients(event: SubmitEvent) {
		event.preventDefault();
		if (loading || !text.trim()) return;
		loading = true;
		error = null;
		try {
			const result = await parseRecipeText(text, getLocale().split('-')[0]);
			const ingredients = apiIngredientsToIngredients(result.ingredients);
			if (!ingredients.length) {
				error = $_('recipe.no_parsed_ingredients', {
					default: 'No ingredients found. Enter each ingredient with its quantity.'
				});
				return;
			}
			onadd(ingredients);
			dialog.close();
		} catch {
			error =
				mode === 'recipe'
					? $_('recipe.add_recipe_failed', {
							default: 'Could not add the recipe. Please try again.'
						})
					: $_('recipe.add_ingredients_failed', {
							default: 'Could not add ingredients. Please try again.'
						});
		} finally {
			loading = false;
		}
	}
</script>

<button
	type="button"
	class={mode === 'recipe' ? 'btn btn-outline' : 'btn btn-outline btn-sm mt-4 gap-1.5 ps-2'}
	aria-haspopup="dialog"
	onclick={openDialog}
>
	{#if mode === 'ingredients'}
		<IconMdiPlus class="h-4 w-4 translate-y-px" aria-hidden="true" />
	{/if}
	<span>{buttonText}</span>
</button>

<dialog
	bind:this={dialog}
	class="modal"
	aria-labelledby="{id}-title"
	oncancel={(event) => {
		if (loading) event.preventDefault();
	}}
>
	<form class="modal-box max-w-2xl" onsubmit={addIngredients}>
		<h2 id="{id}-title" class="mb-4 text-lg font-bold">
			{buttonText}
		</h2>
		<div class="form-control w-full space-y-2">
			<label id="{id}-label" class="label justify-start p-0" for="{id}-text">
				<span class="flex items-center gap-2 text-sm font-medium sm:text-base">
					<span
						>{mode === 'recipe'
							? $_('add.recipe_label', { default: 'Your recipe' })
							: $_('recipe.ingredients_label', { default: 'Your ingredients' })}</span
					>
					<span class="inline-flex translate-y-px">
						<HelperTooltip
							floating
							position="bottom"
							tip={$_('helpers.recipe_text', {
								default:
									'Enter each ingredient on a new line with its quantity (e.g. 200g flour, 3 eggs, 100g sugar).'
							})}
							ariaLabel={$_('helpers.more_info', { default: 'More information' })}
						/>
					</span>
				</span>
			</label>
			<textarea
				bind:this={textarea}
				id="{id}-text"
				bind:value={text}
				class="textarea textarea-bordered block min-h-52 w-full text-base"
				placeholder={mode === 'recipe'
					? $_('add.recipe_placeholder', {
							default: 'Enter your recipe here...\n\nExample:\n200g flour\n3 eggs\n100g sugar'
						})
					: $_('recipe.ingredients_placeholder', {
							default: 'Enter your ingredients here...\n\nExample:\n200g flour\n3 eggs\n100g sugar'
						})}
				disabled={loading}
			></textarea>
		</div>
		{#if error}
			<p class="text-error mt-3 text-sm" role="alert">{error}</p>
		{/if}
		<div class="modal-action">
			<button
				type="button"
				class="btn btn-outline"
				disabled={loading}
				onclick={() => dialog.close()}
			>
				{$_('recipe.cancel', { default: 'Cancel' })}
			</button>
			<button type="submit" class="btn btn-primary" disabled={loading || !text.trim()}>
				{#if loading}
					<span class="loading loading-spinner loading-sm" aria-hidden="true"></span>
				{/if}
				{buttonText}
			</button>
		</div>
	</form>
	<form method="dialog" class="modal-backdrop">
		<button disabled={loading} aria-label={$_('recipe.cancel', { default: 'Cancel' })}></button>
	</form>
</dialog>
