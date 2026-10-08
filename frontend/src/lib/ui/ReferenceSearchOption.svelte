<!-- One autocomplete choice, with source-reported missing-data help beside its name. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { TaxonomyItem } from '$lib/types/ingredient';
	import IconMdiAlertOutline from '@iconify-svelte/mdi/alert-outline';
	import HelperTooltip from './HelperTooltip.svelte';

	let {
		id,
		suggestion,
		active,
		onchoose
	}: {
		id: string;
		suggestion: TaxonomyItem;
		active: boolean;
		onchoose: (item: TaxonomyItem) => void;
	} = $props();
	let warningAnchor = $state<HTMLSpanElement>();
	let tip = $derived(
		suggestion.noData
			? $_('recipe.reference_no_data', { default: 'No data' })
			: $_('recipe.reference_missing_data', {
					default: 'Missing data: {fields}',
					values: {
						fields: (suggestion.missingData ?? [])
							.map((field) =>
								field === 'environmental_data'
									? $_('recipe.environmental_data', { default: 'environmental impact' })
									: $_(`nutrition.nutrients.${field}`, { default: field.replaceAll('_', ' ') })
							)
							.join(', ')
					}
				})
	);
</script>

<button
	{id}
	type="button"
	role="option"
	aria-selected={active}
	class="hover:bg-base-200 flex w-full items-center justify-between gap-3 rounded px-3 py-2 text-left text-sm"
	class:bg-base-200={active}
	tabindex="-1"
	onpointerdown={(event) => event.preventDefault()}
	onclick={() => onchoose(suggestion)}
>
	<span>{suggestion.label}</span>
	{#if suggestion.noData || suggestion.missingData?.length}
		<span
			bind:this={warningAnchor}
			class="inline-flex shrink-0"
			class:text-error={suggestion.noData}
			class:text-warning={!suggestion.noData}
		>
			<IconMdiAlertOutline class="h-4 w-4" aria-hidden="true" />
			<span class="sr-only">{tip}</span>
		</span>
	{/if}
</button>
{#if (suggestion.noData || suggestion.missingData?.length) && warningAnchor}
	<HelperTooltip floating position="bottom" {tip} trigger={warningAnchor} />
{/if}
