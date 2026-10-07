<!-- Fixed-height multi-select: removable badges in the cell and choices in a top-layer menu. -->
<script lang="ts">
	import { untrack } from 'svelte';
	import { _ } from '$lib/i18n';
	import type { TaxonomyItem } from '$lib/types/ingredient';
	import IconMdiClose from '@iconify-svelte/mdi/close';

	type Props = {
		value: TaxonomyItem[];
		options: TaxonomyItem[];
		status: 'loading' | 'ready' | 'failed';
	};
	let { value = $bindable(), options, status }: Props = $props();
	const menuId = $props.id();
	let menu = $state<HTMLDivElement>();
	let cell = $state<HTMLDivElement>();
	let searchInput = $state<HTMLInputElement>();
	let query = $state('');
	let isOpen = $state(false);
	let overflowMenu = $state<HTMLDivElement>();
	let isOverflowOpen = $state(false);
	const overflowMenuId = `${menuId}-overflow`;
	const badgeClasses =
		'label-badge badge badge-soft group pointer-events-auto min-w-0 max-w-28 gap-1';
	let visibleLabels = $derived(value.slice(0, 1));
	let overflowLabels = $derived(value.slice(1));

	$effect(() => {
		if (overflowLabels.length === 0) {
			untrack(() => {
				if (overflowMenu?.matches(':popover-open')) overflowMenu.hidePopover();
			});
		}
	});

	/** Remove a label consistently from the cell or overflow menu. */
	function removeLabel(tag: TaxonomyItem) {
		value = value.filter((item) => (item.id ?? item.label) !== (tag.id ?? tag.label));
	}
	let filteredOptions = $derived(
		options.filter((option) => {
			const search = query.trim().toLocaleLowerCase();
			return [option.label, ...(option.synonyms ?? [])].some((label) =>
				label.toLocaleLowerCase().includes(search)
			);
		})
	);

	/** Toggle a certification without allowing duplicate selections. */
	function toggle(option: TaxonomyItem) {
		value = value.some((item) => item.id === option.id)
			? value.filter((item) => item.id !== option.id)
			: [...value, option];
	}

	/** Anchor the choices to the cell without expanding the table row. */
	function positionMenu(target = menu) {
		if (!target || !cell) return;
		const rect = cell.getBoundingClientRect();
		const width = Math.min(280, window.innerWidth - 16);
		const below = window.innerHeight - rect.bottom - 8;
		const above = rect.top - 8;
		const height = Math.min(280, Math.max(below, above));
		target.style.width = `${width}px`;
		target.style.left = `${Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8))}px`;
		target.style.top = `${below >= Math.min(280, above) ? rect.bottom + 4 : Math.max(8, rect.top - height - 4)}px`;
		target.style.maxHeight = `${height}px`;
	}

	/** Reveal hidden selected labels without scrolling the cell. */
	function openOverflow() {
		if (!overflowMenu) return;
		positionMenu(overflowMenu);
		overflowMenu.togglePopover();
	}

	/** Keep filtering in the cell while displaying choices outside the table's scroll area. */
	function openMenu() {
		if (!menu) return;
		positionMenu();
		if (!menu.matches(':popover-open')) menu.showPopover();
		isOpen = true;
	}

	/** Open from anywhere in the unused cell area and focus its editable search text. */
	function openSearch() {
		openMenu();
		searchInput?.focus();
	}

	/** Add the first filtered unselected label with Enter; Escape dismisses the choices. */
	function handleSearchKey(event: KeyboardEvent) {
		if (event.key === 'Escape') closeMenu();
		if (event.key === 'Enter') {
			event.preventDefault();
			const option = filteredOptions.find((item) => !value.some((tag) => tag.id === item.id));
			if (status === 'ready' && option) {
				toggle(option);
				query = '';
			}
		}
	}

	/** Dismiss a menu whose cell moves during scrolling or resizing. */
	function closeMenu() {
		if (menu?.matches(':popover-open')) menu.hidePopover();
		if (overflowMenu?.matches(':popover-open')) overflowMenu.hidePopover();
	}
</script>

<svelte:window
	onscrollcapture={(event) => {
		const target = event.target;
		if (
			target instanceof Node &&
			(menu?.contains(target) || overflowMenu?.contains(target) || cell?.contains(target))
		)
			return;
		closeMenu();
	}}
	onresize={closeMenu}
/>

{#snippet badgeContent(tag: TaxonomyItem)}
	<span class="truncate">{tag.label}</span>
	<IconMdiClose
		class="group-hover:text-error group-focus-visible:text-error h-3 w-3 shrink-0"
		aria-hidden="true"
	/>
{/snippet}

{#snippet labelBadge(tag: TaxonomyItem)}
	<button
		type="button"
		class={badgeClasses}
		aria-label={$_('recipe.remove_label', {
			default: 'Remove {label}',
			values: { label: tag.label }
		})}
		title={tag.label}
		onclick={() => removeLabel(tag)}
	>
		{@render badgeContent(tag)}
	</button>
{/snippet}

<div bind:this={cell} class="relative flex h-[43px] min-w-0 items-center px-2">
	<button
		type="button"
		class="absolute inset-0 cursor-pointer"
		onclick={openSearch}
		aria-label={$_('recipe.select_labels', { default: 'Select labels' })}
		aria-expanded={isOpen}
		aria-controls={menuId}
	></button>
	<div class="pointer-events-none relative flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
		{#each visibleLabels as tag (tag.id ?? tag.label)}
			{@render labelBadge(tag)}
		{/each}
		{#if overflowLabels.length > 0}
			<button
				type="button"
				class="overflow-badge badge badge-soft pointer-events-auto shrink-0 cursor-default"
				onclick={openOverflow}
				aria-controls={overflowMenuId}
				aria-expanded={isOverflowOpen}
				aria-label={$_('recipe.more_labels', {
					default: 'Show {count} more labels',
					values: { count: overflowLabels.length }
				})}>+{overflowLabels.length}</button
			>
		{/if}
		<input
			bind:this={searchInput}
			bind:value={query}
			class="pointer-events-auto h-[43px] min-w-8 flex-1 border-0 bg-transparent text-sm outline-none"
			aria-label={$_('recipe.search_labels', { default: 'Search labels' })}
			aria-controls={menuId}
			aria-expanded={isOpen}
			onfocus={openMenu}
			onclick={openMenu}
			oninput={openMenu}
			onkeydown={handleSearchKey}
		/>
	</div>
</div>

<div
	bind:this={menu}
	id={menuId}
	popover="auto"
	ontoggle={(event) => {
		isOpen = event.newState === 'open';
		if (!isOpen) query = '';
	}}
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
		{:else if filteredOptions.length === 0}
			<p role="status">{$_('recipe.no_matching_labels', { default: 'No matching labels' })}</p>
		{:else}
			{#each filteredOptions as option (option.id)}
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

<div
	bind:this={overflowMenu}
	id={overflowMenuId}
	popover="auto"
	ontoggle={(event) => (isOverflowOpen = event.newState === 'open')}
	class="border-base-300 bg-base-100 text-base-content fixed m-0 overflow-y-auto rounded-lg border p-3 text-sm shadow-lg"
>
	<div class="flex flex-wrap gap-2">
		{#each overflowLabels as tag (tag.id ?? tag.label)}
			{@render labelBadge(tag)}
		{/each}
	</div>
</div>

<style>
	.label-badge,
	.overflow-badge {
		cursor: default;
		transition: background-color 150ms;
	}
	.label-badge:hover,
	.label-badge:focus-visible,
	.overflow-badge:hover,
	.overflow-badge:focus-visible {
		background: color-mix(in oklab, var(--color-base-content) 16%, var(--color-base-100));
	}
</style>
