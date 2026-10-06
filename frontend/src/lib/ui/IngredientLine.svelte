<!-- Fixed-height ingredient cells; all environmental and preparation fields stay visible. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { untrack } from 'svelte';
	import {
		searchCiqualFoods,
		searchOffProducts,
		searchAgribalyseFoods,
		getIngredientReferences
	} from '$lib/api/nutrition';
	import { syncNutritionSearches, suggestOffProduct } from './nutritionSearch';
	import { getMatchingTags } from '$lib/api/taxonomy';
	import { findMatchingSuggestion } from '$lib/utils/taxonomyMatch';
	import TaxonomyCell from './TaxonomyCell.svelte';
	import IconMdiDelete from '@iconify-svelte/mdi/delete';
	import {
		isIngredientEmpty,
		isIngredientNotEmpty,
		type Ingredient,
		type TaxonomyItem
	} from '$lib/types/ingredient';
	import { ingredientCellErrors } from './ingredientEditor';

	type Props = {
		ingredient: Ingredient;
		recipeId: string;
		isLastItem?: boolean;
		missingIngredientIds?: string[];
		onDelete?: (id: string) => void;
		onNotEmpty?: () => void;
	};
	let {
		ingredient = $bindable(),
		recipeId,
		isLastItem = false,
		missingIngredientIds = [],
		onDelete,
		onNotEmpty
	}: Props = $props();
	let rowId = $derived(`${recipeId}-${ingredient.id}`);
	let errors = $derived(ingredientCellErrors(ingredient));
	let referenceInvalid = $derived(
		errors.environmentalReference || missingIngredientIds.includes(ingredient.id)
	);
	let previousName: string | undefined;
	let productSuggestions = $state<TaxonomyItem[]>([]);

	$effect(() => {
		const name = ingredient.name;
		untrack(() => syncNutritionSearches(ingredient, previousName));
		previousName = name;
	});

	$effect(() => {
		const name = ingredient.name.trim();
		const taxonomyId = ingredient.codifiedIngredient?.id;
		productSuggestions = [];
		const controller = new AbortController();
		let cancelled = false;
		const timer =
			name.length >= 3
				? setTimeout(() => {
						if (!taxonomyId)
							getMatchingTags('ingredients', name, 8)
								.then((result) => {
									if (cancelled) return;
									const exact = findMatchingSuggestion(name, result.suggestions);
									if (exact?.isInTaxonomy) ingredient.codifiedIngredient = exact;
								})
								.catch(() => {
									/* Leave ambiguous names for the chef to select. */
								});
						if (taxonomyId)
							getIngredientReferences(taxonomyId, controller.signal)
								.then((result) => {
									if (cancelled) return;
									if (
										!ingredient.agribalyseCode &&
										!ingredient.agribalyseName &&
										result.agribalyse
									) {
										ingredient.agribalyseCode = result.agribalyse.code;
										ingredient.agribalyseName = result.agribalyse.name;
										ingredient.referenceSource = result.source ?? undefined;
									}
									if (!ingredient.ciqualCode && !ingredient.ciqualName && result.ciqual) {
										ingredient.ciqualCode = result.ciqual.code;
										ingredient.ciqualName = result.ciqual.name;
										ingredient.nutritionReferenceConfirmed = false;
									}
								})
								.catch(() => {
									/* Manual search remains available if matching fails. */
								});
						searchOffProducts(name, 8, controller.signal)
							.then((results) => {
								if (!cancelled) {
									productSuggestions = results;
									suggestOffProduct(ingredient, results);
								}
							})
							.catch(() => {
								/* A service failure must not select an invented product. */
							});
					}, 400)
				: undefined;
		return () => {
			cancelled = true;
			controller.abort();
			clearTimeout(timer);
		};
	});

	$effect(() => {
		if (isLastItem && isIngredientNotEmpty(ingredient)) onNotEmpty?.();
	});

	/** Seasonality is meaningful only for fresh fruit and vegetables. */
	function toggleFreshPlant(event: Event) {
		ingredient.isFreshPlant = (event.target as HTMLSelectElement).value === 'true';
		if (!ingredient.isFreshPlant) ingredient.isInSeason = false;
	}
</script>

<tr>
	<td data-invalid={errors.name}>
		<TaxonomyCell
			id="ingredient-name-{rowId}"
			tagtype="ingredients"
			label={$_('recipe.ingredient_name', { default: 'Ingredient name' })}
			invalid={errors.name}
			tags={ingredient.name ? [{ id: null, label: ingredient.name, isInTaxonomy: false }] : []}
			onchange={(tags) => {
				const selected = tags[0];
				ingredient.name = selected?.label ?? '';
				if (selected?.isInTaxonomy) ingredient.codifiedIngredient = selected;
				else if (ingredient.codifiedIngredient?.label !== ingredient.name)
					ingredient.codifiedIngredient = null;
			}}
		/>
	</td>
	<td>
		<TaxonomyCell
			id="ingredient-ciqual-{rowId}"
			getSuggestions={searchCiqualFoods}
			searchTerm={ingredient.name}
			label={$_('recipe.ciqual_food', { default: 'CIQUAL food' })}
			tags={ingredient.ciqualName
				? [
						{
							id: ingredient.ciqualCode ?? null,
							label: ingredient.ciqualName,
							isInTaxonomy: !!ingredient.ciqualCode
						}
					]
				: []}
			onchange={(tags) => {
				const selected = tags[0];
				const code = selected?.isInTaxonomy ? (selected.id ?? undefined) : undefined;
				if (code !== ingredient.ciqualCode) ingredient.nutritionReferenceConfirmed = false;
				ingredient.ciqualName = selected?.label ?? '';
				ingredient.ciqualCode = code;
			}}
		/>
	</td>
	<td data-invalid={referenceInvalid}>
		<TaxonomyCell
			id="ingredient-reference-{rowId}"
			getSuggestions={searchAgribalyseFoods}
			searchTerm={ingredient.name}
			label={$_('recipe.agribalyse_food', { default: 'Agribalyse correspondence' })}
			tags={ingredient.agribalyseName
				? [
						{
							id: ingredient.agribalyseCode ?? null,
							label: ingredient.agribalyseName,
							isInTaxonomy: !!ingredient.agribalyseCode
						}
					]
				: []}
			invalid={referenceInvalid}
			onchange={(tags) => {
				ingredient.agribalyseName = tags[0]?.label ?? '';
				ingredient.agribalyseCode = tags[0]?.isInTaxonomy ? (tags[0].id ?? undefined) : undefined;
				ingredient.referenceSource = 'manual';
			}}
		/>
	</td>
	<td>
		<TaxonomyCell
			id="ingredient-product-{rowId}"
			getSuggestions={searchOffProducts}
			searchTerm={ingredient.name}
			initialSuggestions={productSuggestions}
			label={$_('recipe.off_product', { default: 'Open Food Facts product' })}
			tags={ingredient.productName
				? [
						{
							id: ingredient.barcode ?? null,
							label: ingredient.productName,
							isInTaxonomy: !!ingredient.barcode
						}
					]
				: []}
			onchange={(tags) => {
				const selected = tags[0];
				const code = selected?.isInTaxonomy ? (selected.id ?? undefined) : undefined;
				if (code !== ingredient.barcode) ingredient.nutritionReferenceConfirmed = false;
				ingredient.productName = selected?.label ?? '';
				ingredient.barcode = code;
			}}
		/>
	</td>
	<td data-invalid={errors.weight}>
		<input
			id="ingredient-weight-{rowId}"
			class="input validator cell-input text-left tabular-nums"
			type="number"
			required
			bind:value={ingredient.weight}
			min="0"
			step="any"
			inputmode="decimal"
			aria-label={$_('recipe.quantity_grams', { default: 'Quantity (grams)' })}
			aria-invalid={errors.weight}
		/>
	</td>
	<td>
		<select
			class="cell-input"
			bind:value={ingredient.state}
			aria-label={$_('recipe.state', { default: 'Ingredient state' })}
		>
			<option value={null}></option>
			<option value="raw">{$_('recipe.states.raw', { default: 'Raw' })}</option>
			<option value="cooked">{$_('recipe.states.cooked', { default: 'Cooked' })}</option>
			<option value="drained">{$_('recipe.states.drained', { default: 'Drained' })}</option>
		</select>
	</td>
	<td>
		<select
			class="cell-input"
			bind:value={ingredient.nutritionReferenceConfirmed}
			disabled={!ingredient.ciqualCode?.trim() && !ingredient.barcode?.trim()}
			aria-label={$_('recipe.nutrition_confirmed', { default: 'Nutrition reference confirmed' })}
		>
			<option value={undefined}></option>
			<option value={false}>{$_('recipe.no', { default: 'No' })}</option>
			<option value={true}>{$_('recipe.yes', { default: 'Yes' })}</option>
		</select>
	</td>
	<td>
		<input
			class="cell-input"
			type="text"
			bind:value={ingredient.preparationProfile}
			aria-label={$_('recipe.preparation_profile', { default: 'Preparation profile' })}
		/>
	</td>
	<td data-invalid={errors.measuredPreparedWeightG}>
		<input
			class="input validator cell-input text-left tabular-nums"
			type="number"
			bind:value={ingredient.measuredPreparedWeightG}
			min="0"
			step="any"
			inputmode="decimal"
			aria-invalid={errors.measuredPreparedWeightG}
			aria-label={$_('recipe.measured_prepared_weight', {
				default: 'Measured prepared weight (grams)'
			})}
		/>
	</td>
	<td data-readonly="true">
		<input
			class="cell-input text-left tabular-nums"
			type="text"
			readonly
			value={ingredient.estimatedPreparedWeightG ?? ''}
			aria-label={$_('recipe.estimated_prepared_weight', {
				default: 'Estimated prepared weight (grams)'
			})}
		/>
	</td>
	<td>
		<TaxonomyCell
			id="ingredient-labels-{rowId}"
			tagtype="labels"
			multiple
			tags={ingredient.labels}
			label={$_('recipe.labels', { default: 'Labels' })}
			onchange={(tags) => (ingredient.labels = tags)}
		/>
	</td>
	<td>
		<TaxonomyCell
			id="ingredient-origin-{rowId}"
			tagtype="countries"
			tags={ingredient.origin ? [ingredient.origin] : []}
			label={$_('recipe.origin', { default: 'Origin' })}
			onchange={(tags) => (ingredient.origin = tags[0] ?? null)}
		/>
	</td>
	<td>
		<select
			class="cell-input"
			value={ingredient.isFreshPlant}
			onchange={toggleFreshPlant}
			aria-label={$_('recipe.fresh_plant', { default: 'Fresh fruit/veg' })}
		>
			<option value={false}>{$_('recipe.no', { default: 'No' })}</option>
			<option value={true}>{$_('recipe.yes', { default: 'Yes' })}</option>
		</select>
	</td>
	<td>
		<select
			class="cell-input"
			bind:value={ingredient.isInSeason}
			disabled={!ingredient.isFreshPlant}
			aria-label={$_('recipe.in_season', { default: 'In season' })}
		>
			<option value={false}>{$_('recipe.no', { default: 'No' })}</option>
			<option value={true}>{$_('recipe.yes', { default: 'Yes' })}</option>
		</select>
	</td>
	<td class="text-center">
		{#if !(isLastItem && isIngredientEmpty(ingredient))}
			<button
				type="button"
				class="btn btn-ghost btn-square btn-sm text-error"
				onclick={() => onDelete?.(ingredient.id)}
				aria-label={$_('recipe.delete_ingredient', { default: 'Delete ingredient' })}
			>
				<IconMdiDelete class="h-4 w-4" aria-hidden="true" />
			</button>
		{/if}
	</td>
</tr>
