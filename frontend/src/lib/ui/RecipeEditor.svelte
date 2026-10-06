<!-- A named recipe table with isolated editing and Green-Score state. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { untrack } from 'svelte';
	import RecipeRowEditor from '$lib/ui/RecipeRowEditor.svelte';
	import ScoreDisplay from '$lib/ui/ScoreDisplay.svelte';
	import CountrySelect from '$lib/ui/CountrySelect.svelte';
	import { countNonEmptyIngredients } from '$lib/types/ingredientsList';
	import type { IngredientsList } from '$lib/types/ingredientsList';
	import { isIngredientNotEmpty } from '$lib/types/ingredient';
	import { canAutoScore, isPositiveAmount } from './ingredientEditor';
	import { computeGreenScore, type GreenScoreResponse } from '$lib/api/recipe';

	/** Each recipe owns its ingredients and an independent score request. */
	type Props = {
		id: string;
		title: string;
		ingredients: IngredientsList;
		portions?: number | null;
		finalWeightG?: number | null;
	};

	let {
		id,
		title,
		ingredients = $bindable(),
		portions = $bindable(null),
		finalWeightG = $bindable(null)
	}: Props = $props();

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
	const SCORE_INACTIVITY_DELAY = 750;

	/**
	 * Signature of the ingredients' relevant fields plus the selected country,
	 * used to detect changes and reset the inactivity timer. The country is
	 * included because it influences the distance modifier (and thus the score).
	 */
	let ingredientsSignature = $derived(
		JSON.stringify({
			ingredients: ingredients.filter(isIngredientNotEmpty),
			country,
			portions,
			finalWeightG
		})
	);
	let scoreReady = $derived(canAutoScore(ingredients, portions, finalWeightG));

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
		if (!scoreReady) {
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
			const result = await computeGreenScore(ingredients, {
				country: country ?? undefined,
				signal: requestController.signal
			});
			if (currentScoreRequestController === requestController) greenScore = result;
		} catch (e) {
			if (currentScoreRequestController !== requestController) return;
			if (e instanceof DOMException && e.name === 'AbortError') return;
			scoreError =
				e instanceof Error
					? e.message
					: $_('recipe.compute_error', {
							default: 'Could not compute the score. Please try again.'
						});
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
		const ready = scoreReady;
		// Immediately invalidate the old analysis while waiting for the next request.
		// untrack keeps request/loading state from becoming dependencies of this effect.
		// https://svelte.dev/docs/svelte/svelte#untrack
		untrack(() => {
			currentScoreRequestController?.abort();
			currentScoreRequestController = null;
			greenScore = null;
			scoreError = null;
			isScoreLoading = false;
		});
		const timer = ready ? setTimeout(fetchGreenScore, SCORE_INACTIVITY_DELAY) : undefined;
		return () => {
			clearTimeout(timer);
			currentScoreRequestController?.abort();
		};
	});
</script>

<section class="w-full min-w-0" aria-labelledby="recipe-heading-{id}">
	<div class="mb-4 flex flex-wrap items-center justify-between gap-2">
		<h2 id="recipe-heading-{id}" class="text-xl font-bold">{title}</h2>
		<p class="text-base-content/70 text-sm">
			{nonEmptyIngredientCount}
			{$_('recipe.ingredients_count', { default: 'ingredient(s) added' })}
		</p>
	</div>
	<div class="mb-4 flex flex-wrap items-end gap-4">
		<label class="fieldset">
			<span class="label">{$_('recipe.portions', { default: 'Number of portions' })}</span>
			<input
				class="input input-sm w-40"
				class:input-error={portions != null &&
					(!isPositiveAmount(portions) || !Number.isInteger(portions))}
				type="number"
				min="1"
				step="1"
				bind:value={portions}
			/>
		</label>
		<label class="fieldset">
			<span class="label"
				>{$_('recipe.final_weight', { default: 'Final dish weight (grams)' })}</span
			>
			<input
				class="input input-sm w-48"
				class:input-error={finalWeightG != null && !isPositiveAmount(finalWeightG)}
				type="number"
				min="0"
				step="any"
				bind:value={finalWeightG}
			/>
		</label>
		<CountrySelect bind:value={country} id="country-select-{id}" />
	</div>

	<RecipeRowEditor bind:ingredients {missingIngredientIds} {title} {id} />

	<div class="mt-6 grid items-start gap-6 lg:grid-cols-2">
		<ScoreDisplay
			score={greenScore}
			totalIngredientCount={nonEmptyIngredientCount}
			{totalWeight}
			{ignoredWeight}
			isLoading={isScoreLoading}
			error={scoreError}
		/>
		<div class="bg-base-200 rounded-lg p-4">
			<h3 class="text-lg font-semibold">{$_('recipe.nutri_score', { default: 'Nutri-Score' })}</h3>
			<p
				class="text-base-content/70 mt-2"
				aria-label={$_('recipe.score_unavailable', { default: 'No score available' })}
			>
				—
			</p>
		</div>
	</div>
</section>
