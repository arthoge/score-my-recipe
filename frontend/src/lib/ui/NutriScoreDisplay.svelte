<!-- Simple nutrition result; detailed diagnostics remain in the analysis API. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { NutritionAnalysis } from '$lib/api/nutritionAnalysis';
	import NutriScore from './NutriScore.svelte';
	import type { Ingredient } from '$lib/types/ingredient';
	import { nutritionExclusionReasons } from './excludedIngredients';
	import ExcludedIngredientsSummary from './ExcludedIngredientsSummary.svelte';
	let dialog: HTMLDialogElement;
	const dialogId = $props.id();
	let {
		analysis = null,
		ingredients,
		recipeId,
		loading = false,
		portionWeightG = null
	}: {
		analysis?: NutritionAnalysis | null;
		ingredients: Ingredient[];
		recipeId: string;
		loading?: boolean;
		portionWeightG?: number | null;
	} = $props();

	// Use nutrition-label order rather than the API object's property order.
	const nutrientOrder = [
		'energy_kj',
		'fat',
		'saturated_fat',
		'carbohydrates',
		'sugars',
		'fiber',
		'proteins',
		'salt'
	];

	/** Both columns use grams for nutrients and kilojoules for energy. */
	function formatNutrient(value: number | null | undefined, key: string): string {
		return value == null ? '—' : `${value.toFixed(2)} ${key === 'energy_kj' ? 'kJ' : 'g'}`;
	}

	/** Display OFF taxonomy identifiers as additive codes or readable allergen names. */
	function formatProductTag(tag: string, additive: boolean): string {
		const name = tag.replace(/^[a-z]{2}:/, '').replaceAll('-', ' ');
		return additive ? name.toUpperCase() : name.charAt(0).toUpperCase() + name.slice(1);
	}
</script>

<div class="bg-base-200 w-96 max-w-full rounded-lg p-4" aria-live="polite" aria-busy={loading}>
	<div class="flex min-h-8 items-center justify-between gap-2">
		<h3 class="text-lg font-semibold">{$_('recipe.nutri_score', { default: 'Nutri-Score' })}</h3>
		<button
			type="button"
			class="btn btn-ghost btn-sm gap-1"
			aria-haspopup="dialog"
			onclick={() => dialog.showModal()}
		>
			<span>{$_('nutrition.details_button', { default: 'Details' })}</span>
			<svg
				class="h-4 w-4 translate-y-px"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				stroke-width="2"
				aria-hidden="true"
			>
				<path d="m9 6 6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		</button>
	</div>
	{#if loading}
		<div class="flex items-center gap-2 py-2">
			<span class="loading loading-spinner loading-sm" aria-hidden="true"></span>
			<span>{$_('recipe.computing', { default: 'Calculating...' })}</span>
		</div>
	{:else}
		{#if analysis?.nutri_score}
			<div class="mt-2">
				<NutriScore grade={analysis.nutri_score.grade} score={analysis.nutri_score.score} />
			</div>
		{:else}
			<p class="text-base-content/70 mt-2 text-sm">
				{$_('recipe.no_score', {
					default: 'Score updates automatically once the required cells are complete.'
				})}
			</p>
		{/if}
		{#if analysis?.nutri_score && analysis.excluded_ingredients?.length}
			<ExcludedIngredientsSummary
				{recipeId}
				count={analysis.excluded_ingredients.length}
				percent={Math.round(analysis.excluded_weight_percent)}
				reasons={nutritionExclusionReasons(ingredients, analysis)}
			/>
		{/if}
		{#if analysis?.status === 'unsupported' && !analysis.excluded_ingredients?.length}
			<p class="text-base-content/70 mt-2 text-sm">
				{$_('nutrition.unsupported_type', { default: 'This recipe type is not supported yet.' })}
			</p>
		{/if}
	{/if}
</div>

<dialog bind:this={dialog} class="modal" aria-labelledby="{dialogId}-title">
	<div class="modal-box">
		<h2 id="{dialogId}-title" class="text-lg font-bold">
			{$_('nutrition.details', { default: 'Nutrition details' })}
		</h2>
		<p class="text-base-content/70 mt-2 mb-4 text-sm">
			{$_('nutrition.details_description', {
				default: 'Based on available product data. Information may be missing or inaccurate.'
			})}
		</p>
		<div class="overflow-x-auto">
			<table class="table-xs table">
				<thead class="bg-base-200"
					><tr
						><th></th><th>{$_('nutrition.per_100g', { default: 'Per 100 g' })}</th><th
							>{$_('nutrition.per_portion', { default: 'Per portion' })}{#if portionWeightG != null}
								{` (${Number(portionWeightG.toFixed(2))} g)`}
							{/if}</th
						></tr
					></thead
				>
				<tbody>
					{#each nutrientOrder as key (key)}
						<tr
							><th>{$_(`nutrition.nutrients.${key}`, { default: key.replaceAll('_', ' ') })}</th><td
								class="whitespace-nowrap"
								>{formatNutrient(analysis?.nutrients_per_100g?.[key], key)}</td
							><td class="whitespace-nowrap"
								>{formatNutrient(analysis?.nutrients_per_portion?.[key], key)}</td
							></tr
						>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-4 space-y-4">
			{#each ['additives', 'allergens'] as field (field)}
				{@const tags = field === 'additives' ? analysis?.additives : analysis?.allergens}
				<section>
					<h3 class="mb-2 text-sm font-semibold">
						{$_(`nutrition.${field}`, {
							default: field === 'additives' ? 'Additives' : 'Allergens'
						})}
					</h3>
					{#if loading}
						<div class="skeleton h-5 w-40" aria-hidden="true"></div>
					{:else if tags?.length}
						<ul class="flex flex-wrap gap-2">
							{#each tags as tag (tag)}
								<li class="badge badge-soft text-xs">
									{formatProductTag(tag, field === 'additives')}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="text-base-content/70 text-xs">
							{$_('nutrition.no_product_information', { default: 'No information available' })}
						</p>
					{/if}
				</section>
			{/each}
		</div>
		<div class="modal-action">
			<button type="button" class="btn btn-outline" onclick={() => dialog.close()}>
				{$_('nutrition.close', { default: 'Close' })}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('nutrition.close', { default: 'Close' })}></button>
	</form>
</dialog>
