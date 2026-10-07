<!-- Select recipe drafts for export; file generation will be connected later. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { RecipeDraft } from '$lib/types/recipeDraft';

	let { recipes }: { recipes: Pick<RecipeDraft, 'id' | 'name'>[] } = $props();
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
		dialog.showModal();
	}

	/** Apply the header checkbox to every recipe, including partially selected lists. */
	function selectAll(selected: boolean) {
		selectedIds = selected ? recipes.map((recipe) => recipe.id) : [];
	}
</script>

<button type="button" class="btn btn-outline shrink-0" aria-haspopup="dialog" onclick={openDialog}>
	{$_('recipe.export_recipes', { default: 'Export recipes' })}
</button>

<dialog bind:this={dialog} class="modal" aria-labelledby="{dialogId}-title">
	<div class="modal-box">
		<h2 id="{dialogId}-title" class="mb-4 text-lg font-bold">
			{$_('recipe.export_recipes', { default: 'Export recipes' })}
		</h2>
		<div class="border-base-300 max-h-80 overflow-auto border">
			<table class="table-sm table">
				<thead class="bg-base-200">
					<tr>
						<th scope="col" class="border-base-300 w-12 border-r">
							<input
								type="checkbox"
								class="checkbox checkbox-sm"
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
		<div class="modal-action">
			<button type="button" class="btn btn-outline" onclick={() => dialog.close()}>
				{$_('recipe.cancel', { default: 'Cancel' })}
			</button>
			<button type="button" class="btn btn-primary">
				{$_('recipe.export', { default: 'Export' })}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('recipe.cancel', { default: 'Cancel' })}></button>
	</form>
</dialog>
