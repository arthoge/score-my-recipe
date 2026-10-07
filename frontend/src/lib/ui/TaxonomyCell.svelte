<!-- A fixed-height cell editor with autocomplete in the browser's top layer. -->
<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { _ } from '$lib/i18n';
	import { getMatchingTags } from '$lib/api/taxonomy';
	import { findMatchingSuggestion } from '$lib/utils/taxonomyMatch';
	import type { TaxonomyItem } from '$lib/types/ingredient';

	type Props = {
		id: string;
		tagtype?: string;
		/** Optional reference provider for food or product searches. */
		getSuggestions?: (
			query: string,
			limit: number,
			signal?: AbortSignal
		) => Promise<TaxonomyItem[]>;
		tags: TaxonomyItem[];
		label: string;
		multiple?: boolean;
		invalid?: boolean;
		/** The ingredient name is being matched before this reference has a value. */
		backgroundLoading?: boolean;
		/** Background suggestions can be shown even before this cell has been edited. */
		initialSuggestions?: TaxonomyItem[];
		searchTerm?: string;
		onchange: (tags: TaxonomyItem[]) => void;
	};
	let {
		id,
		tagtype = 'ingredients',
		getSuggestions,
		tags,
		label,
		multiple = false,
		invalid = false,
		backgroundLoading = false,
		initialSuggestions = [],
		searchTerm = '',
		onchange
	}: Props = $props();
	let input = $state<HTMLInputElement>();
	let menu = $state<HTMLDivElement>();
	let focused = $state(false);
	let dismissed = $state(false);
	let value = $state('');
	let suggestions = $state<TaxonomyItem[]>([]);
	let loading = $state(false);
	let searchFailed = $state(false);
	let searched = $state(false);
	let activeIndex = $state(-1);
	let position = $state({ left: 0, top: 0, width: 0, height: 240 });
	let query = $derived((multiple ? (value.split(',').at(-1) ?? '') : value || searchTerm).trim());

	$effect(() => {
		// Keep imported references visible without overwriting an in-progress edit.
		const text = tags.map((tag) => tag.label).join(', ');
		if (!untrack(() => focused)) value = text;
	});

	/** Anchor the top-layer menu to its cell, including after horizontal scrolling. */
	function positionMenu() {
		if (!input || !menu || !focused) return;
		const rect = input.getBoundingClientRect();
		const below = window.innerHeight - rect.bottom - 8;
		const above = rect.top - 8;
		const height = Math.min(240, Math.max(below, above));
		const width = Math.min(Math.max(rect.width, 240), window.innerWidth - 16);
		position = {
			left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
			top: below >= Math.min(240, above) ? rect.bottom + 4 : Math.max(8, rect.top - height - 4),
			width,
			height
		};
	}

	onMount(() => {
		window.addEventListener('scroll', positionMenu, true);
		window.addEventListener('resize', positionMenu);
		return () => {
			window.removeEventListener('scroll', positionMenu, true);
			window.removeEventListener('resize', positionMenu);
		};
	});

	$effect(() => {
		const search = query;
		const enabled = focused && !dismissed && search.length >= 3;
		const provider = getSuggestions;
		const preloaded = query === searchTerm.trim() ? initialSuggestions : [];
		suggestions = preloaded;
		loading = enabled && preloaded.length === 0;
		searchFailed = false;
		searched = false;
		activeIndex = -1;
		let cancelled = false;
		const controller = new AbortController();
		const timer =
			enabled && preloaded.length === 0
				? setTimeout(async () => {
						try {
							const result = provider
								? await provider(search, 8, controller.signal)
								: (await getMatchingTags(tagtype, search, 8)).suggestions;
							if (!cancelled) suggestions = result;
						} catch {
							// Leave the typed draft intact when the reference service is unavailable.
							if (!cancelled) searchFailed = true;
						} finally {
							if (!cancelled) {
								loading = false;
								searched = true;
							}
						}
					}, 250)
				: undefined;
		return () => {
			cancelled = true;
			controller.abort();
			clearTimeout(timer);
		};
	});

	$effect(() => {
		const open =
			focused &&
			!dismissed &&
			(suggestions.length > 0 || (getSuggestions && (loading || searched)));
		untrack(() => {
			if (!menu) return;
			if (open) {
				positionMenu();
				if (!menu.matches(':popover-open')) menu.showPopover();
			} else if (menu.matches(':popover-open')) menu.hidePopover();
		});
	});

	/** Preserve existing references for unchanged labels; edited values become drafts. */
	function editedTags(text: string): TaxonomyItem[] {
		const names = (multiple ? text.split(',') : [text]).map((name) => name.trim()).filter(Boolean);
		return names.map(
			(name) =>
				tags.find((tag) => tag.label === name) ??
				findMatchingSuggestion(name, suggestions) ?? { id: null, label: name, isInTaxonomy: false }
		);
	}

	/** Commit typed text immediately so an old score is invalidated while editing. */
	function edit(event: Event) {
		value = (event.target as HTMLInputElement).value;
		dismissed = false;
		onchange(editedTags(value));
	}

	/** Select a reference while retaining other labels in a multi-value cell. */
	function choose(item: TaxonomyItem) {
		const previous = multiple ? editedTags(value.split(',').slice(0, -1).join(',')) : [];
		const selected = [...previous.filter((tag) => tag.id !== item.id), item];
		value = selected.map((tag) => tag.label).join(', ');
		onchange(selected);
		dismissed = true;
		input?.focus();
	}

	/** Keep arrow navigation and Enter selection inside the autocomplete. */
	function keydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dismissed = true;
			return;
		}
		if (event.key === 'Enter') {
			event.preventDefault();
			if (activeIndex >= 0 && suggestions[activeIndex]) choose(suggestions[activeIndex]);
			else {
				onchange(editedTags(value));
				dismissed = true;
			}
			return;
		}
		if (suggestions.length && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
			event.preventDefault();
			activeIndex =
				activeIndex < 0
					? event.key === 'ArrowDown'
						? 0
						: suggestions.length - 1
					: (activeIndex + (event.key === 'ArrowDown' ? 1 : -1) + suggestions.length) %
						suggestions.length;
		}
	}
</script>

<div class="relative h-[43px]">
	<input
		bind:this={input}
		{id}
		type="text"
		class="cell-input"
		{value}
		aria-label={label}
		aria-invalid={invalid}
		aria-busy={backgroundLoading}
		role="combobox"
		aria-autocomplete="list"
		aria-expanded={focused &&
			!dismissed &&
			(suggestions.length > 0 || (!!getSuggestions && (loading || searched)))}
		aria-controls="{id}-options"
		aria-activedescendant={activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
		autocomplete="off"
		oninput={edit}
		onkeydown={keydown}
		onfocus={() => {
			focused = true;
			dismissed = false;
		}}
		onblur={() => {
			focused = false;
			onchange(editedTags(value));
		}}
	/>

	{#if backgroundLoading && !focused && !value}
		<div
			class="skeleton pointer-events-none absolute top-1/2 left-3 h-4 w-2/3 -translate-y-1/2 rounded"
			aria-hidden="true"
		></div>
	{/if}
</div>

<!-- Native popovers escape the table's overflow clipping without changing row height.
     https://developer.mozilla.org/en-US/docs/Web/API/Popover_API -->
<div
	bind:this={menu}
	popover="manual"
	class="bg-base-100 border-base-300 rounded-box fixed inset-auto m-0 overflow-auto border p-1 shadow-lg"
	style:left="{position.left}px"
	style:top="{position.top}px"
	style:width="{position.width}px"
	style:max-height="{position.height}px"
>
	<div id="{id}-options" role="listbox" aria-label={label}>
		{#each suggestions as suggestion, index (`${suggestion.id}-${index}`)}
			<button
				id="{id}-option-{index}"
				type="button"
				role="option"
				aria-selected={index === activeIndex}
				class="hover:bg-base-200 w-full rounded px-3 py-2 text-left text-sm"
				class:bg-base-200={index === activeIndex}
				tabindex="-1"
				onpointerdown={(event) => event.preventDefault()}
				onclick={() => choose(suggestion)}
			>
				{suggestion.label}
			</button>
		{/each}
	</div>
	{#if getSuggestions && suggestions.length === 0}
		<p class="text-base-content/70 px-3 py-2 text-sm" role="status">
			{loading
				? $_('recipe.search_loading', { default: 'Searching…' })
				: searchFailed
					? $_('recipe.search_failed', { default: 'Search unavailable. Try again.' })
					: $_('recipe.search_empty', { default: 'No matching foods or products.' })}
		</p>
	{/if}
</div>
