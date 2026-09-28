<!--
  CountrySelect.svelte

  A single-choice country selector for the recipe-level country context.
  Fetches the list of countries relevant for the green-score computation from
  the backend `/v1/countries` endpoint and exposes the selected
  ISO 3166-1 alpha-2 country code via a bindable `value` prop.

  Only countries with a usable country code are offered (see `getCountries`),
  since a country without a code cannot influence the distance modifier.

  Props:
  - value: The currently selected country code (bindable, `null` when unselected).
-->
<script lang="ts">
	import { _, locale } from '$lib/i18n';
	import { getCountries } from '$lib/api/taxonomy';
	import HelperTooltip from '$lib/ui/HelperTooltip.svelte';
	import type { components } from '../../api-schema';

	type Country = components['schemas']['Country'];

	type Props = {
		value?: string | null;
	};

	let { value = $bindable(null) }: Props = $props();

	let countries = $state<Country[]>([]);
	let isLoading = $state(true);
	let loadError = $state<string | null>(null);

	// Fetch or reload countries whenever the active UI locale changes
	$effect(() => {
		const langKey = ($locale ?? '').startsWith('fr') ? 'fr' : 'en';
		isLoading = true;
		loadError = null;
		getCountries(langKey)
			.then((data) => {
				countries = data;
			})
			.catch((e) => {
				loadError = e instanceof Error ? e.message : 'An error occurred';
			})
			.finally(() => {
				isLoading = false;
			});
	});
</script>

<div class="flex flex-col">
	<label class="label py-1" for="country-select">
		<span class="flex items-center gap-1.5">
			<span class="label-text text-xs">{$_('recipe.country', { default: 'Country' })}</span>
			<HelperTooltip
				tip={$_('helpers.country', {
					default:
						'Country where the recipe is prepared or consumed, used to calculate transport distances.'
				})}
				ariaLabel={$_('helpers.more_info', { default: 'More information' })}
			/>
		</span>
	</label>

	{#if loadError}
		<!-- Inline error: the select is disabled so no stale selection can be sent -->
		<div class="flex items-center gap-2" role="alert" aria-live="polite">
			<select
				id="country-select"
				class="select select-bordered w-48"
				disabled
				aria-label={$_('recipe.country_load_error', {
					default: 'Could not load countries'
				})}
			></select>
			<span class="text-error text-xs">
				{$_('recipe.country_load_error', { default: 'Could not load countries' })}
			</span>
		</div>
	{:else}
		<select id="country-select" class="select select-bordered w-48" bind:value disabled={isLoading}>
			<option value={null}>
				{$_('recipe.country_placeholder', { default: 'Select your country' })}
			</option>
			{#each countries as country (country.id)}
				<option value={country.country_code!}>{country.label}</option>
			{/each}
		</select>
	{/if}
</div>
