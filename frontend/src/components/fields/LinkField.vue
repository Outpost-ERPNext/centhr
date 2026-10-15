<template>
	<Combobox
		class="w-full"
		:model-value="modelValue ?? null"
		:options="comboOptions"
		:query="query"
		:filterable="false"
		:loading="loading"
		:placeholder="placeholder || `Select ${doctype}`"
		:label="label"
		:required="required"
		:error="error"
		:disabled="disabled"
		:size="size"
		:variant="variant"
		open-on-focus
		:empty-text="denied ? `You don't have permission to search ${doctype}` : 'No results'"
		@update:query="onQuery"
		@update:open="(open: boolean) => open && search(query)"
		@update:model-value="(v: any) => emit('update:modelValue', v === undefined ? null : (v as string | null))"
	>
		<template v-if="modelValue && !disabled" #suffix>
			<button
				type="button"
				class="lucide-x size-3.5 text-ch-ink-3 hover:text-ch-ink"
				aria-label="Clear"
				@click.stop="emit('update:modelValue', null)"
				@pointerdown.stop
			/>
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Combobox } from "frappe-ui"
import { api } from "@/data/api"

interface SearchResult {
	value: string
	description?: string
	label?: string
}

const props = withDefaults(
	defineProps<{
		doctype: string
		modelValue?: string | null
		/** Extra filters passed to the server search, as a dict or filter list. */
		filters?: Record<string, any> | any[]
		/** A whitelisted search query, for example erpnext.controllers.queries.employee_query. */
		query?: string
		referenceDoctype?: string
		placeholder?: string
		label?: string
		required?: boolean
		error?: string
		disabled?: boolean
		size?: "sm" | "md"
		variant?: "subtle" | "outline"
	}>(),
	{ size: "sm", variant: "subtle" }
)
const emit = defineEmits<{ "update:modelValue": [value: string | null] }>()

const results = ref<SearchResult[]>([])
const loading = ref(false)
const denied = ref(false)
const query = ref("")
let timer: ReturnType<typeof setTimeout> | undefined
let requestId = 0

const comboOptions = computed(() => {
	const options = results.value.map((r) => ({
		label: r.label || r.value,
		value: r.value,
		description: r.description && r.description !== r.value ? r.description : undefined,
	}))
	// Keep the current value selectable, so its label shows even before a search
	if (props.modelValue && !options.some((o) => o.value === props.modelValue)) {
		options.unshift({ label: props.modelValue, value: props.modelValue, description: undefined })
	}
	return options
})

function onQuery(value: string) {
	query.value = value
	clearTimeout(timer)
	timer = setTimeout(() => search(value), 250)
}

async function search(txt: string) {
	const id = ++requestId
	loading.value = true
	try {
		const res = await api<SearchResult[]>(
			"frappe.desk.search.search_link",
			{
				doctype: props.doctype,
				txt: txt === props.modelValue ? "" : txt || "",
				query: props.query,
				filters: props.filters,
				page_length: 20,
				reference_doctype: props.referenceDoctype,
			},
			{ silent: true }
		)
		if (id === requestId) {
			results.value = res || []
			denied.value = false
		}
	} catch (e: any) {
		if (id === requestId) {
			results.value = []
			denied.value = e?.status === 403 || e?.exc_type === "PermissionError"
		}
	} finally {
		if (id === requestId) loading.value = false
	}
}

watch(
	() => JSON.stringify(props.filters),
	() => (results.value = [])
)
</script>
