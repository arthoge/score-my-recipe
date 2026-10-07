<!-- Fixed-height ingredient cells; all environmental and preparation fields stay visible. -->
<script lang="ts">
	import type { NutritionDiagnostic } from '$lib/api/nutritionAnalysis';
	import CellTooltip from './CellTooltip.svelte';
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
		isIngredientNotEmpty,
		PREPARATION_OPTIONS,
		type Ingredient,
		type TaxonomyItem
	} from '$lib/types/ingredient';
	import {
		ingredientCellErrors,
		ingredientCalculationCells,
		isPositiveAmount
	} from './ingredientEditor';
	import { getPreparedWeight, preparedWeightInputKey } from './preparedWeight';
	import { estimatePreparedWeight } from '$lib/api/preparation';

	type Props = {
		ingredient: Ingredient;
		recipeId: string;
		isOnlyItem?: boolean;
		missingIngredientIds?: string[];
		nutritionDiagnostics?: NutritionDiagnostic[];
		nutritionFallbackIds?: string[];
		originOptions: TaxonomyItem[];
		labelOptions: TaxonomyItem[];
		originsStatus: 'loading' | 'ready' | 'failed';
		labelsStatus: 'loading' | 'ready' | 'failed';
		onDelete?: (id: string) => void;
	};
	let {
		ingredient = $bindable(),
		recipeId,
		isOnlyItem = false,
		missingIngredientIds = [],
		nutritionDiagnostics = [],
		nutritionFallbackIds = [],
		originOptions,
		labelOptions,
		originsStatus,
		labelsStatus,
		onDelete
	}: Props = $props();
	let rowId = $derived(`${recipeId}-${ingredient.id}`);
	let errors = $derived(ingredientCellErrors(ingredient));
	let preparedWeight = $derived(getPreparedWeight(ingredient));
	let quantityInput = $state<HTMLInputElement>();
	let preparedInput = $state<HTMLInputElement>();
	let quantityText = $state('0');
	let preparedText = $state('0');
	let preparedEstimateLoading = $state(false);
	let preparedEstimateFailed = $state(false);
	let previousPreparedInputKey: string | undefined;
	let preparedWeightTitle = $derived.by(() => {
		if (ingredient.measuredPreparedWeightG != null)
			return $_('recipe.prepared_weight_manual', {
				default: 'Entered weight. Ingredient, quantity or preparation changes recalculate it.'
			});
		if (preparedEstimateLoading)
			return $_('recipe.prepared_weight_loading', {
				default: 'Estimating prepared weight…'
			});
		if (preparedEstimateFailed)
			return $_('recipe.prepared_weight_failed', {
				default: 'Estimate unavailable. Uses the entered quantity.'
			});
		const suggestion = ingredient.preparedWeightSuggestion;
		if (suggestion?.source && suggestion.inputKey === preparedWeightInputKey(ingredient))
			return $_('recipe.prepared_weight_estimated', {
				default:
					'Estimated with a documented yield (×{factor}). Source: Bognár 2002, {table}. Edit to enter a measured weight.',
				values: { factor: suggestion.yieldFactor ?? 1, table: suggestion.source.table }
			});
		if (
			(ingredient.state ?? 'raw') === 'raw' &&
			ingredient.preparationProfile &&
			ingredient.preparationProfile !== 'none'
		)
			return $_('recipe.prepared_weight_unsupported', {
				default: 'No documented cooking yield. Uses the entered quantity.'
			});
		return $_('recipe.prepared_weight_auto', {
			default: 'Automatic suggestion. Edit to enter a measured weight.'
		});
	});

	$effect(() => {
		const inputKey = preparedWeightInputKey(ingredient);
		// Manual edits last until an estimation input changes, including food reference or state.
		untrack(() => {
			if (previousPreparedInputKey !== undefined && previousPreparedInputKey !== inputKey)
				ingredient.measuredPreparedWeightG = null;
			previousPreparedInputKey = inputKey;
		});
		const needsEstimate =
			isPositiveAmount(ingredient.weight) &&
			ingredient.measuredPreparedWeightG == null &&
			(ingredient.state ?? 'raw') === 'raw' &&
			!!ingredient.preparationProfile &&
			ingredient.preparationProfile !== 'none';
		const controller = new AbortController();
		let cancelled = false;
		preparedEstimateFailed = false;
		preparedEstimateLoading = needsEstimate;
		const timer = needsEstimate
			? setTimeout(() => {
					void estimatePreparedWeight(ingredient, controller.signal)
						.then((result) => {
							if (cancelled || inputKey !== preparedWeightInputKey(ingredient)) return;
							ingredient.preparedWeightSuggestion = {
								inputKey,
								weightG: result.prepared_weight_g,
								yieldFactor: result.yield_factor,
								source: result.source
							};
						})
						.catch(() => {
							if (!cancelled) {
								ingredient.preparedWeightSuggestion = undefined;
								preparedEstimateFailed = true;
							}
						})
						.finally(() => {
							if (!cancelled) preparedEstimateLoading = false;
						});
				}, 300)
			: undefined;
		return () => {
			cancelled = true;
			clearTimeout(timer);
			controller.abort();
		};
	});

	// Preserve the actual typed text (including leading zeros) when positioning the unit.
	// Numeric draft values alone lose formatting such as "00" or "0.0".
	$effect(() => {
		const weight = ingredient.weight ?? 0;
		untrack(() => {
			quantityText = quantityInput?.valueAsNumber === weight ? quantityInput.value : String(weight);
		});
	});
	$effect(() => {
		const weight = preparedWeight ?? 0;
		untrack(() => {
			preparedText = preparedInput?.valueAsNumber === weight ? preparedInput.value : String(weight);
		});
	});
	let rowDiagnostics = $derived(
		nutritionDiagnostics.filter((issue) => issue.ingredient_id === ingredient.id)
	);
	let calculationCells = $derived(
		ingredientCalculationCells(
			ingredient,
			missingIngredientIds.includes(ingredient.id),
			rowDiagnostics,
			nutritionFallbackIds.includes(ingredient.id)
		)
	);
	let nutritionIssueTitle = $derived(
		rowDiagnostics.length > 0
			? $_('recipe.incomplete_nutrition_reference', {
					default: 'This reference is missing data required for Nutri-Score.'
				})
			: $_('recipe.required_nutrition_reference', {
					default: 'Choose a Ciqual food or an Open Food Facts product for nutrition calculations.'
				})
	);

	let previousName: string | undefined;
	let productSuggestions = $state<TaxonomyItem[]>([]);

	$effect(() => {
		const name = ingredient.name;
		untrack(() => syncNutritionSearches(ingredient, previousName));
		previousName = name;
	});

	let referenceLookupKey = $derived(
		JSON.stringify([ingredient.name.trim(), ingredient.codifiedIngredient?.id])
	);
	let settledReferenceKey = $state<string>();
	let settledProductKey = $state<string>();
	let referencesPending = $derived(
		ingredient.name.trim().length >= 3 && settledReferenceKey !== referenceLookupKey
	);
	let productsPending = $derived(
		ingredient.name.trim().length >= 3 && settledProductKey !== referenceLookupKey
	);
	let ciqualLoading = $derived(!ingredient.ciqualName && (referencesPending || productsPending));
	let agribalyseLoading = $derived(!ingredient.agribalyseName && referencesPending);
	let productLoading = $derived(!ingredient.productName && productsPending);

	$effect(() => {
		const name = ingredient.name.trim();
		const taxonomyId = ingredient.codifiedIngredient?.id;
		const lookupKey = referenceLookupKey;
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
								})
								.finally(() => {
									if (!cancelled) settledReferenceKey = lookupKey;
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
								})
								.finally(() => {
									if (!cancelled) settledReferenceKey = lookupKey;
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
							})
							.finally(() => {
								if (!cancelled) settledProductKey = lookupKey;
							});
					}, 400)
				: undefined;
		return () => {
			cancelled = true;
			controller.abort();
			clearTimeout(timer);
		};
	});

	/** Seasonality is meaningful only for fresh fruit and vegetables. */
	function toggleFreshPlant(event: Event) {
		ingredient.isFreshPlant = (event.target as HTMLSelectElement).value === 'true';
		if (!ingredient.isFreshPlant) ingredient.isInSeason = false;
	}
</script>

<tr>
	<td data-invalid={errors.name}>
		<CellTooltip
			tip={errors.name
				? $_('recipe.missing_ingredient_name', { default: 'Enter an ingredient name.' })
				: undefined}
		/>
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
	<td
		data-invalid={!ciqualLoading && calculationCells.ciqual === 'error'}
		data-warning={!ciqualLoading && calculationCells.ciqual === 'warning'}
	>
		<TaxonomyCell
			invalid={!ciqualLoading && calculationCells.ciqual === 'error'}
			id="ingredient-ciqual-{rowId}"
			backgroundLoading={ciqualLoading}
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

		<CellTooltip
			tip={!ciqualLoading && calculationCells.ciqual ? nutritionIssueTitle : undefined}
		/>
	</td>
	<td
		data-invalid={!agribalyseLoading && calculationCells.agribalyse === 'error'}
		data-warning={!agribalyseLoading && calculationCells.agribalyse === 'warning'}
	>
		<TaxonomyCell
			id="ingredient-reference-{rowId}"
			backgroundLoading={agribalyseLoading}
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
			invalid={!agribalyseLoading && calculationCells.agribalyse === 'error'}
			onchange={(tags) => {
				ingredient.agribalyseName = tags[0]?.label ?? '';
				ingredient.agribalyseCode = tags[0]?.isInTaxonomy ? (tags[0].id ?? undefined) : undefined;
				ingredient.referenceSource = 'manual';
			}}
		/>

		<CellTooltip
			tip={!agribalyseLoading && calculationCells.agribalyse
				? $_('recipe.incomplete_environmental_reference', {
						default: 'This reference has no usable environmental data for Green Score.'
					})
				: undefined}
		/>
	</td>
	<td
		data-invalid={!productLoading && calculationCells.product === 'error'}
		data-warning={!productLoading && calculationCells.product === 'warning'}
		data-info={!productLoading && calculationCells.product === 'info'}
	>
		<TaxonomyCell
			invalid={!productLoading && calculationCells.product === 'error'}
			id="ingredient-product-{rowId}"
			backgroundLoading={productLoading}
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

		<CellTooltip
			tip={!productLoading && calculationCells.product === 'info'
				? $_('recipe.off_ciqual_fallback', {
						default: 'Open Food Facts nutrition data is incomplete. Ciqual values are used instead.'
					})
				: !productLoading && calculationCells.product
					? nutritionIssueTitle
					: undefined}
		/>
	</td>
	<td
		data-invalid={errors.weight}
		data-warning={ingredient.weight === 0 && isIngredientNotEmpty(ingredient)}
	>
		<CellTooltip
			tip={errors.weight
				? $_('recipe.invalid_quantity', { default: 'Enter a valid quantity.' })
				: ingredient.weight === 0 && isIngredientNotEmpty(ingredient)
					? $_('recipe.zero_quantity', {
							default: 'Excluded from the calculation because the quantity is 0 grams.'
						})
					: undefined}
		/>
		<div class="relative flex h-[43px] min-w-0 items-center">
			<input
				id="ingredient-weight-{rowId}"
				bind:this={quantityInput}
				class="input validator cell-input min-w-0 flex-1 text-left tabular-nums"
				type="number"
				required
				value={ingredient.weight ?? 0}
				oninput={(event) => {
					quantityText = event.currentTarget.value;
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
				<span class="invisible shrink-0">{quantityText}</span>
				<span class="text-base-content/50 shrink-0 text-xs"
					>{$_('recipe.grams', { default: 'grams' })}</span
				>
			</div>
		</div>
	</td>
	<td data-warning={calculationCells.state === 'warning'}>
		<select
			class="cell-input"
			bind:value={ingredient.state}
			aria-label={$_('recipe.state', { default: 'State when weighed' })}
		>
			<option value="raw">{$_('recipe.states.raw', { default: 'Raw' })}</option>
			<option value="cooked">{$_('recipe.states.cooked', { default: 'Cooked' })}</option>
			<option value="drained">{$_('recipe.states.drained', { default: 'Drained' })}</option>
		</select>

		<CellTooltip
			tip={calculationCells.state
				? $_('recipe.prepared_reference_required', {
						default: 'Choose a nutrition reference for the ingredient in its weighed state.'
					})
				: undefined}
		/>
	</td>
	<td data-warning={calculationCells.preparation === 'warning'}>
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

		<CellTooltip
			tip={calculationCells.preparation
				? $_('recipe.unsupported_nutrition_preparation', {
						default: 'Nutrition data for this preparation is unavailable.'
					})
				: undefined}
		/>
	</td>
	<td data-invalid={errors.preparedWeight}>
		<CellTooltip
			tip={errors.preparedWeight
				? $_('recipe.invalid_prepared_weight', {
						default: 'Enter a prepared weight greater than 0.'
					})
				: undefined}
		/>
		<div class="relative flex h-[43px] min-w-0 items-center">
			<input
				id="ingredient-prepared-weight-{rowId}"
				bind:this={preparedInput}
				class="input validator cell-input min-w-0 flex-1 text-left tabular-nums"
				type="number"
				value={preparedWeight ?? 0}
				oninput={(event) => {
					preparedText = event.currentTarget.value;
					ingredient.measuredPreparedWeightG =
						event.currentTarget.value === '' ? null : event.currentTarget.valueAsNumber;
					if (event.currentTarget.value === '') {
						// Restore the suggestion even when there was no manual value to clear.
						event.currentTarget.value = String(getPreparedWeight(ingredient) ?? 0);
						preparedText = event.currentTarget.value;
					}
				}}
				min="0"
				step="any"
				inputmode="decimal"
				aria-label={$_('recipe.prepared_weight_with_unit', { default: 'Prepared weight (grams)' })}
				aria-invalid={errors.preparedWeight}
				title={errors.preparedWeight ? undefined : preparedWeightTitle}
				aria-busy={preparedEstimateLoading}
			/>
			<!-- The invisible number positions the unit; the full-width input keeps its native arrows. -->
			<div
				class="pointer-events-none absolute inset-y-0 right-8 left-3 flex items-center gap-1 overflow-hidden text-sm whitespace-nowrap tabular-nums"
				aria-hidden="true"
			>
				<span class="invisible shrink-0">{preparedText}</span>
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
			<option value="">{$_('recipe.world', { default: 'World' })}</option>
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
			disabled={isOnlyItem}
			onclick={() => onDelete?.(ingredient.id)}
			aria-label={$_('recipe.delete_ingredient', { default: 'Delete ingredient' })}
		>
			<IconMdiDelete class="h-4 w-4" aria-hidden="true" />
		</button>
	</td>
</tr>
