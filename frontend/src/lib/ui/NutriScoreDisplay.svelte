<!-- Simple nutrition result; detailed diagnostics remain in the analysis API. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { NutritionAnalysis } from '$lib/api/nutritionAnalysis';
	import NutriScore from './NutriScore.svelte';
	let {
		analysis = null,
		loading = false
	}: {
		analysis?: NutritionAnalysis | null;
		loading?: boolean;
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
	let nutrientRows = $derived(
		Object.entries(analysis?.nutrients_per_100g ?? {}).sort(
			([a], [b]) =>
				(nutrientOrder.indexOf(a) === -1 ? nutrientOrder.length : nutrientOrder.indexOf(a)) -
				(nutrientOrder.indexOf(b) === -1 ? nutrientOrder.length : nutrientOrder.indexOf(b))
		)
	);

	/** Both columns use grams for nutrients and kilojoules for energy. */
	function formatNutrient(value: number | null | undefined, key: string): string {
		return value == null ? '—' : `${value.toFixed(2)} ${key === 'energy_kj' ? 'kJ' : 'g'}`;
	}
</script>

<div class="bg-base-200 w-96 max-w-full rounded-lg p-4" aria-live="polite" aria-busy={loading}>
	<h3 class="text-lg font-semibold">{$_('recipe.nutri_score', { default: 'Nutri-Score' })}</h3>
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
		{#if analysis?.nutrients_per_100g}
			<details class="mt-3 text-sm">
				<summary class="cursor-pointer"
					>{$_('nutrition.details', { default: 'Nutrition details' })}</summary
				>
				<div class="mt-2 overflow-x-auto">
					<table class="table-xs table">
						<thead
							><tr
								><th></th><th>{$_('nutrition.per_100g', { default: 'Per 100 grams' })}</th><th
									>{$_('nutrition.per_portion', { default: 'Per portion' })}</th
								></tr
							></thead
						>
						<tbody>
							{#each nutrientRows as [key, value] (key)}
								<tr
									><th>{$_(`nutrition.nutrients.${key}`, { default: key.replaceAll('_', ' ') })}</th
									><td class="whitespace-nowrap">{formatNutrient(value, key)}</td><td
										class="whitespace-nowrap"
										>{formatNutrient(analysis.nutrients_per_portion?.[key], key)}</td
									></tr
								>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
	{/if}
</div>
