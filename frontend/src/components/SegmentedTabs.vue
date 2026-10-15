<template>
	<div class="inline-flex max-w-full overflow-x-auto rounded-4 bg-ch-subtle p-0.5" role="tablist">
		<button
			v-for="tab in tabs"
			:key="tab.value"
			role="tab"
			:aria-selected="modelValue === tab.value"
			class="flex h-7 shrink-0 items-center gap-1.5 rounded-3 px-2.5 text-[13px]"
			:class="modelValue === tab.value ? 'bg-ch-surface font-medium text-ch-ink shadow-ch-xs' : 'text-ch-ink-3 hover:text-ch-ink'"
			@click="$emit('update:modelValue', tab.value)"
		>
			{{ tab.label }}
			<span v-if="tab.count !== undefined" class="tabular-nums text-ch-ink-3">{{ tab.count }}</span>
		</button>
	</div>
</template>

<script setup lang="ts">
defineProps<{ modelValue: string; tabs: { label: string; value: string; count?: number }[] }>()
defineEmits<{ "update:modelValue": [value: string] }>()
</script>
