<template>
	<span
		v-if="status"
		class="inline-flex h-[22px] shrink-0 items-center gap-1.5 rounded-full px-2 text-[12px] font-medium"
		:class="pill ? `bg-ch-${tone}-bg text-ch-${tone}-ink` : 'px-0 text-ch-ink'"
	>
		<span class="size-2 shrink-0 rounded-full" :class="pill ? 'size-1.5' : ''" :style="{ background: `var(--ch-${tone}-dot)` }" />
		{{ status }}
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { toneFor, type Tone } from "@/utils/status"

const props = defineProps<{ doctype?: string; status?: string | null; pill?: boolean; tone?: Tone }>()
const tone = computed(() => props.tone || toneFor(props.doctype || "", props.status))
</script>
