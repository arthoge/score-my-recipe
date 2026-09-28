<script lang="ts">
	import { _, locale, getLocale } from '$lib/i18n';
	import { recipeExamples, type RecipeExample } from './recipeExamples';

	type Props = {
		/** Called with the example's full recipe text when the user picks one. */
		onselect?: (text: string) => void;
	};

	let { onselect }: Props = $props();

	// Resolve examples for the active UI language.
	let currentExamples = $derived(recipeExamples[($locale ?? getLocale()).split('-')[0]] ?? []);

	function loadExample(example: RecipeExample) {
		onselect?.(example.text);
	}
</script>

<div class="flex flex-wrap items-center gap-2 py-1">
	<span class="text-base-content/70 text-xs font-medium">
		{$_('examples.title', { default: 'Or try an example:' })}
	</span>
	{#each currentExamples as ex (ex.id)}
		<button
			type="button"
			class="btn btn-outline btn-xs hover:btn-primary rounded-full font-normal"
			onclick={() => loadExample(ex)}
		>
			{$_(ex.nameKey)}
		</button>
	{/each}
</div>
