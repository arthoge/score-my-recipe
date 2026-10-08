<!-- Navigate from each score's excluded ingredients to the control that needs attention. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import IconMdiChevronRight from '@iconify-svelte/mdi/chevron-right';
	import { exclusionTarget, type ExclusionReason, type ExclusionKind } from './excludedIngredients';

	let {
		count,
		percent,
		reasons,
		recipeId
	}: {
		count: number;
		percent: number;
		reasons: ExclusionReason[];
		recipeId: string;
	} = $props();
	const id = $props.id();
	let trigger = $state<HTMLButtonElement>();
	let menu: HTMLDivElement;
	let open = $state(false);
	let position = $state({ left: 0, top: 0, width: 360, height: 320 });

	const labels: Record<ExclusionKind, string> = {
		agribalyse: 'Agribalyse reference',
		select_agribalyse: 'Agribalyse reference',
		ciqual: 'Ciqual reference',
		select_ciqual: 'Ciqual reference',
		state: 'Ciqual reference',
		off: 'Open Food Facts product',
		off_unavailable: 'Open Food Facts product',
		quantity: 'Quantity',
		preparation: 'Preparation'
	};

	/** Keep the dropdown inside the viewport, including on narrow screens. */
	function positionMenu() {
		if (!trigger) return;
		const rect = trigger.getBoundingClientRect();
		const width = Math.min(360, window.innerWidth - 16);
		const below = window.innerHeight - rect.bottom - 12;
		const above = rect.top - 12;
		const height = Math.min(320, Math.max(below, above));
		position = {
			left: Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)),
			top: below >= Math.min(320, above) ? rect.bottom + 4 : Math.max(8, rect.top - height - 4),
			width,
			height
		};
	}

	/** Close the menu before opening Details and focusing the selected row's input. */
	function focusReference(reason: ExclusionReason) {
		menu.hidePopover();
		const target = exclusionTarget(recipeId, reason);
		if (target.dialogId) {
			const dialog = document.getElementById(target.dialogId);
			if (dialog instanceof HTMLDialogElement && !dialog.open) dialog.showModal();
		}
		const input = document.getElementById(target.inputId);
		input?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
		input?.focus({ preventScroll: true });
	}
</script>

<svelte:window
	onresize={() => {
		if (open) positionMenu();
	}}
	onscrollcapture={() => {
		if (open) positionMenu();
	}}
/>

<button
	bind:this={trigger}
	type="button"
	class="btn btn-ghost -mx-2 mt-3 h-auto min-h-0 w-fit max-w-[calc(100%+1rem)] justify-start gap-1 px-2 py-1 text-left text-sm font-semibold whitespace-normal"
	popovertarget={id}
	aria-expanded={open}
	aria-controls={id}
	disabled={!reasons.length}
>
	<span>
		{$_('recipe.excluded_summary', {
			default: '{count} ingredient(s) excluded ({percent}% of recipe weight).',
			values: { count, percent }
		})}
	</span>
	<IconMdiChevronRight class="h-5 w-5 shrink-0" aria-hidden="true" />
</button>

<div
	bind:this={menu}
	{id}
	popover="auto"
	class="bg-base-100 border-base-300 rounded-box fixed inset-auto m-0 overflow-auto border p-2 text-left shadow-lg"
	style:left="{position.left}px"
	style:top="{position.top}px"
	style:width="{position.width}px"
	style:max-height="{position.height}px"
	aria-labelledby="{id}-title"
	onbeforetoggle={(event) => {
		if (event.newState === 'open') positionMenu();
	}}
	ontoggle={(event) => (open = event.newState === 'open')}
>
	<h4 id="{id}-title" class="px-3 py-2 text-sm font-semibold">
		{$_('recipe.missing_data', { default: 'Missing data' })}
	</h4>
	<ul>
		{#each reasons as reason (`${reason.ingredientId}-${reason.kind}`)}
			<li>
				<button
					type="button"
					class="hover:bg-base-200 flex w-full items-center justify-between gap-3 rounded px-3 py-2 text-left text-sm"
					onclick={() => focusReference(reason)}
				>
					<span class="min-w-0">
						<span class="block wrap-anywhere">{reason.name}</span>
						<span class="text-base-content/60 block text-xs"
							>{$_(`recipe.excluded_fields.${reason.kind}`, { default: labels[reason.kind] })}</span
						>
					</span>
					<IconMdiChevronRight class="h-5 w-5 shrink-0" aria-hidden="true" />
				</button>
			</li>
		{/each}
	</ul>
</div>
