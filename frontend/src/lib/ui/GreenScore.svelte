<!--
  GreenScore.svelte

  Displays only the green-score logo (the SVG matching the letter grade returned
  by the backend) together with the numeric score.

  This is a pure presentational component: it does not know about loading or
  error states — those are handled by the parent `ScoreDisplay` component.

  Props:
  - letterGrade: The letter grade ("A+", "A", ... "F"), or null if unavailable.
  - numericScore: The numeric score (0-100), or null.
-->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import HelperTooltip from './HelperTooltip.svelte';

	type Props = {
		letterGrade?: string | null;
		numericScore?: number | null;
	};

	let { letterGrade = null, numericScore = null }: Props = $props();

	// Map each green-score SVG asset to its letter grade key.
	// Keys use a lowercase, hyphenated form of the grade (e.g. "A+" -> "a-plus").
	const scoreLogos = import.meta.glob<string>('$lib/assets/green-score/green-score-*.svg', {
		eager: true,
		query: '?url',
		import: 'default'
	});

	/**
	 * Convert a letter grade to the asset key used in the file names.
	 * @param grade - The letter grade (e.g. "A+", "B").
	 * @returns The asset key (e.g. "a-plus", "b").
	 */
	function gradeToAssetKey(grade: string): string {
		return grade.toLowerCase().replace('+', '-plus');
	}

	/** Resolve the SVG URL for the current letter grade, falling back to "unknown". */
	let scoreLogoUrl = $derived.by(() => {
		const key = letterGrade ? gradeToAssetKey(letterGrade) : 'unknown';
		const matching = Object.entries(scoreLogos).find(([path]) =>
			path.endsWith(`green-score-${key}.svg`)
		);
		const unknown = Object.entries(scoreLogos).find(([path]) =>
			path.endsWith('green-score-unknown.svg')
		)?.[1];
		return matching?.[1] ?? unknown ?? '';
	});
</script>

<div class="flex flex-col items-start gap-2">
	<img src={scoreLogoUrl} alt={letterGrade ?? 'unknown'} class="h-16 w-auto max-w-none shrink-0" />
	<div class="text-base-content/70 flex min-h-5 items-center gap-1 text-sm">
		{#if numericScore !== null}
			<span
				><span class="font-medium">{$_('recipe.numeric_score', { default: 'Score' })}:</span>
				{numericScore.toFixed(1)}/100</span
			>
			<HelperTooltip
				floating
				inheritColor
				tip={$_('recipe.green_score_help', {
					default: 'Higher scores mean lower environmental impact.'
				})}
				ariaLabel={$_('helpers.more_info', { default: 'More information' })}
			/>
		{/if}
	</div>
</div>
