<!-- Edit a recipe name without applying changes until the form is saved. -->
<script lang="ts">
	import IconMdiPencil from '@iconify-svelte/mdi/pencil';
	import { _ } from '$lib/i18n';
	import { RECIPE_NAME_MAX_LENGTH } from '$lib/types/recipeDraft';

	let { id, name = $bindable(), title }: { id: string; name: string; title: string } = $props();
	let dialog: HTMLDialogElement;
	let input: HTMLInputElement;
	let draft = $state('');

	/** Start each edit from the current name and focus the input inside the modal. */
	function openEditor() {
		draft = name;
		dialog.showModal();
		input.focus();
		input.select();
	}

	/** Save a non-empty trimmed name, leaving the recipe unchanged on cancellation. */
	function saveName(event: SubmitEvent) {
		event.preventDefault();
		const trimmed = draft.trim();
		if (!trimmed || trimmed.length > RECIPE_NAME_MAX_LENGTH) return;
		name = trimmed;
		dialog.close();
	}
</script>

<button
	type="button"
	class="btn btn-ghost btn-sm btn-square text-base-content/40 hover:text-base-content shrink-0 print:hidden"
	aria-label={$_('recipe.edit_name', { default: 'Edit recipe name' })}
	aria-haspopup="dialog"
	onclick={openEditor}
>
	<IconMdiPencil class="h-5 w-5" aria-hidden="true" />
</button>

<dialog
	bind:this={dialog}
	class="modal print:hidden"
	aria-labelledby="recipe-name-dialog-heading-{id}"
>
	<form class="modal-box" onsubmit={saveName}>
		<h3 id="recipe-name-dialog-heading-{id}" class="mb-4 text-lg font-bold">
			{$_('recipe.edit_name', { default: 'Edit recipe name' })}
		</h3>
		<label class="mb-2 block" for="recipe-name-input-{id}">
			{$_('recipe.name', { default: 'Recipe name' })}
		</label>
		<input
			bind:this={input}
			bind:value={draft}
			id="recipe-name-input-{id}"
			type="text"
			class="input w-full"
			placeholder={title}
			required
			maxlength={RECIPE_NAME_MAX_LENGTH}
			aria-describedby="recipe-name-limit-{id}"
		/>
		<p id="recipe-name-limit-{id}" class="text-base-content/70 mt-2 text-sm">
			{$_('recipe.name_character_count', {
				default: '{count}/{max} characters',
				values: { count: draft.length, max: RECIPE_NAME_MAX_LENGTH }
			})}
		</p>
		<div class="modal-action">
			<button type="button" class="btn btn-outline" onclick={() => dialog.close()}>
				{$_('recipe.cancel', { default: 'Cancel' })}
			</button>
			<button
				type="submit"
				class="btn btn-primary"
				disabled={!draft.trim() || draft.length > RECIPE_NAME_MAX_LENGTH}
			>
				{$_('recipe.save', { default: 'Save' })}
			</button>
		</div>
	</form>
	<form method="dialog" class="modal-backdrop">
		<button aria-label={$_('recipe.cancel', { default: 'Cancel' })}></button>
	</form>
</dialog>
