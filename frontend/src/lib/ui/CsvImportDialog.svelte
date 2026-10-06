<script lang="ts">
	import { _ } from '$lib/i18n';
	import CsvFormatGuide from './CsvFormatGuide.svelte';

	let dialog = $state<HTMLDialogElement>();

	/** Open the CSV import dialog with native focus management. */
	export function open() {
		dialog?.showModal();
	}
</script>

<dialog
	bind:this={dialog}
	class="modal"
	aria-labelledby="csv-import-title"
	aria-describedby="csv-import-description"
>
	<div class="modal-box">
		<h2 id="csv-import-title" class="text-lg font-bold">
			{$_('add.csv_import.title', { default: 'Import a CSV' })}
		</h2>
		<p id="csv-import-description" class="text-base-content/70 mt-2 text-sm">
			{$_('add.csv_import.description', {
				default:
					'Import your recipes from a spreadsheet, with one ingredient per row and quantities in grams.'
			})}
		</p>
		<CsvFormatGuide />
		<a
			href="/templates/recipes.csv"
			download="recipes-template.csv"
			class="link link-primary mt-2 inline-block text-sm"
		>
			{$_('add.csv_import.download_template', { default: 'Download CSV template' })}
		</a>
		<fieldset class="fieldset mt-4">
			<legend id="csv-file-label" class="fieldset-legend">
				{$_('add.csv_import.file_label', { default: 'Pick a file' })}
			</legend>
			<input
				id="csv-file"
				type="file"
				accept=".csv,text/csv"
				class="file-input w-full"
				aria-labelledby="csv-file-label"
				aria-describedby="csv-file-size"
			/>
			<label id="csv-file-size" class="label" for="csv-file">
				{$_('add.csv_import.max_size', { default: 'Max size 2MB' })}
			</label>
		</fieldset>
		<div class="modal-action">
			<form method="dialog">
				<button type="submit" class="btn btn-ghost">
					{$_('add.csv_import.close', { default: 'Close' })}
				</button>
			</form>
			<button type="button" class="btn btn-primary" disabled>
				{$_('add.csv_import.import_button', { default: 'Import' })}
			</button>
		</div>
	</div>
	<form method="dialog" class="modal-backdrop">
		<button type="submit">
			{$_('add.csv_import.close', { default: 'Close' })}
		</button>
	</form>
</dialog>
