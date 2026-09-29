<!--
  ScoreSheet.svelte

  Sticky bottom sheet for mobile viewport displaying the green-score results.
  In collapsed state, shows only the compact score indicator, recompute button,
  and an expand affordance.
  In expanded state, reveals the full score details, ignored ingredients
  breakdown, and recipe summary stats.
-->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import GreenScore from './GreenScore.svelte';
	import ScoreDisplay from './ScoreDisplay.svelte';
	import IconMdiChevronUp from '@iconify-svelte/mdi/chevron-up';
	import IconMdiRefresh from '@iconify-svelte/mdi/refresh';
	import IconMdiAlertCircle from '@iconify-svelte/mdi/alert-circle';
	import IconMdiClose from '@iconify-svelte/mdi/close';
	import type { GreenScoreResponse } from '$lib/api/recipe';

	type Props = {
		score?: GreenScoreResponse | null;
		isLoading?: boolean;
		error?: string | null;
		totalIngredientCount?: number;
		totalWeight?: number;
		ignoredWeight?: number;
		canCompute?: boolean;
		onRecompute: () => void;
	};

	let {
		score = null,
		isLoading = false,
		error = null,
		totalIngredientCount = 0,
		totalWeight = 0,
		ignoredWeight = 0,
		canCompute = false,
		onRecompute
	}: Props = $props();

	let isExpanded = $state(false);

	function toggleExpanded() {
		isExpanded = !isExpanded;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && isExpanded) {
			isExpanded = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Semi-transparent backdrop when sheet is expanded -->
{#if isExpanded}
	<div
		class="fixed inset-0 z-40 bg-black/40 backdrop-blur-xs transition-opacity duration-300"
		onclick={() => (isExpanded = false)}
		aria-hidden="true"
	></div>
{/if}

<!-- Sticky Bottom Sheet container -->
<div
	class="bg-base-100 border-base-300 fixed inset-x-0 bottom-0 z-50 flex max-h-[85vh] flex-col rounded-t-2xl border-t pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-8px_30px_rgba(0,0,0,0.15)] transition-all duration-300 ease-in-out"
	role="region"
	aria-label={$_('recipe.green_score', { default: 'Green Score' })}
>
	<!-- Drag handle / Expand touch area -->
	<button
		type="button"
		class="flex w-full cursor-pointer justify-center pt-2.5 pb-1 select-none focus:outline-hidden"
		onclick={toggleExpanded}
		aria-label={isExpanded
			? $_('recipe.collapse_details', { default: 'Collapse details' })
			: $_('recipe.expand_details', { default: 'Expand details' })}
	>
		<span class="bg-base-content/25 h-1.25 w-12 rounded-full"></span>
	</button>

	<!-- Compact Bar: Always visible, displaying just score and recompute -->
	<div
		class="flex items-center justify-between gap-2 px-4 py-2 {isExpanded
			? 'border-base-200 border-b'
			: ''}"
	>
		<!-- Left: Score preview or state -->
		<button
			type="button"
			class="flex min-w-0 cursor-pointer items-center gap-2.5 text-left select-none focus:outline-hidden"
			onclick={toggleExpanded}
			aria-expanded={isExpanded}
			aria-controls="mobile-result-sheet-content"
		>
			{#if isLoading}
				<div class="flex items-center gap-2 py-1">
					<span class="loading loading-spinner text-primary loading-sm"></span>
					<span class="text-xs font-medium sm:text-sm"
						>{$_('recipe.computing', { default: 'Computing score...' })}</span
					>
				</div>
			{:else if error}
				<div class="text-error flex items-center gap-1.5 py-1 text-xs font-medium sm:text-sm">
					<IconMdiAlertCircle class="h-4 w-4 shrink-0" />
					<span class="max-w-[130px] truncate sm:max-w-xs">{error}</span>
				</div>
			{:else if score?.letterGrade}
				<div class="flex items-center gap-2">
					<GreenScore letterGrade={score.letterGrade} size="sm" showScoreText={false} />
					<div class="flex flex-col">
						<span class="text-sm leading-tight font-bold">
							{score.numericScore !== null && score.numericScore !== undefined
								? score.numericScore.toFixed(1)
								: ''}
							<span class="text-base-content/60 text-[11px] font-normal">/100</span>
						</span>
						<span
							class="text-base-content/60 text-[10px] leading-none font-semibold tracking-wider uppercase"
						>
							{$_('recipe.green_score', { default: 'Green Score' })}
						</span>
					</div>
				</div>
			{:else}
				<span class="text-base-content/60 text-xs sm:text-sm">
					{$_('recipe.no_score_short', { default: 'No score yet' })}
				</span>
			{/if}
		</button>

		<!-- Right: Recompute button & Expand toggle -->
		<div class="flex shrink-0 items-center gap-2">
			<button
				type="button"
				class="btn btn-primary btn-sm gap-1.5"
				onclick={onRecompute}
				disabled={isLoading || !canCompute}
			>
				{#if isLoading}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					<IconMdiRefresh class="h-4 w-4" />
				{/if}
				<span class="text-xs">{$_('recipe.recompute', { default: 'Recompute' })}</span>
			</button>

			<button
				type="button"
				class="btn btn-ghost btn-sm btn-circle"
				onclick={toggleExpanded}
				aria-label={isExpanded
					? $_('recipe.collapse_details', { default: 'Collapse details' })
					: $_('recipe.expand_details', { default: 'Expand details' })}
				aria-expanded={isExpanded}
				aria-controls="mobile-result-sheet-content"
			>
				<IconMdiChevronUp
					class="h-5 w-5 transition-transform duration-300 {isExpanded ? 'rotate-180' : ''}"
				/>
			</button>
		</div>
	</div>

	<!-- Expanded Content Area: "The rest" -->
	{#if isExpanded}
		<div id="mobile-result-sheet-content" class="space-y-4 overflow-y-auto px-4 pt-3 pb-6">
			<!-- Header inside sheet -->
			<div class="flex items-center justify-between">
				<h3 class="text-base font-bold">
					{$_('recipe.green_score', { default: 'Green Score' })}
				</h3>
				<button
					type="button"
					class="btn btn-ghost btn-xs btn-circle"
					onclick={() => (isExpanded = false)}
					aria-label={$_('recipe.collapse_details', { default: 'Collapse details' })}
				>
					<IconMdiClose class="h-4 w-4" />
				</button>
			</div>

			<!-- Full Score Display & Ignored Ingredients -->
			<ScoreDisplay
				{score}
				{totalIngredientCount}
				{totalWeight}
				{ignoredWeight}
				{isLoading}
				{error}
				showHeader={false}
				class="bg-base-200/70 rounded-xl p-4"
			/>

			<!-- Recipe Summary Details -->
			<div class="bg-base-200/70 space-y-2 rounded-xl p-4">
				<h4 class="text-base-content/80 text-sm font-semibold">
					{$_('recipe.summary', { default: 'Summary' })}
				</h4>
				<div class="flex justify-between text-sm">
					<span class="text-base-content/70"
						>{$_('recipe.ingredients_count', { default: 'ingredient(s) added' })}:</span
					>
					<span class="font-medium">{totalIngredientCount}</span>
				</div>
				{#if totalWeight > 0}
					<div class="flex justify-between text-sm">
						<span class="text-base-content/70"
							>{$_('recipe.total_weight', { default: 'Total weight' })}:</span
						>
						<span class="font-medium">{totalWeight} g</span>
					</div>
				{/if}
			</div>

			<!-- Recompute action inside expanded view -->
			<button
				type="button"
				class="btn btn-primary w-full gap-2"
				onclick={onRecompute}
				disabled={isLoading || !canCompute}
			>
				{#if isLoading}
					<span class="loading loading-spinner loading-sm"></span>
				{:else}
					<IconMdiRefresh class="h-4 w-4" />
				{/if}
				{$_('recipe.recompute', { default: 'Recompute' })}
			</button>
		</div>
	{/if}
</div>
