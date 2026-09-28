<script lang="ts">
	import { _, locale, supportedLocales, setAppLocale, type SupportedLocaleCode } from '$lib/i18n';

	let currentLocale = $derived(($locale as SupportedLocaleCode) ?? 'en-US');

	function handleSelect(code: string) {
		setAppLocale(code);
		// Close details dropdown if used as <details>
		const openDetails = document.querySelectorAll('details.language-dropdown[open]');
		openDetails.forEach((el) => el.removeAttribute('open'));
	}
</script>

<details class="dropdown dropdown-end language-dropdown">
	<summary
		class="btn btn-ghost btn-sm flex items-center gap-1.5 px-2 font-medium"
		aria-label={$_('languages.ui_language', { default: 'Language' })}
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 24 24"
			class="text-base-content/80 h-4 w-4"
			fill="currentColor"
		>
			<path
				d="M12.87 15.07l-2.54-2.51.03-.03c1.74-1.94 2.98-4.17 3.71-6.53H17V4h-7V2H8v2H1v1.99h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"
			/>
		</svg>
		<span class="text-xs uppercase">{currentLocale.startsWith('fr') ? 'FR' : 'EN'}</span>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 20 20"
			fill="currentColor"
			class="h-3.5 w-3.5 opacity-60"
		>
			<path
				fill-rule="evenodd"
				d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
				clip-rule="evenodd"
			/>
		</svg>
	</summary>
	<ul
		class="menu dropdown-content bg-base-100 rounded-box border-base-300 z-50 mt-1 w-36 border p-1 shadow-lg"
	>
		{#each supportedLocales as loc (loc.code)}
			<li>
				<button
					type="button"
					class="flex items-center justify-between py-2 text-xs"
					class:active={currentLocale.startsWith(loc.lang)}
					onclick={() => handleSelect(loc.code)}
				>
					<span>{loc.label}</span>
					<span class="text-base-content/50 font-mono text-[10px]">{loc.short}</span>
				</button>
			</li>
		{/each}
	</ul>
</details>
