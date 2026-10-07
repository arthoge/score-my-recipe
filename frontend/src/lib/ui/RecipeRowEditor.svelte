<!--
  RecipeRowEditor.svelte

  Handles the edition of the ingredient rows: it renders one `IngredientLine` per
  ingredient and takes care of deleting a row or adding a new empty line when the
  last one becomes non-empty.

  The ingredients array is bindable so that the shared state stays in the parent
  page (which also uses it to compute the score).

  Props:
  - ingredients: The full list of ingredients (bindable, owned by the parent page).
-->
<script lang="ts">
	import IngredientLine from './IngredientLine.svelte';
	import HelperTooltip from './HelperTooltip.svelte';
	import { _, getLocale } from '$lib/i18n';
	import { onMount } from 'svelte';
	import { getCountries, getLabelsTaxonomy } from '$lib/api/taxonomy';
	import type { TaxonomyItem } from '$lib/types/ingredient';
	import { removeIngredientFromList, addEmptyIngredientIfNeeded } from '$lib/types/ingredientsList';
	import type { IngredientsList } from '$lib/types/ingredientsList';

	type Props = {
		ingredients: IngredientsList;
		/** Ingredient ids flagged as missing in the last computed green-score. */
		missingIngredientIds?: string[];
		/** Recipe name used to identify the table to assistive technology. */
		title: string;
		id: string;
	};

	let { ingredients = $bindable(), missingIngredientIds = [], title, id }: Props = $props();

	// Load each choice list once per recipe, rather than once per ingredient row.
	let originOptions = $state<TaxonomyItem[]>([]);
	let labelOptions = $state<TaxonomyItem[]>([]);
	let originsStatus = $state<'loading' | 'ready' | 'failed'>('loading');
	let labelsStatus = $state<'loading' | 'ready' | 'failed'>('loading');

	onMount(() => {
		let cancelled = false;
		void getCountries(getLocale().startsWith('fr') ? 'fr' : 'en')
			.then((countries) => {
				if (cancelled) return;
				originOptions = countries.map((country) => ({
					id: country.id,
					label: country.label,
					isInTaxonomy: true
				}));
				originsStatus = 'ready';
			})
			.catch(() => {
				if (!cancelled) originsStatus = 'failed';
			});
		void getLabelsTaxonomy(false)
			.then((labels) => {
				if (cancelled) return;
				labelOptions = labels;
				labelsStatus = 'ready';
			})
			.catch(() => {
				if (!cancelled) labelsStatus = 'failed';
			});
		return () => {
			cancelled = true;
		};
	});

	/** Handle delete of an ingredient by id. */
	function handleIngredientDelete(id: string) {
		ingredients = removeIngredientFromList(ingredients, id);
	}

	/** Ensure a new empty line exists when the last line is no longer empty. */
	function addIngredientLine() {
		ingredients = addEmptyIngredientIfNeeded(ingredients);
	}

	// Data columns share a width; the icon-only action column stays compact.
	const columns = [
		{
			key: 'ingredient_name',
			label: 'Ingredient name'
		},
		{
			key: 'ciqual_food',
			label: 'Ciqual',
			help: 'Generic food from the French Ciqual nutrition database, such as raw tomato. Choose the food that best matches your ingredient.'
		},
		{
			key: 'agribalyse_food',
			label: 'Agribalyse',
			help: 'Food from the Agribalyse environmental database, used to calculate the Green Score. You can change the suggested match.'
		},
		{
			key: 'off_product',
			label: 'Open Food Facts',
			help: 'Select your exact packaged product by name and brand as the nutrition reference. Clear this field to use the generic Ciqual food instead.'
		},
		{
			key: 'quantity_grams',
			label: 'Quantity (grams)'
		},
		{
			key: 'state',
			label: 'State when weighed'
		},
		{
			key: 'preparation_profile',
			label: 'Preparation'
		},
		{
			key: 'labels',
			label: 'Labels',
			help: 'Certifications carried by this ingredient, such as organic or fair trade. These can affect the Green Score.'
		},
		{
			key: 'origin',
			label: 'Origin',
			help: 'Country where this ingredient was produced. Used to estimate transport impact.'
		},
		{
			key: 'fresh_plant',
			label: 'Fresh fruit/veg',
			help: 'Select Yes for fresh fruit or vegetables to enable the seasonality field.'
		},
		{
			key: 'in_season',
			label: 'In season',
			help: 'Select Yes if this fresh fruit or vegetable is in season where and when you prepare the recipe.'
		},
		{ key: 'action', label: 'Action' }
	];
</script>

<div class="w-full min-w-0">
	<!-- Keyboard focus lets users scroll the wide table with arrow keys. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		class="border-base-300 max-h-96 overflow-auto border"
		tabindex="0"
		role="region"
		aria-label={title}
	>
		<table class="ingredient-table table-sm table-pin-rows table table-fixed">
			<caption class="sr-only">{title}</caption>
			<colgroup
				>{#each columns as column (column.key)}<col
						class:action-column={column.key === 'action'}
					/>{/each}</colgroup
			>
			<thead>
				<tr>
					{#each columns as column (column.key)}
						<th class:action-column={column.key === 'action'} scope="col">
							<div class="header-content">
								<span class:sr-only={column.key === 'action'}
									>{$_(`recipe.${column.key}`, { default: column.label })}</span
								>
								{#if column.help}
									<HelperTooltip
										floating
										position="bottom"
										tip={$_(`recipe.column_help.${column.key}`, { default: column.help })}
										ariaLabel={$_('helpers.column_info', {
											default: 'Information about {column}',
											values: { column: $_(`recipe.${column.key}`, { default: column.label }) }
										})}
									/>
								{/if}
							</div>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each ingredients as ingredient, index (ingredient.id)}
					<IngredientLine
						recipeId={id}
						bind:ingredient={ingredients[index]}
						isLastItem={index === ingredients.length - 1}
						isOnlyItem={ingredients.length === 1}
						onDelete={handleIngredientDelete}
						onNotEmpty={addIngredientLine}
						{missingIngredientIds}
						{originOptions}
						{labelOptions}
						{originsStatus}
						{labelsStatus}
					/>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.ingredient-table {
		width: max(100%, 2176px);
	}
	.ingredient-table col {
		width: 192px;
	}
	.ingredient-table col.action-column {
		width: 64px;
	}
	.ingredient-table th.action-column {
		padding-inline: 4px;
	}
	.header-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}
	.header-content > span {
		min-width: 0;
	}
	.action-column .header-content {
		gap: 2px;
	}
	.ingredient-table th {
		height: 72px;
		white-space: normal;
		background: var(--color-base-200);
	}
	.ingredient-table th:not(:last-child) {
		border-right: 1px solid var(--color-base-300);
	}
	/* DaisyUI omits the last row border; keep it so adding a row cannot change geometry. */
	.ingredient-table :global(tbody tr) {
		height: 44px;
		border-bottom: 1px solid var(--color-base-300);
	}
	/* Shared cell geometry applies to controls rendered by the row components. */
	:global(.ingredient-table td) {
		height: 44px;
		padding: 0;
		border-right: 1px solid var(--color-base-300);
		background: var(--color-base-100);
	}
	:global(.ingredient-table .cell-input) {
		display: block;
		width: 100%;
		height: 43px;
		min-width: 0;
		border: 0;
		border-radius: 0;
		padding: 0 12px;
		background: transparent;
		/* Cell styling replaces DaisyUI input depth shadows, including validation colors. */
		box-shadow: none;
		font-size: 0.875rem;
		outline: none;
	}
	:global(.ingredient-table .cell-input:disabled) {
		opacity: 0.5;
	}
	:global(.ingredient-table td:hover),
	:global(.ingredient-table td:focus-within) {
		background: var(--color-base-200);
	}
	:global(.ingredient-table td:focus-within) {
		box-shadow: inset 0 0 0 1px var(--color-primary);
	}
	:global(.ingredient-table td[data-invalid='true']:not(:focus-within)) {
		background: color-mix(in oklab, var(--color-error) 15%, var(--color-base-100));
	}
</style>
