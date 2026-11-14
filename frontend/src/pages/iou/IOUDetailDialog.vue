<template>
	<Dialog v-model:open="isOpen" title="Transaction Details" size="2xl">
		<template #default>
			<div v-if="loading" class="flex h-48 items-center justify-center text-sm text-ch-ink-3">
				Loading details…
			</div>
			<div v-else-if="row" class="flex flex-col gap-5 py-1 text-[13px]">
				<!-- Top Header Details -->
				<div class="flex flex-wrap items-center justify-between gap-2 rounded-4 border border-ch-line bg-ch-subtle/50 p-3">
					<div class="flex items-center gap-2">
						<span class="text-[15px] font-semibold text-ch-ink">{{ row.name }}</span>
						<span
							class="rounded-full px-2.5 py-0.5 text-[11px] font-medium"
							:class="categoryClass(row.category)"
						>
							{{ row.category }}
						</span>
						<StatusBadge :doctype="row.doctype" :status="row.status" pill />
					</div>
					<div class="flex items-center gap-2">
						<Button
							size="sm"
							icon-left="lucide-external-link"
							label="Open Desk"
							@click="openDeskDoc(row.doctype, row.name)"
						/>
					</div>
				</div>

				<!-- Overview Grid -->
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
					<div class="flex flex-col gap-0.5">
						<span class="text-[11px] font-medium uppercase tracking-wider text-ch-ink-3">Employee</span>
						<span class="font-medium text-ch-ink">{{ row.employee_name }}</span>
						<span class="text-[11.5px] text-ch-ink-3">{{ row.employee }}</span>
					</div>
					<div class="flex flex-col gap-0.5">
						<span class="text-[11px] font-medium uppercase tracking-wider text-ch-ink-3">Department</span>
						<span class="text-ch-ink">{{ row.department || "—" }}</span>
					</div>
					<div class="flex flex-col gap-0.5">
						<span class="text-[11px] font-medium uppercase tracking-wider text-ch-ink-3">Application Date</span>
						<span class="text-ch-ink">{{ formatDateShort(row.posting_date) }}</span>
					</div>
					<div class="flex flex-col gap-0.5">
						<span class="text-[11px] font-medium uppercase tracking-wider text-ch-ink-3">Due Date</span>
						<div class="flex items-center gap-1.5">
							<span class="text-ch-ink">{{ row.due_date ? formatDateShort(row.due_date) : "—" }}</span>
							<span
								v-if="row.is_overdue"
								class="rounded px-1.5 py-0.2 text-[10.5px] font-medium bg-ch-red-bg text-ch-red-ink"
							>
								Overdue
							</span>
						</div>
					</div>
				</div>

				<!-- Financial Breakdown -->
				<div class="rounded-4 border border-ch-line p-3.5">
					<h4 class="mb-2 text-[12px] font-semibold uppercase tracking-wider text-ch-ink-3">Financial Details</h4>
					<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
						<div class="flex flex-col gap-0.5">
							<span class="text-[11.5px] text-ch-ink-3">Total Amount</span>
							<span class="text-[16px] font-semibold text-ch-ink">{{ formatCurrency(row.amount) }}</span>
						</div>
						<div v-if="row.outstanding_amount !== undefined" class="flex flex-col gap-0.5">
							<span class="text-[11.5px] text-ch-ink-3">Outstanding</span>
							<span class="text-[16px] font-semibold text-ch-amber-ink">{{ formatCurrency(row.outstanding_amount) }}</span>
						</div>
						<div v-if="detailDoc?.claim_method" class="flex flex-col gap-0.5">
							<span class="text-[11.5px] text-ch-ink-3">Claim Method</span>
							<span class="font-medium text-ch-ink">{{ detailDoc.claim_method }}</span>
						</div>
						<div v-if="row.employee_advance" class="flex flex-col gap-0.5">
							<span class="text-[11.5px] text-ch-ink-3">Linked Advance</span>
							<a
								href="javascript:void(0)"
								class="font-medium text-ch-primary underline hover:text-ch-primary-hover"
								@click="openDeskDoc('Employee Advance', row.employee_advance!)"
							>
								{{ row.employee_advance }} ↗
							</a>
						</div>
					</div>

					<!-- Bank details if available -->
					<div v-if="detailDoc?.bank_name || detailDoc?.bank_ac_no" class="mt-3 border-t border-ch-line pt-2 text-[12px] text-ch-ink-2">
						<span class="font-medium text-ch-ink">Bank Account:</span>
						{{ detailDoc.bank_name || "Bank" }} · {{ detailDoc.bank_ac_no || "—" }}
					</div>

					<div v-if="row.rejection_reason" class="mt-2 text-[12.5px] text-ch-red-ink">
						<span class="font-medium">Reason for Rejection:</span> {{ row.rejection_reason }}
					</div>
					<div v-if="row.purpose" class="mt-2 text-[12.5px] text-ch-ink-2">
						<span class="font-medium text-ch-ink">Purpose:</span> {{ row.purpose }}
					</div>
				</div>

				<!-- Approval Trail -->
				<div class="rounded-4 border border-ch-line p-3.5">
					<h4 class="mb-2 text-[12px] font-semibold uppercase tracking-wider text-ch-ink-3">Approval Trail</h4>
					<div class="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
						<!-- HOD -->
						<div class="flex flex-col gap-1 rounded-3 bg-ch-subtle/60 p-2.5">
							<div class="flex items-center justify-between">
								<span class="text-[11px] font-semibold uppercase text-ch-ink-3">HOD Approver</span>
								<span class="rounded px-1.5 py-0.5 text-[10.5px] font-medium" :class="approverTone(row.approvers?.hod?.status)">
									{{ row.approvers?.hod?.status || "Pending" }}
								</span>
							</div>
							<span class="font-medium text-ch-ink">{{ row.approvers?.hod?.name || row.approvers?.hod?.user || "—" }}</span>
							<span v-if="row.approvers?.hod?.datetime" class="text-[11px] text-ch-ink-3">
								{{ formatDateTime(row.approvers?.hod?.datetime) }}
							</span>
							<span v-if="row.approvers?.hod?.reason" class="text-[11px] text-ch-red-ink">
								Reason: {{ row.approvers?.hod?.reason }}
							</span>
						</div>

						<!-- Finance 1 -->
						<div class="flex flex-col gap-1 rounded-3 bg-ch-subtle/60 p-2.5">
							<div class="flex items-center justify-between">
								<span class="text-[11px] font-semibold uppercase text-ch-ink-3">Finance 1</span>
								<span class="rounded px-1.5 py-0.5 text-[10.5px] font-medium" :class="approverTone(row.approvers?.finance_1?.status)">
									{{ row.approvers?.finance_1?.status || "Pending" }}
								</span>
							</div>
							<span class="font-medium text-ch-ink">{{ row.approvers?.finance_1?.name || row.approvers?.finance_1?.user || "—" }}</span>
							<span v-if="row.approvers?.finance_1?.datetime" class="text-[11px] text-ch-ink-3">
								{{ formatDateTime(row.approvers?.finance_1?.datetime) }}
							</span>
							<span v-if="row.approvers?.finance_1?.reason" class="text-[11px] text-ch-red-ink">
								Reason: {{ row.approvers?.finance_1?.reason }}
							</span>
						</div>

						<!-- Finance 2 -->
						<div class="flex flex-col gap-1 rounded-3 bg-ch-subtle/60 p-2.5">
							<div class="flex items-center justify-between">
								<span class="text-[11px] font-semibold uppercase text-ch-ink-3">Finance 2</span>
								<span class="rounded px-1.5 py-0.5 text-[10.5px] font-medium" :class="approverTone(row.approvers?.finance_2?.status)">
									{{ row.approvers?.finance_2?.status || "Pending" }}
								</span>
							</div>
							<span class="font-medium text-ch-ink">{{ row.approvers?.finance_2?.name || row.approvers?.finance_2?.user || "—" }}</span>
							<span v-if="row.approvers?.finance_2?.datetime" class="text-[11px] text-ch-ink-3">
								{{ formatDateTime(row.approvers?.finance_2?.datetime) }}
							</span>
						</div>
					</div>
				</div>

				<!-- Expenses Table if available -->
				<div v-if="expenses && expenses.length" class="rounded-4 border border-ch-line p-3.5">
					<h4 class="mb-2 text-[12px] font-semibold uppercase tracking-wider text-ch-ink-3">
						Claim Expenses ({{ expenses.length }})
					</h4>
					<div class="overflow-x-auto">
						<table class="w-full text-left text-[12.5px]">
							<thead>
								<tr class="border-b border-ch-line text-ch-ink-3">
									<th class="py-1.5 pr-2 font-medium">Claim Type</th>
									<th class="py-1.5 pr-2 font-medium">Description</th>
									<th class="py-1.5 pr-2 font-medium">Cost Center</th>
									<th class="py-1.5 pr-2 font-medium">Amount</th>
									<th class="py-1.5 text-right font-medium">Receipt</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(exp, idx) in expenses" :key="idx" class="border-b border-ch-line/60">
									<td class="py-1.5 pr-2 font-medium text-ch-ink">{{ exp.expense_claim_type || exp.expense_type }}</td>
									<td class="py-1.5 pr-2 text-ch-ink-2">{{ exp.description || "—" }}</td>
									<td class="py-1.5 pr-2 text-ch-ink-3">{{ exp.cost_center || "—" }}</td>
									<td class="py-1.5 pr-2 font-medium text-ch-ink tabular-nums">{{ formatCurrency(exp.amount) }}</td>
									<td class="py-1.5 text-right">
										<a
											v-if="exp.attachment"
											:href="exp.attachment"
											target="_blank"
											class="inline-flex items-center gap-1 rounded bg-ch-subtle px-1.5 py-0.5 text-[11px] text-ch-ink-2 hover:text-ch-ink"
										>
											<span class="lucide-paperclip size-3" /> View
										</a>
										<span v-else class="text-ch-ink-4">—</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Close" @click="isOpen = false" />
				<!-- What the current user can do now (SOP approval steps) -->
				<Button
					v-for="action in detailDoc?.actions || []"
					:key="action"
					:variant="action === 'Approve' || action === 'Pay' ? 'solid' : 'subtle'"
					:theme="action === 'Reject' ? 'red' : 'gray'"
					:label="action"
					@click="emit('action', action)"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { getIOUDetail, type IOUAction, type IOURow, type IOUExpenseItem } from "@/data/iou"
import { formatCurrency, formatDateShort, formatDateTime } from "@/utils/format"

const props = defineProps<{
	modelValue: boolean
	row: IOURow | null
}>()

const emit = defineEmits<{
	"update:modelValue": [value: boolean]
	action: [action: IOUAction]
}>()

const isOpen = computed({
	get: () => props.modelValue,
	set: (v) => emit("update:modelValue", v),
})

const loading = ref(false)
const detailDoc = ref<Record<string, any> | null>(null)
const expenses = ref<IOUExpenseItem[]>([])

watch(
	() => props.row,
	async (newRow) => {
		if (!newRow) {
			detailDoc.value = null
			expenses.value = []
			return
		}
		loading.value = true
		try {
			const res = await getIOUDetail(newRow.name, newRow.doctype)
			detailDoc.value = res
			expenses.value = res.expenses || []
		} catch {
			detailDoc.value = null
			expenses.value = []
		} finally {
			loading.value = false
		}
	},
	{ immediate: true }
)

function openDeskDoc(doctype: string, name: string) {
	const slug = doctype.toLowerCase().replace(/ /g, "-")
	window.open(`/desk/${slug}/${encodeURIComponent(name)}`, "_blank")
}

function categoryClass(category: string) {
	if (category === "IOU Application") {
		return "bg-ch-blue-bg text-ch-blue-ink"
	}
	if (category === "IOU Claim Settlement – No Linked IOU") {
		return "bg-ch-amber-bg text-ch-amber-ink"
	}
	return "bg-ch-green-bg text-ch-green-ink"
}

function approverTone(status: string | undefined): string {
	if (status === "Approved") return "bg-ch-green-bg text-ch-green-ink"
	if (status === "Rejected") return "bg-ch-red-bg text-ch-red-ink"
	if (status === "Pending") return "bg-ch-amber-bg text-ch-amber-ink"
	return "bg-ch-subtle text-ch-ink-3"
}
</script>
