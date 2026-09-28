import type { Handle } from '@sveltejs/kit';
import { locale } from '$lib/i18n';

import { clearWindow } from 'isomorphic-dompurify';

export const handle: Handle = async ({ event, resolve }) => {
	// set language based on cookie, fallback to accept-language header
	// FIXME: I would like to use a redirect instead and have the language in the url
	const cookieLocale = event.cookies.get('locale');
	const headerLang = event.request.headers.get('accept-language')?.split(',')[0];
	const rawLang = cookieLocale || headerLang;
	const normalizedLocale = rawLang?.toLowerCase().startsWith('fr') ? 'fr-FR' : 'en-US';

	if (rawLang) {
		locale.set(normalizedLocale);
	}

	const resolved = await resolve(event, {
		transformPageChunk: ({ html }) => {
			// Replace the %lang% placeholder in app.html with the user's active language
			const htmlLang = normalizedLocale.split('-')[0];
			return html.replace('%lang%', htmlLang);
		},

		// headers to include on fetch requests
		filterSerializedResponseHeaders(name) {
			return ['content-length', 'content-type', 'etag', 'cache-control'].includes(
				name.toLowerCase()
			);
		}
	});

	// Clear the jsdom window to prevent memory leaks in server-side rendering
	clearWindow();

	return resolved;
};
