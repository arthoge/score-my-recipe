/** Turn reported exclusions into named references and their editable controls. */
import type { NutritionAnalysis } from '$lib/api/nutritionAnalysis';
import type { Ingredient } from '$lib/types/ingredient';

export type ExclusionKind =
	| 'agribalyse'
	| 'ciqual'
	| 'off'
	| 'select_agribalyse'
	| 'select_ciqual'
	| 'quantity'
	| 'preparation'
	| 'state'
	| 'off_unavailable';

export type ExclusionReason = {
	kind: ExclusionKind;
	name: string;
	ingredientId: string;
};

/** Resolve the editable control within its own recipe, including references inside Details. */
export function exclusionTarget(recipeId: string, reason: ExclusionReason) {
	const rowId = `${recipeId}-${reason.ingredientId}`;
	const fields: Record<ExclusionKind, string> = {
		agribalyse: 'reference',
		select_agribalyse: 'reference',
		ciqual: 'ciqual',
		select_ciqual: 'ciqual',
		state: 'ciqual',
		off: 'product',
		off_unavailable: 'product',
		quantity: 'weight',
		preparation: 'preparation'
	};
	const field = fields[reason.kind];
	return {
		inputId: `ingredient-${field}-${rowId}`,
		dialogId:
			field === 'reference' || field === 'ciqual' ? `ingredient-details-dialog-${rowId}` : null
	};
}

/** Identify the actual environmental reference, or the ingredient needing a selection. */
export function greenExclusionReasons(
	ingredients: Ingredient[],
	excludedIds: string[]
): ExclusionReason[] {
	return ingredients
		.filter((row) => excludedIds.includes(row.id))
		.map((row): ExclusionReason => {
			const ingredientId = row.id;
			if (row.weight == null || row.weight <= 0)
				return { kind: 'quantity', name: row.name, ingredientId };
			const reference = row.agribalyseName?.trim() || row.agribalyseCode;
			return reference
				? { kind: 'agribalyse', name: reference, ingredientId }
				: { kind: 'select_agribalyse', name: row.name, ingredientId };
		});
}

/** Follow the backend's chosen nutrition source, including an incomplete Ciqual fallback. */
export function nutritionExclusionReasons(
	ingredients: Ingredient[],
	analysis: NutritionAnalysis | null
): ExclusionReason[] {
	if (!analysis) return [];
	return (analysis.excluded_ingredients ?? []).map((excluded): ExclusionReason => {
		const ingredientId = excluded.ingredient_id;
		const row = ingredients.find((item) => item.id === excluded.ingredient_id);
		const name = row?.name || excluded.ingredient_name;
		const codes = new Set(
			(analysis.diagnostics ?? [])
				.filter((issue) => issue.ingredient_id === excluded.ingredient_id)
				.map((issue) => issue.code)
		);
		if (codes.has('zero_quantity') || codes.has('quantity_missing'))
			return { kind: 'quantity', name, ingredientId };
		if (codes.has('unsupported_preparation')) return { kind: 'preparation', name, ingredientId };
		if (codes.has('prepared_reference_required')) return { kind: 'state', name, ingredientId };
		const source = analysis.ingredients?.find(
			(trace) => trace.ingredient_id === excluded.ingredient_id
		)?.source;
		if (source !== 'CIQUAL-2025' && row?.barcode) {
			return {
				kind: codes.has('product_unavailable') ? 'off_unavailable' : 'off',
				ingredientId,
				name: row.productName?.trim() || row.barcode
			};
		}
		return row?.ciqualCode
			? { kind: 'ciqual', name: row.ciqualName?.trim() || row.ciqualCode, ingredientId }
			: { kind: 'select_ciqual', name, ingredientId };
	});
}
