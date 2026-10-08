<!-- Preview and confirm resolved substitutions for one recipe, using the export table design. -->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import { _, getLocale } from '$lib/i18n';
	import type { Ingredient } from '$lib/types/ingredient';
	import { recipeExportInputs } from '$lib/api/recipeExport';
	import {
		checkImprovements,
		optimizeRecipe,
		ImprovementError,
		type ImprovementRequest,
		type ImprovementResponse
	} from '$lib/api/improvements';
	import {
		applyOptimizedRecipe,
		formatImprovementPercent,
		hasScoreRegression
	} from './makeItBetter';

	let {
		id,
		name,
		ingredients = $bindable(),
		portions,
		country,
		disabled = false,
		onoptimized
	}: {
		id: string;
		name: string;
		ingredients: Ingredient[];
		portions?: number | null;
		country?: string | null;
		disabled?: boolean;
		onoptimized?: () => void;
	} = $props();
	let dialog: HTMLDialogElement;
	const dialogId = $props.id();
	let loading = $state(false);
	let optimizing = $state(false);
	let error = $state<ImprovementError['reason'] | null>(null);
	const errorDefaults = {
		failed: 'Could not verify these improvements. Try again; your recipe has not changed.',
		selection_unavailable:
			'A selected alternative is no longer available. Close this dialog and check again; your recipe has not changed.',
		no_combined_gain:
			'These changes do not improve the recipe when combined. Try selecting fewer changes; your recipe has not changed.'
	};
	let result = $state<ImprovementResponse | null>(null);
	let selectedIds = $state<string[]>([]);
	let snapshot: ImprovementRequest | undefined;
	let snapshotSignature = $state('');
	let controller: AbortController | undefined;
	let recipe = $derived(
		recipeExportInputs([{ id, name, ingredients, portions, country }]).recipes[0]
	);
	let signature = $derived(JSON.stringify(recipe));
	let stale = $derived(snapshotSignature !== '' && snapshotSignature !== signature);
	let suggestions = $derived(result?.suggestions ?? []);
	let allSelected = $derived(
		suggestions.length > 0 && suggestions.every((row) => selectedIds.includes(row.id))
	);
	let someSelected = $derived(suggestions.some((row) => selectedIds.includes(row.id)));
	let hasRows = $derived(recipe.ingredients.some((row) => (row.quantity_g ?? 0) > 0));

	onDestroy(() => controller?.abort());

	/** Open immediately, then load suggestions from an immutable recipe snapshot. */
	async function openDialog() {
		if (disabled) return;
		controller?.abort();
		const requestController = new AbortController();
		controller = requestController;
		snapshot = structuredClone($state.snapshot({ recipe, lang: getLocale().slice(0, 2) }));
		snapshotSignature = signature;
		result = null;
		selectedIds = [];
		error = null;
		loading = true;
		dialog.showModal();
		try {
			const response = await checkImprovements(snapshot, requestController.signal);
			if (requestController.signal.aborted) return;
			result = response;
			selectedIds = (response.suggestions ?? [])
				.filter((row) => !hasScoreRegression(row))
				.map((row) => row.id);
		} catch {
			if (!requestController.signal.aborted) error = 'failed';
		} finally {
			if (controller === requestController) loading = false;
		}
	}

	/** Cancel network work as well as the dialog; cancelled responses never mutate a recipe. */
	function closeDialog() {
		controller?.abort();
		// Do not compare a closing modal's old preview with the newly applied recipe.
		snapshotSignature = '';
		dialog.close();
	}

	/** Validate the combined effect and apply replacements only while the recipe is unchanged. */
	async function optimize() {
		if (!snapshot || stale || optimizing || !selectedIds.length) return;
		const requestController = new AbortController();
		controller = requestController;
		const selection = [...selectedIds];
		optimizing = true;
		error = null;
		try {
			const response = await optimizeRecipe(snapshot, selection, requestController.signal);
			if (requestController.signal.aborted || signature !== snapshotSignature) return;
			const optimizedIngredients = applyOptimizedRecipe(
				ingredients,
				response,
				suggestions.filter((row) => selection.includes(row.id))
			);
			closeDialog();
			ingredients = optimizedIngredients;
			onoptimized?.();
		} catch (failure) {
			if (!requestController.signal.aborted)
				error = failure instanceof ImprovementError ? failure.reason : 'failed';
		} finally {
			optimizing = false;
		}
	}
</script>

<button
	type="button"
	class="btn btn-success improvement-button"
	aria-haspopup="dialog"
	disabled={disabled || !hasRows}
	onclick={openDialog}
>
	{$_('improvements.title', { default: 'Make it better' })}
</button>

<dialog
	bind:this={dialog}
	class="modal"
	aria-labelledby="{dialogId}-title"
	onclose={() => {
		controller?.abort();
		snapshotSignature = '';
	}}
>
	<div class="modal-box w-11/12 max-w-5xl">
		<h2 id="{dialogId}-title" class="mb-4 text-lg font-bold">
			{$_('improvements.title', { default: 'Make it better' })}
		</h2>
		<p class="text-base-content/70 mb-4 text-sm">
			{$_('improvements.description', {
				default: 'Select changes to improve your recipe.'
			})}
		</p>
		<div class="border-base-300 max-h-80 overflow-auto border" aria-busy={loading || optimizing}>
			<table
				class="table-sm [&_td]:border-base-300 [&_th]:border-base-300 table min-w-[44rem] [&_td:not(:last-child)]:border-r [&_th:not(:last-child)]:border-r"
			>
				<thead class="bg-base-200">
					<tr>
						<th scope="col" class="border-base-300 w-12 border-r">
							<input
								type="checkbox"
								class="checkbox checkbox-sm"
								checked={allSelected}
								indeterminate={someSelected && !allSelected}
								disabled={loading || optimizing || stale || !suggestions.length}
								aria-label={$_('improvements.select_all', { default: 'Select all improvements' })}
								onchange={(event) =>
									(selectedIds = event.currentTarget.checked
										? suggestions.map((row) => row.id)
										: [])}
							/>
						</th>
						<th scope="col">{$_('improvements.category', { default: 'Category' })}</th>
						<th scope="col">{$_('improvements.before', { default: 'Before' })}</th>
						<th scope="col">{$_('improvements.after', { default: 'After' })}</th>
						<th scope="col" class="whitespace-nowrap"
							>{$_('recipe.green_score', { default: 'Green Score' })}</th
						>
						<th scope="col" class="whitespace-nowrap"
							>{$_('recipe.nutri_score', { default: 'Nutri-Score' })}</th
						>
					</tr>
				</thead>
				<tbody>
					{#if loading}
						<tr
							><td colspan="6" class="py-8 text-center"
								><span class="loading loading-spinner loading-sm mr-2" aria-hidden="true"
								></span>{$_('improvements.loading', { default: 'Checking improvements…' })}</td
							></tr
						>
					{:else if !suggestions.length}
						<tr
							><td colspan="6" class="text-base-content/70 py-8 text-center"
								>{#if error}
									{$_(`improvements.${error}`, { default: errorDefaults[error] })}
								{:else if result?.reason === 'no_candidates'}
									{$_('improvements.no_candidates', {
										default: 'No substitutions are available for these ingredient references yet.'
									})}
								{:else if result?.reason === 'references_missing'}
									{$_('improvements.references_missing', {
										default:
											'Choose CIQUAL foods or Open Food Facts products for the ingredients, then try again.'
									})}
								{:else if result?.reason === 'scores_unavailable'}
									{$_('improvements.scores_unavailable', {
										default:
											'Score or ingredient data is unavailable. Improvements could not be verified.'
									})}
								{:else}
									{$_('improvements.empty', {
										default:
											'The checked alternatives did not improve either available recipe score.'
									})}
								{/if}</td
							></tr
						>
					{:else}
						{#each suggestions as suggestion (suggestion.id)}
							<tr>
								<td class="border-base-300 border-r"
									><input
										type="checkbox"
										class="checkbox checkbox-sm"
										value={suggestion.id}
										bind:group={selectedIds}
										disabled={optimizing || stale}
										aria-label={$_('improvements.select_change', {
											default: 'Replace {before} with {after}',
											values: {
												before: suggestion.before.name,
												after: suggestion.product_name ?? suggestion.after.name
											}
										})}
									/></td
								>
								<td
									>{suggestion.category === 'open_food_facts'
										? $_('improvements.off', { default: 'Open Food Facts' })
										: $_('improvements.ingredient', { default: 'Ingredient name' })}</td
								>
								<td class="wrap-anywhere"
									>{suggestion.category === 'open_food_facts'
										? ingredients.find((row) => row.id === suggestion.ingredient_id)?.productName ||
											suggestion.before.name
										: suggestion.before.name}</td
								>
								<td class="wrap-anywhere">{suggestion.product_name ?? suggestion.after.name}</td>
								{#each [suggestion.green_score, suggestion.nutri_score] as change, index (index)}
									<td class="font-medium whitespace-nowrap tabular-nums">
										<span
											class:text-success-strong={change?.percent != null && change.percent > 0}
											class:text-error={change?.percent != null && change.percent < 0}
											>{formatImprovementPercent(change?.percent)}</span
										>
									</td>
								{/each}
							</tr>
						{/each}
					{/if}
				</tbody>
			</table>
		</div>
		{#if result?.limited}<p class="text-base-content/70 mt-3 text-sm">
				{$_('improvements.limited', {
					default: 'This search checked up to 60 alternatives across the recipe.'
				})}
			</p>{/if}
		{#if stale}<p class="text-warning mt-3 text-sm" role="alert">
				{$_('improvements.stale', {
					default: 'The recipe changed. Close this dialog and check for improvements again.'
				})}
			</p>{/if}
		{#if error && suggestions.length}<p class="text-error mt-3 text-sm" role="alert">
				{$_(`improvements.${error}`, { default: errorDefaults[error] })}
			</p>{/if}
		<div class="modal-action">
			<button type="button" class="btn btn-outline" onclick={closeDialog}
				>{$_('recipe.cancel', { default: 'Cancel' })}</button
			>
			<button
				type="button"
				class="btn btn-success improvement-button"
				disabled={loading || optimizing || stale || !selectedIds.length}
				onclick={optimize}
			>
				{#if optimizing}<span class="loading loading-spinner loading-sm" aria-hidden="true"
					></span>{/if}
				{$_('improvements.optimize', { default: 'Optimize' })}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('recipe.cancel', { default: 'Cancel' })}></button>
	</form>
</dialog>

<style>
	/* Keep DaisyUI hover and disabled behavior while using the stronger semantic green. */
	.improvement-button:not(:disabled) {
		--btn-color: var(--color-success-strong);
		--btn-fg: var(--color-neutral-content);
	}
</style>
