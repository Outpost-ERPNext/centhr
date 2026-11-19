<template>
	<div class="flex flex-col gap-3 px-5 py-3">
		<div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
			<StatCard label="Pending advances" :value="`${advances.length}`" :loading="loading" />
			<StatCard label="Unrecovered amount" :value="formatCurrency(sum(advances, 'pending_amount'))" tone="amber" :loading="loading" />
			<StatCard label="Deductions this cycle" :value="`${deductions.length}`" :loading="loading" />
			<StatCard label="Deducted this cycle" :value="formatCurrency(sum(deductions, 'amount'))" tone="red" :loading="loading" />
		</div>

		<div
			v-if="scope.company && data"
			class="flex flex-wrap items-center gap-2 rounded-4 px-4 py-2.5 text-[13px]"
			:class="data.auto_recovery ? 'bg-ch-green-bg text-ch-green-ink' : 'bg-ch-subtle text-ch-ink-2'"
		>
			<span class="size-4" :class="data.auto_recovery ? 'lucide-circle-check' : 'lucide-circle-pause'" />
			<span>
				<b>Auto-recovery {{ data.auto_recovery ? "active" : "inactive" }}.</b>
				{{
					data.auto_recovery
						? `When payroll is generated for ${scope.company}, overdue advances are deducted from that cycle's salary.`
						: `Overdue advances of ${scope.company} are deducted only when you recover them here. Turn it on in Payroll settings.`
				}}
			</span>
		</div>

		<section class="rounded-5 border border-ch-line bg-ch-surface">
			<header class="flex flex-wrap items-center gap-2 border-b border-ch-line px-4 py-2.5">
				<h3 class="text-[14px] font-medium text-ch-ink">Pending employee advances</h3>
				<span class="text-[12.5px] text-ch-ink-3">Paid, not yet settled by an expense claim, a return or payroll</span>
				<Button
					v-if="scope.company && can('Additional Salary').create"
					class="ml-auto"
					size="sm"
					icon-left="lucide-hand-coins"
					:label="`Recover all due (${dueCount})`"
					:disabled="!dueCount"
					:loading="recoveringAll"
					@click="confirmRecoverAll"
				/>
			</header>
			<DataTable :columns="advanceColumns" :rows="advances" :loading="loading" :error="error" empty-icon="lucide-hand-coins" empty-message="No unrecovered advances" min-width="1000px" @row-click="(row) => (quickView = row.name)">
				<template #cell-employee_name="{ row }">
					<EmployeeCell :employee="row.employee" :name="row.employee_name" :detail="`${row.employee} · ${row.name}`" />
				</template>
				<template #cell-state="{ row }">
					<StatusBadge pill :tone="row.recovery_scheduled ? 'blue' : row.overdue ? 'amber' : 'gray'" :status="row.recovery_scheduled ? 'Recovery scheduled' : row.overdue ? 'Due this cycle' : 'Upcoming'" />
				</template>
				<template #cell-actions="{ row }">
					<div class="flex justify-end" @click.stop>
						<Button
							v-if="row.repay_unclaimed_amount_from_salary && !row.recovery_scheduled"
							size="sm"
							label="Recover in payroll"
							@click="startRecovery(row)"
						/>
					</div>
				</template>
			</DataTable>
		</section>

		<section class="rounded-5 border border-ch-line bg-ch-surface">
			<header class="flex items-center gap-2 border-b border-ch-line px-4 py-2.5">
				<h3 class="text-[14px] font-medium text-ch-ink">Deductions this cycle</h3>
				<span class="text-[12.5px] text-ch-ink-3">Additional Salary deductions dated in the cycle</span>
			</header>
			<DataTable :columns="deductionColumns" :rows="deductions" :loading="loading" empty-icon="lucide-minus-circle" empty-message="No deductions in this cycle" min-width="760px" @row-click="openDeduction">
				<template #cell-employee_name="{ row }">
					<EmployeeCell :employee="row.employee" :name="row.employee_name" />
				</template>
				<template #cell-ref_docname="{ row }">
					<span class="text-ch-ink-2">{{ row.ref_docname || "—" }}</span>
				</template>
			</DataTable>
		</section>
	</div>

	<Dialog v-model:open="recoverOpen" title="Recover advance in payroll">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Deducts {{ recovering && formatCurrency(recovering.pending_amount, recovering.currency) }} from
				{{ recovering?.employee_name }}'s salary in this cycle, as an Additional Salary.
			</p>
			<LinkField v-model="component" doctype="Salary Component" label="Deduction component" required size="md" :filters="{ type: 'Deduction', disabled: 0 }" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="recoverOpen = false" />
				<Button variant="solid" label="Recover" :disabled="!component" :loading="saving" @click="recover" />
			</div>
		</template>
	</Dialog>

	<AdvanceQuickView :name="quickView" @close="quickView = null" @recover="recoverFromQuickView" />

	<Dialog :open="!!deduction" title="Salary deduction" @update:open="(value: boolean) => !value && (deduction = null)">
		<dl v-if="deduction" class="text-[13px]">
			<div v-for="item in deductionFacts" :key="item.label" class="flex justify-between gap-3 py-1">
				<dt class="shrink-0 text-ch-ink-3">{{ item.label }}</dt>
				<dd class="truncate text-right text-ch-ink">{{ item.value || "—" }}</dd>
			</div>
		</dl>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button icon-left="lucide-external-link" label="Open in Desk" @click="openDesk('additional-salary', deduction!.name)" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, dialog, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import LinkField from "@/components/fields/LinkField.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import AdvanceQuickView from "../AdvanceQuickView.vue"
import EmployeeCell from "./EmployeeCell.vue"
import { getAdvances, recoverAdvance, recoverOverdueAdvances, useTabData, type AdvanceDetails, type Scope } from "@/data/payrollDashboard"
import { can } from "@/data/permissions"
import { formatCurrency, formatDateShort } from "@/utils/format"

const props = defineProps<{ scope: Scope }>()
const { data, loading, error, reload } = useTabData(props.scope, getAdvances)

const advances = computed(() => data.value?.advances || [])
const deductions = computed(() => data.value?.deductions || [])
const sum = (rows: Record<string, any>[], key: string) => rows.reduce((total, r) => total + (r[key] || 0), 0)

// Due in this cycle and not scheduled for deduction yet
const dueCount = computed(() => advances.value.filter((r) => r.overdue && !r.recovery_scheduled).length)
const recoveringAll = ref(false)

function confirmRecoverAll() {
	dialog.confirm({
		title: "Recover all due advances",
		message: `Deduct ${dueCount.value} overdue advances of ${props.scope.company} from the salaries of ${cycleLabel(props.scope.from, props.scope.to)}? Advances with an expense claim still in approval are skipped.`,
		confirmLabel: "Recover",
		onConfirm: async () => {
			recoveringAll.value = true
			try {
				const count = await recoverOverdueAdvances(props.scope)
				toast.success(`${count} deductions added to this cycle`)
				await reload()
			} finally {
				recoveringAll.value = false
			}
		},
	})
}

const recoverOpen = ref(false)
const recovering = ref<Record<string, any> | null>(null)
const component = ref<string | null>(null)
const saving = ref(false)

function openDesk(route: string, name: string) {
	window.open(`/desk/${route}/${encodeURIComponent(name)}`, "_blank")
}

// Rows open on this page, as salary slips do; Desk is one click further
const quickView = ref<string | null>(null)
const deduction = ref<Record<string, any> | null>(null)

/** A deduction made for an advance shows that advance; any other deduction shows its own details. */
function openDeduction(row: Record<string, any>) {
	if (row.ref_doctype === "Employee Advance" && row.ref_docname) quickView.value = row.ref_docname
	else deduction.value = row
}

const deductionFacts = computed(() => [
	{ label: "Employee", value: `${deduction.value!.employee_name} (${deduction.value!.employee})` },
	{ label: "Component", value: deduction.value!.salary_component },
	{ label: "Amount", value: formatCurrency(deduction.value!.amount, deduction.value!.currency) },
	{ label: "Payroll date", value: formatDateShort(deduction.value!.payroll_date) },
	{ label: "Record", value: deduction.value!.name },
])

function recoverFromQuickView(advance: AdvanceDetails) {
	quickView.value = null
	startRecovery({ ...advance, pending_amount: advance.outstanding_amount })
}

function startRecovery(row: Record<string, any>) {
	recovering.value = row
	component.value = null
	recoverOpen.value = true
}

async function recover() {
	saving.value = true
	try {
		const name = await recoverAdvance(recovering.value!.name, component.value!, props.scope.to)
		toast.success(`Deduction ${name} added to this cycle`)
		recoverOpen.value = false
		await reload()
	} finally {
		saving.value = false
	}
}

const money = (label: string, key: string): Column => ({ key, label, width: "minmax(110px,1fr)", align: "right", format: (v, r) => formatCurrency(v, r.currency) })
const advanceColumns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,1.8fr)" },
	{ key: "posting_date", label: "Date", width: "100px", format: (v) => formatDateShort(v) },
	{ key: "due_date", label: "Due", width: "100px", format: (v) => (v ? formatDateShort(v) : "—") },
	money("Advance", "advance_amount"),
	money("Paid", "paid_amount"),
	money("Pending", "pending_amount"),
	{ key: "state", label: "Status", width: "150px" },
	{ key: "actions", label: "", width: "150px", align: "right" },
]
const deductionColumns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,1.8fr)", class: "font-medium" },
	{ key: "salary_component", label: "Component", width: "minmax(140px,1.2fr)" },
	{ key: "ref_docname", label: "Employee advance", width: "minmax(140px,1.2fr)" },
	{ key: "payroll_date", label: "Payroll date", width: "110px", format: (v) => formatDateShort(v) },
	money("Amount", "amount"),
]
</script>
