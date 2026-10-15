<template>
	<div class="w-[calc(50%-4px)] sm:w-44">
		<LinkField
			:doctype="doctype"
			:model-value="modelValue || null"
			:placeholder="placeholder"
			:filters="filters"
			size="sm"
			@update:model-value="$emit('update:modelValue', $event || '')"
		/>
	</div>
</template>

<script setup lang="ts">
import LinkField from "./fields/LinkField.vue"

defineProps<{ doctype: string; modelValue?: string; placeholder: string; filters?: Record<string, any> }>()
defineEmits<{ "update:modelValue": [value: string] }>()
</script>
