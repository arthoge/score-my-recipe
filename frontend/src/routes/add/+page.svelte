<script lang="ts">
	import { _, getLocale, locale } from '$lib/i18n';
	import { goto } from '$app/navigation';
	import { parseRecipeText, apiIngredientsToIngredients } from '$lib/api/recipe';
	import OnboardingBanner from '$lib/ui/OnboardingBanner.svelte';
	import HelperTooltip from '$lib/ui/HelperTooltip.svelte';

	let recipeText = $state('');
	let isLoading = $state(false);
	let error = $state<string | null>(null);

	let onboardingRef = $state<ReturnType<typeof OnboardingBanner> | null>(null);
	let isOnboardingDismissed = $state(true);

	const recipeExamples: Record<string, Array<{ id: string; nameKey: string; text: string }>> = {
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

	let currentExamples = $derived(
		($locale ?? getLocale()).startsWith('fr') ? recipeExamples.fr : recipeExamples.en
	);

	function loadExample(example: { text: string }) {
		recipeText = example.text;
	}

	async function handleSubmit(event: Event) {
		event.preventDefault();
		isLoading = true;
		error = null;

		try {
			// the recipe text is most likely written in the language of the
			// interface, the API expects a 2-letter language code (eg. "fr")
			const lang = getLocale().split('-')[0];
			const result = await parseRecipeText(recipeText, lang);
			const ingredients = apiIngredientsToIngredients(result.ingredients);
			await goto('/score', { state: { ingredients } });
		} catch (e) {
			error = e instanceof Error ? e.message : 'Une erreur est survenue';
			isLoading = false;
		}
	}
</script>

<svelte:head>
	<title>{$_('add.title', { default: 'Ajouter une recette' })}</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8">
	<!-- Onboarding Callout -->
	<OnboardingBanner bind:this={onboardingRef} bind:isDismissed={isOnboardingDismissed} />

	<!-- Header -->
	<div class="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
		<div>
			<h1 class="text-3xl font-bold">{$_('add.title', { default: 'Ajouter une recette' })}</h1>
			<p class="text-base-content/70 mt-2">
				{$_('add.description', { default: 'Entrez votre recette ci-dessous' })}
				{$_('add.or', { default: 'ou utilisez la' })}
				<a href="/score" class="link link-primary"
					>{$_('add.guided_entry', { default: 'saisie guidée' })}</a
				>.
			</p>
		</div>

		{#if isOnboardingDismissed}
			<button
				type="button"
				class="btn btn-ghost btn-sm text-primary gap-1.5 self-start sm:self-auto"
				onclick={() => onboardingRef?.show()}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-4 w-4"
				>
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
						clip-rule="evenodd"
					/>
				</svg>
				<span>{$_('onboarding.help_button', { default: 'How does it work?' })}</span>
			</button>
		{/if}
	</div>

	<!-- Recipe Form -->
	<form onsubmit={handleSubmit} class="space-y-6">
		<div class="form-control w-full space-y-2">
			<!-- Field label -->
			<div class="flex items-center justify-between">
				<label class="label justify-start p-0" for="recipe-text">
					<span class="flex items-center gap-2 text-sm font-medium sm:text-base">
						<span>{$_('add.recipe_label', { default: 'Votre recette' })}</span>
						<HelperTooltip
							tip={$_('helpers.recipe_text', {
								default:
									'Enter each ingredient on a new line with its quantity (e.g. 200g flour, 3 eggs, 100g sugar).'
							})}
							ariaLabel={$_('helpers.more_info', { default: 'More information' })}
						/>
					</span>
				</label>
			</div>

			<!-- Example recipe shortcuts (honors UI language) -->
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

			<textarea
				id="recipe-text"
				bind:value={recipeText}
				class="textarea textarea-bordered min-h-64 w-full text-base"
				placeholder={$_('add.recipe_placeholder', {
					default: 'Entrez votre recette ici...\n\nExemple:\n200g de farine\n3 œufs\n100g de sucre'
				})}
				required
			></textarea>
		</div>

		<button type="submit" class="btn btn-primary btn-lg" disabled={isLoading}>
			{#if isLoading}
				<span class="loading loading-spinner"></span>
				{$_('add.loading', { default: 'Calcul en cours...' })}
			{:else}
				{$_('add.score_button', { default: 'Score recipe' })}
			{/if}
		</button>
	</form>

	<!-- Error Display -->
	{#if error}
		<div class="alert alert-error mt-6">
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-6 w-6 shrink-0 stroke-current"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<span>{error}</span>
		</div>
	{/if}
</div>
