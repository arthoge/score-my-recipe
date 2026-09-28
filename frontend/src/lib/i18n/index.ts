/**
 * fileOverview Translations management
 *
 * Loads translations from messages files
 * and decides which locale to use (see getLocale)
 * Note: also look at hooks.server which sets locale based on cookie or request headers
 *
 * It also exports functions from svelte-i18n, like the translate function (aka `_`)
 */
import { init, register, getLocaleFromNavigator, isLoading, locale } from 'svelte-i18n';
import { browser } from '$app/environment';
import { getCookie, setCookie } from '$lib/utils/cookies';

export const supportedLocales = [
	{ code: 'en-US', label: 'English', short: 'EN', lang: 'en' },
	{ code: 'fr-FR', label: 'Français', short: 'FR', lang: 'fr' }
] as const;

export type SupportedLocaleCode = (typeof supportedLocales)[number]['code'];

const FALLBACK_LOCALE = 'en-US';

// Register full locale tags
register('en-US', async () => (await import('./messages/en-US.json')).default);
register('fr-FR', async () => (await import('./messages/fr-FR.json')).default);

// Also register 2-letter aliases for svelte-i18n resolution
register('en', async () => (await import('./messages/en-US.json')).default);
register('fr', async () => (await import('./messages/fr-FR.json')).default);

init({
	fallbackLocale: FALLBACK_LOCALE,
	initialLocale: getLocale()
});

/**
 * Normalize an arbitrary locale string to a supported locale code.
 */
export function normalizeLocale(loc?: string | null): SupportedLocaleCode {
	if (!loc) return FALLBACK_LOCALE;
	const lower = loc.toLowerCase();
	if (lower.startsWith('fr')) return 'fr-FR';
	return 'en-US';
}

/**
 * getLocale to use to display the page
 * @returns {String} locale code (eg. "en-US")
 */
export function getLocale(): SupportedLocaleCode {
	return browser ? getBrowserLocale() : FALLBACK_LOCALE;
}

export function getBrowserLocale(): SupportedLocaleCode {
	if (!browser) return FALLBACK_LOCALE;
	const cookieLocale = getCookie('locale');
	if (cookieLocale) {
		return normalizeLocale(cookieLocale);
	}
	const navLang = getLocaleFromNavigator();
	return normalizeLocale(navLang);
}

/**
 * Change the active UI locale and persist it in a cookie.
 */
export function setAppLocale(target: string): void {
	const normalized = normalizeLocale(target);
	locale.set(normalized);
	setCookie('locale', normalized, { maxAge: 31536000, path: '/' });
	if (typeof document !== 'undefined') {
		document.documentElement.lang = normalized.split('-')[0];
	}
}

export { isLoading };
export * from 'svelte-i18n';
