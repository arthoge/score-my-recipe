<!-- Reuse the table-header tooltip for whole-cell hover and control focus. -->
<script lang="ts">
	import HelperTooltip from './HelperTooltip.svelte';
	let { tip }: { tip?: string } = $props();
	let anchor = $state<HTMLDivElement>();
</script>

<div bind:this={anchor} class="contents">
	{#if tip && anchor?.parentElement}
		<HelperTooltip {tip} floating trigger={anchor.parentElement} position="bottom" />
	{/if}
</div>
