<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<!-- Desktop: grid table -->
		<div class="hidden min-h-0 flex-1 overflow-x-auto px-5 md:block">
			<div :style="{ minWidth: minWidth }">
				<div
					class="sticky top-0 z-[1] grid h-8 items-center gap-3 rounded-3 bg-ch-subtle px-3 text-[13px] text-ch-ink-3"
					:style="gridStyle"
					role="row"
				>
					<div v-if="selectable" class="flex items-center">
						<Checkbox
							:model-value="allSelected"
							aria-label="Select all"
							@update:model-value="toggleAll"
						/>
					</div>
					<div
						v-for="col in columns"
						:key="col.key"
						role="columnheader"
						class="truncate"
						:class="col.align === 'right' ? 'text-right' : ''"
					>
						<button
							v-if="col.sortable"
							class="inline-flex max-w-full items-center gap-1 rounded-1 hover:text-ch-ink"
							:class="sortField === col.key ? 'text-ch-ink' : ''"
							@click="$emit('sort', col.key)"
						>
							<span class="truncate">{{ col.label }}</span>
							<span
								v-if="sortField === col.key"
								class="size-3.5 shrink-0"
								:class="sortOrder === 'asc' ? 'lucide-arrow-up' : 'lucide-arrow-down'"
							/>
						</button>
						<span v-else>{{ col.label }}</span>
					</div>
				</div>

				<div v-if="loading && !rows.length" class="flex flex-col">
					<div v-for="n in 6" :key="n" class="flex h-12 items-center border-b border-ch-line px-3">
						<div class="h-3 w-1/3 animate-pulse rounded-1 bg-ch-subtle" />
					</div>
				</div>
				<div
					v-for="(row, index) in rows"
					v-else
					:key="row[rowKey] ?? index"
					role="row"
					class="grid min-h-12 items-center gap-3 border-b border-ch-line px-3 py-1.5 text-[13.5px] text-ch-ink transition-colors"
					:class="[clickable ? 'cursor-pointer hover:bg-ch-hover' : '', loading ? 'opacity-60' : '']"
					:style="gridStyle"
					:tabindex="clickable ? 0 : undefined"
					@click="clickable && $emit('row-click', row)"
					@keydown.enter="clickable && $emit('row-click', row)"
				>
					<div v-if="selectable" class="flex items-center" @click.stop>
						<Checkbox
							:model-value="isSelected(row)"
							:aria-label="`Select ${row[rowKey]}`"
							@update:model-value="toggleRow(row)"
						/>
					</div>
					<div
						v-for="col in columns"
						:key="col.key"
						class="min-w-0 truncate"
						:class="[col.align === 'right' ? 'text-right tabular-nums' : '', col.class || '']"
					>
						<slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
							{{ col.format ? col.format(row[col.key], row) : row[col.key] ?? "" }}
						</slot>
					</div>
				</div>
			</div>
		</div>

		<!-- Mobile: stacked rows -->
		<div class="flex min-h-0 flex-1 flex-col overflow-y-auto md:hidden">
			<div v-if="loading && !rows.length" class="px-4 py-6 text-center text-sm text-ch-ink-3">Loading…</div>
			<button
				v-for="(row, index) in rows"
				v-else
				:key="row[rowKey] ?? index"
				class="flex w-full flex-col gap-1 border-b border-ch-line px-4 py-3 text-left"
				@click="clickable && $emit('row-click', row)"
			>
				<div class="flex items-center justify-between gap-3">
					<div class="min-w-0 flex-1 truncate text-[14px] font-medium text-ch-ink">
						<slot :name="`cell-${columns[0].key}`" :row="row" :value="row[columns[0].key]">
							{{ row[columns[0].key] }}
						</slot>
					</div>
					<div v-if="mobileAside" class="shrink-0">
						<slot :name="`cell-${mobileAside}`" :row="row" :value="row[mobileAside]">
							{{ row[mobileAside] }}
						</slot>
					</div>
				</div>
				<div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[12.5px] text-ch-ink-3">
					<template v-for="col in mobileColumns" :key="col.key">
						<span v-if="row[col.key] !== null && row[col.key] !== '' && row[col.key] !== undefined">
							{{ col.format ? col.format(row[col.key], row) : row[col.key] }}
						</span>
					</template>
				</div>
			</button>
		</div>

		<div v-if="error" class="mx-5 my-6 rounded-5 bg-ch-red-bg px-4 py-3 text-sm text-ch-red-ink" role="alert">
			{{ error }}
		</div>
		<div v-else-if="!loading && !rows.length" class="flex flex-col items-center gap-2 px-5 py-16 text-center">
			<span class="size-6 text-ch-ink-4" :class="emptyIcon" />
			<p class="text-sm text-ch-ink-3">{{ emptyMessage }}</p>
			<Button v-if="showClear" label="Clear filters" variant="ghost" @click="$emit('clear-filters')" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, Checkbox } from "frappe-ui"

export interface Column {
	key: string
	label: string
	/** CSS grid track, for example "2fr" or "120px". */
	width?: string
	sortable?: boolean
	align?: "left" | "right"
	class?: string
	format?: (value: any, row: Record<string, any>) => string
	/** Hide in the stacked mobile row. */
	hideOnMobile?: boolean
}

const props = withDefaults(
	defineProps<{
		columns: Column[]
		rows: Record<string, any>[]
		rowKey?: string
		loading?: boolean
		error?: string | null
		sortField?: string
		sortOrder?: "asc" | "desc"
		selectable?: boolean
		clickable?: boolean
		emptyMessage?: string
		emptyIcon?: string
		showClear?: boolean
		minWidth?: string
		/** Column shown on the right of a stacked mobile row, usually the status. */
		mobileAside?: string
	}>(),
	{
		rowKey: "name",
		clickable: true,
		emptyMessage: "No records found",
		emptyIcon: "lucide-inbox",
		minWidth: "760px",
	}
)

const selected = defineModel<string[]>("selected", { default: () => [] })
defineEmits<{ sort: [key: string]; "row-click": [row: Record<string, any>]; "clear-filters": [] }>()

const gridStyle = computed(() => ({
	gridTemplateColumns: [
		props.selectable ? "20px" : null,
		...props.columns.map((c) => c.width || "minmax(0, 1fr)"),
	]
		.filter(Boolean)
		.join(" "),
}))

const mobileColumns = computed(() =>
	props.columns.slice(1).filter((c) => !c.hideOnMobile && c.key !== props.mobileAside)
)

const allSelected = computed(
	() => props.rows.length > 0 && props.rows.every((row) => selected.value.includes(row[props.rowKey]))
)

function isSelected(row: Record<string, any>) {
	return selected.value.includes(row[props.rowKey])
}

function toggleRow(row: Record<string, any>) {
	const key = row[props.rowKey]
	selected.value = isSelected(row) ? selected.value.filter((k) => k !== key) : [...selected.value, key]
}

function toggleAll() {
	selected.value = allSelected.value ? [] : props.rows.map((row) => row[props.rowKey])
}
</script>
