<template>
	<div
		v-if="total > 0"
		class="flex flex-wrap items-center justify-between gap-3 border-t border-ch-line px-5 py-3 text-[13px] text-ch-ink-3"
	>
		<div class="flex items-center gap-2">
			<div class="inline-flex rounded-3 bg-ch-subtle p-0.5" role="group" aria-label="Rows per load">
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
			<Button v-if="shown < total" size="sm" variant="subtle" @click="$emit('update:page', page + 1)">
				Load More
			</Button>
		</div>
		<span class="tabular-nums">{{ shown }} of {{ total }}</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button } from "frappe-ui"

/** `page` is the number of chunks loaded; the list shows `page * pageSize` rows. */
const props = defineProps<{ total: number; page: number; pageSize: number }>()
defineEmits<{ "update:page": [page: number]; "update:pageSize": [size: number] }>()

const sizes = [50, 100, 500, 2500]
const shown = computed(() => Math.min(props.page * props.pageSize, props.total))
</script>
