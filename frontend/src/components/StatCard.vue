<template>
	<component
		:is="clickable ? 'button' : 'div'"
		:type="clickable ? 'button' : undefined"
		:aria-pressed="clickable ? active : undefined"
		class="flex min-w-0 flex-col gap-1 rounded-5 border bg-ch-surface px-4 py-3 text-left transition-colors"
		:class="[
			active ? 'border-ch-primary shadow-[inset_0_0_0_1px_var(--ch-primary)]' : 'border-ch-line',
			clickable ? 'hover:bg-ch-hover' : '',
		]"
		@click="clickable && $emit('click')"
	>
		<span class="flex items-center gap-2">
			<span class="truncate text-[11.5px] font-medium uppercase tracking-wide" :class="tone ? `text-ch-${tone}-ink` : 'text-ch-ink-3'">
				{{ label }}
			</span>
			<span
				v-if="change !== null && change !== undefined"
				class="ml-auto shrink-0 text-[12px] font-medium tabular-nums"
				:class="change >= 0 ? 'text-ch-green-ink' : 'text-ch-red-ink'"
				:title="'Against the previous cycle'"
			>
				{{ change >= 0 ? "↑" : "↓" }} {{ Math.abs(change).toFixed(1) }}%
			</span>
		</span>
		<span class="truncate text-[20px] font-semibold tabular-nums" :class="tone ? `text-ch-${tone}-ink` : 'text-ch-ink'">
			{{ loading ? "—" : value }}
		</span>
		<span v-if="sub" class="truncate text-[12px] text-ch-ink-3">{{ sub }}</span>
	</component>
</template>

<script setup lang="ts">
import type { Tone } from "@/utils/status"

/** A figure with its label; clickable cards act as filters. */
defineProps<{
	label: string
	value: string | number
	tone?: Tone
	sub?: string
	change?: number | null
	active?: boolean
	clickable?: boolean
	loading?: boolean
}>()
defineEmits<{ click: [] }>()
</script>
