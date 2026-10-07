<script lang="ts">
	import { _ } from '$lib/i18n';

	export type ImprovementSuggestion = {
		ingredient: string;
		original: { id: string; name: string; nutriScore: string; greenScore: string };
		suggested: { id: string; name: string; nutriScore: string; greenScore: string };
		improvements: { label: string; fromScore: string; toScore: string }[];
	};

	type Props = {
		suggestions: ImprovementSuggestion[];
		open?: boolean;
		ondismiss?: () => void;
		onswitch?: () => void;
		onapply?: (suggestions: ImprovementSuggestion[]) => void;
	};

	let { suggestions, open = $bindable(false), ondismiss, onswitch, onapply }: Props = $props();
	let dialog = $state<HTMLDialogElement>();
	let selected = $state<boolean[]>([]);
	let isSelectionStep = $state(false);

	$effect(() => {
		if (open && !dialog?.open) {
			isSelectionStep = false;
			selected = suggestions.map(() => false);
			dialog?.showModal();
		} else if (!open && dialog?.open) {
			dialog.close();
		}
	});

	/** Close the whole improvement flow without changing the recipe. */
	function dismiss() {
		open = false;
		isSelectionStep = false;
		ondismiss?.();
	}

	/** Show selection controls only after the user explicitly chooses Switch. */
	function showSelection() {
		isSelectionStep = true;
		onswitch?.();
	}

	/** Apply only the recommendations whose checkbox is checked. */
	function applySelected() {
		const selectedSuggestions = suggestions.filter((_, index) => selected[index]);
		if (selectedSuggestions.length === 0) return;
		open = false;
		isSelectionStep = false;
		onapply?.(selectedSuggestions);
	}
</script>

<dialog bind:this={dialog} class="modal" aria-labelledby="make-it-better-title" onclose={dismiss}>
	<div class="modal-box max-w-3xl">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h2 id="make-it-better-title" class="text-xl font-semibold sm:text-2xl">
					{isSelectionStep
						? $_('make_it_better.select_title', { default: 'Choose products to replace' })
						: $_('make_it_better.comparison_title', { default: 'Make your recipe better' })}
				</h2>
				<p class="text-base-content/70 mt-2">
					{isSelectionStep
						? $_('make_it_better.select_description', {
								default: 'Select only the recommended products you want to replace.'
							})
						: $_('make_it_better.comparison_description', {
								default: 'Review the catalogued score improvements before changing your recipe.'
							})}
				</p>
			</div>
			<button
				type="button"
				class="btn btn-ghost btn-sm btn-square"
				aria-label={$_('make_it_better.close', { default: 'Close' })}
				onclick={dismiss}
			>
				×
			</button>
		</div>

		{#if isSelectionStep}
			<fieldset class="mt-6 space-y-3">
				<legend class="text-base font-medium">
					{$_('make_it_better.select_legend', { default: 'Available replacements' })}
				</legend>
				{#each suggestions as suggestion, index (suggestion.ingredient + index)}
					<label
						class="border-base-300 rounded-box flex cursor-pointer items-start gap-3 border p-4"
					>
						<input
							type="checkbox"
							class="checkbox checkbox-primary mt-0.5"
							bind:checked={selected[index]}
						/>
						<span class="min-w-0">
							<span class="block font-medium">{suggestion.original.name}</span>
							<span class="text-base-content/70 block text-sm">
								→ {suggestion.suggested.name}
							</span>
						</span>
					</label>
				{/each}
			</fieldset>

			<div class="modal-action flex-col-reverse sm:flex-row">
				<button type="button" class="btn btn-ghost min-h-11" onclick={dismiss}>
					{$_('make_it_better.no', { default: 'No' })}
				</button>
				<button
					type="button"
					class="btn btn-primary min-h-11"
					disabled={!selected.some(Boolean)}
					onclick={applySelected}
				>
					{$_('make_it_better.apply', { default: 'Apply selected changes' })}
				</button>
			</div>
		{:else}
			<div class="mt-6 grid gap-4 md:grid-cols-2">
				<section class="bg-base-200 rounded-box p-4" aria-labelledby="original-recipe-title">
					<h3 id="original-recipe-title" class="font-semibold">
						{$_('make_it_better.original', { default: 'Original Recipe' })}
					</h3>
					<ul class="mt-3 space-y-3">
						{#each suggestions as suggestion, index (suggestion.ingredient + index)}
							<li>
								<p>{suggestion.original.name}</p>
								<p class="text-base-content/70 text-sm">
									Nutri-Score {suggestion.original.nutriScore} · Green-Score {suggestion.original
										.greenScore}
								</p>
							</li>
						{/each}
					</ul>
				</section>
				<section class="bg-base-200 rounded-box p-4" aria-labelledby="improved-recipe-title">
					<h3 id="improved-recipe-title" class="font-semibold">
						{$_('make_it_better.improved', { default: 'Improved Recipe' })}
					</h3>
					<ul class="mt-3 space-y-3">
						{#each suggestions as suggestion, index (suggestion.ingredient + index)}
							<li>
								<p>{suggestion.suggested.name}</p>
								<p class="text-base-content/70 text-sm">
									Nutri-Score {suggestion.suggested.nutriScore} · Green-Score {suggestion.suggested
										.greenScore}
								</p>
							</li>
						{/each}
					</ul>
				</section>
			</div>

			<div class="modal-action flex-col-reverse sm:flex-row">
				<button type="button" class="btn btn-ghost min-h-11" onclick={dismiss}>
					{$_('make_it_better.no', { default: 'No' })}
				</button>
				<button type="button" class="btn btn-primary min-h-11" onclick={showSelection}>
					{$_('make_it_better.switch', { default: 'Switch' })}
				</button>
			</div>
		{/if}
	</div>
	<form method="dialog" class="modal-backdrop"><button aria-label="Close">close</button></form>
</dialog>
