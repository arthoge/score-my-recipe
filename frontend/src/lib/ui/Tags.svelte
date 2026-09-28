<!--
  Tags.svelte

  A Svelte component for managing a list of tags with autocomplete suggestions.
  It supports adding new tags, editing existing ones, and removing tags.

  Props:
    - tagtype: A string representing the type of tags (e.g., "labels", "origins")
	  for fetching relevant autocomplete suggestions.
	- tags: An array of TaxonomyItem representing the current tags.
	- single: A boolean indicating whether only a single tag is allowed (default: false).
	- id: An optional string to set the HTML id attribute for the root element.
	- onChange: A callback function that is called whenever the tags change.

  Features:
	- Add new tags by typing and pressing Enter or comma.
	- Edit existing tags by double-clicking them.
	- Remove tags using a close button.
	- Autocomplete suggestions appear when typing, with keyboard navigation support (ArrowUp/Down).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import type { Snippet } from 'svelte';
	import { fade } from 'svelte/transition';
	import debounce from 'lodash.debounce';
	import { getMatchingTags } from '$lib/api/taxonomy';
	import type { TaxonomyItem } from '$lib/types/ingredient';

	import IconMdiClose from '@iconify-svelte/mdi/close';

	type Props = {
		id?: string;
		tagtype: string;
		tags?: TaxonomyItem[];
		single?: boolean; // optional prop to allow only a single tag
		onChange?: (tags: TaxonomyItem[]) => void;
		// Optional snippet rendered before the label of each autocomplete suggestion.
		suggestionIcon?: Snippet<[TaxonomyItem]>;
	};

	type Suggestion = {
		item: TaxonomyItem;
	};

	let {
		id,
		tagtype,
		tags = $bindable([]),
		single = false,
		onChange,
		suggestionIcon
	}: Props = $props();

	let autoCompleteIndex = $state(-1);
	// suggestions returned by API
	let currentSuggestions = $state<Suggestion[]>([]);

	// tracking input values for both adding new tags and editing existing ones
	let newValue = $state('');
	let editingIndex = $state(-1);
	let editingValue = $state('');

	// Track active search value (newValue for additions, editingValue for inline edits)
	let activeSearchValue = $derived(editingIndex === -1 ? newValue : editingValue);

	// Reactive bounds check: reset suggestion index to -1 if list shrinks under it
	$effect(() => {
		if (autoCompleteIndex >= currentSuggestions.length) {
			autoCompleteIndex = -1;
		}
	});

	async function rawFetchSuggestions(value: string): Promise<void> {
		const q = value.trim();
		if (q.length < 3) {
			currentSuggestions = [];
			return;
		}
		try {
			const resp = await getMatchingTags(tagtype, q);
			// see later how to show synonyms in the UI
			currentSuggestions = resp.suggestions.map((s) => ({ item: s }));
		} catch (e) {
			console.error('Failed to fetch tag suggestions', e);
			currentSuggestions = [];
		}
	}
	// this will be the debounced version of rawFetchSuggestions, to avoid too many API calls
	let fetchSuggestions: ReturnType<typeof debounce> | undefined;

	onMount(() => {
		fetchSuggestions = debounce(rawFetchSuggestions, 500);
		return () => fetchSuggestions?.cancel?.();
	});

	// fetch suggestion as soon as inputValue changes
	$effect(() => {
		if (fetchSuggestions) {
			fetchSuggestions(activeSearchValue);
		}
	});

	/**
	 * Handle keyboard navigation (ArrowUp/Down) through autocomplete suggestions
	 * @param {KeyboardEvent} event
	 * @returns true if the event was handled, false otherwise
	 */
	function handleNavigationKeys(event: KeyboardEvent): boolean {
		if (currentSuggestions.length === 0) return false;

		if (event.key === 'ArrowDown') {
			event.preventDefault();
			if (autoCompleteIndex === -1) {
				autoCompleteIndex = 0;
			} else if (autoCompleteIndex < currentSuggestions.length - 1) {
				autoCompleteIndex += 1;
			}
			return true;
		} else if (event.key === 'ArrowUp') {
			event.preventDefault();
			if (autoCompleteIndex === -1) {
				autoCompleteIndex = currentSuggestions.length - 1;
			} else if (autoCompleteIndex > 0) {
				autoCompleteIndex -= 1;
			}
			return true;
		}
		return false;
	}

	/**
	 * Add a tag from the input field, either from the current suggestions or the typed value.
	 */
	function addTagInput() {
		if (autoCompleteIndex !== -1 && currentSuggestions[autoCompleteIndex]) {
			const selectedItem = currentSuggestions[autoCompleteIndex].item;
			newValue = selectedItem.label;
		}
		// don't validate empty tags
		if (newValue.trim() === '') {
			return;
		}
		// If we selected from suggestions, we have the full item object; otherwise create a new one
		const tag =
			autoCompleteIndex !== -1 && currentSuggestions[autoCompleteIndex]
				? currentSuggestions[autoCompleteIndex].item
				: tagFromStrValue(newValue);
		newValue = '';
		autoCompleteIndex = -1;
		addTag(tag);
	}

	/**
	 * Handle key events in the main input:
	 * Enter or comma will add the tag,
	 * Backspace will remove the last tag if input is empty,
	 * and Arrow keys will navigate suggestions.
	 * @param event
	 */
	function inputHandler(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ',') {
			addTagInput();
			event.preventDefault();
		} else if (newValue.length === 0 && event.key === 'Backspace') {
			tags = tags.slice(0, -1);
			onChange?.(tags);
		} else {
			handleNavigationKeys(event);
		}
	}

	/**
	 * Handle blur event on the input field to add the tag
	 * if the user clicks outside.
	 * @param event
	 */
	function inputBlurHandler(event: FocusEvent) {
		// If the blur event is caused by clicking on a suggestion, we don't want to add the tag yet
		const relatedTarget = event.relatedTarget as HTMLElement | null;
		if (relatedTarget && relatedTarget.closest('.dropdown-content')) {
			return;
		}
		addTagInput();
	}

	/**
	 * Add a new tag if it doesn't already exist.
	 *
	 * Trims whitespace and ignores empty tags. Logs a warning if the tag already exists.
	 * @param tag
	 */
	function addTag(tag: TaxonomyItem) {
		if (tags.some((t) => t.id === tag.id)) {
			console.warn(`Tag "${tag.label}" already exists.`);
			return;
		}
		tags = [...tags, tag];
		onChange?.(tags);
	}

	/**
	 * Remove a tag by filtering it out of the tags array.
	 * @param tag
	 */
	function removeTag(tag: TaxonomyItem) {
		tags = tags.filter((t) => t.id !== tag.id);
		onChange?.(tags);
	}

	/**
	 * Create an out of taxonomy TaxonomyItem from a string value
	 * @param value
	 */
	function tagFromStrValue(value: string): TaxonomyItem {
		return { id: value.trim(), label: value.trim(), isInTaxonomy: false };
	}

	/**
	 * Start editing a tag by setting the editing index and value. Also resets the autocomplete index to prevent stale suggestions.
	 * @param index
	 * @param tag
	 */
	function startEditing(index: number, tag: TaxonomyItem) {
		editingIndex = index;
		editingValue = tag.label;
		autoCompleteIndex = -1;
	}

	/**
	 * Save the edited tag by updating the tags array if the value has changed and is not empty. Resets editing state and autocomplete index afterward.
	 * @param index
	 */
	function saveEdit(index: number) {
		const trimmedValue = editingValue.trim();
		const originalTag = tags[index];
		if (trimmedValue !== '' && trimmedValue !== originalTag.label) {
			tags = tags.map((tag, i) => (i === index ? { ...originalTag, label: trimmedValue } : tag));
			onChange?.(tags);
		}
		editingIndex = -1;
		editingValue = '';
		autoCompleteIndex = -1;
	}

	/**
	 * Cancel editing by resetting the editing index and value,
	 * as well as the autocomplete index to prevent stale suggestions.
	 */
	function cancelEdit() {
		editingIndex = -1;
		editingValue = '';
		autoCompleteIndex = -1;
	}

	/**
	 * Handle key events in the edit input:
	 * Enter will save the edit,
	 * Escape will cancel it,
	 * and Arrow keys will navigate suggestions.
	 * @param event
	 * @param index
	 */
	function handleEditKeydown(event: KeyboardEvent, index: number) {
		if (event.key === 'Enter') {
			if (autoCompleteIndex !== -1 && currentSuggestions[autoCompleteIndex]) {
				editingValue = currentSuggestions[autoCompleteIndex].item.label;
				autoCompleteIndex = -1;
				event.preventDefault();
				return;
			}
			event.preventDefault();
			saveEdit(index);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			cancelEdit();
		} else {
			handleNavigationKeys(event);
		}
	}

	/**
	 * Handle selection of a suggestion from the autocomplete dropdown list.
	 * Selecting it from known values, or adding the value as a new value.
	 * @param item
	 */
	function selectSuggestion(item: TaxonomyItem) {
		if (editingIndex !== -1) {
			editingValue = item.label;
			const idx = editingIndex;
			setTimeout(() => saveEdit(idx), 0);
		} else {
			newValue = '';
			autoCompleteIndex = -1;
			addTag(item);
		}
	}

	/**
	 * Focus and select the content of an input element.
	 * @param element
	 */
	function focus(element: HTMLInputElement) {
		element.focus();
		element.select();
	}
</script>

<!-- Autocomplete Dropdown 
 Handles displaying autocomplete suggestions and keyboard navigation for both adding new tags and editing existing ones.
-->
{#snippet autocompleteDropdown()}
	{#if currentSuggestions.length > 0}
		<div
			class="dropdown-content bg-base-100 z-100 mt-1 w-full rounded-md shadow-lg focus:outline-none"
		>
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<ul tabindex="0" class="divide-base-200 divide-y">
				{#each currentSuggestions as suggestion, index (suggestion.item.id)}
					{@const item = suggestion.item}
					<li>
						<button
							type="button"
							class="bg-base-200 text-base-content hover:bg-primary hover:text-primary-content focus:bg-primary focus:text-primary-content flex w-full items-center gap-2 rounded-md px-4 py-2 text-left transition-colors duration-150"
							class:bg-primary={autoCompleteIndex === index}
							class:text-primary-content={autoCompleteIndex === index}
							onmousedown={(e) => {
								// Use mousedown instead of click to fire selectSuggestion before the input's blur event
								e.preventDefault();
								selectSuggestion(item);
							}}
						>
							{#if suggestionIcon}
								{@render suggestionIcon(item)}
							{/if}
							<span class="block truncate">{item.label}</span>
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
{/snippet}

<!-- Tag widget -->
<div
	{id}
	class="bg-base-100 border-base-200 focus-within:border-primary focus-within:outline-primary flex h-auto min-h-12 w-full flex-wrap gap-x-1.5 gap-y-1 rounded-md"
>
	<!-- each value of the tag (multi valued) -->
	{#each tags as tag, index (tag.id)}
		<div class="badge badge-ghost flex h-min items-center py-2" transition:fade={{ duration: 100 }}>
			{#if editingIndex === index}
				<!-- Existing tag editing input with autocomplete dropdown -->
				<div class="dropdown">
					<input
						type="text"
						class="input w-full min-w-0 border bg-transparent outline-none"
						bind:value={editingValue}
						onkeydown={(e) => handleEditKeydown(e, index)}
						onblur={() => {
							setTimeout(() => {
								if (editingIndex === index) saveEdit(index);
							}, 150);
						}}
						use:focus
					/>
					{@render autocompleteDropdown()}
				</div>
			{:else}
				<!-- Tag already added, visible as a label -->
				<span
					class="cursor-pointer truncate"
					ondblclick={() => startEditing(index, tag)}
					title="Double-click to edit"
					role="button"
					tabindex="0"
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							startEditing(index, tag);
						}
					}}
				>
					{tag.label}
				</span>
			{/if}
			<!-- Remove tag button -->
			<button
				class="hover:bg-base-300 ml-1 cursor-pointer p-1 leading-0"
				onclick={() => removeTag(tag)}
				aria-label={`Remove tag "${tag.label}"`}
			>
				<IconMdiClose class="h-4 w-4" />
			</button>
		</div>
	{/each}

	<!-- add a tag -->
	{#if !single || tags.length === 0}
		<div class="dropdown grow">
			<input
				type="text"
				class="input input-bordered w-full bg-transparent outline-hidden"
				onkeydown={inputHandler}
				onblur={inputBlurHandler}
				bind:value={newValue}
			/>
			{@render autocompleteDropdown()}
		</div>
	{/if}
</div>
