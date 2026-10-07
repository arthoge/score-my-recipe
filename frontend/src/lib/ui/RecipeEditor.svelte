<!-- A named recipe table with isolated editing and Green-Score state. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { untrack } from 'svelte';
	import RecipeRowEditor from '$lib/ui/RecipeRowEditor.svelte';
	import ScoreDisplay from '$lib/ui/ScoreDisplay.svelte';
	import NutriScoreDisplay from '$lib/ui/NutriScoreDisplay.svelte';
	import {
		analyzeNutrition,
		nutritionInputs,
		type NutritionAnalysis,
		type NutritionCategory
	} from '$lib/api/nutritionAnalysis';
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

	let nutritionCategory = $state<NutritionCategory>('en:meals');
	let nutrition = $state<NutritionAnalysis | null>(null);
	let nutritionLoading = $state(false);
	let nutritionPayload = $derived(nutritionInputs(ingredients, portions, nutritionCategory));
	let nutritionSignature = $derived(JSON.stringify(nutritionPayload));
	let nutritionReady = $derived(
		nutritionPayload.ingredients.length > 0 &&
			Number.isInteger(portions) &&
			isPositiveAmount(portions) &&
			nutritionPayload.ingredients.every(
				(row) =>
					isPositiveAmount(row.quantity_g) &&
					(row.prepared_weight_g == null || isPositiveAmount(row.prepared_weight_g))
			)
	);

	// Nutrition has its own validity and request lifecycle; environmental errors do not block it.
	$effect(() => {
		void nutritionSignature;
		const payload = nutritionPayload;
		const ready = nutritionReady;
		const controller = new AbortController();
		let cancelled = false;
		nutrition = null;
		nutritionLoading = ready;
		const timer = ready
			? setTimeout(() => {
					void analyzeNutrition(payload, controller.signal)
						.then((result) => {
							if (!cancelled) nutrition = result;
						})
						.catch(() => {
							if (!cancelled) nutrition = null;
						})
						.finally(() => {
							if (!cancelled) nutritionLoading = false;
						});
				}, 750)
			: undefined;
		return () => {
			cancelled = true;
			clearTimeout(timer);
			controller.abort();
		};
	});

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
			isScoreLoading = ready;
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
		<label class="fieldset w-max" for="recipe-type-{id}">
			<span class="label whitespace-nowrap"
				>{$_('nutrition.recipe_type', { default: 'Recipe type' })}</span
			>
			<select
				id="recipe-type-{id}"
				bind:value={nutritionCategory}
				class="select select-sm w-32 min-w-full"
			>
				<option value="en:meals">{$_('nutrition.category.dish', { default: 'Dish' })}</option>
				<option value="en:cheeses">{$_('nutrition.category.cheese', { default: 'Cheese' })}</option>
				<option value="en:fats"
					>{$_('nutrition.category.fats', { default: 'Fats and oils' })}</option
				>
				<option value="en:beverages"
					>{$_('nutrition.category.beverage', { default: 'Beverage' })}</option
				>
			</select>
		</label>

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
						default: 'Total prepared weight of all ingredients.'
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
		<ScoreDisplay score={greenScore} isLoading={isScoreLoading} error={scoreError} />
		<NutriScoreDisplay analysis={nutrition} loading={nutritionLoading} />
	</div>
</section>
