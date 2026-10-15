<template>
	<div class="flex flex-wrap items-center gap-2">
		<div class="w-32">
			<Select
				:model-value="op || ''"
				:options="operators"
				size="sm"
				:aria-label="`${label} operator`"
				@update:model-value="$emit('update:op', ($event as string) || '')"
			/>
		</div>
		<template v-if="op">
			<div class="w-36">
				<DatePicker
					:model-value="from || ''"
					:format="pickerDateFormat()"
					size="sm"
					:placeholder="op === 'between' ? 'From' : 'Date'"
					@update:model-value="$emit('update:from', $event || '')"
				/>
			</div>
			<div v-if="op === 'between'" class="w-36">
				<DatePicker
					:model-value="to || ''"
					:format="pickerDateFormat()"
					size="sm"
					placeholder="To"
					@update:model-value="$emit('update:to', $event || '')"
				/>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { DatePicker, Select } from "frappe-ui"
import { pickerDateFormat } from "@/utils/format"

const props = withDefaults(defineProps<{ op?: string; from?: string; to?: string; label?: string }>(), {
	label: "Date",
})
defineEmits<{ "update:op": [v: string]; "update:from": [v: string]; "update:to": [v: string] }>()

const operators = computed(() => [
	{ label: `Any ${props.label.toLowerCase()}`, value: "" },
	{ label: "Between", value: "between" },
	{ label: "Equals", value: "=" },
	{ label: "On or before", value: "<=" },
	{ label: "On or after", value: ">=" },
])
</script>
