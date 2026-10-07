<script lang="ts">
	import { _ } from '$lib/i18n';
	import GreenScore from './GreenScore.svelte';
	import type { GreenScoreResponse } from '$lib/api/recipe';

	type Props = {
		score?: GreenScoreResponse | null;
		isLoading?: boolean;
		error?: string | null;
	};

	let { score = null, isLoading = false, error = null }: Props = $props();
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
	{:else if !error && score?.letterGrade && score.missingIngredientIds.length === 0}
		<!-- Score logo + numeric score -->
		<div class="mt-2">
			<GreenScore letterGrade={score.letterGrade} numericScore={score.numericScore} />
		</div>
	{:else}
		<p class="text-base-content/70 mt-2 text-sm">
			{$_('recipe.no_score', {
				default: 'Score updates automatically once the required cells are complete.'
			})}
		</p>
	{/if}
</div>
