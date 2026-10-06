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
	import { _ } from '$lib/i18n';
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
		{ key: 'ingredient_name', label: 'Ingredient name' },
		{ key: 'ciqual_food', label: 'CIQUAL food' },
		{ key: 'agribalyse_food', label: 'Agribalyse correspondence' },
		{ key: 'off_product', label: 'Open Food Facts product' },
		{ key: 'quantity_grams', label: 'Quantity (grams)' },
		{ key: 'state', label: 'Ingredient state' },
		{ key: 'nutrition_confirmed', label: 'Nutrition reference confirmed' },
		{ key: 'preparation_profile', label: 'Preparation profile' },
		{ key: 'measured_prepared_weight', label: 'Measured prepared weight (grams)' },
		{ key: 'estimated_prepared_weight', label: 'Estimated prepared weight (grams)' },
		{ key: 'labels', label: 'Labels' },
		{ key: 'origin', label: 'Origin' },
		{ key: 'fresh_plant', label: 'Fresh fruit/veg' },
		{ key: 'in_season', label: 'In season' },
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
							{$_(`recipe.${column.key}`, { default: column.label })}
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
						onDelete={handleIngredientDelete}
						onNotEmpty={addIngredientLine}
						{missingIngredientIds}
					/>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.ingredient-table {
		width: max(100%, 2752px);
	}
	.ingredient-table col {
		width: 192px;
	}
	.ingredient-table col.action-column {
		width: 64px;
	}
	.ingredient-table th.action-column {
		padding-inline: 8px;
		text-align: center;
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
	:global(.ingredient-table td[data-readonly='true']) {
		background: var(--color-base-200);
	}
	:global(.ingredient-table td:focus-within) {
		box-shadow: inset 0 0 0 1px var(--color-primary);
	}
	:global(.ingredient-table td[data-invalid='true']:not(:focus-within)) {
		background: color-mix(in oklab, var(--color-error) 15%, var(--color-base-100));
	}
	@media (min-width: 768px) {
		:global(.ingredient-table td:first-child),
		.ingredient-table th:first-child {
			position: sticky;
			left: 0;
			z-index: 1;
		}
		.ingredient-table th:first-child {
			z-index: 3;
		}
	}
</style>
