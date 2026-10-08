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
		onapply?: (suggestions: ImprovementSuggestion[]) => void;
	};

	let { suggestions, open = $bindable(false), ondismiss, onapply }: Props = $props();
	let dialog = $state<HTMLDialogElement>();
	let selected = $state<boolean[]>([]);

	$effect(() => {
		if (open && !dialog?.open) {
			// Select all by default or let user select? The user might prefer if we leave them unselected, or pre-selected.
			// Currently they were initialized to false. Let's keep it false.
			selected = suggestions.map(() => false);
			dialog?.showModal();
		} else if (!open && dialog?.open) {
			dialog.close();
		}
	});

	function dismiss() {
		open = false;
		ondismiss?.();
	}

	function applySelected() {
		const selectedSuggestions = suggestions.filter((_, index) => selected[index]);
		if (selectedSuggestions.length === 0) return;
		open = false;
		onapply?.(selectedSuggestions);
	}
</script>

<dialog bind:this={dialog} class="modal" aria-labelledby="make-it-better-title" onclose={dismiss}>
	<div class="modal-box max-w-3xl">
		<div class="flex items-start justify-between gap-4">
			<div>
				<h2 id="make-it-better-title" class="text-xl font-semibold sm:text-2xl">
					{$_('make_it_better.comparison_title', { default: 'Make your recipe better' })}
				</h2>
				<p class="text-base-content/70 mt-2">
					{$_('make_it_better.select_description', {
						default: 'Select the recommended products you want to replace.'
					})}
				</p>
			</div>
		</div>

		<div class="mt-6 space-y-4">
			{#each suggestions as suggestion, index (suggestion.ingredient + index)}
				<label
					class="border-base-300 bg-base-100 rounded-box flex cursor-pointer items-center gap-4 border p-4 transition-colors hover:bg-base-200"
				>
					<input
						type="checkbox"
						class="checkbox checkbox-primary"
						bind:checked={selected[index]}
					/>
					<div class="flex-1 min-w-0 grid sm:grid-cols-[1fr_auto_1fr] gap-4 items-center">
						<div>
							<div class="font-medium text-base-content">{suggestion.original.name}</div>
							<div class="text-base-content/70 text-sm mt-1">
								Nutri-Score {suggestion.original.nutriScore} · Green-Score {suggestion.original.greenScore}
							</div>
						</div>
						<div class="hidden sm:flex text-xl text-base-content/30">→</div >
						<div class="flex items-center gap-2 sm:gap-0 sm:block">
							<span class="sm:hidden text-xl text-base-content/30">→</span >
							<div class="font-medium text-success">{suggestion.suggested.name}</div>
							<div class="text-base-content/70 text-sm mt-1">
								Nutri-Score {suggestion.suggested.nutriScore} · Green-Score {suggestion.suggested.greenScore}
							</div>
						</div>
					</div>
				</label>
			{/each}
		</div>

		<div class="modal-action flex-col-reverse sm:flex-row mt-6">
			<button type="button" class="btn btn-outline btn-ghost min-h-11" onclick={dismiss}>
				{$_('make_it_better.no', { default: 'Cancel' })}
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
	</div>
	<form method="dialog" class="modal-backdrop"><button aria-label="Close">close</button></form>
</dialog>
