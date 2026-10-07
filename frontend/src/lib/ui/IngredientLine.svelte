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
	import LabelsCell from './LabelsCell.svelte';
	import IconMdiDelete from '@iconify-svelte/mdi/delete';
	import {
		PREPARATION_OPTIONS,
		isIngredientEmpty,
		isIngredientNotEmpty,
		type Ingredient,
		type TaxonomyItem
	} from '$lib/types/ingredient';
	import { ingredientCellErrors } from './ingredientEditor';
	import { getPreparedWeight } from './preparedWeight';

	type Props = {
		ingredient: Ingredient;
		recipeId: string;
		isLastItem?: boolean;
		isOnlyItem?: boolean;
		missingIngredientIds?: string[];
		originOptions: TaxonomyItem[];
		labelOptions: TaxonomyItem[];
		originsStatus: 'loading' | 'ready' | 'failed';
		labelsStatus: 'loading' | 'ready' | 'failed';
		onDelete?: (id: string) => void;
		onNotEmpty?: () => void;
	};
	let {
		ingredient = $bindable(),
		recipeId,
		isLastItem = false,
		isOnlyItem = false,
		missingIngredientIds = [],
		originOptions,
		labelOptions,
		originsStatus,
		labelsStatus,
		onDelete,
		onNotEmpty
	}: Props = $props();
	let rowId = $derived(`${recipeId}-${ingredient.id}`);
	let errors = $derived(ingredientCellErrors(ingredient));
	let preparedWeight = $derived(getPreparedWeight(ingredient));
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
			label={$_('recipe.ciqual_food', { default: 'Ciqual food' })}
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
				ingredient.productName = selected?.label ?? '';
				ingredient.barcode = code;
			}}
		/>
	</td>
	<td data-invalid={errors.weight}>
		<div class="relative flex h-[43px] min-w-0 items-center">
			<input
				id="ingredient-weight-{rowId}"
				class="input validator cell-input min-w-0 flex-1 text-left tabular-nums"
				type="number"
				required
				value={ingredient.weight ?? 0}
				oninput={(event) => {
					ingredient.weight =
						event.currentTarget.value === '' ? null : event.currentTarget.valueAsNumber;
				}}
				min="0"
				step="any"
				inputmode="decimal"
				aria-label={$_('recipe.quantity_with_unit', { default: 'Quantity (grams)' })}
				aria-invalid={errors.weight}
			/>
			<!-- The invisible number positions the unit; the full-width input keeps its native arrows. -->
			<div
				class="pointer-events-none absolute inset-y-0 right-8 left-3 flex items-center gap-1 overflow-hidden text-sm whitespace-nowrap tabular-nums"
				aria-hidden="true"
			>
				<span class="invisible shrink-0">{ingredient.weight ?? 0}</span>
				<span class="text-base-content/50 shrink-0 text-xs"
					>{$_('recipe.grams', { default: 'grams' })}</span
				>
			</div>
		</div>
	</td>
	<td>
		<select
			class="cell-input"
			bind:value={ingredient.state}
			aria-label={$_('recipe.state', { default: 'State when weighed' })}
		>
			<option value="raw">{$_('recipe.states.raw', { default: 'Raw' })}</option>
			<option value="cooked">{$_('recipe.states.cooked', { default: 'Cooked' })}</option>
			<option value="drained">{$_('recipe.states.drained', { default: 'Drained' })}</option>
		</select>
	</td>
	<td>
		<select
			class="cell-input"
			bind:value={ingredient.preparationProfile}
			aria-label={$_('recipe.preparation_profile', { default: 'Preparation' })}
		>
			{#each PREPARATION_OPTIONS as option (option.value)}
				<option value={option.value}
					>{$_(`recipe.preparations.${option.value}`, { default: option.label })}</option
				>
			{/each}
		</select>
	</td>
	<td data-invalid={errors.preparedWeight}>
		<div class="relative flex h-[43px] min-w-0 items-center">
			<input
				id="ingredient-prepared-weight-{rowId}"
				class="input validator cell-input min-w-0 flex-1 text-left tabular-nums"
				type="number"
				value={preparedWeight ?? 0}
				oninput={(event) => {
					ingredient.measuredPreparedWeightG =
						event.currentTarget.value === '' ? null : event.currentTarget.valueAsNumber;
				}}
				min="0"
				step="any"
				inputmode="decimal"
				aria-label={$_('recipe.prepared_weight_with_unit', { default: 'Prepared weight (grams)' })}
				aria-invalid={errors.preparedWeight}
				title={$_(
					ingredient.measuredPreparedWeightG == null
						? 'recipe.prepared_weight_auto'
						: 'recipe.prepared_weight_manual',
					{
						default:
							ingredient.measuredPreparedWeightG == null
								? 'Automatic suggestion. Edit to enter a measured weight.'
								: 'Measured weight. Clear to restore the automatic suggestion.'
					}
				)}
			/>
			<!-- The invisible number positions the unit; the full-width input keeps its native arrows. -->
			<div
				class="pointer-events-none absolute inset-y-0 right-8 left-3 flex items-center gap-1 overflow-hidden text-sm whitespace-nowrap tabular-nums"
				aria-hidden="true"
			>
				<span class="invisible shrink-0">{preparedWeight ?? 0}</span>
				<span class="text-base-content/50 shrink-0 text-xs"
					>{$_('recipe.grams', { default: 'grams' })}</span
				>
			</div>
		</div>
	</td>
	<td>
		<LabelsCell bind:value={ingredient.labels} options={labelOptions} status={labelsStatus} />
	</td>
	<td>
		<select
			id="ingredient-origin-{rowId}"
			class="cell-input"
			value={ingredient.origin?.id ?? ''}
			disabled={originsStatus !== 'ready'}
			aria-label={$_('recipe.origin', { default: 'Origin' })}
			onchange={(event) => {
				const selected = event.currentTarget.value;
				ingredient.origin =
					originOptions.find((option) => option.id === selected) ??
					(selected && selected === ingredient.origin?.id ? ingredient.origin : null);
			}}
		>
			<option value=""
				>{originsStatus === 'loading'
					? $_('recipe.search_loading', { default: 'Searching…' })
					: originsStatus === 'failed'
						? $_('recipe.search_failed', { default: 'Search unavailable. Try again.' })
						: $_('recipe.world', { default: 'World' })}</option
			>
			{#if ingredient.origin?.id && !originOptions.some((option) => option.id === ingredient.origin?.id)}
				<option class="text-base-content" value={ingredient.origin.id}
					>{ingredient.origin.label}</option
				>
			{/if}
			{#each originOptions as option (option.id)}
				<option class="text-base-content" value={option.id ?? ''}>{option.label}</option>
			{/each}
		</select>
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
		<button
			type="button"
			class="btn btn-ghost btn-square btn-sm text-error disabled:text-base-content/30 disabled:bg-transparent disabled:opacity-50"
			disabled={isOnlyItem || (isLastItem && isIngredientEmpty(ingredient))}
			onclick={() => onDelete?.(ingredient.id)}
			aria-label={$_('recipe.delete_ingredient', { default: 'Delete ingredient' })}
		>
			<IconMdiDelete class="h-4 w-4" aria-hidden="true" />
		</button>
	</td>
</tr>
