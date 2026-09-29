<!--
  Recipe Editor Page

  Main page for creating and editing recipes.
  Holds the shared state (ingredients + green-score) and orchestrates the
  computation. The row edition logic lives in `RecipeRowEditor` and the score
  display (logo + limitations) lives in `ScoreDisplay`.

  Features:
  - Dynamic ingredient lines (adds new line when typing in the last empty line)
  - Computes the green-score automatically after a delay of inactivity or on demand
-->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { page } from '$app/state';
	import RecipeRowEditor from '$lib/ui/RecipeRowEditor.svelte';
	import ScoreDisplay from '$lib/ui/ScoreDisplay.svelte';
	import ScoreSheet from '$lib/ui/ScoreSheet.svelte';
	import CountrySelect from '$lib/ui/CountrySelect.svelte';
	import IconMdiRefresh from '@iconify-svelte/mdi/refresh';
	import { createEmptyIngredient } from '$lib/types/ingredient';
	import { addEmptyIngredientIfNeeded, countNonEmptyIngredients } from '$lib/types/ingredientsList';
	import type { IngredientsList } from '$lib/types/ingredientsList';
	import {
		isIngredientNotEmpty,
		ingredientSignature,
		type Ingredient
	} from '$lib/types/ingredient';
	import { computeGreenScore, type GreenScoreResponse } from '$lib/api/recipe';

	/**
	 * Initial ingredients coming from the `/add` page (passed via `goto` state).
	 * Falls back to a single empty line when no state is provided.
	 */
	function getInitialIngredients(): IngredientsList {
		const state = (page.state ?? {}) as { ingredients?: Ingredient[] };
		const stateIngredients = state.ingredients;
		if (stateIngredients && stateIngredients.length > 0) {
			// we need an empty line at the end for the user to add new ingredients
			return addEmptyIngredientIfNeeded(stateIngredients);
		}
		return [createEmptyIngredient()];
	}

	// --- Shared state -------------------------------------------------------
	// Recipe state - starts with one empty ingredient line, or with parsed ingredients from /add
	let ingredients = $state<IngredientsList>(getInitialIngredients());

	// Country the recipe is being cooked in (ISO 3166-1 alpha-2 code, or null).
	// Used to compute the distance modifier in the green-score.
	let country = $state<string | null>(null);

	// --- Green-score state -------------------------------------------------
	// The latest computed score response (null until computed or while loading).
	let greenScore = $state<GreenScoreResponse | null>(null);
	let isScoreLoading = $state(false);
	let scoreError = $state<string | null>(null);
	let currentScoreRequestController = $state<AbortController | null>(null);

	/** Inactivity delay (in ms) before the green-score is recomputed automatically. */
	const SCORE_INACTIVITY_DELAY = 3000;

	/**
	 * Signature of the ingredients' relevant fields plus the selected country,
	 * used to detect changes and reset the inactivity timer. The country is
	 * included because it influences the distance modifier (and thus the score).
	 */
	let ingredientsSignature = $derived(
		`${ingredients.map(ingredientSignature).join('|')}@${country ?? ''}`
	);

	/**
	 * Total weight (in grams) of the non-empty ingredients sent to the backend.
	 */
	let totalWeight = $derived(
		ingredients.filter(isIngredientNotEmpty).reduce((sum, i) => sum + (i.weight ?? 0), 0)
	);

	/**
	 * Total weight (in grams) of the ingredients that were ignored by the
	 * backend (i.e. whose id appears in the missing list of the last response).
	 */
	let ignoredWeight = $derived.by(() => {
		if (!greenScore) return 0;
		const missing = new Set(greenScore.missingIngredientIds);
		return ingredients
			.filter((i) => missing.has(i.id))
			.reduce((sum, i) => sum + (i.weight ?? 0), 0);
	});

	/** Number of non-empty ingredients currently in the editor. */
	let nonEmptyIngredientCount = $derived(countNonEmptyIngredients(ingredients));

	/**
	 * Ingredient ids flagged as missing in the last computed score.
	 *
	 * Cleared while a recomputation is in flight (see `isScoreLoading`) so the
	 * highlight always reflects the currently displayed score, never a stale one.
	 */
	let missingIngredientIds = $derived(
		isScoreLoading || !greenScore ? [] : greenScore.missingIngredientIds
	);

	/** Whether there is at least one non-empty ingredient to compute a score for. */
	let hasIngredients = $derived(ingredients.some(isIngredientNotEmpty));

	/**
	 * Compute the green-score for the current ingredients.
	 *
	 * Guards against concurrent computations: only the result of the most recent
	 * call is applied, earlier (stale) results are discarded. Captures errors
	 * from the latest call only.
	 */
	async function fetchGreenScore() {
		currentScoreRequestController?.abort(); // abort previous request
		// Only compute when there is at least one non-empty ingredient
		if (!hasIngredients) {
			currentScoreRequestController = null;
			isScoreLoading = false;
			greenScore = null;
			return;
		}
		const requestController = new AbortController();
		currentScoreRequestController = requestController;
		isScoreLoading = true;
		scoreError = null;
		try {
			greenScore = await computeGreenScore(ingredients, {
				country: country ?? undefined,
				signal: requestController.signal
			});
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') return;
			scoreError = e instanceof Error ? e.message : 'An error occurred';
			greenScore = null;
		} finally {
			if (currentScoreRequestController === requestController) {
				currentScoreRequestController = null;
				isScoreLoading = false;
			}
		}
	}

	// Reset the inactivity timer whenever the ingredients change.
	// After the delay without edits, the score is recomputed automatically.
	$effect(() => {
		// Read the signature so the effect re-runs on any ingredient change
		void ingredientsSignature;
		const timer = setTimeout(fetchGreenScore, SCORE_INACTIVITY_DELAY);
		return () => clearTimeout(timer);
	});
</script>

<svelte:head>
	<title>{$_('recipe.title', { default: 'Recipe Editor' })}</title>
</svelte:head>

<div class="mx-auto max-w-7xl px-4 py-8 pb-32 lg:pb-8">
	<!-- Responsive Grid: On desktop (lg+), 2 columns with sticky sidebar; on mobile, single column with sticky bottom sheet -->
	<div class="lg:grid lg:grid-cols-12 lg:items-start lg:gap-8">
		<!-- Left Column: Recipe Editor & Actions -->
		<div class="space-y-6 lg:col-span-7 xl:col-span-8">
			<!-- Header -->
			<div>
				<h1 class="text-3xl font-bold">{$_('recipe.title', { default: 'Recipe Editor' })}</h1>
				<p class="text-base-content/70 mt-2">
					{$_('recipe.description', { default: 'Add ingredients to your recipe' })}
				</p>
			</div>

			<!-- Ingredients List (row edition logic delegated to RecipeRowEditor) -->
			<RecipeRowEditor bind:ingredients {missingIngredientIds} />

			<!-- Actions -->
			<div class="flex flex-wrap items-end gap-4">
				<CountrySelect bind:value={country} />
				<button
					class="btn btn-primary"
					onclick={fetchGreenScore}
					disabled={isScoreLoading || !hasIngredients}
				>
					{#if isScoreLoading}
						<span class="loading loading-spinner loading-sm"></span>
					{/if}
					{$_('recipe.compute_score', { default: 'Compute score' })}
				</button>
			</div>
		</div>

		<!-- Right Column: Desktop Sidebar (visible on lg+ screens, sticky) -->
		<aside class="sticky top-6 hidden space-y-6 lg:col-span-5 lg:block xl:col-span-4">
			<div class="bg-base-200 border-base-300 space-y-6 rounded-2xl border p-6 shadow-sm">
				<!-- Header with title and Recompute button -->
				<div class="border-base-content/10 flex items-center justify-between gap-3 border-b pb-4">
					<h2 class="text-xl font-bold tracking-tight">
						{$_('recipe.green_score', { default: 'Green Score' })}
					</h2>
					<button
						type="button"
						class="btn btn-primary btn-sm gap-1.5"
						onclick={fetchGreenScore}
						disabled={isScoreLoading || !hasIngredients}
					>
						{#if isScoreLoading}
							<span class="loading loading-spinner loading-xs"></span>
						{:else}
							<IconMdiRefresh class="h-4 w-4" />
						{/if}
						{$_('recipe.recompute', { default: 'Recompute' })}
					</button>
				</div>

				<!-- Green Score visual & details -->
				<ScoreDisplay
					score={greenScore}
					totalIngredientCount={nonEmptyIngredientCount}
					{totalWeight}
					{ignoredWeight}
					isLoading={isScoreLoading}
					error={scoreError}
					showHeader={false}
					class="space-y-4"
				/>

				<!-- Summary Stats Card -->
				<div class="bg-base-100/80 border-base-content/5 space-y-2 rounded-xl border p-4">
					<h3 class="text-base-content/80 text-sm font-semibold">
						{$_('recipe.summary', { default: 'Summary' })}
					</h3>
					<div class="flex justify-between text-sm">
						<span class="text-base-content/70">
							{$_('recipe.ingredients_count', { default: 'ingredient(s) added' })}:
						</span>
						<span class="font-medium">{nonEmptyIngredientCount}</span>
					</div>
					{#if totalWeight > 0}
						<div class="flex justify-between text-sm">
							<span class="text-base-content/70">
								{$_('recipe.total_weight', { default: 'Total weight' })}:
							</span>
							<span class="font-medium">{totalWeight} g</span>
						</div>
					{/if}
				</div>
			</div>
		</aside>
	</div>

	<!-- Mobile: Sticky Bottom Sheet (hidden on lg+ screens) -->
	<div class="lg:hidden">
		<ScoreSheet
			score={greenScore}
			isLoading={isScoreLoading}
			error={scoreError}
			totalIngredientCount={nonEmptyIngredientCount}
			{totalWeight}
			{ignoredWeight}
			canCompute={hasIngredients}
			onRecompute={fetchGreenScore}
		/>
	</div>
</div>
