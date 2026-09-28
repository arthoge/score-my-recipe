<script>
	import { _ } from '$lib/i18n';
	import Logo from '$lib/ui/Logo.svelte';
	import { offLinks } from '$lib/offLink';

	const navItems = $state([
		{ name: 'navbar.score_recipe', href: '/add' },
		{ name: 'navbar.methodology', href: `${offLinks.website}/green-score` }
	]);
</script>

<nav class="bg-base-200 border-base-300 sticky top-0 z-50 border-b">
	<div
		class="mx-auto flex w-full max-w-7xl flex-col justify-between gap-4 px-6 py-4 md:flex-row md:items-center"
	>
		<Logo />
		<ul class="flex hidden w-full justify-evenly md:flex">
			{#each navItems as item (item.name)}
				<li class="px-4 py-2">
					<a href={item.href} class="font-medium hover:underline">
						{$_(item.name)}
					</a>
				</li>
			{/each}
		</ul>

		<div class="hidden gap-4 lg:flex">
			<button class="btn btn-primary font-bold">
				{$_('navbar.join_community')}
			</button>
		</div>
	</div>
</nav>

<nav class="bg-secondary mt-2 mb-8 px-4"></nav>
