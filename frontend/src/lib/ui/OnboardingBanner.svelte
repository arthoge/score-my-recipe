<script lang="ts">
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { getCookie, setCookie } from '$lib/utils/cookies';

	const COOKIE_NAME = 'scorer_onboarding_dismissed';

	type Props = {
		isDismissed?: boolean;
	};

	let { isDismissed = $bindable(true) }: Props = $props();

	onMount(() => {
		const cookieVal = getCookie(COOKIE_NAME);
		isDismissed = cookieVal === '1';
	});

	export function dismiss() {
		isDismissed = true;
		setCookie(COOKIE_NAME, '1', { maxAge: 31536000, path: '/' });
	}

	export function show() {
		isDismissed = false;
	}
</script>

{#if !isDismissed}
	<div
		class="bg-base-200/80 border-primary/20 relative mb-8 overflow-hidden rounded-2xl border p-5 shadow-sm transition-all sm:p-6"
		role="region"
		aria-labelledby="onboarding-heading"
	>
		<!-- Top header -->
		<div class="flex items-start justify-between gap-4">
			<div class="flex items-center gap-3">
				<div
					class="bg-primary/10 text-primary flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-bold"
				>
					<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="h-5 w-5 fill-current">
						<path
							d="M17 8C8 10 5.9 16.17 3.82 21.34L5.71 22l1-2.3A4.49 4.49 0 0 0 8 20C19 20 22 3 22 3c-1 2-8 2.25-13 3.25S2 11.5 2 13.5s1.75 3.75 1.75 3.75C7 8 17 8 17 8Z"
						/>
					</svg>
				</div>
				<div>
					<h2 id="onboarding-heading" class="text-lg font-bold sm:text-xl">
						{$_('onboarding.title', { default: 'How to score your recipe' })}
					</h2>
					<p class="text-base-content/70 text-xs sm:text-sm">
						{$_('onboarding.subtitle', {
							default: 'Calculate the environmental impact of your culinary creations in seconds.'
						})}
					</p>
				</div>
			</div>

			<button
				type="button"
				class="btn btn-ghost btn-xs sm:btn-sm btn-circle text-base-content/60 hover:text-base-content"
				onclick={dismiss}
				aria-label={$_('onboarding.dismiss', { default: 'Got it!' })}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-4 w-4"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M6 18L18 6M6 6l12 12"
					/>
				</svg>
			</button>
		</div>

		<!-- 3 Steps Grid -->
		<div class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
			<div class="bg-base-100 border-base-300 rounded-xl border p-4 shadow-2xs">
				<div class="mb-1.5 flex items-center gap-2">
					<span class="badge badge-primary badge-sm font-semibold">1</span>
					<h3 class="text-sm font-bold">
						{$_('onboarding.step1_title', { default: '1. Enter ingredients' })}
					</h3>
				</div>
				<p class="text-base-content/70 text-xs leading-relaxed">
					{$_('onboarding.step1_desc', {
						default:
							'Paste or type your ingredients with their quantities (e.g. 200g flour, 3 eggs).'
					})}
				</p>
			</div>

			<div class="bg-base-100 border-base-300 rounded-xl border p-4 shadow-2xs">
				<div class="mb-1.5 flex items-center gap-2">
					<span class="badge badge-secondary badge-sm font-semibold">2</span>
					<h3 class="text-sm font-bold">
						{$_('onboarding.step2_title', { default: '2. Automatic matching' })}
					</h3>
				</div>
				<p class="text-base-content/70 text-xs leading-relaxed">
					{$_('onboarding.step2_desc', {
						default:
							'We recognize your ingredients and match them to the official Agribalyse/PEF database.'
					})}
				</p>
			</div>

			<div class="bg-base-100 border-base-300 rounded-xl border p-4 shadow-2xs">
				<div class="mb-1.5 flex items-center gap-2">
					<span class="badge badge-accent badge-sm font-semibold">3</span>
					<h3 class="text-sm font-bold">
						{$_('onboarding.step3_title', { default: '3. Real-time Green-Score' })}
					</h3>
				</div>
				<p class="text-base-content/70 text-xs leading-relaxed">
					{$_('onboarding.step3_desc', {
						default:
							'Get your score from A to F, see missing matches, and optimize your recipe impact.'
					})}
				</p>
			</div>
		</div>

		<!-- Footer actions -->
		<div class="mt-4 flex items-center justify-end">
			<button type="button" class="btn btn-primary btn-sm font-semibold" onclick={dismiss}>
				{$_('onboarding.dismiss', { default: 'Got it!' })}
			</button>
		</div>
	</div>
{/if}
