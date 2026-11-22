<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="flex flex-wrap items-center gap-2 text-[13px] text-ch-ink-3">
			<span>Audit for <b class="text-ch-ink">{{ cycleLabel(scope.from, scope.to) }}</b> · {{ scope.company || "All companies" }}</span>
			<Button
				v-if="data?.auto_attendance"
				class="ml-auto"
				icon-left="lucide-calendar-check"
				label="Mark auto attendance"
				tooltip="Mark Present on the unmarked working days of employees whose salary structure asks for it"
				:loading="busy === 'attendance'"
				@click="confirmAutoAttendance"
			/>
			<Button :class="data?.auto_attendance ? '' : 'ml-auto'" icon-left="lucide-rotate-ccw" label="Re-run audit" :loading="loading" @click="reload" />
		</div>
		<div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
			<StatCard
				v-for="card in data?.cards || []"
				:key="card.key"
				clickable
				:active="check === card.key"
				:label="card.label"
				:value="cardValue(card)"
				:tone="card.info ? 'blue' : card.key === 'hold' ? (card.count ? 'red' : undefined) : card.count ? 'amber' : 'green'"
				:loading="loading"
				@click="check = check === card.key ? 'status' : card.key"
			/>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<h3 class="text-[14px] font-medium text-ch-ink">{{ cardLabel }} — Details</h3>
			<SegmentedTabs v-model="view" :tabs="VIEWS.map((v) => ({ label: v.label, value: v.key, count: viewCounts[v.key] }))" />
			<!-- What can be done about the card that is open -->
			<div class="ml-auto flex flex-wrap gap-2">
				<Button
					v-if="NOTIFY_CHECKS.includes(check) && checked.length"
					icon-left="lucide-bell"
					label="Notify all"
					tooltip="Remind employees of unmarked attendance and approvers of open leave and attendance requests"
					:loading="busy === 'notify'"
					@click="confirmNotify(checked)"
				/>
				<Button
					v-if="check === 'negative' && negativeDrafts"
					theme="red"
					icon-left="lucide-trash-2"
					:label="`Delete ${negativeDrafts} negative drafts`"
					:loading="busy === 'negative'"
					@click="confirmDeleteNegative"
				/>
			</div>
		</div>
	</div>

	<div v-if="selected.length" class="mx-5 mt-3 flex flex-wrap items-center gap-2 rounded-4 bg-ch-subtle px-3 py-2 text-[13px]">
		<span class="font-medium">{{ selected.length }} selected</span>
		<Button v-if="canAssign" size="sm" icon-left="lucide-user-plus" label="Assign salary structure" @click="assignStructure" />
		<Button size="sm" icon-left="lucide-bell" label="Notify" :loading="busy === 'notify'" @click="confirmNotify(selectedRows)" />
		<Button v-if="selectedHolds.length" size="sm" icon-left="lucide-play" :label="`Release ${selectedHolds.length} holds`" :loading="busy === 'release'" @click="confirmReleaseSelected" />
		<Button size="sm" variant="ghost" label="Clear selection" class="ml-auto" @click="selected = []" />
	</div>

	<FilterBar v-model:search="search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="employee" @clear="clear">
		<FilterLink v-model="department" doctype="Department" placeholder="Department" :filters="companyFilter" />
		<FilterLink v-model="structure" doctype="Salary Structure" placeholder="Salary structure" :filters="companyFilter" />
	</FilterBar>

	<DataTable
		v-model:selected="selected"
		selectable
		:columns="columns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:show-clear="hasFilters"
		empty-icon="lucide-shield-check"
		:empty-message="check === 'status' ? 'No employees match these filters' : 'No employee fails this check'"
		mobile-aside="payroll"
		min-width="1080px"
		@row-click="(row) => openEmployee(row.name)"
		@clear-filters="clear"
	>
		<template #cell-name="{ row }">
			<span class="font-medium text-ch-primary">{{ row.name }}</span>
		</template>
		<template #cell-salary_structure="{ row }">
			<span v-if="row.salary_structure" class="truncate rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] font-medium text-ch-ink-2">{{ row.salary_structure }}</span>
			<StatusBadge v-else tone="amber" status="Missing" />
		</template>
		<template #cell-issues="{ row }">
			<div class="flex min-w-0 flex-wrap gap-1">
				<span
					v-for="(detail, key) in row.issues"
					:key="key"
					:title="detail"
					class="rounded-full bg-ch-amber-bg px-2 py-0.5 text-[11.5px] font-medium text-ch-amber-ink"
				>
					{{ ISSUE_LABELS[key] || key }}
				</span>
				<StatusBadge v-if="!Object.keys(row.issues).length" pill tone="green" status="Clear" />
				<span v-if="row.reminded_on" class="text-[12px] text-ch-ink-3" :title="formatDateTime(row.reminded_on)">Reminded {{ timeAgo(row.reminded_on) }}</span>
			</div>
		</template>
		<template #cell-payroll="{ row }">
			<div class="min-w-0">
				<StatusBadge pill :tone="payrollTone(row)" :status="payrollStatus(row)" />
				<div v-if="row.hold" class="truncate text-[12px] text-ch-ink-3" :title="holdNote(row)">{{ holdNote(row) }}</div>
			</div>
		</template>
		<template #cell-actions="{ row }">
			<div class="flex justify-end" @click.stop>
				<Button v-if="row.hold" size="sm" icon-left="lucide-play" label="Release" :loading="acting === row.name" @click="release(row)" />
				<Button v-else-if="row.status === 'Active'" size="sm" theme="red" icon-left="lucide-ban" label="Set hold" :loading="acting === row.name" @click="hold(row)" />
			</div>
		</template>
	</DataTable>
	<Pager v-model:page="page" v-model:page-size="pageSize" :total="filtered.length" />

	<HoldDialog v-model:open="holdOpen" :scope="scope" :employee="holding" @saved="reload" />
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, dialog, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import Pager from "@/components/Pager.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import {
	OPEN_EMPLOYEE,
	deleteNegativeSlips,
	getAudit,
	markAutoAttendance,
	releaseHold,
	releaseHolds,
	sendReminders,
	useTabData,
	type AuditCard,
	type AuditRow,
	type Scope,
} from "@/data/payrollDashboard"
import { can } from "@/data/permissions"
import { formatDateShort, formatDateTime, timeAgo } from "@/utils/format"
import type { Tone } from "@/utils/status"
import HoldDialog from "./HoldDialog.vue"

const props = defineProps<{ scope: Scope }>()
const openEmployee = inject(OPEN_EMPLOYEE)!
const { data, loading, error, reload } = useTabData(props.scope, getAudit)

const ISSUE_LABELS: Record<string, string> = {
	structure_missing: "No structure",
	structure_inactive: "Inactive structure",
	joiners: "New joiner",
	leave: "Pending leave",
	attendance: "Attendance",
	negative: "Negative pay",
	dimensions: "Dimensions",
	bank: "Bank details",
}
const VIEWS = [
	{ key: "all", label: "All employees", test: () => true },
	{ key: "ready", label: "Ready to process", test: (r: AuditRow) => !r.hold && !Object.keys(r.issues).length },
	{ key: "hold", label: "On hold", test: (r: AuditRow) => !!r.hold },
	{ key: "action", label: "Action needed", test: (r: AuditRow) => !!Object.keys(r.issues).length },
]

const check = ref("status")
const view = ref("all")
const search = ref("")
const department = ref("")
const structure = ref("")
const page = ref(1)
const pageSize = ref(20)
const acting = ref<string | null>(null)
const router = useRouter()
// Employee IDs ticked in the table, and the bulk action that is running
const selected = ref<string[]>([])
const busy = ref<string | null>(null)
// Cards whose employees, or their approvers, can be reminded
const NOTIFY_CHECKS = ["attendance", "leave"]
const STRUCTURE_CHECKS = ["structure_missing", "structure_inactive", "joiners"]

const cardLabel = computed(() => data.value?.cards.find((c) => c.key === check.value)?.label || "Employee Status")
const companyFilter = computed(() => (props.scope.company ? { company: props.scope.company } : undefined))
// The selected card narrows to employees failing that check; the chips count within it
const checked = computed(() => (data.value?.rows || []).filter((r) => check.value === "status" || (check.value === "hold" ? !!r.hold : check.value in r.issues)))
const viewCounts = computed(() => Object.fromEntries(VIEWS.map((v) => [v.key, checked.value.filter(v.test).length])))
const filtered = computed(() => {
	const term = search.value.trim().toLowerCase()
	const test = VIEWS.find((v) => v.key === view.value)!.test
	return checked.value
		.filter(test)
		.filter((r) => !term || r.name.toLowerCase().includes(term) || r.employee_name.toLowerCase().includes(term))
		.filter((r) => !department.value || r.department === department.value)
		.filter((r) => !structure.value || r.salary_structure === structure.value)
})
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const hasFilters = computed(() => !!(search.value || department.value || structure.value || view.value !== "all"))
watch([check, view, search, department, structure, pageSize], () => (page.value = 1))
watch([check, data], () => (selected.value = []))

const selectedRows = computed(() => (data.value?.rows || []).filter((r) => selected.value.includes(r.name)))
const selectedHolds = computed(() => selectedRows.value.filter((r) => r.hold).map((r) => r.hold!))
const canAssign = computed(() => can("Bulk Salary Structure Assignment").write && selectedRows.value.some((r) => STRUCTURE_CHECKS.some((key) => key in r.issues)))
const negativeDrafts = computed(() => (data.value?.rows || []).filter((r) => r.slip_status === "Draft" && (r.net_pay || 0) < 0).length)

function cardValue(card: AuditCard) {
	if (card.info) return `${card.count} Active`
	if (card.key === "hold") return card.count ? `${card.count} On hold` : "None"
	return card.count ? `${card.count} Issues` : "Passed"
}

function holdNote(row: AuditRow) {
	const until = row.hold_until_released ? "until released" : `until ${formatDateShort(row.hold_to)}`
	return `${row.hold_reason} · ${until} · by ${row.hold_by}`
}

/** Opens the bulk assignment with the ticked employees chosen. */
function assignStructure() {
	router.push({ name: "BulkSalaryStructureAssignment", query: { employees: selected.value.join(",") } })
}

function confirmNotify(rows: AuditRow[]) {
	dialog.confirm({
		title: "Send reminders",
		message: `Remind ${rows.length} employees about ${cycleLabel(props.scope.from, props.scope.to)}? Each one with unmarked attendance gets an email, and each approver one email listing the open leave applications and attendance requests they have to decide.`,
		confirmLabel: "Send",
		onConfirm: () =>
			run("notify", async () => {
				const result = await sendReminders(props.scope, rows.map((r) => r.name))
				return result.sent ? `${result.sent} reminders sent` : "Nobody to remind: nothing is open, or no email address is known"
			}),
	})
}

function confirmDeleteNegative() {
	dialog.confirm({
		title: "Delete negative draft slips",
		message: `Delete the ${negativeDrafts.value} draft salary slips of this cycle whose net pay is below zero? Correct their cause, then generate them again. Submitted slips and slips of exactly zero are kept.`,
		confirmLabel: "Delete",
		theme: "red",
		onConfirm: () => run("negative", async () => summary(await deleteNegativeSlips(props.scope), "salary slips deleted")),
	})
}

function confirmReleaseSelected() {
	dialog.confirm({
		title: "Release holds",
		message: `Release the hold on ${selectedHolds.value.length} salaries? They are paid with the next payment of their payroll run.`,
		confirmLabel: "Release",
		onConfirm: () => run("release", async () => summary(await releaseHolds(selectedHolds.value), "holds released")),
	})
}

function confirmAutoAttendance() {
	dialog.confirm({
		title: "Mark auto attendance",
		message: `Mark Present on every unmarked working day of ${cycleLabel(props.scope.from, props.scope.to)}, up to today, for employees whose salary structure has automatic attendance? Holidays, leave, open requests and days that have attendance are left alone.`,
		confirmLabel: "Mark attendance",
		onConfirm: () =>
			run("attendance", async () => {
				const result = await markAutoAttendance(props.scope)
				return `${result.created} days marked for ${result.employees} employees`
			}),
	})
}

const summary = (result: { done: string[]; failed: { error: string }[] }, done: string) =>
	`${result.done.length} ${done}${result.failed.length ? `; ${result.failed.length} skipped: ${result.failed[0].error}` : ""}`

/** Runs a bulk action, says what it did and audits again. */
async function run(action: string, call: () => Promise<string>) {
	busy.value = action
	try {
		toast.success(await call())
		await reload()
	} finally {
		busy.value = null
	}
}

function clear() {
	search.value = department.value = structure.value = ""
	view.value = "all"
}

function payrollStatus(row: AuditRow) {
	if (row.hold) return "On Hold"
	if (row.slip_status) return row.slip_status
	return row.assignment ? "Eligible" : "Not eligible"
}

function payrollTone(row: AuditRow): Tone {
	if (row.hold) return "red"
	if (row.slip_status) return row.slip_status === "Submitted" ? "green" : "amber"
	return row.assignment ? "green" : "gray"
}

// The employee whose hold is being set, and why
const holdOpen = ref(false)
const holding = ref<AuditRow | null>(null)

function hold(row: AuditRow) {
	holding.value = row
	holdOpen.value = true
}

function release(row: AuditRow) {
	return act(row, () => releaseHold(row.hold!), "Hold released")
}

async function act(row: AuditRow, call: () => Promise<unknown>, message: string) {
	acting.value = row.name
	try {
		await call()
		toast.success(message)
		await reload()
	} finally {
		acting.value = null
	}
}

const columns: Column[] = [
	{ key: "name", label: "Employee ID", width: "110px" },
	{ key: "employee_name", label: "Employee name", width: "minmax(170px,1.6fr)", class: "font-medium" },
	{ key: "department", label: "Department", width: "minmax(120px,1.1fr)", hideOnMobile: true },
	{ key: "salary_structure", label: "Salary structure", width: "minmax(150px,1.3fr)" },
	{ key: "issues", label: "Audit status", width: "minmax(170px,1.6fr)" },
	{ key: "payroll", label: "Payroll status", width: "110px" },
	{ key: "actions", label: "", width: "110px", align: "right" },
]
</script>
