<template>
	<div class="flex flex-col gap-2">
		<div class="flex items-center justify-between">
			<span class="text-xs text-ch-ink-2">
				{{ field.label }}<span v-if="required" class="text-ch-red-dot"> *</span>
			</span>
		</div>
		<div class="overflow-x-auto rounded-4 border border-ch-line">
			<table class="w-full min-w-[560px] text-[13px]">
				<thead class="bg-ch-subtle text-left text-ch-ink-3">
					<tr>
						<th class="w-10 px-2 py-1.5 font-normal">No.</th>
						<th v-for="col in columns" :key="col.fieldname" class="px-2 py-1.5 font-normal">
							{{ col.label }}
						</th>
						<th v-if="!readOnly" class="w-10" />
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, index) in rows" :key="row.name || index" class="border-t border-ch-line align-top">
						<td class="px-2 py-1.5 text-ch-ink-3">{{ index + 1 }}</td>
						<td v-for="col in columns" :key="col.fieldname" class="px-1 py-1">
							<span v-if="readOnly || col.read_only" class="block px-1 py-1">
								{{ displayValue(row[col.fieldname], col.fieldtype) }}
							</span>
							<FieldControl
								v-else
								:field="{ ...col, label: '' }"
								:model-value="row[col.fieldname]"
								:doc="row"
								:doctype="childDoctype"
								@update:model-value="(v) => setCell(index, col.fieldname, v)"
							/>
						</td>
						<td v-if="!readOnly" class="px-1 py-1">
							<Button
								variant="ghost"
								icon="lucide-trash-2"
								aria-label="Delete row"
								@click="removeRow(index)"
							/>
						</td>
					</tr>
					<tr v-if="!rows.length">
						<td :colspan="columns.length + 2" class="px-2 py-4 text-center text-ch-ink-3">No rows</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div v-if="!readOnly">
			<Button size="sm" icon-left="lucide-plus" label="Add row" @click="addRow" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button } from "frappe-ui"
import { getMeta, NO_VALUE_TYPES, type DocField } from "@/data/meta"
import { displayValue } from "@/utils/format"
import FieldControl from "./FieldControl.vue"

const props = defineProps<{ field: DocField; modelValue: Record<string, any>[] | null; readOnly?: boolean; required?: boolean }>()
const emit = defineEmits<{ "update:modelValue": [rows: Record<string, any>[]] }>()

const childDoctype = computed(() => props.field.options || "")
const rows = computed(() => props.modelValue || [])

const columns = computed(() => {
	const fields = (getMeta(childDoctype.value)?.fields || []).filter(
		(f) => !NO_VALUE_TYPES.includes(f.fieldtype) && !f.hidden
	)
	const listed = fields.filter((f) => f.in_list_view)
	return (listed.length ? listed : fields).slice(0, 6)
})

function setCell(index: number, fieldname: string, value: any) {
	const next = rows.value.map((row, i) => (i === index ? { ...row, [fieldname]: value } : row))
	emit("update:modelValue", next)
}

function addRow() {
	const row: Record<string, any> = { doctype: childDoctype.value }
	for (const f of getMeta(childDoctype.value)?.fields || []) {
		if (f.default !== undefined && f.default !== null && !NO_VALUE_TYPES.includes(f.fieldtype)) row[f.fieldname] = f.default
	}
	emit("update:modelValue", [...rows.value, row])
}

function removeRow(index: number) {
	emit(
		"update:modelValue",
		rows.value.filter((_, i) => i !== index)
	)
}
</script>
