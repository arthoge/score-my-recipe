<!-- A named recipe table with isolated editing and Green-Score state. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { untrack } from 'svelte';
	import RecipeRowEditor from '$lib/ui/RecipeRowEditor.svelte';
	import ScoreDisplay from '$lib/ui/ScoreDisplay.svelte';
	import CountrySelect from '$lib/ui/CountrySelect.svelte';
	import HelperTooltip from '$lib/ui/HelperTooltip.svelte';
	import { getFinalPreparedWeight } from './preparedWeight';
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
	};

	let { id, title, ingredients = $bindable(), portions = $bindable(1) }: Props = $props();

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
			portions
		})
	);

	let scoreReady = $derived(canAutoScore(ingredients, portions));
	let finalPreparedWeight = $derived(getFinalPreparedWeight(ingredients));

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
	</div>
	<div class="mb-4 flex flex-wrap items-end gap-4">
		<CountrySelect bind:value={country} id="country-select-{id}" />
		<label class="fieldset w-max">
			<span class="label whitespace-nowrap"
				>{$_('recipe.portions', { default: 'Number of portions' })}</span
			>
			<input
				class="input input-sm w-28 min-w-full"
				class:input-error={portions != null &&
					(!isPositiveAmount(portions) || !Number.isInteger(portions))}
				type="number"
				min="1"
				step="1"
				bind:value={portions}
			/>
		</label>
		<label class="fieldset w-max" for="prepared-weight-total-{id}">
			<span class="label flex items-center gap-1.5 whitespace-nowrap">
				<span
					>{$_('recipe.final_prepared_weight_grams', {
						default: 'Prepared weight'
					})}</span
				>
				<HelperTooltip
					tip={$_('recipe.final_prepared_weight_help', {
						default:
							'Total prepared weight of all ingredients. Available once every ingredient has a prepared weight.'
					})}
					ariaLabel={$_('helpers.more_info', { default: 'More information' })}
				/>
			</span>
			<output
				id="prepared-weight-total-{id}"
				class="border-base-300 bg-base-200 text-base-content/80 rounded-field flex h-8 w-32 min-w-full cursor-default items-center border px-3 text-sm tabular-nums"
				aria-live="polite"
			>
				<span>{finalPreparedWeight ?? 0}</span>
				<span class="text-base-content/50 ml-1 text-xs"
					>{$_('recipe.grams', { default: 'grams' })}</span
				>
			</output>
		</label>
	</div>

	<RecipeRowEditor bind:ingredients {missingIngredientIds} {title} {id} />

	<div class="mt-6 flex flex-wrap items-stretch gap-4">
		<ScoreDisplay
			score={greenScore}
			{totalWeight}
			{ignoredWeight}
			isLoading={isScoreLoading}
			error={scoreError}
		/>
		<div class="bg-base-200 w-96 max-w-full rounded-lg p-4">
			<h3 class="text-lg font-semibold">{$_('recipe.nutri_score', { default: 'Nutri-Score' })}</h3>
			<p class="text-base-content/70 mt-2 text-sm">
				{$_('recipe.no_score', {
					default: 'Scores update automatically once the required cells are complete.'
				})}
			</p>
		</div>
	</div>
</section>
