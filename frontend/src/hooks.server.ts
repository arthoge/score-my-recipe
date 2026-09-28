import type { Handle } from '@sveltejs/kit';
import { locale } from '$lib/i18n';

import { clearWindow } from 'isomorphic-dompurify';

export const handle: Handle = async ({ event, resolve }) => {
	// set language based on accept-language header
	// FIXME: I would like to use a redirect instead and have the language in the url
	const lang = event.request.headers.get('accept-language')?.split(',')[0];
	if (lang) {
		locale.set(lang);
	}

	const resolved = await resolve(event, {
		transformPageChunk: ({ html }) => {
			// Replace the %lang% placeholder in app.html with the user's active language
			// from the accept-language header to ensure proper accessibility and SEO.
			return html.replace('%lang%', lang || 'en');
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
