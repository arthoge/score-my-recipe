/**
 * fileOverview Translations management
 *
 * Loads translations from messages files
 * and decide which locale to use (see getLocale)
 * Note: also look at hooks.server which may set locale based on request headers
 *
 * It also exports functions from svelte-i18n, like the translate function (aka `_`)
 */
import { init, register, getLocaleFromNavigator, isLoading } from 'svelte-i18n';
import { browser } from '$app/environment';

const locales = ['en-US', 'fr-FR'];

const FALLBACK_LOCALE = 'en-US';

// TODO: when we have many locales we should load them lazily, when we really need them
locales.forEach((locale) => {
	register(locale, async () => {
		const messages = await import(`./messages/${locale}.json`);
		return messages.default;
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

export { isLoading };
export * from 'svelte-i18n';
