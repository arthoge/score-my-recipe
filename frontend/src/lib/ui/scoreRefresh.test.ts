/** Hide stale grades and keep missing-reference searches active during recalculation. */
import { expect, it, vi } from 'vitest';
import { render } from 'svelte/server';
import { writable } from 'svelte/store';
import ScoreDisplay from './ScoreDisplay.svelte';
import NutriScoreDisplay from './NutriScoreDisplay.svelte';
import IngredientLine from './IngredientLine.svelte';
import { createEmptyIngredient } from '$lib/types/ingredient';
import type { NutritionAnalysis } from '$lib/api/nutritionAnalysis';

vi.mock('$lib/i18n', () => ({
	_: writable((_key: string, options: { default: string }) => options.default),
	getLocale: () => 'en-US',
	waitLocale: async () => {}
}));

it('marks the environmental score as busy instead of displaying the old result', () => {
	const { body } = render(ScoreDisplay, {
		props: {
			recipeId: 'recipe',
			ingredients: [],
			isLoading: true,
			score: { letterGrade: 'B', numericScore: 72, missingIngredientIds: [] }
		}
	});
	expect(body).not.toContain('72.0/100');
	expect(body).toContain('aria-busy="true"');
	expect(body).toContain('Calculating...');
});

it('marks nutrition as recalculating instead of displaying the old grade', () => {
	const analysis = {
		status: 'complete',
		nutri_score: { grade: 'C', score: 9 },
		nutrients_per_100g: { proteins: 12 },
		additives: ['en:e330'],
		allergens: ['en:milk']
	} as NutritionAnalysis;
	const { body } = render(NutriScoreDisplay, {
		props: { recipeId: 'recipe', ingredients: [], analysis, loading: true }
	});
	expect(body).not.toContain('nutri-score-c');
	expect(body).toContain('12.00 g');
	expect(body).not.toContain('E330');
	expect(body).toContain('skeleton');
	expect(body).toContain('Calculating...');
});

it('continues missing product lookup after a verified replacement', () => {
	const ingredient = {
		...createEmptyIngredient(),
		name: 'Reduced-fat butter',
		ciqualCode: '16410',
		ciqualName: 'Reduced-fat butter',
		weight: 100
	};
	const props = {
		recipeId: 'recipe',
		ingredient,
		originOptions: [],
		labelOptions: [],
		originsStatus: 'ready' as const,
		labelsStatus: 'ready' as const
	};
	expect(render(IngredientLine, { props }).body).toContain('skeleton');
	const verified = render(IngredientLine, {
		props: { ...props, ingredient: { ...ingredient, resolvedReferenceName: ingredient.name } }
	}).body;
	expect(verified).toContain('skeleton');
	expect(verified).toContain('Reduced-fat butter');
});
