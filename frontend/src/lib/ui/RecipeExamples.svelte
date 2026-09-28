<script lang="ts">
	import { _, locale, getLocale, dictionary } from '$lib/i18n';
	import { getRecipeExamples, type RecipeExample } from './recipeExamples';

	type Props = {
		/** Called with the example's full recipe text when the user picks one. */
		onselect?: (text: string) => void;
	};

	let { onselect }: Props = $props();

	// Resolve examples for the active UI language. `$dictionary` is passed in so
	// we re-resolve after a language switch, once the new locale's messages have
	// finished loading asynchronously.
	let currentExamples = $derived(getRecipeExamples($locale ?? getLocale(), $dictionary));

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
			{ex.name}
		</button>
	{/each}
</div>
