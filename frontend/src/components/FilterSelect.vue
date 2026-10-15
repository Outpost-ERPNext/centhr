<template>
	<div class="w-[calc(50%-4px)] sm:w-40">
		<Select
			:model-value="modelValue || ''"
			:options="selectOptions"
			:placeholder="placeholder"
			size="sm"
			:aria-label="placeholder"
			@update:model-value="$emit('update:modelValue', ($event as string) || '')"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Select } from "frappe-ui"

const props = defineProps<{
	modelValue?: string
	options: (string | { label: string; value: string })[]
	placeholder: string
}>()
defineEmits<{ "update:modelValue": [value: string] }>()

const selectOptions = computed(() => [
	{ label: `All · ${props.placeholder}`, value: "" },
	...props.options.map((o) => (typeof o === "string" ? { label: o, value: o } : o)),
])
</script>
