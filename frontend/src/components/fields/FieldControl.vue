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

	<Combobox
		v-else-if="field.fieldtype === 'Autocomplete'"
		class="w-full"
		:model-value="modelValue || null"
		:options="autocompleteOptions"
		:label="field.label"
		:placeholder="field.label ? `Select ${field.label}` : ''"
		:required="required"
		:disabled="readOnly"
		:error="error"
		size="md"
		open-on-focus
		@update:model-value="(v: any) => update(v ?? '')"
	>
		<template v-if="modelValue && !readOnly" #suffix>
			<button
				type="button"
				class="lucide-x size-3.5 text-ch-ink-3 hover:text-ch-ink"
				aria-label="Clear"
				@click.stop="update('')"
				@pointerdown.stop
			/>
		</template>
	</Combobox>

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
		v-else-if="TEXT_TYPES.includes(field.fieldtype) && !compact"
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
		:model-value="inputValue"
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
import { Checkbox, Combobox, DatePicker, DateTimePicker, Select, Textarea, TextInput } from "frappe-ui"
import { stripHtml } from "@/data/api"
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
	/** Choices of an Autocomplete field set by the page, like `set_data` in a Desk form script. */
	options?: { label: string; value: string }[]
	/** One line for text fields, for table cells. */
	compact?: boolean
}>()
const emit = defineEmits<{ "update:modelValue": [value: any] }>()

const linkDoctype = computed(() =>
	props.field.fieldtype === "Dynamic Link" ? props.doc[props.field.options || ""] : props.field.options || ""
)

const selectOptions = computed(() =>
	(props.field.options || "").split("\n").map((o) => ({ label: o || "—", value: o }))
)

const autocompleteOptions = computed(() => {
	const options =
		props.options ||
		(props.field.options || "")
			.split("\n")
			.filter(Boolean)
			.map((o) => ({ label: o, value: o }))
	// Keep the current value selectable, so it shows before the choices load
	if (props.modelValue && !options.some((o) => o.value === props.modelValue)) {
		return [{ label: String(props.modelValue), value: String(props.modelValue) }, ...options]
	}
	return options
})

// A compact text cell shows Text Editor HTML as plain text
const inputValue = computed(() => {
	const value = props.modelValue ?? ""
	return props.compact && TEXT_TYPES.includes(props.field.fieldtype) && /<[a-z]/i.test(value) ? stripHtml(value) : value
})

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
