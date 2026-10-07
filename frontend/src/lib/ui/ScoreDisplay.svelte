<script lang="ts">
	import { _ } from '$lib/i18n';
	import GreenScore from './GreenScore.svelte';
	import type { GreenScoreResponse } from '$lib/api/recipe';

	type Props = {
		score?: GreenScoreResponse | null;
		isLoading?: boolean;
		error?: string | null;
		excludedWeightPercent?: number;
	};

	let {
		score = null,
		isLoading = false,
		error = null,
		excludedWeightPercent = 0
	}: Props = $props();
</script>

<div class="bg-base-200 w-96 max-w-full rounded-lg p-4" aria-live="polite" aria-busy={isLoading}>
	<h3 class="text-lg font-semibold">
		{$_('recipe.green_score', { default: 'Green Score' })}
	</h3>

	{#if isLoading}
		<div class="flex items-center gap-2 py-2">
			<span class="loading loading-spinner loading-sm" aria-hidden="true"></span>
			<span>{$_('recipe.computing', { default: 'Calculating...' })}</span>
		</div>
	{:else if !error && score?.letterGrade}
		<!-- Score logo + numeric score -->
		<div class="mt-2">
			<GreenScore letterGrade={score.letterGrade} numericScore={score.numericScore} />
		</div>
	{:else}
		<p class="text-base-content/70 mt-2 text-sm">
			{$_(error ? 'recipe.compute_error' : 'recipe.no_score', {
				default: error
					? 'Could not compute the score. Please try again.'
					: 'Score updates automatically once the required cells are complete.'
			})}
		</p>
	{/if}
	{#if !isLoading && !error && score?.letterGrade && score.missingIngredientIds.length > 0}
		<p class="text-base-content mt-3 text-sm font-semibold" role="status">
			{$_('recipe.excluded_summary', {
				default: '{count} ingredient(s) excluded ({percent}% of recipe weight).',
				values: { count: score?.missingIngredientIds.length ?? 0, percent: excludedWeightPercent }
			})}
		</p>
	{/if}
</div>
