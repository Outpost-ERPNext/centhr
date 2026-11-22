<template>
	<Dialog v-model:open="open" :title="`Salary structure rules · ${company}`" size="3xl">
		<div class="flex flex-col gap-3 text-[13px]">
			<template v-if="!editing">
				<div class="flex flex-wrap items-center gap-2">
					<p class="mr-auto max-w-xl text-ch-ink-3">
						A confidential salary structure is paid in its own payroll batch, and only users with its role see its employees, salary slips
						and amounts. A structure with automatic attendance has its employees marked Present on unmarked working days.
					</p>
					<Button v-if="rights.create" variant="solid" icon-left="lucide-plus" label="Add rule" @click="add()" />
				</div>
				<div class="max-h-[52vh] overflow-auto rounded-4 border border-ch-line">
					<table class="w-full min-w-[620px] text-left">
						<thead class="sticky top-0 bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-2 font-normal">Salary structure</th>
								<th class="px-3 py-2 font-normal">Confidential</th>
								<th class="px-3 py-2 font-normal">Attendance</th>
								<th class="px-3 py-2 font-normal">Status</th>
								<th class="w-24 px-3 py-2" />
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in rows" :key="row.name" class="border-t border-ch-line">
								<td class="px-3 py-1.5 font-medium text-ch-ink">{{ row.salary_structure }}</td>
								<td class="px-3 py-1.5 text-ch-ink-2">
									<template v-if="row.confidential">{{ row.batch_name }} batch · seen by {{ row.allowed_role }}</template>
									<template v-else>—</template>
								</td>
								<td class="px-3 py-1.5 text-ch-ink-2">{{ row.auto_attendance ? "Marked automatically" : "—" }}</td>
								<td class="px-3 py-1.5"><StatusBadge pill :tone="row.disabled ? 'gray' : 'green'" :status="row.disabled ? 'Disabled' : 'Active'" /></td>
								<td class="px-3 py-1.5">
									<div class="flex justify-end gap-1">
										<Button v-if="rights.write" size="sm" icon="lucide-pencil" aria-label="Edit" tooltip="Edit" @click="edit(row)" />
										<Button v-if="rights.delete" size="sm" theme="red" icon="lucide-trash-2" aria-label="Delete" tooltip="Delete" @click="confirmRemove(row)" />
									</div>
								</td>
							</tr>
							<tr v-if="!rows.length">
								<td colspan="5" class="px-3 py-6 text-center text-ch-ink-3">
									{{ loading ? "Loading…" : rights.read ? "No rules yet: every salary structure is paid in the Regular batch" : "Only an HR Manager can see these rules" }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>

			<div v-else class="flex flex-col gap-3">
				<LinkField v-model="editing.salary_structure" doctype="Salary Structure" label="Salary structure" required size="md" :filters="structureFilters" :disabled="!!editing.name" />
				<label class="flex items-start gap-2">
					<Checkbox :model-value="!!editing.confidential" @update:model-value="(value) => (editing!.confidential = value ? 1 : 0)" />
					<span>
						<span class="text-ch-ink">Confidential</span>
						<span class="block text-ch-ink-3">Its employees are paid in their own batch and hidden from users without the role.</span>
					</span>
				</label>
				<div v-if="editing.confidential" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<LinkField v-model="editing.allowed_role" doctype="Role" label="Role that may see them" required size="md" />
					<FormControl v-model="editing.batch_name" label="Payroll batch" placeholder="For example: Confidential, Expat" required />
				</div>
				<label class="flex items-start gap-2">
					<Checkbox :model-value="!!editing.auto_attendance" @update:model-value="(value) => (editing!.auto_attendance = value ? 1 : 0)" />
					<span>
						<span class="text-ch-ink">Mark attendance automatically</span>
						<span class="block text-ch-ink-3">
							Daily, and from the Pre-Check Audit, unmarked working days become Present. Holidays, leave and open requests are left alone.
						</span>
					</span>
				</label>
				<label class="flex items-center gap-2 text-ch-ink-2">
					<Checkbox :model-value="!!editing.disabled" @update:model-value="(value) => (editing!.disabled = value ? 1 : 0)" /> Disabled
				</label>
			</div>
		</div>

		<template v-if="editing" #actions>
			<div class="flex justify-end gap-2">
				<Button label="Back" @click="editing = null" />
				<Button variant="solid" label="Save" :disabled="!complete" :loading="saving" @click="saveAndReload" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, watch } from "vue"
import { Button, Checkbox, Dialog, FormControl, dialog, toast } from "frappe-ui"
import LinkField from "@/components/fields/LinkField.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useRecords } from "@/data/records"

/** The company's Payroll Structure Rules: which salary structures are confidential, with their role
 * and batch, and which have attendance marked automatically. */
const props = defineProps<{ company: string }>()
const open = defineModel<boolean>("open", { default: false })

const { rows, loading, saving, editing, rights, load, add, edit, save, remove } = useRecords<Record<string, any>>(
	"Payroll Structure Rule",
	["salary_structure", "company", "confidential", "allowed_role", "batch_name", "auto_attendance", "disabled"],
	() => ({ confidential: 0, auto_attendance: 0, disabled: 0 })
)
const reload = () => load([["company", "=", props.company]])
watch(open, (value) => {
	if (!value) return
	editing.value = null
	reload()
})

const structureFilters = computed(() => ({ company: props.company, docstatus: 1 }))
const complete = computed(() => {
	const rule = editing.value
	return !!rule?.salary_structure && (!rule.confidential || !!(rule.allowed_role && rule.batch_name?.trim()))
})

async function saveAndReload() {
	await save()
	toast.success("Rule saved")
	await reload()
}

function confirmRemove(row: Record<string, any>) {
	dialog.confirm({
		title: "Delete rule",
		message: `Delete the rule of ${row.salary_structure}? Its employees are paid in the Regular batch again and everyone who may see salaries sees theirs.`,
		confirmLabel: "Delete",
		theme: "red",
		onConfirm: async () => {
			await remove(row)
			await reload()
		},
	})
}
</script>
