<template>
	<div
		v-if="total > 0"
		class="flex flex-wrap items-center justify-between gap-3 border-t border-ch-line px-5 py-3 text-[13px] text-ch-ink-3"
	>
		<div class="flex items-center gap-2">
			<span class="hidden sm:inline">Rows</span>
			<div class="inline-flex rounded-3 bg-ch-subtle p-0.5" role="group" aria-label="Rows per page">
				<button
					v-for="size in sizes"
					:key="size"
					class="h-6 rounded-[5px] px-2 text-[12.5px]"
					:class="size === pageSize ? 'bg-ch-surface font-medium text-ch-ink shadow-ch-xs' : 'hover:text-ch-ink'"
					:aria-pressed="size === pageSize"
					@click="$emit('update:pageSize', size)"
				>
					{{ size }}
				</button>
			</div>
		</div>
		<div class="flex items-center gap-2">
			<span class="tabular-nums">{{ from }}–{{ to }} of {{ total }}</span>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-chevron-left"
				aria-label="Previous page"
				:disabled="page <= 1"
				@click="$emit('update:page', page - 1)"
			/>
			<Button
				size="sm"
				variant="ghost"
				icon="lucide-chevron-right"
				aria-label="Next page"
				:disabled="to >= total"
				@click="$emit('update:page', page + 1)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button } from "frappe-ui"

const props = defineProps<{ total: number; page: number; pageSize: number }>()
defineEmits<{ "update:page": [page: number]; "update:pageSize": [size: number] }>()

const sizes = [10, 20, 50]
const from = computed(() => (props.page - 1) * props.pageSize + 1)
const to = computed(() => Math.min(props.page * props.pageSize, props.total))
</script>
