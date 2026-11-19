<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
			<StatCard label="Total headcount" :value="formatNumber(totals.headcount)" :change="change(totals.headcount, previous.headcount)" :loading="loading" />
			<StatCard label="Total gross pay" :value="money(totals.gross_pay)" :change="change(totals.gross_pay, previous.gross_pay)" tone="blue" :loading="loading" />
			<StatCard label="Total deductions" :value="money(totals.total_deduction)" :change="change(totals.total_deduction, previous.total_deduction)" tone="amber" :loading="loading" />
			<StatCard label="Total net pay" :value="money(totals.net_pay)" :change="change(totals.net_pay, previous.net_pay)" tone="green" :loading="loading" />
		</div>

		<CollapsibleSection title="Payroll entries" storage-key="dashboard-runs" :summary="runsSummary">
			<div class="flex flex-col gap-2">
				<div class="flex flex-wrap items-center gap-2 text-[13px] text-ch-ink-3">
					<span>
						{{ eligible }} active employees with a salary structure have no slip yet<template v-if="exited">, and {{ exited }} who left in this cycle</template>.
					</span>
					<div v-if="canGenerate" class="ml-auto">
						<Dropdown :options="generateOptions" align="end">
						<Button
							variant="solid"
							icon-left="lucide-play"
							icon-right="lucide-chevron-down"
							label="Generate"
							:tooltip="scope.company ? undefined : 'Choose a company to generate its payroll'"
							:disabled="!scope.company"
							:loading="generating"
						/>
						</Dropdown>
					</div>
				</div>
				<PayrollRunCard v-for="run in data?.runs || []" :key="run.name" :run="run" @changed="refresh" />
			</div>
		</CollapsibleSection>

		<div class="flex flex-wrap items-center gap-2">
			<h3 class="text-[14px] font-medium text-ch-ink">Salary slips</h3>
			<SegmentedTabs v-model="status" :tabs="STATUSES.map((s) => ({ label: s, value: s, count: statusCounts[s] }))" />
			<button
				v-if="excelNote"
				type="button"
				class="rounded-full bg-ch-subtle px-3 py-1 text-[12px] text-ch-ink-2 hover:text-ch-ink"
				title="Open the Excel reconciliation"
				@click="reconcileOpen = true"
			>
				Excel · {{ excelNote }}
			</button>
		</div>
	</div>

	<FilterBar v-model:search="search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="salary slip" @clear="clear">
		<FilterLink v-model="department" doctype="Department" placeholder="Department" :filters="scope.company ? { company: scope.company } : undefined" />
		<FilterSelect v-if="reconciled?.rows?.length" v-model="excelStatus" :options="EXCEL_STATUSES" placeholder="Excel" />
		<Button icon-left="lucide-scale" label="Reconcile with Excel" @click="reconcileOpen = true" />
		<Button icon-left="lucide-file-spreadsheet" label="Export (Excel)" :disabled="!filtered.length" :loading="exporting" @click="exportRows" />
	</FilterBar>

	<div v-if="selected.length" class="mx-5 mb-2 flex flex-wrap items-center gap-2 rounded-4 bg-ch-subtle px-3 py-2 text-[13px]">
		<span class="font-medium">{{ selected.length }} selected</span>
		<Button size="sm" variant="solid" label="Submit" :loading="bulk === 'submit'" @click="runBulk('submit')" />
		<Button size="sm" icon-left="lucide-refresh-cw" label="Recalculate" :loading="bulk === 'recalculate'" @click="runBulk('recalculate')" />
		<Button size="sm" theme="red" icon-left="lucide-trash-2" label="Delete" :loading="bulk === 'delete'" @click="runBulk('delete')" />
		<Button size="sm" variant="ghost" label="Clear selection" class="ml-auto" @click="selected = []" />
	</div>

	<DataTable
		v-model:selected="selected"
		selectable
		:columns="columns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:show-clear="hasFilters"
		empty-icon="lucide-receipt"
		:empty-message="hasFilters ? 'No salary slips match these filters' : 'No salary slips in this cycle yet'"
		mobile-aside="net_pay"
		min-width="1080px"
		@row-click="(row) => (quickView = row.name)"
		@clear-filters="clear"
	>
		<template #cell-employee="{ row }">
			<EmployeeCell :employee="row.employee" :name="row.employee_name" :detail="[row.employee, row.department].filter(Boolean).join(' · ')" />
		</template>
		<template #cell-status="{ row }">
			<StatusBadge pill doctype="Salary Slip" :status="row.status" />
		</template>
		<template #cell-absent_days="{ row }">
			<span :class="row.absent_days ? 'font-medium text-ch-red-ink' : 'text-ch-ink-3'">{{ formatNumber(row.absent_days) }}</span>
		</template>
		<template #cell-leave_without_pay="{ row }">
			<span :class="row.leave_without_pay ? 'font-medium text-ch-amber-ink' : 'text-ch-ink-3'">{{ formatNumber(row.leave_without_pay) }}</span>
		</template>
		<template #cell-net_pay="{ row }">
			<span class="font-medium" :class="row.net_pay > 0 ? 'text-ch-green-ink' : 'text-ch-red-ink'">{{ formatCurrency(row.net_pay, row.currency) }}</span>
		</template>
		<template #cell-excel="{ row }">
			<StatusBadge v-if="excel[row.employee]" pill :tone="EXCEL_TONES[excel[row.employee]]" :status="excel[row.employee]" />
		</template>
		<template #cell-actions="{ row }">
			<div v-if="row.docstatus === 0" class="flex justify-end gap-1" @click.stop>
				<Button size="sm" icon="lucide-refresh-cw" aria-label="Recalculate" tooltip="Recalculate" @click="runOne('recalculate', row.name)" />
				<Button size="sm" theme="red" icon="lucide-trash-2" aria-label="Delete" tooltip="Delete" @click="runOne('delete', row.name)" />
			</div>
		</template>
	</DataTable>
	<Pager v-model:page="page" v-model:page-size="pageSize" :total="filtered.length" />

	<SalarySlipQuickView :name="quickView" @close="quickView = null" @action="quickAction" />
	<ExcelReconcileDialog v-model:open="reconcileOpen" v-model:result="reconciled" :scope="scope" :loading="reconciling" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { Button, Dropdown, dialog, toast } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import ExcelReconcileDialog from "../ExcelReconcileDialog.vue"
import PayrollRunCard from "../PayrollRunCard.vue"
import SalarySlipQuickView from "../SalarySlipQuickView.vue"
import EmployeeCell from "./EmployeeCell.vue"
import { cycleLabel } from "@/data/payroll"
import { getReconciliation } from "@/data/masterSheet"
import { change, exportSlips, getProcessing, updateSlips, useTabData, type Scope, type Totals } from "@/data/payrollDashboard"
import { generatePayroll, type PayrollBatch } from "@/data/payrollRun"
import { can } from "@/data/permissions"
import type { SalaryRow } from "@/data/salaryOverview"
import { formatCurrency, formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"

const props = defineProps<{ scope: Scope; employees: SalaryRow[] }>()
const emit = defineEmits<{ changed: [] }>()
const { data, loading, error, reload } = useTabData(props.scope, getProcessing)

const STATUSES = ["All", "Draft", "Submitted", "Withheld"]
const EMPTY: Totals = { headcount: 0, gross_pay: 0, total_deduction: 0, net_pay: 0 }
const POLL_MS = 3000

const status = ref("All")
const search = ref("")
const department = ref("")
const selected = ref<string[]>([])
const page = ref(1)
const pageSize = ref(20)
const bulk = ref<string | null>(null)
const generating = ref(false)
const exporting = ref(false)

const totals = computed(() => data.value?.totals || EMPTY)
const previous = computed(() => data.value?.previous || EMPTY)
const currency = computed(() => data.value?.slips[0]?.currency)
const money = (v: number) => formatCurrency(v, currency.value)
const canGenerate = computed(() => can("Payroll Entry").create && can("Payroll Entry").submit)
const leftInCycle = (r: SalaryRow) => !!r.relieving_date && r.relieving_date >= props.scope.from && r.relieving_date <= props.scope.to
const eligible = computed(() => props.employees.filter((r) => r.status === "Active" && r.assignment && !r.salary_slip && !leftInCycle(r)).length)
/** Each batch is generated once per company and cycle. */
const hasRun = (batch: PayrollBatch) => (data.value?.runs || []).some((r) => r.company === props.scope.company && r.batch === batch)
// Employees who left in the cycle are paid in their own batch
const exited = computed(() => props.employees.filter((r) => leftInCycle(r) && r.assignment && !r.salary_slip).length)
const generateOptions = computed(() => [
	{
		label: "Regular payroll",
		description: hasRun("Regular") ? "Generated for this cycle" : `${eligible.value} employees waiting`,
		icon: "lucide-users",
		disabled: !eligible.value || hasRun("Regular"),
		onClick: () => confirmGenerate("Regular"),
	},
	{
		label: "Exited employees",
		description: hasRun("Exited") ? "Generated for this cycle" : `${exited.value} left in this cycle`,
		icon: "lucide-user-minus",
		disabled: !exited.value || hasRun("Exited"),
		onClick: () => confirmGenerate("Exited"),
	},
])

// Opened from a row; the full slip is one click further
const quickView = ref<string | null>(null)
const reconcileOpen = ref(false)
// The cycle's master sheet against its slips; the dialog replaces it after an upload or a new mapping
const { data: reconciled, loading: reconciling, reload: reconcile } = useTabData(props.scope, getReconciliation)
const EXCEL_TONES: Record<string, Tone> = { Matched: "green", Discrepancy: "red", "Missing in Excel": "amber" }
const EXCEL_STATUSES = Object.keys(EXCEL_TONES)
const excelStatus = ref("")
/** How each employee's slip compares with the master sheet, shown as a badge on the slip. */
const excel = computed(() => Object.fromEntries((reconciled.value?.rows || []).map((r) => [r.employee, r.status])))
// Without a compared sheet the Excel filter is hidden, so it must not go on filtering
watch(reconciled, (value) => !value?.rows?.length && (excelStatus.value = ""))
const excelNote = computed(() => {
	const summary = reconciled.value?.rows?.length ? reconciled.value.summary : undefined
	if (!summary) return ""
	return `${summary.Matched} matched · ${summary.Discrepancy} discrepancies · ${summary["Missing in ERP"]} missing in ERP`
})
// Who a payroll run pays: active employees with a salary structure and no slip in the cycle yet
const runsSummary = computed(() => {
	const runs = data.value?.runs || []
	return runs.length ? `${runs.length} in this cycle` : "None yet"
})

const statusCounts = computed(() => {
	const slips = data.value?.slips || []
	return Object.fromEntries(STATUSES.map((s) => [s, s === "All" ? slips.length : slips.filter((x) => x.status === s).length]))
})
const filtered = computed(() => {
	const term = search.value.trim().toLowerCase()
	return (data.value?.slips || [])
		.filter((s) => status.value === "All" || s.status === status.value)
		.filter((s) => !term || s.employee.toLowerCase().includes(term) || s.employee_name.toLowerCase().includes(term))
		.filter((s) => !department.value || s.department === department.value)
		.filter((s) => !excelStatus.value || excel.value[s.employee] === excelStatus.value)
})
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const hasFilters = computed(() => !!(search.value || department.value || excelStatus.value || status.value !== "All"))
watch([status, search, department, excelStatus, pageSize], () => (page.value = 1))
watch(data, () => (selected.value = []))

// HRMS creates and submits large payrolls in a background job; follow it until it ends
let pollTimer: ReturnType<typeof setTimeout> | undefined
watch(data, (value) => {
	clearTimeout(pollTimer)
	if (value?.runs.some((r) => r.status === "Queued")) pollTimer = setTimeout(refresh, POLL_MS)
})
onBeforeUnmount(() => clearTimeout(pollTimer))

/** A step changes slips everywhere on the dashboard, so the other tabs reload too. */
async function refresh() {
	// Changed slips compare differently with the master sheet
	await Promise.all([reload(), reconcile()])
	emit("changed")
}

function clear() {
	search.value = department.value = excelStatus.value = ""
	status.value = "All"
}

function confirmGenerate(batch: PayrollBatch) {
	const count = batch === "Exited" ? exited.value : eligible.value
	const who = batch === "Exited" ? "employees who left in this cycle" : "employees"
	dialog.confirm({
		title: batch === "Exited" ? "Generate payroll for exited employees" : "Generate regular payroll",
		message: `Create the payroll for ${props.scope.company}, ${cycleLabel(props.scope.from, props.scope.to)}? A payroll entry is submitted and draft salary slips are created for ${count} ${who}. Review the Pre-Check Audit first.`,
		confirmLabel: "Generate",
		onConfirm: async () => {
			generating.value = true
			try {
				const run = await generatePayroll(props.scope.company, props.scope.from, props.scope.to, batch)
				const recovered = run.advances_recovered ? `; ${run.advances_recovered} overdue advances scheduled for deduction` : ""
				toast.success(`Payroll entry ${run.name} created${recovered}`)
				await refresh()
			} finally {
				generating.value = false
			}
		},
	})
}

function quickAction(action: "recalculate" | "delete", name: string) {
	quickView.value = null
	runOne(action, name)
}

function runOne(action: "recalculate" | "delete", name: string) {
	if (action === "delete") {
		dialog.confirm({ title: "Delete salary slip", message: `Delete draft salary slip ${name}?`, confirmLabel: "Delete", theme: "red", onConfirm: () => apply(action, [name]) })
	} else apply(action, [name])
}

function runBulk(action: "submit" | "recalculate" | "delete") {
	const verb = { submit: "Submit", recalculate: "Recalculate", delete: "Delete" }[action]
	dialog.confirm({
		title: `${verb} salary slips`,
		message: `${verb} ${selected.value.length} selected salary slips? Only drafts are changed.`,
		confirmLabel: verb,
		theme: action === "delete" ? "red" : undefined,
		onConfirm: () => apply(action, [...selected.value]),
	})
}

async function apply(action: "submit" | "recalculate" | "delete", names: string[]) {
	bulk.value = action
	try {
		const result = await updateSlips(action, names)
		if (result.done.length) toast.success(`${result.done.length} salary slips done`)
		if (result.failed.length) toast.warning(`${result.failed.length} skipped: ${result.failed[0].error}`)
		await refresh()
	} finally {
		bulk.value = null
	}
}

async function exportRows() {
	exporting.value = true
	try {
		await exportSlips(props.scope, filtered.value.map((s) => s.employee))
	} catch {
		// downloadFile already showed the server's message
	} finally {
		exporting.value = false
	}
}

const days = (label: string, key: string): Column => ({ key, label, width: "72px", align: "right", format: (v) => formatNumber(v) })
const amount = (label: string, key: string): Column => ({ key, label, width: "minmax(110px,1fr)", align: "right", format: (v, r) => formatCurrency(v, r.currency) })
const columns = computed<Column[]>(() => [
	{ key: "employee", label: "Employee", width: "minmax(200px,1.8fr)" },
	{ key: "status", label: "Status", width: "100px" },
	...(reconciled.value?.rows?.length ? [{ key: "excel", label: "Excel", width: "140px" } as Column] : []),
	days("Work days", "total_working_days"),
	days("Absent", "absent_days"),
	days("LWP", "leave_without_pay"),
	days("Pay days", "payment_days"),
	amount("Gross", "gross_pay"),
	amount("Deductions", "total_deduction"),
	{ key: "net_pay", label: "Net pay", width: "minmax(120px,1fr)", align: "right" },
	{ key: "actions", label: "", width: "84px", align: "right" },
])
</script>
