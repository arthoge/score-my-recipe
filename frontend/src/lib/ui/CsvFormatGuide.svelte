<script lang="ts">
	import { _ } from '$lib/i18n';

	// Column order matches the downloadable template and the planned import API.
	const fields = [
		{ name: 'recipe_id', label: 'Recipe ID', required: true, example: 'salad-01' },
		{
			name: 'recipe_name',
			label: 'Recipe title',
			required: true,
			exampleKey: 'recipe_name',
			example: 'Tomato salad'
		},
		{ name: 'portions', label: 'Number of portions', required: true, example: '4' },
		{
			name: 'ingredient',
			label: 'Ingredient',
			required: true,
			exampleKey: 'ingredient',
			example: 'Tomatoes'
		},
		{ name: 'quantity_g', label: 'Quantity (grams)', required: true, example: '400' },
		{ name: 'state', label: 'Ingredient state', required: true, example: 'raw / cooked / drained' },
		{
			name: 'ciqual_code',
			label: 'Nutrition reference',
			required: false,
			exampleKey: 'ciqual_code',
			example: 'CIQUAL code'
		},
		{
			name: 'barcode',
			label: 'Product barcode',
			required: false,
			exampleKey: 'barcode',
			example: 'Product barcode'
		},
		{
			name: 'preparation_profile',
			label: 'Preparation profile',
			required: false,
			exampleKey: 'preparation_profile',
			example: 'Profile ID'
		},
		{ name: 'final_weight_g', label: 'Final dish weight (grams)', required: false, example: '1200' }
	];
</script>

<details class="collapse-arrow border-base-300 bg-base-200 collapse mt-4 border">
	<summary class="collapse-title text-sm font-medium">
		{$_('add.csv_import.format.title', { default: 'CSV format: required and optional columns' })}
	</summary>
	<div class="collapse-content">
		<p class="text-base-content/70 mb-3 text-xs">
			{$_('add.csv_import.format.description', {
				default:
					'Repeat the same recipe ID, name and portions for each ingredient in a recipe. Optional cells can be left blank.'
			})}
		</p>
		<!-- Make the scrollable table focusable so keyboard users can scroll it. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="max-h-64 overflow-auto"
			tabindex="0"
			role="region"
			aria-label={$_('add.csv_import.format.title', {
				default: 'CSV format: required and optional columns'
			})}
		>
			<table class="table-xs table w-full">
				<thead>
					<tr>
						<th scope="col">{$_('add.csv_import.format.field', { default: 'Field' })}</th>
						<th scope="col"
							>{$_('add.csv_import.format.requirement', { default: 'Requirement' })}</th
						>
						<th scope="col">{$_('add.csv_import.format.example', { default: 'Example' })}</th>
					</tr>
				</thead>
				<tbody>
					{#each fields as field (field.name)}
						<tr>
							<th scope="row" class="font-normal whitespace-normal">
								{$_(`add.csv_import.format.fields.${field.name}`, { default: field.label })}
							</th>
							<td>
								<span
									class:badge-primary={field.required}
									class:badge-ghost={!field.required}
									class="badge badge-sm"
								>
									{field.required
										? $_('add.csv_import.format.required', { default: 'Required' })
										: $_('add.csv_import.format.optional', { default: 'Optional' })}
								</span>
							</td>
							<td class="whitespace-normal">
								{field.exampleKey
									? $_(`add.csv_import.format.examples.${field.exampleKey}`, {
											default: field.example
										})
									: field.example}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</details>
