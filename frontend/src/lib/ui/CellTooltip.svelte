<!-- Reuse the table-header tooltip for whole-cell hover and control focus. -->
<script lang="ts">
	import HelperTooltip from './HelperTooltip.svelte';
	let { tip, disabled = false }: { tip?: string; disabled?: boolean } = $props();
	let anchor = $state<HTMLDivElement>();
</script>

<div bind:this={anchor} class="contents">
	{#if !disabled && tip && anchor?.parentElement}
		<HelperTooltip {tip} floating trigger={anchor.parentElement} position="bottom" />
	{/if}
</div>
