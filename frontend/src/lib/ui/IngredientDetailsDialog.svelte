<!-- Edit the ingredient's nutrition and environmental references without widening the table. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { Ingredient } from '$lib/types/ingredient';
	import { searchCiqualFoods, searchAgribalyseFoods } from '$lib/api/nutrition';
	import type { ingredientCalculationCells } from './ingredientEditor';
	import TaxonomyCell from './TaxonomyCell.svelte';
	import HelperTooltip from './HelperTooltip.svelte';

	let {
		ingredient = $bindable(),
		rowId,
		ciqualLoading,
		agribalyseLoading,
		calculationCells,
		nutritionIssueTitle
	}: {
		ingredient: Ingredient;
		rowId: string;
		ciqualLoading: boolean;
		agribalyseLoading: boolean;
		calculationCells: ReturnType<typeof ingredientCalculationCells>;
		nutritionIssueTitle: string;
	} = $props();
	let dialog: HTMLDialogElement;
</script>

<button
	type="button"
	class="btn btn-ghost btn-sm px-2"
	aria-haspopup="dialog"
	onclick={() => dialog.showModal()}
>
	{$_('recipe.details_button', { default: 'Details' })}
</button>
<dialog
	id="ingredient-details-dialog-{rowId}"
	bind:this={dialog}
	class="modal"
	aria-labelledby="ingredient-details-{rowId}"
	aria-describedby="ingredient-details-description-{rowId}"
>
	<div class="modal-box max-w-xl text-left">
		<h2 id="ingredient-details-{rowId}" class="text-lg font-bold">
			{$_('recipe.ingredient_details', { default: 'Ingredient details' })}
		</h2>
		{#if ingredient.name?.trim()}
			<p class="mt-1 text-sm font-medium">{ingredient.name.trim()}</p>
		{/if}
		<p id="ingredient-details-description-{rowId}" class="text-base-content/70 py-4 text-sm">
			{$_('recipe.ingredient_details_description', {
				default: 'Food references used to calculate nutrition and environmental scores.'
			})}
		</p>
		<div class="space-y-4">
			<div class="space-y-2">
				<div class="flex items-center gap-2">
					<label
						class="text-base-content text-sm font-medium sm:text-base"
						for="ingredient-ciqual-{rowId}"
					>
						{$_('recipe.ciqual_food', { default: 'Ciqual reference' })}
					</label>
					<span class="inline-flex translate-y-px">
						<HelperTooltip
							floating
							position="bottom"
							tip={$_('recipe.column_help.ciqual_food', {
								default:
									'Generic food from the French Ciqual database, providing nutrition values for this ingredient.'
							})}
							ariaLabel={$_('helpers.more_info', { default: 'More information' })}
						/>
					</span>
				</div>
				<div>
					<TaxonomyCell
						inputStyle="form"
						invalid={!ciqualLoading &&
							!!ingredient.ciqualName?.trim() &&
							calculationCells.ciqual === 'error'}
						id="ingredient-ciqual-{rowId}"
						backgroundLoading={ciqualLoading}
						getSuggestions={searchCiqualFoods}
						searchTerm={ingredient.name}
						label={$_('recipe.ciqual_food', { default: 'Ciqual reference' })}
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
				</div>
				{#if !ciqualLoading && ingredient.ciqualName?.trim() && calculationCells.ciqual === 'error'}
					<p class="text-error text-sm" role="status">
						{nutritionIssueTitle}
					</p>
				{/if}
			</div>
			<div class="space-y-2">
				<div class="flex items-center gap-2">
					<label
						class="text-base-content text-sm font-medium sm:text-base"
						for="ingredient-reference-{rowId}"
					>
						{$_('recipe.agribalyse_food', { default: 'Agribalyse reference' })}
					</label>
					<span class="inline-flex translate-y-px">
						<HelperTooltip
							floating
							position="bottom"
							tip={$_('recipe.column_help.agribalyse_food', {
								default:
									'Food from the Agribalyse environmental database, used to calculate the Green Score.'
							})}
							ariaLabel={$_('helpers.more_info', { default: 'More information' })}
						/>
					</span>
				</div>
				<div>
					<TaxonomyCell
						inputStyle="form"
						id="ingredient-reference-{rowId}"
						backgroundLoading={agribalyseLoading}
						getSuggestions={searchAgribalyseFoods}
						searchTerm={ingredient.name}
						label={$_('recipe.agribalyse_food', { default: 'Agribalyse reference' })}
						tags={ingredient.agribalyseName
							? [
									{
										id: ingredient.agribalyseCode ?? null,
										label: ingredient.agribalyseName,
										isInTaxonomy: !!ingredient.agribalyseCode
									}
								]
							: []}
						invalid={!agribalyseLoading &&
							!!ingredient.agribalyseName?.trim() &&
							calculationCells.agribalyse === 'error'}
						onchange={(tags) => {
							ingredient.agribalyseName = tags[0]?.label ?? '';
							ingredient.agribalyseCode = tags[0]?.isInTaxonomy
								? (tags[0].id ?? undefined)
								: undefined;
							ingredient.referenceSource = 'manual';
						}}
					/>
				</div>
				{#if !agribalyseLoading && ingredient.agribalyseName?.trim() && calculationCells.agribalyse === 'error'}
					<p class="text-error text-sm" role="status">
						{$_('recipe.incomplete_environmental_reference', {
							default: 'This reference has no usable environmental data for Green Score.'
						})}
					</p>
				{/if}
			</div>
		</div>
		<div class="modal-action">
			<!-- Focus Close on opening so neither autocomplete nor tooltip opens automatically. -->
			<!-- svelte-ignore a11y_autofocus -->
			<button autofocus type="button" class="btn btn-ghost" onclick={() => dialog.close()}
				>{$_('recipe.close', { default: 'Close' })}</button
			>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('recipe.close', { default: 'Close' })}></button>
	</form>
</dialog>
