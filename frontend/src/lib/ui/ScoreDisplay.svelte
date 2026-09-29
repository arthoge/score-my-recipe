<!--
  ScoreDisplay.svelte

  Displays the computed green-score of a recipe: it wraps the `GreenScore` logo
  component and adds the surrounding context (loading state, error, and the
  summary of ingredients that were ignored by the backend computation).

  Props:
  - score: The full green-score response from the backend, or null.
  - totalIngredientCount: The total number of ingredients sent to the backend.
  - ignoredWeight: The total weight (in grams) of the ignored ingredients.
  - totalWeight: The total weight (in grams) of all sent ingredients.
  - isLoading: Whether the score is currently being computed.
  - error: An error message, if the computation failed.
-->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import GreenScore from './GreenScore.svelte';
	import type { GreenScoreResponse } from '$lib/api/recipe';

	type Props = {
		score?: GreenScoreResponse | null;
		totalIngredientCount?: number;
		ignoredWeight?: number;
		totalWeight?: number;
		isLoading?: boolean;
		error?: string | null;
		showHeader?: boolean;
		size?: 'sm' | 'md' | 'lg';
		class?: string;
	};

	let {
		score = null,
		totalIngredientCount = 0,
		ignoredWeight = 0,
		totalWeight = 0,
		isLoading = false,
		error = null,
		showHeader = true,
		size = 'lg',
		class: className = 'bg-base-200 rounded-lg p-4'
	}: Props = $props();

	/** Number of ignored ingredients. */
	let ignoredCount = $derived(score?.missingIngredientIds.length ?? 0);

	/** Percentage of the total weight that the ignored ingredients represent. */
	let ignoredWeightPercent = $derived(
		totalWeight > 0 ? Math.round((ignoredWeight / totalWeight) * 100) : 0
	);
</script>

<div class={className}>
	{#if showHeader}
		<h2 class="text-lg font-semibold">
			{$_('recipe.green_score', { default: 'Green Score' })}
		</h2>
	{/if}

	{#if isLoading}
		<div class="flex items-center gap-3 py-4">
			<span class="loading loading-spinner loading-lg"></span>
			<span>{$_('recipe.computing', { default: 'Computing score...' })}</span>
		</div>
	{:else if error}
		<div class="alert alert-error mt-2">
			<span>{error}</span>
		</div>
	{:else if score?.letterGrade}
		<!-- Score logo + numeric score -->
		<div class="mt-2">
			<GreenScore letterGrade={score.letterGrade} numericScore={score.numericScore} {size} />
		</div>

		<!-- Ignored ingredients summary -->
		{#if totalIngredientCount > 0}
			<div class="text-base-content/70 mt-3 text-sm">
				<p>
					<strong>{ignoredCount}</strong>
					{$_('recipe.ignored_ingredients', { default: 'ingredient(s) ignored' })}
				</p>
				<p>
					<strong>{ignoredWeightPercent}%</strong>
					{$_('recipe.ignored_weight', { default: 'of total weight' })}
				</p>
			</div>
		{/if}
	{:else}
		<p class="text-base-content/70 mt-2 text-sm">
			{$_('recipe.no_score', {
				default: 'No score available. Add ingredients with weights to compute the score.'
			})}
		</p>
	{/if}
</div>
