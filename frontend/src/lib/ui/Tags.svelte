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
	import { findMatchingSuggestion } from '$lib/utils/taxonomyMatch';
	import type { TaxonomyItem } from '$lib/types/ingredient';

	import IconMdiClose from '@iconify-svelte/mdi/close';
	import { _ } from '$lib/i18n';

	type Props = {
		id?: string;
		tagtype: string;
		tags?: TaxonomyItem[];
		single?: boolean; // optional prop to allow only a single tag
		onChange?: (tags: TaxonomyItem[]) => void;
		// Optional snippet rendered before the label of each autocomplete suggestion.
		suggestionIcon?: Snippet<[TaxonomyItem]>;
		// When true, the widget border turns red to signal an invalid/unresolved
		// value (e.g. an ingredient missing from the green-score computation).
		invalid?: boolean;
		/** Accessible name for the widget's editable inputs. */
		ariaLabel?: string;
		/** Keep suggestions in the row flow inside a scrollable ingredient table. */
		inlineSuggestions?: boolean;
		/** Render a single value as a borderless editor that fills a table cell. */
		cell?: boolean;
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
		suggestionIcon,
		invalid = false,
		ariaLabel,
		inlineSuggestions = false,
		cell = false
	}: Props = $props();

	// Border treatment mirrors the focus state: red when invalid, otherwise the
	// default base/primary colours. A border width is only applied when invalid
	// so the normal (valid) layout is unchanged.
	let borderClass = $derived(
		invalid
			? 'border border-error focus-within:border-error focus-within:outline-error'
			: 'border-base-200 focus-within:border-primary focus-within:outline-primary'
	);

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
	 * @param index
	 */
	function removeTag(index: number) {
		tags = tags.filter((_, i) => i !== index);
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
	 * Commit an in-progress edit by replacing the tag at `index` with `newTag`,
	 * then reset the editing state. Shared by the suggestion-selection and
	 * free-typed edit paths so they always leave a consistent state.
	 * @param index - Index of the tag being edited.
	 * @param newTag - The tag replacing the edited one.
	 */
	function applyEdit(index: number, newTag: TaxonomyItem) {
		if (newTag.isInTaxonomy && tags.some((tag, i) => i !== index && tag.id === newTag.id)) {
			console.warn(`Tag "${newTag.label}" already exists.`);
			cancelEdit();
			return;
		}
		tags = tags.map((tag, i) => (i === index ? newTag : tag));
		onChange?.(tags);
		editingIndex = -1;
		editingValue = '';
		autoCompleteIndex = -1;
	}

	/**
	 * Save a free-typed edit, i.e. a value typed by the user and submitted on
	 * Enter/blur without being picked from the autocomplete suggestions.
	 *
	 * If the typed value exactly matches a proposed suggestion (by label or
	 * synonym), it is registered as if the user had clicked it, keeping the
	 * taxonomy id in sync with the selected item. Otherwise the id is reset to
	 * `null` (and `isInTaxonomy` to false): the tag must not keep being matched
	 * against the old taxonomy node.
	 *
	 * An empty value, an unchanged label, or a value already resolved to the
	 * current item simply cancels the edit.
	 * @param index - Index of the tag being edited.
	 */
	function saveEdit(index: number) {
		const trimmedValue = editingValue.trim();
		const originalTag = tags[index];

		// A free-typed value that exactly matches a proposed suggestion (by label
		// or synonym) is registered as if the user had clicked it, keeping the
		// taxonomy id in sync instead of resetting it to null.
		const matched =
			trimmedValue !== ''
				? findMatchingSuggestion(
						trimmedValue,
						currentSuggestions.map((s) => s.item)
					)
				: undefined;

		if (matched && matched.id !== originalTag.id) {
			// resolved to a (different) taxonomy item
			applyEdit(index, matched);
		} else if (!matched && trimmedValue !== '' && trimmedValue !== originalTag.label) {
			// genuine free-text value not in the suggestions: reset the id to null
			applyEdit(index, { id: null, label: trimmedValue, isInTaxonomy: false });
		} else {
			// empty, unchanged, or already resolved to the current item: cancel
			editingIndex = -1;
			editingValue = '';
			autoCompleteIndex = -1;
		}
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
				// Enter on a highlighted suggestion: commit the full taxonomy item
				// (id + label) instead of just copying its label, so the id stays
				// in sync with the selected suggestion.
				event.preventDefault();
				applyEdit(index, currentSuggestions[autoCompleteIndex].item);
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
			// A suggestion was explicitly selected while editing: replace the
			// edited tag with the full taxonomy item (id + label), keeping the id
			// in sync with the selection.
			applyEdit(editingIndex, item);
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
			class="bg-base-100 z-100 mt-1 w-full rounded-md shadow-lg focus:outline-none"
			class:dropdown-content={!inlineSuggestions}
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
	class={cell
		? 'flex min-h-10 w-full flex-wrap items-center'
		: `bg-base-100 ${borderClass} flex h-auto min-h-12 w-full flex-wrap gap-x-1.5 gap-y-1 rounded-md`}
	class:text-error={cell && invalid}
>
	<!-- each value of the tag (multi valued) -->
	{#each tags as tag, index (tag)}
		<div
			class={cell
				? 'group flex min-h-10 w-full items-center'
				: 'badge badge-ghost flex h-min items-center py-2'}
			transition:fade={{ duration: 100 }}
		>
			{#if editingIndex === index}
				<!-- Existing tag editing input with autocomplete dropdown -->
				<div class={cell ? 'dropdown min-w-0 grow' : 'dropdown'}>
					<input
						type="text"
						class={cell
							? 'block min-h-10 w-full min-w-0 bg-transparent px-3 py-2 text-sm focus:outline-none'
							: 'input w-full min-w-0 border bg-transparent outline-none'}
						bind:value={editingValue}
						aria-label={ariaLabel}
						onkeydown={(e) => handleEditKeydown(e, index)}
						onblur={() => {
							setTimeout(() => {
								saveEdit(index);
							}, 150);
						}}
						use:focus
					/>
					{@render autocompleteDropdown()}
				</div>
			{:else}
				<!-- Tag already added, visible as a label -->
				<span
					class={cell
						? 'flex min-h-10 min-w-0 grow cursor-text items-center px-3 py-2 text-sm'
						: 'cursor-pointer truncate'}
					onclick={() => {
						if (cell) startEditing(index, tag);
					}}
					ondblclick={() => {
						if (!cell) startEditing(index, tag);
					}}
					title={$_(cell ? 'recipe.edit_ingredient_hint' : 'recipe.edit_tag_hint', {
						default: cell ? 'Click to edit' : 'Double-click to edit'
					})}
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
				class={cell
					? 'hover:bg-base-300 mr-2 cursor-pointer p-1 opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 focus:opacity-100'
					: 'hover:bg-base-300 ml-1 cursor-pointer p-1 leading-0'}
				onclick={() => removeTag(index)}
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
				class={cell
					? 'block min-h-10 w-full bg-transparent px-3 py-2 text-sm focus:outline-none'
					: 'input input-bordered w-full bg-transparent outline-hidden'}
				placeholder={cell
					? $_('recipe.add_ingredient_placeholder', { default: 'Add an ingredient…' })
					: undefined}
				onkeydown={inputHandler}
				onblur={inputBlurHandler}
				bind:value={newValue}
				aria-label={ariaLabel}
			/>
			{@render autocompleteDropdown()}
		</div>
	{/if}
</div>
