<!-- Official algorithm-2023 illustration and numeric score, matching GreenScore layout. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
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
		class="h-16 w-auto"
	/>
	<span class="text-base-content/70 text-sm">
		{$_('recipe.numeric_score', { default: 'Score' })}: {score}
	</span>
</div>
