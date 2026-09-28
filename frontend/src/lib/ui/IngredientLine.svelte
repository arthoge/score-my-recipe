<!--
  IngredientLine.svelte
  
  A single row component representing one ingredient in the recipe editor.
  Contains fields for: name, weight, codified ingredient, labels, fresh plant + seasonality, origin, and delete action.
  
  Props:
  - ingredient: The ingredient data object (bindable - changes propagate to parent)
  - ingredientsTaxonomy: List of codified ingredient options
  - labelsTaxonomy: List of available labels for autocomplete
  - countriesTaxonomy: List of countries for origin autocomplete
  - isLastItem: Whether this is the last item in the list (controls new line creation)
  - onDelete: Callback when delete button is clicked
-->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import Tags from './Tags.svelte';
	import IconMdiDelete from '@iconify-svelte/mdi/delete';
	import IconMdiAlertCircle from '@iconify-svelte/mdi/alert-circle';
	import IconMaterialSymbolsSunnyOutline from '@iconify-svelte/material-symbols/sunny-outline';
	import IconMaterialSymbolsCloudOutline from '@iconify-svelte/material-symbols/cloud-outline';
	import type { Ingredient } from '$lib/types/ingredient';
	import { isIngredientEmpty, isIngredientNotEmpty } from '$lib/types/ingredient';

	type Props = {
		// The ingredient data object (bindable): name, weight, etc.
		ingredient: Ingredient;
		isFirstItem?: boolean;
		isLastItem?: boolean;
		// Ingredient ids flagged as missing in the last computed green-score.
		missingIngredientIds?: string[];
		onDelete?: (id: string) => void;
		onNotEmpty?: () => void; // Optional callback for when line becomes non-empty
	};

	let {
		ingredient = $bindable(),
		isFirstItem = false, // eslint-disable-line @typescript-eslint/no-unused-vars
		isLastItem = false,
		missingIngredientIds = [],
		onDelete,
		onNotEmpty
	}: Props = $props();

	/** Whether this ingredient was not accounted for in the last green-score. */
	let isMissing = $derived(missingIngredientIds.includes(ingredient.id));

	// Track if this ingredient was empty when the component was created
	// This is used to detect when user starts typing in an empty last line
	let wasEmptyOnMount = $state(ingredient.name === '');
	let isNotEmpty = $derived(wasEmptyOnMount && isIngredientNotEmpty(ingredient));

	// trigger onNotEmpty when isNoteEmpty becomes true
	$effect(() => {
		if (isNotEmpty && onNotEmpty) {
			onNotEmpty();
		}
	});

	/**
	 * Handle delete button click
	 */
	function handleDelete() {
		onDelete?.(ingredient.id);
	}

	/**
	 * Toggle the "fresh fruit or vegetable" flag.
	 *
	 * When the ingredient is no longer a fresh plant, seasonality is reset to
	 * off-season (`false`): the seasonal state is meaningless without it.
	 */
	function toggleFreshPlant() {
		ingredient.isFreshPlant = !ingredient.isFreshPlant;
		if (!ingredient.isFreshPlant) {
			ingredient.isInSeason = false;
		}
	}
</script>

<div
	class="flex flex-col gap-2 rounded-lg p-3 sm:flex-row sm:items-start"
	class:ingredient-missing={isMissing}
>
	{#if isMissing}
		<!-- Badge column: an invisible label spacer aligns the badge with the
		     sibling form fields (which sit below their own labels), rather than
		     at the labels' top level. -->
		<div class="flex w-auto flex-col">
			<span class="label invisible py-1">&nbsp;</span>
			<span
				class="tooltip badge badge-warning badge-sm gap-1"
				data-tip={$_('recipe.ingredient_not_accounted_tooltip', {
					default: 'We could not find a correspondence in our impact database for this ingredient'
				})}
			>
				<IconMdiAlertCircle class="h-4 w-4" aria-hidden="true" />
				{$_('recipe.ingredient_not_accounted', { default: 'Not accounted' })}
			</span>
		</div>
	{/if}

	<!-- Codified Ingredient name -->
	<div class="flex grow-3 flex-col">
		<label class="label py-1" for="ingredient-codified-{ingredient.id}">
			<span class="label-text text-xs"
				>{$_('recipe.codified_ingredient', { default: 'Codified' })}</span
			>
		</label>
		<Tags
			tagtype="ingredients"
			id="ingredient-codified-{ingredient.id}"
			tags={ingredient.codifiedIngredient ? [ingredient.codifiedIngredient] : []}
			onChange={(newTags) => {
				ingredient.codifiedIngredient = newTags[0] ?? null;
			}}
			single={true}
		/>
	</div>

	<!-- Weight -->
	<div class="flex w-24 flex-col">
		<label class="label py-1" for="ingredient-weight-{ingredient.id}">
			<span class="label-text text-xs">{$_('recipe.weight', { default: 'Weight (g)' })}</span>
		</label>
		<input
			id="ingredient-weight-{ingredient.id}"
			type="number"
			class="input input-bordered w-full"
			placeholder="0"
			bind:value={ingredient.weight}
			min="0"
		/>
	</div>

	<!-- Labels -->
	<div class="flex grow-3 flex-col">
		<label class="label py-1" for="ingredient-labels-{ingredient.id}">
			<span class="label-text text-xs" id="ingredient-labels-label-{ingredient.id}"
				>{$_('recipe.labels', { default: 'Labels' })}</span
			>
		</label>
		<Tags tagtype="labels" bind:tags={ingredient.labels} />
	</div>

	<!-- Fresh fruit/vegetable + seasonality -->
	<div class="flex w-48 flex-col">
		<label class="label py-1" for="ingredient-fresh-{ingredient.id}">
			<span class="label-text text-xs" id="ingredient-fresh-label-{ingredient.id}"
				>{$_('recipe.fresh_plant', { default: 'Fresh fruit/veg' })}</span
			>
		</label>
		<div class="flex min-h-10 items-center gap-2">
			<input
				id="ingredient-fresh-{ingredient.id}"
				type="checkbox"
				class="checkbox checkbox-primary"
				checked={ingredient.isFreshPlant}
				onchange={toggleFreshPlant}
				aria-labelledby="ingredient-fresh-label-{ingredient.id}"
			/>
			{#if ingredient.isFreshPlant}
				<!-- Vertical selector: off-season (default, top) / in-season (bottom) -->
				<div
					class="join join-vertical"
					role="group"
					aria-label={$_('recipe.seasonality', { default: 'Seasonality' })}
				>
					<button
						type="button"
						class="btn btn-xs join-item"
						class:btn-active={!ingredient.isInSeason}
						aria-pressed={!ingredient.isInSeason}
						onclick={() => (ingredient.isInSeason = false)}
					>
						<IconMaterialSymbolsCloudOutline class="h-4 w-4" aria-hidden="true" />
						{$_('recipe.off_season', { default: 'Off season' })}
					</button>
					<button
						type="button"
						class="btn btn-xs join-item"
						class:btn-active={ingredient.isInSeason}
						aria-pressed={ingredient.isInSeason}
						onclick={() => (ingredient.isInSeason = true)}
					>
						<IconMaterialSymbolsSunnyOutline class="h-4 w-4" aria-hidden="true" />
						{$_('recipe.in_season', { default: 'In season' })}
					</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Origin -->
	<div class="flex grow-3 flex-col">
		<label class="label py-1" for="ingredient-origin-{ingredient.id}">
			<span class="label-text text-xs" id="ingredient-origin-label-{ingredient.id}"
				>{$_('recipe.origin', { default: 'Origin' })}</span
			>
		</label>
		<Tags
			tagtype="countries"
			tags={ingredient.origin ? [ingredient.origin] : []}
			onChange={(newTags) => {
				ingredient.origin = newTags[0] ?? null;
			}}
			single={true}
		/>
	</div>

	<!-- Delete Button -->
	<div class="flex w-12 flex-col items-end justify-center pb-1">
		{#if !(isLastItem && isIngredientEmpty(ingredient))}
			<button
				class="btn btn-circle btn-ghost btn-sm text-error mt-2"
				onclick={handleDelete}
				aria-label={$_('recipe.delete_ingredient', { default: 'Delete ingredient' })}
			>
				<IconMdiDelete class="h-5 w-5" />
			</button>
		{/if}
	</div>
</div>
