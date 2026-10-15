<template>
	<div class="flex flex-wrap items-center gap-2 px-5 py-3">
		<div class="relative w-full sm:w-56">
			<span class="lucide-search pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-ch-ink-3" />
			<input
				v-model="search"
				type="search"
				:placeholder="searchPlaceholder"
				:aria-label="searchPlaceholder"
				class="h-7 w-full rounded-3 border-0 bg-ch-subtle pl-7 pr-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4 focus:ring-2 focus:ring-[var(--ch-line-2)]"
			/>
		</div>
		<slot />
		<Button v-if="active" variant="ghost" size="sm" icon-left="lucide-x" label="Clear" @click="$emit('clear')" />
		<span class="ml-auto text-[13px] tabular-nums text-ch-ink-3">{{ countLabel }}</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button } from "frappe-ui"

const props = withDefaults(
	defineProps<{ total: number; active?: boolean; searchPlaceholder?: string; noun?: string }>(),
	{ searchPlaceholder: "Search", noun: "record" }
)
defineEmits<{ clear: [] }>()
const search = defineModel<string>("search", { default: "" })

const countLabel = computed(() => `${props.total} ${props.noun}${props.total === 1 ? "" : "s"}`)
</script>
