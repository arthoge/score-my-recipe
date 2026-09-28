<script>
	import { _ } from '$lib/i18n';
	import Logo from '$lib/ui/Logo.svelte';
	import LanguageSelector from '$lib/ui/LanguageSelector.svelte';
	import { offLinks } from '$lib/offLink';

	const navItems = $state([
		{ name: 'navbar.score_recipe', href: '/add' },
		{ name: 'navbar.methodology', href: `${offLinks.website}/green-score` }
	]);
</script>

<nav class="bg-base-200 border-base-300 sticky top-0 z-50 border-b">
	<div class="mx-auto flex w-full max-w-7xl flex-row items-center justify-between gap-4 px-6 py-4">
		<div class="flex items-center gap-6">
			<Logo />
			<ul class="hidden items-center gap-2 md:flex">
				{#each navItems as item (item.name)}
					<li class="px-3 py-1">
						<a href={item.href} class="font-medium hover:underline">
							{$_(item.name)}
						</a>
					</li>
				{/each}
			</ul>
		</div>

		<div class="flex items-center gap-3">
			<LanguageSelector />
			<div class="hidden lg:flex">
				<button class="btn btn-primary font-bold">
					{$_('navbar.join_community')}
				</button>
			</div>
		</div>
	</div>
</nav>

<nav class="bg-secondary mt-2 mb-8 px-4"></nav>
