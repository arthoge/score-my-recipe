<!-- Fixed-height multi-select: removable badges in the cell and choices in a top-layer menu. -->
<script lang="ts">
	import { _ } from '$lib/i18n';
	import type { TaxonomyItem } from '$lib/types/ingredient';
	import IconMdiClose from '@iconify-svelte/mdi/close';
	import IconMdiChevronDown from '@iconify-svelte/mdi/chevron-down';

	type Props = {
		value: TaxonomyItem[];
		options: TaxonomyItem[];
		status: 'loading' | 'ready' | 'failed';
	};
	let { value = $bindable(), options, status }: Props = $props();
	const menuId = $props.id();
	let menu = $state<HTMLDivElement>();

	/** Toggle a certification without allowing duplicate selections. */
	function toggle(option: TaxonomyItem) {
		value = value.some((item) => item.id === option.id)
			? value.filter((item) => item.id !== option.id)
			: [...value, option];
	}

	/** Anchor the choices to the cell without expanding the table row. */
	function positionMenu(event: MouseEvent) {
		if (!menu) return;
		const rect = (event.currentTarget as HTMLButtonElement).getBoundingClientRect();
		const width = Math.min(280, window.innerWidth - 16);
		const below = window.innerHeight - rect.bottom - 8;
		const above = rect.top - 8;
		const height = Math.min(280, Math.max(below, above));
		menu.style.width = `${width}px`;
		menu.style.left = `${Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8))}px`;
		menu.style.top = `${below >= Math.min(280, above) ? rect.bottom + 4 : Math.max(8, rect.top - height - 4)}px`;
		menu.style.maxHeight = `${height}px`;
	}

	/** Dismiss a menu whose cell moves during scrolling or resizing. */
	function closeMenu() {
		if (menu?.matches(':popover-open')) menu.hidePopover();
	}
</script>

<svelte:window
	onscrollcapture={(event) => {
		if (event.target !== menu) closeMenu();
	}}
	onresize={closeMenu}
/>

<div class="flex h-[43px] min-w-0 items-center gap-1 px-2">
	<div class="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
		{#each value as tag, index (tag.id ?? tag.label)}
			<button
				type="button"
				class="badge badge-soft group max-w-36 shrink-0 cursor-pointer gap-1"
				aria-label={$_('recipe.remove_label', {
					default: 'Remove {label}',
					values: { label: tag.label }
				})}
				title={tag.label}
				onclick={() => (value = value.filter((_, itemIndex) => itemIndex !== index))}
			>
				<span class="truncate">{tag.label}</span>
				<IconMdiClose
					class="group-hover:text-error group-focus-visible:text-error h-3 w-3 shrink-0"
					aria-hidden="true"
				/>
			</button>
		{/each}
	</div>
	<button
		type="button"
		class="btn btn-ghost btn-square btn-xs shrink-0"
		popovertarget={menuId}
		onclick={positionMenu}
		aria-label={$_('recipe.select_labels', { default: 'Select labels' })}
	>
		<IconMdiChevronDown class="h-4 w-4" aria-hidden="true" />
	</button>
</div>

<div
	bind:this={menu}
	id={menuId}
	popover="auto"
	class="border-base-300 bg-base-100 text-base-content fixed m-0 overflow-y-auto rounded-lg border p-2 text-sm shadow-lg"
>
	<fieldset>
		<legend class="sr-only">{$_('recipe.select_labels', { default: 'Select labels' })}</legend>
		{#if status === 'loading'}
			<p role="status">{$_('recipe.search_loading', { default: 'Searching…' })}</p>
		{:else if status === 'failed'}
			<p role="status">
				{$_('recipe.search_failed', { default: 'Search unavailable. Try again.' })}
			</p>
		{:else if options.length === 0}
			<p>{$_('recipe.no_labels_available', { default: 'No labels available' })}</p>
		{:else}
			{#each options as option (option.id)}
				<label class="hover:bg-base-200 flex cursor-pointer items-center gap-2 rounded px-2 py-2">
					<input
						type="checkbox"
						class="checkbox checkbox-sm"
						checked={value.some((item) => item.id === option.id)}
						onchange={() => toggle(option)}
					/>
					<span>{option.label}</span>
				</label>
			{/each}
		{/if}
	</fieldset>
</div>
