<template>
	<div v-if="field.fieldtype === 'Check'" class="pt-1">
		<Checkbox
			:model-value="!!modelValue"
			:label="field.label"
			:disabled="readOnly"
			@update:model-value="(v: boolean) => update(v ? 1 : 0)"
		/>
		<p v-if="field.description" class="mt-1 text-xs text-ch-ink-3" v-html="field.description" />
	</div>

	<LinkField
		v-else-if="field.fieldtype === 'Link' || field.fieldtype === 'Dynamic Link'"
		:doctype="linkDoctype"
		:model-value="modelValue"
		:label="field.label"
		:required="required"
		:disabled="readOnly || !linkDoctype"
		:error="error"
		:filters="linkFilters"
		:query="linkQuery"
		:reference-doctype="doctype"
		size="md"
		@update:model-value="update"
	/>

	<Select
		v-else-if="field.fieldtype === 'Select'"
		:model-value="modelValue ?? ''"
		:options="selectOptions"
		:label="field.label"
		:required="required"
		:disabled="readOnly"
		:error="error"
		:description="field.description"
		size="md"
		@update:model-value="update"
	/>

	<DatePicker
		v-else-if="field.fieldtype === 'Date'"
		:model-value="modelValue || ''"
		:label="field.label"
		:required="required"
		:disabled="readOnly"
		:error="error"
		:format="pickerDateFormat()"
		size="md"
		clearable
		@update:model-value="(v: string) => update(v || null)"
	/>

	<DateTimePicker
		v-else-if="field.fieldtype === 'Datetime'"
		:model-value="modelValue || ''"
		:format="`${pickerDateFormat()} HH:mm`"
		:label="field.label"
		:required="required"
		:disabled="readOnly"
		:error="error"
		size="md"
		@update:model-value="(v: string) => update(v || null)"
	/>

	<Textarea
		v-else-if="TEXT_TYPES.includes(field.fieldtype)"
		:model-value="modelValue ?? ''"
		:label="field.label"
		:required="required"
		:disabled="readOnly"
		:error="error"
		:description="field.description"
		:rows="field.fieldtype === 'Small Text' ? 3 : 5"
		size="md"
		@update:model-value="update"
	/>

	<div v-else-if="field.fieldtype === 'Attach Image' || field.fieldtype === 'Attach'" class="flex flex-col gap-1.5">
		<span class="text-xs text-ch-ink-2">{{ field.label }}</span>
		<a v-if="modelValue" :href="modelValue" target="_blank" class="truncate text-sm text-ch-ink underline">
			{{ modelValue.split("/").pop() }}
		</a>
		<span v-else class="text-sm text-ch-ink-4">No file</span>
	</div>

	<TextInput
		v-else
		:model-value="modelValue ?? ''"
		:type="inputType"
		:label="field.label"
		:required="required"
		:disabled="readOnly"
		:error="error"
		:description="field.description"
		size="md"
		@update:model-value="onInput"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Checkbox, DatePicker, DateTimePicker, Select, Textarea, TextInput } from "frappe-ui"
import type { DocField } from "@/data/meta"
import { pickerDateFormat } from "@/utils/format"
import LinkField from "./LinkField.vue"

const TEXT_TYPES = ["Small Text", "Text", "Long Text", "Text Editor", "Code", "Markdown Editor", "HTML Editor"]
const NUMBER_TYPES = ["Int", "Float", "Currency", "Percent"]

const props = defineProps<{
	field: DocField
	modelValue: any
	doc: Record<string, any>
	doctype: string
	required?: boolean
	readOnly?: boolean
	error?: string
	/** Filters for Link fields, keyed by fieldname. */
	linkFilters?: Record<string, any>
	linkQuery?: string
}>()
const emit = defineEmits<{ "update:modelValue": [value: any] }>()

const linkDoctype = computed(() =>
	props.field.fieldtype === "Dynamic Link" ? props.doc[props.field.options || ""] : props.field.options || ""
)

const selectOptions = computed(() =>
	(props.field.options || "").split("\n").map((o) => ({ label: o || "—", value: o }))
)

const inputType = computed(() => {
	if (NUMBER_TYPES.includes(props.field.fieldtype)) return "number"
	if (props.field.options === "Email") return "email"
	if (props.field.options === "Phone" || props.field.fieldtype === "Phone") return "tel"
	if (props.field.fieldtype === "Password") return "password"
	if (props.field.fieldtype === "Time") return "time"
	return "text"
})

function onInput(value: string) {
	if (NUMBER_TYPES.includes(props.field.fieldtype)) {
		const num = props.field.fieldtype === "Int" ? parseInt(value, 10) : parseFloat(value)
		update(value === "" || Number.isNaN(num) ? null : num)
	} else {
		update(value)
	}
}

function update(value: any) {
	emit("update:modelValue", value)
}
</script>
