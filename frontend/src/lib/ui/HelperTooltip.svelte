<script module lang="ts">
	// Monotonic counter guaranteeing a unique id per HelperTooltip instance,
	// so each button can point aria-describedby at its own instruction text.
	let tooltipCounter = 0;

	/** Returns a fresh, unique id for a tooltip's screen-reader description. */
	function nextTipId(): string {
		const id = `helper-tooltip-${tooltipCounter}`;
		tooltipCounter += 1;
		return id;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		tip: string;
		ariaLabel?: string;
		position?: 'top' | 'bottom' | 'left' | 'right';
		// Optional custom trigger icon rendered in place of the default info
		// icon, so callers can reuse this accessible tooltip wrapper for a
		// status icon (e.g. a "not accounted" stop icon).
		icon?: Snippet;
	};

	let { tip, ariaLabel = 'More information', position = 'top', icon }: Props = $props();

	let positionClass = $derived(`tooltip-${position}`);

	// Deterministic per render pass, so server-rendered and hydrated markup
	// produce matching ids (no hydration mismatch).
	const tipId = nextTipId();
</script>

<div
	class="tooltip {positionClass} tooltip-primary z-50 [&:before]:max-w-[160px] [&:before]:p-1.5 [&:before]:text-[0.65rem] [&:before]:leading-tight [&:before]:break-words [&:before]:whitespace-pre-wrap sm:[&:before]:max-w-[180px] sm:[&:before]:p-2 sm:[&:before]:text-xs"
	data-tip={tip}
>
	<button
		type="button"
		class="btn btn-ghost btn-xs hover:bg-primary/10 h-5 min-h-0 w-5 rounded-full p-0 transition-colors duration-200"
		aria-label={ariaLabel}
		aria-describedby={tipId}
	>
		{#if icon}
			<!-- Custom trigger icon provided by the caller (e.g. a status icon). -->
			{@render icon()}
		{:else}
			<svg
				xmlns="http://www.w3.org/2000/svg"
				viewBox="0 0 24 24"
				class="text-primary hover:text-primary/70 h-4 w-4 transition-colors duration-200"
				fill="currentColor"
			>
				<path
					d="M11 9h2V7h-2m1 13c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m0-18A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2m-1 15h2v-6h-2v6Z"
				/>
			</svg>
		{/if}
	</button>
	<!-- Screen-reader text: daisyUI renders the visible tooltip from data-tip
	     via a CSS pseudo-element, which assistive technology does not reliably
	     announce, so the same guidance is exposed here as real DOM content. -->
	<span id={tipId} class="sr-only">{tip}</span>
</div>
