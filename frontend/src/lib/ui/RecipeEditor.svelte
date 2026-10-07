<!-- A named recipe table with isolated editing and Green-Score state. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import { untrack } from 'svelte';
	import RecipeRowEditor from '$lib/ui/RecipeRowEditor.svelte';
	import RecipeNameEditor from '$lib/ui/RecipeNameEditor.svelte';
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
	import { canAutoScore, isPositiveAmount, isNonNegativeAmount } from './ingredientEditor';
	import {
		computeGreenScore,
		ingredientToGreenScoreInput,
		getMakeItBetterSuggestions,
		type MakeItBetterSuggestion,
		type GreenScoreResponse
	} from '$lib/api/recipe';
	import MakeItBetterDialog from '$lib/ui/MakeItBetterDialog.svelte';
	import { replaceSelectedRecipeProducts } from '$lib/ui/makeItBetter';

	/** Each recipe owns its ingredients and an independent score request. */
	type Props = {
		id: string;
		name: string;
		fallbackTitle: string;
		ingredients: IngredientsList;
		portions?: number | null;
	};

	let {
		id,
		name = $bindable(),
		fallbackTitle,
		ingredients = $bindable(),
		portions = $bindable(1)
	}: Props = $props();
	let title = $derived(name || fallbackTitle);

	let nutritionCategory = $state<NutritionCategory>('en:meals');
	let nutrition = $state<NutritionAnalysis | null>(null);
	let nutritionLoading = $state(false);
	let nutritionFailed = $state(false);
	let nutritionFeedbackRows = $state<Record<string, string>>({});
	let nutritionPayload = $derived(nutritionInputs(ingredients, portions, nutritionCategory));
	let nutritionSignature = $derived(JSON.stringify(nutritionPayload));
	let nutritionReady = $derived(
		nutritionPayload.ingredients.some((row) => isPositiveAmount(row.quantity_g)) &&
			Number.isInteger(portions) &&
			isPositiveAmount(portions) &&
			nutritionPayload.ingredients.every(
				(row) =>
					(row.quantity_g == null || isNonNegativeAmount(row.quantity_g)) &&
					(row.prepared_weight_g == null || isPositiveAmount(row.prepared_weight_g))
			)
	);

	// Nutrition has its own validity and request lifecycle; environmental errors do not block it.
	$effect(() => {
		void nutritionSignature;
		const payload = untrack(() => nutritionPayload);
		const ready = nutritionReady;
		const controller = new AbortController();
		let cancelled = false;
		if (!ready) nutrition = null;
		nutritionFailed = false;
		nutritionLoading = ready;
		const timer = ready
			? setTimeout(() => {
					void analyzeNutrition(payload, controller.signal)
						.then((result) => {
							if (!cancelled) {
								nutrition = result;
								nutritionFeedbackRows = Object.fromEntries(
									payload.ingredients.map((row) => [row.id, JSON.stringify(row)])
								);
							}
						})
						.catch(() => {
							if (!cancelled) {
								nutrition = null;
								nutritionFailed = true;
							}
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
	let greenFeedbackRows = $state<Record<string, string>>({});
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

	let excludedGreenIngredients = $derived(
		ingredients.filter((row) => greenScore?.missingIngredientIds.includes(row.id))
	);
	let totalGreenWeight = $derived(
		ingredients.filter(isIngredientNotEmpty).reduce((sum, row) => sum + (row.weight ?? 0), 0)
	);
	let excludedGreenPercent = $derived(
		totalGreenWeight > 0
			? Math.round(
					(excludedGreenIngredients.reduce((sum, row) => sum + (row.weight ?? 0), 0) /
						totalGreenWeight) *
						100
				)
			: 0
	);

	// Keep feedback for unchanged rows during recomputation; edited rows cannot reuse stale diagnostics.
	let missingIngredientIds = $derived(
		(greenScore?.missingIngredientIds ?? []).filter((id) => {
			const row = ingredients.find((row) => row.id === id);
			return row && greenFeedbackRows[id] === JSON.stringify(ingredientToGreenScoreInput(row));
		})
	);
	let unchangedNutritionIds = $derived(
		new Set(
			nutritionPayload.ingredients
				.filter((row) => nutritionFeedbackRows[row.id] === JSON.stringify(row))
				.map((row) => row.id)
		)
	);
	let nutritionDiagnostics = $derived(
		(nutrition?.diagnostics ?? []).filter(
			(issue) => issue.ingredient_id && unchangedNutritionIds.has(issue.ingredient_id)
		)
	);
	let nutritionFallbackIds = $derived(
		(nutrition?.assumptions ?? [])
			.filter(
				(issue) =>
					issue.code === 'off_ciqual_fallback' &&
					issue.ingredient_id &&
					unchangedNutritionIds.has(issue.ingredient_id)
			)
			.map((issue) => issue.ingredient_id!)
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
			const feedbackRows = Object.fromEntries(
				ingredients
					.filter(isIngredientNotEmpty)
					.map((row) => [row.id, JSON.stringify(ingredientToGreenScoreInput(row))])
			);
			const result = await computeGreenScore(ingredients, {
				country: country ?? undefined,
				signal: requestController.signal
			});
			if (currentScoreRequestController === requestController) {
				greenScore = result;
				greenFeedbackRows = feedbackRows;
			}
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
		// Retain unchanged-row feedback while waiting for the next request.
		// untrack keeps request/loading state from becoming dependencies of this effect.
		// https://svelte.dev/docs/svelte/svelte#untrack
		untrack(() => {
			currentScoreRequestController?.abort();
			currentScoreRequestController = null;
			if (!ready) greenScore = null;
			scoreError = null;
			isScoreLoading = ready;
		});
		const timer = ready ? setTimeout(fetchGreenScore, SCORE_INACTIVITY_DELAY) : undefined;
		return () => {
			clearTimeout(timer);
			currentScoreRequestController?.abort();
		};
	});

	// --- Make It Better state ----------------------------------------------
	let isCheckingImprovements = $state(false);
	let improvementError = $state<string | null>(null);
	let improvementSuggestions = $state<MakeItBetterSuggestion[]>([]);
	let isImprovementDialogOpen = $state(false);

	async function openMakeItBetter() {
		isCheckingImprovements = true;
		improvementError = null;
		try {
			const names = ingredients.map((i) => {
				if (i.codifiedIngredient?.id) {
					// Use language-agnostic ID (e.g. 'en:chocolate-yogurt' -> 'chocolate-yogurt')
					// which converts to 'chocolate yogurt' during catalog matching.
					return i.codifiedIngredient.id.split(':').pop()?.replace(/-/g, ' ');
				}
				return i.name;
			}).filter(Boolean) as string[];
			const result = await getMakeItBetterSuggestions(names);
			improvementSuggestions = result.suggestions;
			if (result.suggestions.length === 0) {
				improvementError = 'No catalogued improvements are available for this recipe.';
				return;
			}
			isImprovementDialogOpen = true;
		} catch (e) {
			improvementError = e instanceof Error ? e.message : 'Could not check recipe improvements.';
		} finally {
			isCheckingImprovements = false;
		}
	}

	function applySelectedImprovements(suggestions: MakeItBetterSuggestion[]) {
		replaceSelectedRecipeProducts(ingredients, suggestions);
	}
</script>

<section class="w-full min-w-0" aria-labelledby="recipe-heading-{id}">
	<div class="mb-4 flex items-center gap-2">
		<h2 id="recipe-heading-{id}" class="min-w-0 text-xl font-bold wrap-anywhere">{title}</h2>
		<RecipeNameEditor {id} bind:name {title} />
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

	<RecipeRowEditor
		bind:ingredients
		{missingIngredientIds}
		{nutritionDiagnostics}
		{nutritionFallbackIds}
		{title}
		{id}
	/>

	<div class="mt-6 flex flex-wrap items-stretch gap-4">
		<ScoreDisplay
			score={greenScore}
			isLoading={isScoreLoading}
			error={scoreError}
			excludedWeightPercent={excludedGreenPercent}
		/>
		<NutriScoreDisplay analysis={nutrition} loading={nutritionLoading} failed={nutritionFailed} />
		<div class="bg-base-200 w-96 max-w-full rounded-lg p-4" aria-live="polite" aria-busy={isCheckingImprovements}>
			<h3 class="text-lg font-semibold">{$_('make_it_better.title', { default: 'Make It Better' })}</h3>
			<p class="text-base-content/70 mt-2 text-sm">
				{improvementError || $_('make_it_better.box_description', { default: 'Check for catalogued score improvements for your recipe ingredients.' })}
			</p>
			<button
				type="button"
				class="btn btn-sm mt-4 w-full border-0 bg-gradient-to-r from-yellow-400 to-amber-500 text-white shadow-[0_0_15px_rgba(251,191,36,0.6)] transition-all hover:scale-[1.02] hover:shadow-[0_0_25px_rgba(245,158,11,0.8)] font-semibold"
				disabled={isCheckingImprovements || ingredients.length === 0}
				onclick={openMakeItBetter}
			>
				{#if isCheckingImprovements}
					<span class="loading loading-spinner loading-xs"></span>
				{:else}
					<span aria-hidden="true">✨</span>
				{/if}
				{$_('make_it_better.button', { default: 'Check for improvements' })}
			</button>
		</div>
	</div>
</section>

<MakeItBetterDialog
	bind:open={isImprovementDialogOpen}
	suggestions={improvementSuggestions}
	onapply={applySelectedImprovements}
/>
