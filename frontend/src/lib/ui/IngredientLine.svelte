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
	import HelperTooltip from './HelperTooltip.svelte';
	import IconMdiDelete from '@iconify-svelte/mdi/delete';
	import IconMdiAlertOutline from '@iconify-svelte/mdi/alert-outline';
	import IconMdiLeaf from '@iconify-svelte/mdi/leaf';
	import IconMaterialSymbolsSunnyOutline from '@iconify-svelte/material-symbols/sunny-outline';
	import IconMaterialSymbolsCloudOutline from '@iconify-svelte/material-symbols/cloud-outline';
	import type { Ingredient } from '$lib/types/ingredient';
	import type { IngredientSuggestion, TaxonomyItem } from '$lib/types/ingredient';
	import { isIngredientEmpty, isIngredientNotEmpty } from '$lib/types/ingredient';
	import { ITEM_UNIT_ID } from '$lib/api/taxonomy';

	/** Taxonomy id of the gram unit — the only unit for which grams track the
	 * quantity value live (identity, not a transformation). */
	const GRAM_UNIT_ID = 'en:gram';

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

	/** Whether a non-empty ingredient has a zero or missing quantity, which excludes
	 * it from score computation. The always-present empty line remains unflagged. */
	let isZeroWeight = $derived(
		isIngredientNotEmpty(ingredient) && (ingredient.weight === 0 || ingredient.weight == null)
	);

	/**
	 * Keep the grams (weight) in sync with the quantity value when the unit is
	 * the gram unit. This is the only live conversion: for any other unit (kg,
	 * ml, cup, item…), grams stay frozen (the parser's quantity_g, or 0) — unit
	 * transformations are deferred to a later step.
	 *
	 * Writing ``ingredient.weight`` here does not re-trigger this effect
	 * because ``weight`` is not read (only ``quantityUnit`` and
	 * ``quantityValue`` are), so there is no update cycle.
	 */
	$effect(() => {
		if (ingredient.quantityUnit?.id === GRAM_UNIT_ID) {
			ingredient.weight = ingredient.quantityValue;
		}
	});

	/**
	 * Display label for a unit TaxonomyItem.
	 *
	 * The synthetic ``item`` unit (for countable ingredients) is shown as the
	 * ingredient name instead of the literal 'item', so that "3 eggs" reads
	 * naturally as "3" + "eggs". Falls back to the codified ingredient label,
	 * then to 'item' when the name is empty (e.g. a fresh empty line).
	 */
	function formatUnitLabel(unit: TaxonomyItem): string {
		if (unit.id === ITEM_UNIT_ID) {
			return ingredient.name || ingredient.codifiedIngredient?.label || ITEM_UNIT_ID;
		}
		return unit.label;
	}

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

<div class="flex flex-col gap-2 rounded-lg p-3 sm:flex-row sm:items-start">
	<!-- Codified Ingredient name -->
	<div class="flex grow-3 flex-col">
		<label class="label py-1" for="ingredient-codified-{ingredient.id}">
			<span class="flex items-center gap-1.5">
				<span class="label-text text-xs" class:text-error={isMissing}
					>{$_('recipe.codified_ingredient', { default: 'Codified' })}</span
				>
				{#if isMissing}
					<!-- Screen-reader status: the missing state is otherwise conveyed
					     only by colour + icon, so expose it as text here. -->
					<span class="sr-only">
						{$_('recipe.ingredient_not_accounted', { default: 'Not accounted' })}
					</span>
				{/if}
				<HelperTooltip
					tip={$_('helpers.codified_ingredient', {
						default: 'Standardized ingredient from the Open Food Facts / Agribalyse database.'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
				{#if isMissing}
					<!-- Stop icon is itself the tooltip trigger (via HelperTooltip's
					     custom icon snippet) explaining why the ingredient is not
					     accounted for in the green-score. -->
					<HelperTooltip
						tip={$_('recipe.ingredient_not_accounted_tooltip', {
							default:
								'We could not find a correspondence in our impact database for this ingredient'
						})}
						ariaLabel={$_('helpers.more_info', { default: 'More information' })}
					>
						{#snippet icon()}
							<IconMdiAlertOutline
								class="text-error h-4 w-4 shrink-0 transition-colors duration-200"
								aria-hidden="true"
							/>
						{/snippet}
					</HelperTooltip>
				{/if}
			</span>
		</label>
		<Tags
			tagtype="ingredients"
			id="ingredient-codified-{ingredient.id}"
			tags={ingredient.codifiedIngredient ? [ingredient.codifiedIngredient] : []}
			onChange={(newTags) => {
				ingredient.codifiedIngredient = newTags[0] ?? null;
			}}
			single={true}
			invalid={isMissing}
		>
			{#snippet suggestionIcon(item)}
				<!-- Show a leaf icon for ingredients that have an EF score (are scorable
				     in the green-score). The snippet receives a TaxonomyItem from Tags;
				     for ingredients it is an IngredientSuggestion carrying hasEfScore. -->
				{@const suggestion = item as IngredientSuggestion}
				{#if suggestion.hasEfScore}
					<span
						title={$_('recipe.ingredient_scorable', {
							default: 'This ingredient can be counted in the green score'
						})}
					>
						<IconMdiLeaf class="h-4 w-4 shrink-0" aria-hidden="true" />
						<span class="sr-only">
							{$_('recipe.ingredient_scorable', {
								default: 'This ingredient can be counted in the green score'
							})}
						</span>
					</span>
				{/if}
			{/snippet}
		</Tags>
	</div>

	<!-- Quantity -->
	<div class="flex w-20 flex-col">
		<label class="label py-1" for="ingredient-quantity-{ingredient.id}">
			<span class="label-text text-xs">
				{$_('recipe.quantity', { default: 'Quantity' })}
			</span>
		</label>
		<input
			id="ingredient-quantity-{ingredient.id}"
			type="number"
			class="input input-bordered w-full"
			placeholder="0"
			bind:value={ingredient.quantityValue}
			min="0"
		/>
	</div>

	<!-- Unit -->
	<div class="flex w-32 flex-col">
		<label class="label py-1" for="ingredient-unit-{ingredient.id}">
			<span class="label-text text-xs">
				{$_('recipe.unit', { default: 'Unit' })}
			</span>
		</label>
		<Tags
			tagtype="units"
			id="ingredient-unit-{ingredient.id}"
			tags={ingredient.quantityUnit ? [ingredient.quantityUnit] : []}
			onChange={(newTags) => {
				ingredient.quantityUnit = newTags[0] ?? null;
			}}
			single={true}
			minChars={0}
			formatLabel={formatUnitLabel}
		/>
	</div>

	<!-- Grams (read-only, frozen except for the gram unit) -->
	<div class="flex w-20 flex-col">
		<label class="label py-1" for="ingredient-grams-{ingredient.id}">
			<span class="flex items-center gap-1.5">
				<span class="label-text text-xs" class:text-error={isZeroWeight}
					>{$_('recipe.grams', { default: 'Grams' })}</span
				>
				{#if isZeroWeight}
					<!-- Screen-reader status: the zero-quantity state is otherwise
					     conveyed only by colour + icon, so expose it as text here. -->
					<span class="sr-only">
						{$_('recipe.ingredient_zero_quantity', { default: 'Zero quantity' })}
					</span>
				{/if}
				<HelperTooltip
					tip={$_('helpers.grams', {
						default:
							'Quantity in grams, used for the green-score computation. ' +
							'For non-gram units it is frozen from the parsed value (no conversion yet).'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
				{#if isZeroWeight}
					<HelperTooltip
						tip={$_('recipe.ingredient_zero_quantity_tooltip', {
							default:
								"This ingredient's quantity is 0g, so it cannot be taken into account in the calculation."
						})}
						ariaLabel={$_('helpers.more_info', { default: 'More information' })}
					>
						{#snippet icon()}
							<IconMdiAlertOutline
								class="text-error h-4 w-4 shrink-0 transition-colors duration-200"
								aria-hidden="true"
							/>
						{/snippet}
					</HelperTooltip>
				{/if}
			</span>
		</label>
		<input
			id="ingredient-grams-{ingredient.id}"
			type="number"
			class="input input-bordered w-full"
			class:input-error={isZeroWeight}
			value={ingredient.weight ?? 0}
			readonly
			placeholder="0"
		/>
	</div>

	<!-- Labels -->
	<div class="flex grow-3 flex-col">
		<label class="label py-1" for="ingredient-labels-{ingredient.id}">
			<span class="flex items-center gap-1.5">
				<span class="label-text text-xs" id="ingredient-labels-label-{ingredient.id}"
					>{$_('recipe.labels', { default: 'Labels' })}</span
				>
				<HelperTooltip
					tip={$_('helpers.labels', {
						default:
							'Official certifications (e.g. Organic, Label Rouge, Fair Trade) that grant Green-Score bonuses.'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
			</span>
		</label>
		<Tags tagtype="labels" bind:tags={ingredient.labels} />
	</div>

	<!-- Fresh fruit/vegetable + seasonality -->
	<div class="flex w-48 flex-col">
		<label class="label py-1" for="ingredient-fresh-{ingredient.id}">
			<span class="flex items-center gap-1.5">
				<span class="label-text text-xs" id="ingredient-fresh-label-{ingredient.id}"
					>{$_('recipe.fresh_plant', { default: 'Fresh fruit/veg' })}</span
				>
				<HelperTooltip
					tip={$_('helpers.seasonality', {
						default:
							'Check if seasonal fruits and vegetables are produced in season for a score bonus.'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
			</span>
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
			<span class="flex items-center gap-1.5">
				<span class="label-text text-xs" id="ingredient-origin-label-{ingredient.id}"
					>{$_('recipe.origin', { default: 'Origin' })}</span
				>
				<HelperTooltip
					tip={$_('helpers.origin', {
						default:
							'Geographical origin of the ingredient, used to evaluate transportation impact.'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
			</span>
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
