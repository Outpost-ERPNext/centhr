<template>
	<Dialog v-model:open="open" title="Statutory obligations" size="3xl">
		<div class="flex flex-col gap-3 text-[13px]">
			<template v-if="!editing">
				<div class="flex flex-wrap items-center gap-2">
					<p class="mr-auto max-w-lg text-ch-ink-3">
						Each obligation is a statutory payment, such as tax or pension, that payroll accrues to a liability account and that is paid by
						a deadline.
					</p>
					<Button v-if="rights.create" variant="solid" icon-left="lucide-plus" label="Add obligation" @click="add({ company: company || undefined })" />
				</div>
				<div class="max-h-[52vh] overflow-auto rounded-4 border border-ch-line">
					<table class="w-full min-w-[640px] text-left">
						<thead class="sticky top-0 bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-2 font-normal">Obligation</th>
								<th class="px-3 py-2 font-normal">Liability account</th>
								<th class="px-3 py-2 font-normal">Due</th>
								<th class="px-3 py-2 font-normal">Status</th>
								<th class="w-24 px-3 py-2" />
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in rows" :key="row.name" class="border-t border-ch-line">
								<td class="px-3 py-1.5">
									<div class="font-medium text-ch-ink">{{ row.obligation_name }}</div>
									<div v-if="!company" class="text-[12px] text-ch-ink-3">{{ row.company }}</div>
								</td>
								<td class="px-3 py-1.5 text-ch-ink-2">{{ row.liability_account }}</td>
								<td class="px-3 py-1.5 text-ch-ink-2">{{ row.frequency }}, day {{ row.due_day }}</td>
								<td class="px-3 py-1.5"><StatusBadge pill :tone="row.disabled ? 'gray' : 'green'" :status="row.disabled ? 'Disabled' : 'Active'" /></td>
								<td class="px-3 py-1.5">
									<div class="flex justify-end gap-1">
										<Button v-if="rights.write" size="sm" icon="lucide-pencil" aria-label="Edit" tooltip="Edit" @click="edit(row)" />
										<Button v-if="rights.delete" size="sm" theme="red" icon="lucide-trash-2" aria-label="Delete" tooltip="Delete" @click="confirmRemove(row)" />
									</div>
								</td>
							</tr>
							<tr v-if="!rows.length">
								<td colspan="5" class="px-3 py-6 text-center text-ch-ink-3">{{ loading ? "Loading…" : "No obligations set up yet" }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>

			<div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl v-model="editing.obligation_name" label="Obligation" placeholder="For example: PAYE, Pension" required />
				<LinkField v-model="editing.company" doctype="Company" label="Company" required size="md" :disabled="!!editing.name" />
				<LinkField v-model="editing.liability_account" doctype="Account" label="Liability account" required size="md" :filters="liabilityFilters" />
				<LinkField v-model="editing.payment_account" doctype="Account" label="Usually paid from" size="md" :filters="paymentFilters" />
				<FormControl v-model="editing.frequency" type="select" label="Falls due" :options="FREQUENCIES" />
				<FormControl v-model="editing.due_day" type="number" label="Due on day of the month" :min="1" :max="31" />
				<FormControl
					v-if="editing.frequency !== 'Monthly'"
					v-model="editing.due_months"
					label="Due months"
					placeholder="For example: 1, 4, 7, 10"
					description="Month numbers, separated by commas. Leave empty for the usual months of the frequency."
				/>
				<label class="flex items-center gap-2 self-end pb-1 text-ch-ink-2"><Checkbox v-model="disabled" /> Disabled</label>
				<p class="text-ch-ink-3 sm:col-span-2">
					The liability account is the plain liability account that payroll credits for this obligation, not a payable party account.
				</p>
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

const FREQUENCIES = ["Monthly", "Quarterly", "Bi-Annually", "Yearly"]

/** Set up the statutory obligations of the company without leaving the dashboard. What a user may do
 * here follows their rights on Statutory Obligation. */
const props = defineProps<{ company: string }>()
const emit = defineEmits<{ changed: [] }>()
const open = defineModel<boolean>("open", { default: false })

const { rows, loading, saving, editing, rights, load, add, edit, save, remove } = useRecords<Record<string, any>>(
	"Statutory Obligation",
	["obligation_name", "company", "liability_account", "payment_account", "frequency", "due_day", "due_months", "disabled"],
	() => ({ frequency: "Monthly", due_day: 10, disabled: 0 })
)
const reload = () => load(props.company ? [["company", "=", props.company]] : [])
watch(open, (value) => {
	if (!value) return
	editing.value = null
	reload()
})

const liabilityFilters = computed(() => ({ company: editing.value?.company, is_group: 0, root_type: "Liability", account_type: ["not in", ["Payable", "Receivable"]] }))
const paymentFilters = computed(() => ({ company: editing.value?.company, is_group: 0, account_type: ["in", ["Bank", "Cash"]] }))
const complete = computed(() => !!(editing.value?.obligation_name && editing.value.company && editing.value.liability_account && editing.value.due_day))
const disabled = computed({
	get: () => !!editing.value?.disabled,
	set: (value: boolean) => (editing.value!.disabled = value ? 1 : 0),
})

async function saveAndReload() {
	await save()
	toast.success("Obligation saved")
	emit("changed")
	await reload()
}

function confirmRemove(row: Record<string, any>) {
	dialog.confirm({
		title: "Delete obligation",
		message: `Delete ${row.obligation_name}? Its ledger entries stay as they are; the Compliance tab only stops tracking it.`,
		confirmLabel: "Delete",
		theme: "red",
		onConfirm: async () => {
			await remove(row)
			emit("changed")
			await reload()
		},
	})
}
</script>
