<!--
  RecipeRowEditor.svelte

  Handles the edition of the ingredient rows: it renders one `IngredientLine` per
  ingredient and handles explicit addition and deletion of rows.

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
	import { type TaxonomyItem } from '$lib/types/ingredient';
	import AddIngredientsDialog from './AddIngredientsDialog.svelte';
	import { removeIngredientFromList } from '$lib/types/ingredientsList';
	import type { NutritionDiagnostic } from '$lib/api/nutritionAnalysis';
	import type { IngredientsList } from '$lib/types/ingredientsList';

	type Props = {
		ingredients: IngredientsList;
		/** Ingredient ids flagged as missing in the last computed green-score. */
		missingIngredientIds?: string[];
		nutritionDiagnostics?: NutritionDiagnostic[];
		nutritionFallbackIds?: string[];
		/** Recipe name used to identify the table to assistive technology. */
		title: string;
		id: string;
	};

	let {
		ingredients = $bindable(),
		missingIngredientIds = [],
		nutritionDiagnostics = [],
		nutritionFallbackIds = [],
		title,
		id
	}: Props = $props();

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

	// Column widths allow room for names, numeric values and concise select choices.
	const columns = [
		{
			key: 'ingredient_name',
			width: 192,
			label: 'Ingredient name'
		},
		{
			key: 'ciqual_food',
			width: 192,
			label: 'Ciqual',
			help: 'Generic food from the French Ciqual database, providing nutrition values for this ingredient.'
		},
		{
			key: 'agribalyse_food',
			width: 192,
			label: 'Agribalyse',
			help: 'Food from the Agribalyse environmental database, used to calculate the Green Score.'
		},
		{
			key: 'off_product',
			width: 208,
			label: 'Open Food Facts',
			help: 'Packaged product used as the nutrition reference. When empty, the generic Ciqual food is used.'
		},
		{
			key: 'quantity_grams',
			width: 144,
			label: 'Quantity'
		},
		{
			key: 'state',
			width: 176,
			label: 'State when weighed'
		},
		{
			key: 'preparation_profile',
			width: 176,
			label: 'Preparation'
		},
		{
			key: 'prepared_weight_grams',
			width: 176,
			label: 'Prepared weight',
			help: 'Weight of this ingredient as served. Uses documented cooking yields where available, otherwise the entered quantity.'
		},
		{
			key: 'labels',
			width: 224,
			label: 'Labels',
			help: 'Certifications carried by this ingredient, such as organic or fair trade. These can affect the Green Score.'
		},
		{
			key: 'origin',
			width: 160,
			label: 'Origin',
			help: 'Country where this ingredient was produced. When World is selected, conservative penalties for origin and transport are used.'
		},
		{
			key: 'fresh_plant',
			width: 120,
			label: 'Fresh',
			help: 'Fresh fruit or vegetables whose environmental impact can depend on seasonality.'
		},
		{
			key: 'in_season',
			width: 120,
			label: 'In season',
			help: 'Whether this fresh fruit or vegetable is in season at the place and time the recipe is prepared.'
		},
		{ key: 'action', label: 'Action', width: 56 }
	];
	const tableWidth = columns.reduce((total, column) => total + column.width, 0);
</script>

<div class="w-full min-w-0">
	<!-- Let ingredient rows flow naturally; only scroll horizontally. -->
	<!-- Keyboard focus lets users scroll the wide table with arrow keys. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		class="table-container border-base-300 overflow-x-auto border"
		tabindex="0"
		role="region"
		aria-label={title}
	>
		<table
			class="ingredient-table table-sm table table-fixed"
			style:width={`max(100%, ${tableWidth}px)`}
		>
			<caption class="sr-only">{title}</caption>
			<colgroup
				>{#each columns as column (column.key)}<col
						style:width={`${column.width}px`}
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
						onDelete={handleIngredientDelete}
						{missingIngredientIds}
						{nutritionDiagnostics}
						{nutritionFallbackIds}
						{originOptions}
						{labelOptions}
						{originsStatus}
						{labelsStatus}
					/>
				{:else}
					<tr>
						<td colspan={columns.length}>
							<span class="empty-ingredients text-base-content/60 text-sm">
								{$_('recipe.no_ingredients', { default: 'No ingredients' })}
							</span>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<AddIngredientsDialog onadd={(added) => (ingredients = [...ingredients, ...added])} />
</div>

<style>
	.table-container {
		container-type: inline-size;
	}
	/* Center the empty message in the visible area of the horizontally scrolling table. */
	.empty-ingredients {
		position: sticky;
		left: 0;
		display: block;
		width: 100cqw;
		text-align: center;
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
		height: 44px;
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
	:global(.ingredient-table td[data-info='true']:not(:focus-within)) {
		background: color-mix(in oklab, var(--color-info) 15%, var(--color-base-100));
	}
	:global(.ingredient-table td[data-warning='true']:not(:focus-within)) {
		background: color-mix(in oklab, var(--color-warning) 15%, var(--color-base-100));
	}
	:global(.ingredient-table td[data-invalid='true']:not(:focus-within)) {
		background: color-mix(in oklab, var(--color-error) 15%, var(--color-base-100));
	}
</style>
