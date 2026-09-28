import { describe, it, expect, beforeEach, afterAll } from 'vitest';
import { getCookie, setCookie, deleteCookie } from './cookies';

describe('cookies utility', () => {
	let mockCookieStore: Record<string, string> = {};

	const originalDocument = globalThis.document;

	beforeEach(() => {
		mockCookieStore = {};

		// Mock document.cookie getter and setter
		Object.defineProperty(globalThis, 'document', {
			value: {
				get cookie() {
					return Object.entries(mockCookieStore)
						.map(([k, v]) => `${k}=${v}`)
						.join('; ');
				},
				set cookie(str: string) {
					const parts = str.split(';');
					const [keyVal] = parts;
					const eqIdx = keyVal.indexOf('=');
					if (eqIdx !== -1) {
						const key = keyVal.slice(0, eqIdx).trim();
						const val = keyVal.slice(eqIdx + 1).trim();
						const isExpired = parts.some(
							(p) => p.trim().startsWith('max-age=0') || p.trim().startsWith('expires=')
						);
						if (isExpired) {
							delete mockCookieStore[key];
						} else {
							mockCookieStore[key] = val;
						}
					}
				}
			},
			configurable: true,
			writable: true
		});
	});

	afterAll(() => {
		globalThis.document = originalDocument;
	});

	it('returns null when cookie does not exist', () => {
		expect(getCookie('nonexistent')).toBeNull();
	});

	it('sets and gets a cookie value correctly', () => {
		setCookie('test_cookie', 'test_value');
		expect(getCookie('test_cookie')).toBe('test_value');
	});

	it('handles encoded characters properly', () => {
		setCookie('special', 'hello world');
		expect(getCookie('special')).toBe('hello world');
	});

	it('deletes a cookie properly', () => {
		setCookie('to_delete', 'value');
		expect(getCookie('to_delete')).toBe('value');
		deleteCookie('to_delete');
		expect(getCookie('to_delete')).toBeNull();
	});
});
