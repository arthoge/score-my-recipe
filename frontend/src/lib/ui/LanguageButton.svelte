<script lang="ts">
	import { _, AVAILABLE_LOCALES } from '$lib/i18n';
	import { locale } from 'svelte-i18n';

	function updateLanguage(event: Event & { currentTarget: EventTarget & HTMLSelectElement }) {
		const value = event.target instanceof HTMLSelectElement ? event.target.value : null;

		if (value) {
			locale.set(value);
		}
	}
</script>

<div class="locale-selector flex flex-1">
	<div class="select">
		<select value={$locale} onchange={updateLanguage}>
			{#each AVAILABLE_LOCALES as locale (locale.get('code'))}
				<option value={locale.get('code')}>{locale.get('label')}</option>
			{/each}
		</select>
	</div>
</div>
