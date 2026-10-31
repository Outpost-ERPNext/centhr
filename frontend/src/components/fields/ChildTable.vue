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
						<th class="w-20" />
					</tr>
				</thead>
				<tbody>
					<template v-for="(row, index) in rows" :key="row.name || index">
						<tr class="border-t border-ch-line align-top">
							<td class="px-2 py-1.5 text-ch-ink-3">{{ index + 1 }}</td>
							<td v-for="col in columns" :key="col.fieldname" class="px-1 py-1">
								<span v-if="readOnly || col.read_only" class="block px-1 py-1">
									{{ cellText(row, col) }}
								</span>
								<FieldControl
									v-else
									:field="{ ...col, label: '' }"
									:model-value="row[col.fieldname]"
									:doc="row"
									:doctype="childDoctype"
									compact
									@update:model-value="(v) => setCell(index, col.fieldname, v)"
								/>
							</td>
							<td class="px-1 py-1">
								<div class="flex justify-end gap-0.5">
									<Button
										v-if="moreFields.length"
										variant="ghost"
										:icon="expanded.has(index) ? 'lucide-chevron-up' : 'lucide-chevron-down'"
										:aria-label="expanded.has(index) ? 'Hide row details' : 'Show row details'"
										:aria-expanded="expanded.has(index)"
										@click="toggle(index)"
									/>
									<Button
										v-if="!readOnly"
										variant="ghost"
										icon="lucide-trash-2"
										aria-label="Delete row"
										@click="removeRow(index)"
									/>
								</div>
							</td>
						</tr>
						<!-- The row's other fields, like the row form of a Desk grid -->
						<tr v-if="expanded.has(index)" class="bg-ch-subtle">
							<td :colspan="columns.length + 2" class="px-3 py-3">
								<div class="grid grid-cols-1 gap-x-5 gap-y-3 md:grid-cols-3">
									<template v-for="f in moreFields" :key="f.fieldname">
										<div v-if="readOnly || f.read_only" class="flex flex-col gap-1">
											<span class="text-xs text-ch-ink-3">{{ f.label }}</span>
											<span class="text-ch-ink">{{ cellText(row, f) || "—" }}</span>
										</div>
										<FieldControl
											v-else
											:field="f"
											:model-value="row[f.fieldname]"
											:doc="row"
											:doctype="childDoctype"
											@update:model-value="(v) => setCell(index, f.fieldname, v)"
										/>
									</template>
								</div>
							</td>
						</tr>
					</template>
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
import { computed, reactive } from "vue"
import { Button } from "frappe-ui"
import { stripHtml } from "@/data/api"
import { getMeta, NO_VALUE_TYPES, type DocField } from "@/data/meta"
import { displayValue } from "@/utils/format"
import FieldControl from "./FieldControl.vue"

const props = defineProps<{ field: DocField; modelValue: Record<string, any>[] | null; readOnly?: boolean; required?: boolean }>()
const emit = defineEmits<{ "update:modelValue": [rows: Record<string, any>[]] }>()

const childDoctype = computed(() => props.field.options || "")
const rows = computed(() => props.modelValue || [])

const fields = computed(() =>
	(getMeta(childDoctype.value)?.fields || []).filter((f) => !NO_VALUE_TYPES.includes(f.fieldtype) && !f.hidden)
)
const columns = computed(() => {
	const listed = fields.value.filter((f) => f.in_list_view)
	return (listed.length ? listed : fields.value).slice(0, 6)
})
/** Fields that have no column, shown when a row is expanded. */
const moreFields = computed(() => fields.value.filter((f) => !columns.value.includes(f)))

const expanded = reactive(new Set<number>())
function toggle(index: number) {
	if (expanded.has(index)) expanded.delete(index)
	else expanded.add(index)
}

function cellText(row: Record<string, any>, field: DocField) {
	const value = row[field.fieldname]
	return typeof value === "string" && /<[a-z]/i.test(value) ? stripHtml(value) : displayValue(value, field.fieldtype)
}

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
	// Row numbers shift, so the expanded rows would point at other rows
	expanded.clear()
	emit(
		"update:modelValue",
		rows.value.filter((_, i) => i !== index)
	)
}
</script>
