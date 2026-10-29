<template>
	<div class="grid grid-cols-2 overflow-hidden rounded-5 border border-ch-line bg-ch-surface sm:grid-cols-3 xl:grid-cols-6" role="group" aria-label="Filter employees">
		<button
			v-for="tile in tiles"
			:key="tile.key"
			type="button"
			:aria-pressed="modelValue === tile.key"
			class="flex flex-col items-center gap-1 border-b border-r border-ch-line px-3 py-3 transition-colors"
			:class="modelValue === tile.key ? 'bg-ch-subtle shadow-[inset_0_-2px_0_var(--ch-primary)]' : 'hover:bg-ch-hover'"
			@click="$emit('update:modelValue', tile.key)"
		>
			<span class="text-[11.5px] font-medium uppercase tracking-wide" :class="tile.tone ? `text-ch-${tile.tone}-ink` : 'text-ch-ink-3'">
				{{ tile.label }}
			</span>
			<span class="text-[22px] font-semibold tabular-nums" :class="tile.tone ? `text-ch-${tile.tone}-ink` : 'text-ch-ink'">
				{{ loading ? "—" : formatNumber(counts[tile.key] || 0) }}
			</span>
		</button>
	</div>
</template>

<script setup lang="ts">
import type { Tile } from "@/data/salaryOverview"
import { formatNumber } from "@/utils/format"

defineProps<{ tiles: Tile[]; counts: Record<string, number>; modelValue: string; loading?: boolean }>()
defineEmits<{ "update:modelValue": [key: string] }>()
</script>
