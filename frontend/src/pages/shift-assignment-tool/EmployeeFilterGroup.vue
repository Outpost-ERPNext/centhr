<template>
	<div class="flex flex-col gap-2">
		<div v-for="(row, index) in rows" :key="row.id" class="flex flex-wrap items-center gap-2 sm:flex-nowrap">
			<div class="w-full sm:w-52">
				<Select
					:model-value="row.fieldname"
					:options="fieldOptions"
					size="sm"
					aria-label="Field"
					@update:model-value="(v) => setField(index, String(v || ''))"
				/>
			</div>
			<div class="w-[calc(50%-4px)] sm:w-32">
				<Select
					:model-value="row.condition"
					:options="CONDITIONS"
					size="sm"
					aria-label="Condition"
					@update:model-value="(v) => update(index, { condition: String(v), value: null })"
				/>
			</div>
			<div class="min-w-0 flex-1">
				<Select
					v-if="row.condition === 'is'"
					:model-value="row.value || ''"
					:options="[
						{ label: 'Set', value: 'set' },
						{ label: 'Not Set', value: 'not set' },
					]"
					size="sm"
					aria-label="Value"
					@update:model-value="(v) => update(index, { value: v })"
				/>
				<input
					v-else-if="TEXT_CONDITIONS.includes(row.condition) || !fieldOf(row)"
					:value="row.value || ''"
					type="text"
					:placeholder="row.condition.endsWith('in') ? 'Values separated by commas' : 'Value'"
					aria-label="Value"
					class="h-7 w-full rounded-3 border-0 bg-ch-subtle px-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4 focus:ring-2 focus:ring-[var(--ch-line-2)]"
					@input="update(index, { value: ($event.target as HTMLInputElement).value })"
				/>
				<FieldControl
					v-else
					:field="{ ...fieldOf(row)!, label: '', reqd: 0, read_only: 0 }"
					:model-value="row.value"
					:doc="{}"
					doctype="Employee"
					compact
					@update:model-value="(v) => update(index, { value: v })"
				/>
			</div>
			<Button variant="ghost" icon="lucide-x" aria-label="Remove filter" @click="remove(index)" />
		</div>
		<p v-if="!rows.length" class="text-[13px] text-ch-ink-3">No filters selected</p>
		<div class="flex gap-2">
			<Button size="sm" icon-left="lucide-plus" label="Add a Filter" @click="add" />
			<Button v-if="rows.length" size="sm" variant="ghost" label="Clear Filters" @click="clear" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Select } from "frappe-ui"
import FieldControl from "@/components/fields/FieldControl.vue"
import { getMeta, loadMeta, NO_VALUE_TYPES, type DocField } from "@/data/meta"

/** A filter as the Desk FilterGroup hands it to the tool: `[fieldname, condition, value]`. */
export type EmployeeFilter = [string, string, any]

interface Row {
	id: number
	fieldname: string
	condition: string
	value: any
}

// The conditions of the Desk filter group that the tool's server check allows
const CONDITIONS = ["=", "!=", "like", "not like", "in", "not in", "is", ">", "<", ">=", "<="].map((c) => ({
	label: { "=": "Equals", "!=": "Not Equals", like: "Like", "not like": "Not Like", in: "In", "not in": "Not In", is: "Is" }[c] || c,
	value: c,
}))
const TEXT_CONDITIONS = ["like", "not like", "in", "not in"]

const filters = defineModel<EmployeeFilter[]>({ default: () => [] })

const ready = ref(false)
loadMeta("Employee").then(() => (ready.value = true))

const fields = computed(() =>
	ready.value
		? (getMeta("Employee")?.fields || []).filter(
				(f) => !NO_VALUE_TYPES.includes(f.fieldtype) && !["Table", "Table MultiSelect", "Attach Image"].includes(f.fieldtype)
			)
		: []
)
const fieldOptions = computed(() => [
	{ label: "ID", value: "name" },
	...fields.value
		.map((f) => ({ label: f.label || f.fieldname, value: f.fieldname }))
		.sort((a, b) => a.label.localeCompare(b.label)),
])
const fieldOf = (row: Row): DocField | undefined => fields.value.find((f) => f.fieldname === row.fieldname)

const rows = ref<Row[]>([])
let nextId = 0

function add() {
	rows.value = [...rows.value, { id: nextId++, fieldname: "name", condition: "=", value: null }]
}

function setField(index: number, fieldname: string) {
	update(index, { fieldname, value: null })
}

function update(index: number, change: Partial<Row>) {
	rows.value = rows.value.map((row, i) => (i === index ? { ...row, ...change } : row))
	emitFilters()
}

function remove(index: number) {
	rows.value = rows.value.filter((_, i) => i !== index)
	emitFilters()
}

function clear() {
	rows.value = []
	emitFilters()
}

/** Only rows with a value count, as in hrms.setup_employee_filter_group. */
function emitFilters() {
	filters.value = rows.value
		.filter((row) => row.fieldname && row.value !== null && row.value !== undefined && row.value !== "")
		.map((row): EmployeeFilter => [row.fieldname, row.condition, toValue(row)])
}

/** The value the way the Desk filter sends it: `like` gets `%…%`, `in` a list. */
function toValue(row: Row) {
	const value = row.value
	if (row.condition.endsWith("like")) return String(value).includes("%") ? value : `%${value}%`
	if (row.condition.endsWith("in"))
		return String(value)
			.split(",")
			.map((v) => v.trim())
			.filter(Boolean)
	return value
}
</script>
