import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { tracker, type Tracker } from './tracker';
import { MATOMO_HOST, MATOMO_SITE_ID, MATOMO_URL } from '$lib/const';

describe('matomo tracker', () => {
	it('has default constants configured', () => {
		expect(MATOMO_URL).toBe('https://analytics.openfoodfacts.org');
		expect(MATOMO_HOST).toBe('https://analytics.openfoodfacts.org');
		expect(MATOMO_SITE_ID).toBe(18);
	});

	it('initializes with undefined and allows setting a tracker', () => {
		expect(get(tracker)).toBeUndefined();

		const mockTracker = {
			trackPageView: () => {},
			trackEvent: () => {},
			setCustomUrl: () => {}
		} as unknown as Tracker;

		tracker.set(mockTracker);
		expect(get(tracker)).toBe(mockTracker);

		tracker.set(undefined);
		expect(get(tracker)).toBeUndefined();
	});
});
