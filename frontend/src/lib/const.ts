import { env } from '$env/dynamic/public';

export const MATOMO_URL = env.PUBLIC_MATOMO_URL || 'https://analytics.openfoodfacts.org';
export const MATOMO_HOST = MATOMO_URL;
export const MATOMO_SITE_ID = Number(env.PUBLIC_MATOMO_SITE_ID || '18');
