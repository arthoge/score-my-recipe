<!-- Select recipe drafts and download a report calculated by the backend. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { RecipeDraft } from '$lib/types/recipeDraft';
	import { exportRecipes } from '$lib/api/recipeExport';

	let { recipes }: { recipes: RecipeDraft[] } = $props();
	let exporting = $state(false);
	let exportError = $state(false);
	let dialog: HTMLDialogElement;
	const dialogId = $props.id();
	let selectedIds = $state<string[]>([]);
	const allSelected = $derived(
		recipes.length > 0 && recipes.every((recipe) => selectedIds.includes(recipe.id))
	);
	const someSelected = $derived(recipes.some((recipe) => selectedIds.includes(recipe.id)));

	/** Start each export dialog with all current recipes selected. */
	function openDialog() {
		selectedIds = recipes.map((recipe) => recipe.id);
		exportError = false;
		dialog.showModal();
	}

	/** Apply the header checkbox to every recipe, including partially selected lists. */
	function selectAll(selected: boolean) {
		selectedIds = selected ? recipes.map((recipe) => recipe.id) : [];
	}

	/** Snapshot the selection so edits cannot change a report already being generated. */
	async function downloadPdf() {
		if (exporting || !selectedIds.length) return;
		exporting = true;
		exportError = false;
		try {
			const selection = structuredClone($state.snapshot(recipes))
				.map((recipe, index) => ({
					...recipe,
					name:
						recipe.name ||
						$_('recipe.untitled', { default: 'Recipe {number}', values: { number: index + 1 } })
				}))
				.filter((recipe) => selectedIds.includes(recipe.id));
			const blob = await exportRecipes(selection);
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.href = url;
			link.download = 'recipes.pdf';
			document.body.append(link);
			link.click();
			link.remove();
			setTimeout(() => URL.revokeObjectURL(url), 1000);
			dialog.close();
		} catch {
			exportError = true;
		} finally {
			exporting = false;
		}
	}
</script>

<button type="button" class="btn btn-primary shrink-0" aria-haspopup="dialog" onclick={openDialog}>
	{$_('recipe.export_recipes', { default: 'Export recipes' })}
</button>

<dialog bind:this={dialog} class="modal" aria-labelledby="{dialogId}-title">
	<div class="modal-box">
		<h2 id="{dialogId}-title" class="mb-4 text-lg font-bold">
			{$_('recipe.export_recipes', { default: 'Export recipes' })}
		</h2>
		<p class="text-base-content/70 mb-4 text-sm">
			{$_('recipe.export_description', {
				default: 'Download a PDF with basic information about the selected recipes.'
			})}
		</p>
		<div class="border-base-300 max-h-80 overflow-auto border">
			<table class="table-sm table">
				<thead class="bg-base-200">
					<tr>
						<th scope="col" class="border-base-300 w-12 border-r">
							<input
								type="checkbox"
								class="checkbox checkbox-sm"
								disabled={exporting}
								checked={allSelected}
								indeterminate={someSelected && !allSelected}
								aria-label={$_('recipe.select_all_recipes', { default: 'Select all recipes' })}
								onchange={(event) => selectAll(event.currentTarget.checked)}
							/>
						</th>
						<th scope="col">{$_('recipe.name', { default: 'Recipe name' })}</th>
					</tr>
				</thead>
				<tbody>
					{#each recipes as recipe, index (recipe.id)}
						{@const title =
							recipe.name ||
							$_('recipe.untitled', { default: 'Recipe {number}', values: { number: index + 1 } })}
						<tr>
							<td class="border-base-300 border-r">
								<input
									type="checkbox"
									class="checkbox checkbox-sm"
									disabled={exporting}
									value={recipe.id}
									bind:group={selectedIds}
									aria-label={title}
								/>
							</td>
							<td class="wrap-anywhere">{title}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if exportError}
			<p class="text-error mt-3 text-sm" role="alert">
				{$_('recipe.export_failed', {
					default: 'Could not export recipes. Check quantities and portions, then try again.'
				})}
			</p>
		{/if}
		<div class="modal-action">
			<button type="button" class="btn btn-outline" onclick={() => dialog.close()}>
				{$_('recipe.cancel', { default: 'Cancel' })}
			</button>
			<button
				type="button"
				class="btn btn-primary"
				disabled={exporting || !selectedIds.length}
				onclick={downloadPdf}
			>
				{#if exporting}
					<span class="loading loading-spinner loading-sm" aria-hidden="true"></span>
				{/if}
				{$_('recipe.export', { default: 'Export' })}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('recipe.cancel', { default: 'Cancel' })}></button>
	</form>
</dialog>
