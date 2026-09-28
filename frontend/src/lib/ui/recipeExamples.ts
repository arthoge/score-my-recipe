/**
 * @fileoverview Example recipes shown on the "add recipe" page as quick-fill
 * shortcuts (the "Or try an example:" buttons).
 *
 * The data is keyed by a 2-letter language code (e.g. "fr", "en"). Callers must
 * normalise the active locale to its 2-letter part before looking it up — see
 * RecipeExamples.svelte, which mirrors offLink.ts' `locale.split('-')[0]`.
 */

export type RecipeExample = {
	id: string;
	nameKey: string;
	text: string;
};

export const recipeExamples: Record<string, RecipeExample[]> = {
	fr: [
		{
			id: 'quiche',
			nameKey: 'examples.quiche',
			text: "200g de pâte brisée\n200g de lardons\n3 œufs\n200ml de crème fraîche\n150ml de lait\n100g d'emmental râpé"
		},
		{
			id: 'apple_pie',
			nameKey: 'examples.apple_pie',
			text: '1 pâte feuilletée\n4 pommes\n50g de sucre\n30g de beurre'
		},
		{
			id: 'ratatouille',
			nameKey: 'examples.ratatouille',
			text: "500g de tomates\n300g de courgettes\n300g d'aubergines\n200g de poivrons\n100g d'oignons\n30ml d'huile d'olive"
		}
	],
	en: [
		{
			id: 'quiche',
			nameKey: 'examples.quiche',
			text: '200g shortcrust pastry\n200g bacon lardons\n3 eggs\n200ml crème fraîche\n150ml milk\n100g grated emmental'
		},
		{
			id: 'apple_pie',
			nameKey: 'examples.apple_pie',
			text: '1 puff pastry\n4 apples\n50g sugar\n30g butter'
		},
		{
			id: 'ratatouille',
			nameKey: 'examples.ratatouille',
			text: '500g tomatoes\n300g zucchini\n300g eggplant\n200g bell peppers\n100g onions\n30ml olive oil'
		}
	]
};
