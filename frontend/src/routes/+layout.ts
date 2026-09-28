import { waitLocale } from '$lib/i18n';
import type { LayoutLoad } from './$types';

/**
 * At load time we set the language
 */
export const load: LayoutLoad = async () => {
	await waitLocale();

	return {};
};
