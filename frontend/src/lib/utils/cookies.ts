/**
 * Cookie utilities for reading and writing client-side cookies.
 */

/**
 * Get the value of a cookie by name.
 * Returns null if not found, if running on the server, or if the stored value
 * cannot be decoded (malformed percent-encoding).
 */
export function getCookie(name: string): string | null {
	if (typeof document === 'undefined') return null;
	const escapedName = name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1');
	const regex = new RegExp(`(?:^|; )${escapedName}=([^;]*)`);
	const match = document.cookie.match(regex);
	if (!match) return null;
	try {
		return decodeURIComponent(match[1]);
	} catch {
		// Malformed percent-encoded value; treat the cookie as absent.
		return null;
	}
}

export type CookieOptions = {
	maxAge?: number; // In seconds (default: 1 year)
	path?: string; // Default: '/'
	sameSite?: 'Lax' | 'Strict' | 'None'; // Default: 'Lax'
	secure?: boolean;
};

/**
 * Set a cookie with name, value, and options.
 */
export function setCookie(name: string, value: string, options: CookieOptions = {}): void {
	if (typeof document === 'undefined') return;
	const { maxAge = 31536000, path = '/', sameSite = 'Lax', secure } = options;

	let cookieStr = `${encodeURIComponent(name)}=${encodeURIComponent(value)}; max-age=${maxAge}; path=${path}; SameSite=${sameSite}`;
	if (secure) {
		cookieStr += '; Secure';
	}
	document.cookie = cookieStr;
}

/**
 * Delete a cookie by name.
 */
export function deleteCookie(name: string, path = '/'): void {
	if (typeof document === 'undefined') return;
	document.cookie = `${encodeURIComponent(name)}=; max-age=0; path=${path}`;
}
