/**
 * fileOverview Translations management
 *
 * Loads translations from messages files
 * and decide which locale to use (see getLocale)
 * Note: also look at hooks.server which may set locale based on request headers
 *
 * It also exports functions from svelte-i18n, like the translate function (aka `_`)
 */
import { init, register, getLocaleFromNavigator } from 'svelte-i18n';
import { browser } from '$app/environment';
import countries from './countries.json';

function generateCountryCode(country: Record<string, string>) {
	return `${country['languageCode']}-${country['countryCode'].toUpperCase()}`;
}

const AVAILABLE_LOCALES: Map<string, string>[] = [];

countries.forEach((country) => {
	const country_local: Map<string, string> = new Map();
	country_local.set('label', country['label']);
	country_local.set('code', generateCountryCode(country));
	AVAILABLE_LOCALES.push(country_local);
});

const FALLBACK_LOCALE = 'en-US';

// TODO: when we have many locales we should load them lazily, when we really need them
countries.forEach((locale) => {
	const code = generateCountryCode(locale);
	register(code, async () => {
		return (await import(`./messages/${code}.json`)).default;
	});
});

init({
	fallbackLocale: FALLBACK_LOCALE,
	initialLocale: getLocale()
});

/**
 * getLocale to use to display the page
 * @returns {String} locale code (eg. "en-US")
 */
export function getLocale() {
	return browser ? getBrowserLocale() : FALLBACK_LOCALE;
}

export function getBrowserLocale() {
	if (!browser) throw new Error('getBrowserLocale should only be called in the browser');
	// const preferredLang = get(preferences).lang;
	const navLang = getLocaleFromNavigator();
	return navLang || FALLBACK_LOCALE;
}

// Explicitly re-export the svelte-i18n helpers used elsewhere in the app
// waitLocale and isLoading are used to wait for translations files to be ready
export { isLoading, locale, waitLocale, _ } from 'svelte-i18n';
export { AVAILABLE_LOCALES };
