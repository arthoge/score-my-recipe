/** Typed recipe-level substitutions, recalculated and validated by the backend. */
import { env } from '$env/dynamic/public';
import type { components } from '../../api-schema';

export type ImprovementSuggestion = components['schemas']['ImprovementSuggestion'];
export type ImprovementResponse = components['schemas']['ImprovementResponse'];
export type ImprovementRequest = components['schemas']['ImprovementRequest'];
export type OptimizeResponse = components['schemas']['OptimizeResponse'];
export type ScoreChange = components['schemas']['ScoreChange'];

/** Known validation failures have localized explanations in the dialog. */
export class ImprovementError extends Error {
	constructor(public reason: 'failed' | 'selection_unavailable' | 'no_combined_gain') {
		super(`Recipe optimization failed: ${reason}`);
	}
}

/** Request candidates or validate a selection, preserving cancellation across both steps. */
async function request<T>(path: string, payload: unknown, signal: AbortSignal): Promise<T> {
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/make-it-better/${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload),
		signal
	});
	if (!response.ok) {
		const body = await response.json().catch(() => null);
		const detail = body?.detail;
		if (response.status === 409 && detail === 'Selected suggestions are no longer available') {
			throw new ImprovementError('selection_unavailable');
		}
		if (
			response.status === 409 &&
			detail === 'Selected changes do not improve the combined recipe scores'
		) {
			throw new ImprovementError('no_combined_gain');
		}
		throw new ImprovementError('failed');
	}
	return response.json() as Promise<T>;
}

/** Calculate each proposed substitution against the same recipe snapshot. */
export function checkImprovements(payload: ImprovementRequest, signal: AbortSignal) {
	return request<ImprovementResponse>('check', payload, signal);
}

/** Recalculate selected changes together; a rejected combination never changes the editor. */
export function optimizeRecipe(
	payload: ImprovementRequest,
	selectedIds: string[],
	signal: AbortSignal
) {
	return request<OptimizeResponse>('optimize', { ...payload, selected_ids: selectedIds }, signal);
}
