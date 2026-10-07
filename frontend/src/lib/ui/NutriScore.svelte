<!-- Official algorithm-2023 illustration and numeric score, matching GreenScore layout. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import HelperTooltip from './HelperTooltip.svelte';
	let { grade, score }: { grade: string; score: number } = $props();
	const logos = import.meta.glob<string>('$lib/assets/nutri-score/nutri-score-*.svg', {
		eager: true,
		query: '?url',
		import: 'default'
	});
	/** Resolve the official illustration for the returned grade. */
	let logoUrl = $derived(
		Object.entries(logos).find(([path]) =>
			path.endsWith(`nutri-score-${grade.toLowerCase()}.svg`)
		)?.[1] ?? ''
	);
</script>

<div class="flex flex-col items-start gap-2">
	<img
		src={logoUrl}
		alt={$_('nutrition.logo_alt', { default: 'Nutri-Score {grade}', values: { grade } })}
		class="h-16 w-auto max-w-none shrink-0"
	/>
	<div class="text-base-content/70 flex min-h-5 items-center gap-1 text-sm">
		<span
			><span class="font-medium">{$_('recipe.numeric_score', { default: 'Score' })}:</span>
			{score}</span
		>
		<HelperTooltip
			floating
			inheritColor
			tip={$_('recipe.nutri_score_help', {
				default: 'Lower scores mean better nutritional quality.'
			})}
			ariaLabel={$_('helpers.more_info', { default: 'More information' })}
		/>
	</div>
</div>
