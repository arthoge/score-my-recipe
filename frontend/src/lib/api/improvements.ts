/** Typed recipe-level substitutions, recalculated and validated by the backend. */
import { env } from '$env/dynamic/public';
import type { components } from '../../api-schema';

export type ImprovementSuggestion = components['schemas']['ImprovementSuggestion'];
export type ImprovementResponse = components['schemas']['ImprovementResponse'];
export type ImprovementRequest = components['schemas']['ImprovementRequest'];
export type OptimizeResponse = components['schemas']['OptimizeResponse'];
export type ScoreChange = components['schemas']['ScoreChange'];

/** Request candidates or validate a selection, preserving cancellation across both steps. */
async function request<T>(path: string, payload: unknown, signal: AbortSignal): Promise<T> {
	const response = await fetch(`${env.PUBLIC_RECIPE_API_URL ?? ''}/v1/make-it-better/${path}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload),
		signal
	});
	if (!response.ok) throw new Error(`Recipe optimization failed: ${response.status}`);
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
