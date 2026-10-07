<script lang="ts">
	import { onDestroy, type Snippet } from 'svelte';

	type Props = {
		tip: string;
		ariaLabel?: string;
		position?: 'top' | 'bottom' | 'left' | 'right';
		/** Render a hover and focus bubble above scrolling containers. */
		floating?: boolean;
		// Optional custom trigger icon rendered in place of the default info
		// icon, so callers can reuse this accessible tooltip wrapper for a
		// status icon (e.g. a "not accounted" stop icon).
		icon?: Snippet;
	};

	let {
		tip,
		ariaLabel = 'More information',
		position = 'top',
		floating = false,
		icon
	}: Props = $props();

	let positionClass = $derived(`tooltip-${position}`);

	// Svelte keeps this id consistent between server rendering and hydration.
	const tipId = $props.id();
	let bubble = $state<HTMLDivElement>();
	let triggerButton = $state<HTMLButtonElement>();
	let closeTimer: ReturnType<typeof setTimeout>;
	onDestroy(() => clearTimeout(closeTimer));

	/** Place the top-layer bubble within the viewport before its native toggle opens it. */
	function positionBubble(event: MouseEvent | FocusEvent) {
		if (!floating || !bubble) return;
		const trigger = (event.currentTarget as HTMLButtonElement).getBoundingClientRect();
		const width = Math.min(240, window.innerWidth - 16);
		bubble.style.width = `${width}px`;
		bubble.style.left = `${Math.max(8, Math.min(trigger.right - width, window.innerWidth - width - 8))}px`;
		bubble.style.top = `${trigger.bottom + 8}px`;
		bubble.style.maxHeight = `${Math.max(40, window.innerHeight - trigger.bottom - 16)}px`;
	}

	/** Show the same help on pointer hover and keyboard focus. */
	function showBubble(event: PointerEvent | FocusEvent) {
		if (!floating || !bubble) return;
		clearTimeout(closeTimer);
		positionBubble(event);
		if (!bubble.matches(':popover-open')) bubble.showPopover();
	}

	/** Allow moving onto the bubble to read it; keyboard focus also keeps it visible. */
	function scheduleClose() {
		if (!floating) return;
		clearTimeout(closeTimer);
		closeTimer = setTimeout(() => {
			if (!triggerButton?.matches(':focus') && !bubble?.matches(':hover')) closeBubble();
		}, 150);
	}

	/** Close a floating bubble when scrolling moves its table header. */
	function closeBubble() {
		clearTimeout(closeTimer);
		if (floating && bubble?.matches(':popover-open')) bubble.hidePopover();
	}
</script>

<svelte:window onscrollcapture={closeBubble} onresize={closeBubble} />

<div
	class="{floating
		? 'shrink-0'
		: 'tooltip'} {positionClass} tooltip-primary z-50 [&:before]:max-w-[160px] [&:before]:p-1.5 [&:before]:text-[0.65rem] [&:before]:leading-tight [&:before]:break-words [&:before]:whitespace-pre-wrap sm:[&:before]:max-w-[180px] sm:[&:before]:p-2 sm:[&:before]:text-xs"
	data-tip={floating ? undefined : tip}
>
	<button
		bind:this={triggerButton}
		type="button"
		class="btn btn-ghost btn-xs hover:bg-primary/10 h-5 min-h-0 w-5 rounded-full p-0 transition-colors duration-200"
		aria-label={ariaLabel}
		aria-describedby={tipId}
		popovertarget={floating ? tipId : undefined}
		popovertargetaction="show"
		onclick={positionBubble}
		onpointerenter={showBubble}
		onpointerleave={scheduleClose}
		onfocus={showBubble}
		onblur={closeBubble}
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
	{#if floating}
		<div
			bind:this={bubble}
			id={tipId}
			popover="auto"
			role="tooltip"
			onpointerenter={() => clearTimeout(closeTimer)}
			onpointerleave={scheduleClose}
			class="bg-primary text-primary-content fixed m-0 overflow-auto rounded-lg border-0 p-3 text-left text-xs leading-relaxed font-normal whitespace-normal shadow-lg"
		>
			{tip}
		</div>
	{:else}
		<span id={tipId} class="sr-only">{tip}</span>
	{/if}
</div>
