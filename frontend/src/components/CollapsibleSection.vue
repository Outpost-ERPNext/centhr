<template>
	<section class="rounded-5 border border-ch-line bg-ch-surface">
		<button
			type="button"
			class="flex w-full items-center gap-2 px-4 py-2.5 text-left"
			:aria-expanded="open"
			@click="open = !open"
		>
			<span class="lucide-chevron-right size-4 text-ch-ink-3 transition-transform" :class="{ 'rotate-90': open }" />
			<span class="text-[13.5px] font-medium text-ch-ink">{{ title }}</span>
			<slot name="badge" />
			<span v-if="summary" class="ml-auto truncate text-[12.5px] text-ch-ink-3">{{ summary }}</span>
		</button>
		<div v-show="open" class="border-t border-ch-line p-3">
			<slot />
		</div>
	</section>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { readStorage, writeStorage } from "@/utils/storage"

const props = withDefaults(defineProps<{ title: string; summary?: string; storageKey: string; defaultOpen?: boolean }>(), {
	defaultOpen: true,
})

// Each section remembers whether the user left it open
const key = `centhr-section-${props.storageKey}`
const open = ref(readStorage(key, props.defaultOpen ? "open" : "closed") === "open")
watch(open, (value) => writeStorage(key, value ? "open" : "closed"))
</script>
