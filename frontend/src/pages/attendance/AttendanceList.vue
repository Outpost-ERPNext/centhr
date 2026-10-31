<template>
	<PageHeader :crumbs="[{ label: 'Attendance' }]">
		<template #actions>
			<Button
				v-if="can('Attendance Request').read"
				icon-left="lucide-calendar-plus"
				label="Requests"
				class="hidden sm:inline-flex"
				:route="{ name: 'AttendanceRequestList', query: list.state.filters.employee ? { employee: list.state.filters.employee } : {} }"
			/>
			<Button
				v-if="can('Attendance').create"
				icon-left="lucide-calendar-check"
				label="Mark attendance"
				class="hidden sm:inline-flex"
				@click="openMark([])"
			/>
			<Button
				v-if="can('Attendance').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New"
				:route="{ name: 'AttendanceNew', query: list.state.filters.employee ? { employee: list.state.filters.employee } : {} }"
			/>
		</template>
	</PageHeader>

	<div class="flex flex-wrap items-center gap-3 px-5 pt-3">
		<SegmentedTabs
			v-model="view"
			:tabs="[
				{ label: 'Records', value: 'records' },
				{ label: 'Register', value: 'register' },
			]"
		/>
		<div v-if="view === 'records'" class="flex flex-wrap items-center gap-1.5">
			<button
				v-for="s in statusOptions"
				:key="s"
				class="inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12.5px]"
				:class="list.state.filters.status === s ? 'border-ch-ink text-ch-ink' : 'border-ch-line text-ch-ink-2 hover:border-ch-line-2'"
				@click="list.state.filters.status = list.state.filters.status === s ? '' : s"
			>
				<span class="size-2 rounded-full" :style="{ background: `var(--ch-${toneFor('Attendance', s)}-dot)` }" />
				{{ s }}
				<span class="tabular-nums text-ch-ink-3">{{ statusCounts[s] || 0 }}</span>
			</button>
			<!-- Attendance of employees with pending leave (PLA) or a pending attendance request (ARR) -->
			<span class="mx-1 h-4 w-px bg-ch-line" aria-hidden="true" />
			<button
				v-for="p in PENDING_CHIPS"
				:key="p.value"
				class="inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[12.5px]"
				:class="list.state.filters.pending === p.value ? 'border-ch-ink text-ch-ink' : 'border-ch-line text-ch-ink-2 hover:border-ch-line-2'"
				:aria-pressed="list.state.filters.pending === p.value"
				:title="`Attendance of employees with ${p.label.toLowerCase()} in the date range`"
				@click="list.state.filters.pending = list.state.filters.pending === p.value ? '' : p.value"
			>
				<span
					class="inline-flex h-4 min-w-6 items-center justify-center rounded-[4px] px-1 text-[10px] font-semibold"
					:style="{ background: `var(--ch-${p.tone}-bg)`, color: `var(--ch-${p.tone}-ink)` }"
				>{{ p.code }}</span>
				{{ p.label }}
			</button>
		</div>
	</div>

	<template v-if="view === 'records'">
		<FilterBar
			v-model:search="list.state.search"
			:total="list.total.value"
			:active="hasFilters"
			search-placeholder="Search employee or ID"
			noun="record"
			@clear="list.clearFilters"
		>
			<EmployeeSearch
				v-model="list.state.filters.employee_id"
				placeholder="Employee name or ID"
				:company="list.state.filters.company"
				@select="pickEmployee"
			/>
			<FilterLink
				v-model="list.state.filters.employee"
				doctype="Employee"
				placeholder="Employee"
				:filters="list.state.filters.company ? { company: list.state.filters.company } : undefined"
			/>
			<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
			<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" />
			<FilterSelect
				v-model="list.state.filters.state"
				:options="[
					{ label: 'Submitted', value: '1' },
					{ label: 'Cancelled', value: '2' },
				]"
				placeholder="Document"
			/>
			<DateFilter
				v-model:op="list.state.filters.date_op"
				v-model:from="list.state.filters.date_from"
				v-model:to="list.state.filters.date_to"
			/>
			<PayrollCycleNav
				v-if="list.state.filters.company"
				:company="list.state.filters.company"
				allow-whole-year
				:from="list.state.filters.date_op === 'between' ? list.state.filters.date_from : ''"
				:to="list.state.filters.date_op === 'between' ? list.state.filters.date_to : ''"
				@update:from="setPeriodDate('date_from', $event)"
				@update:to="setPeriodDate('date_to', $event)"
			/>
		</FilterBar>

		<div
			v-if="selected.length"
			class="mx-5 mb-2 flex flex-wrap items-center gap-2 rounded-4 bg-ch-subtle px-3 py-2 text-[13px]"
		>
			<span class="font-medium">{{ selected.length }} selected</span>
			<Button
				v-if="can('Attendance').submit"
				size="sm"
				label="Submit"
				:loading="bulkBusy === 'submit'"
				@click="bulk('submit')"
			/>
			<Button
				v-if="can('Attendance').cancel"
				size="sm"
				theme="red"
				label="Cancel"
				:loading="bulkBusy === 'cancel'"
				@click="bulk('cancel')"
			/>
			<Button size="sm" variant="ghost" label="Clear selection" class="ml-auto" @click="selected = []" />
		</div>

		<DataTable
			v-model:selected="selected"
			:columns="columns"
			:rows="list.rows.value"
			:loading="list.loading.value"
			:error="list.error.value"
			:sort-field="list.state.sortField"
			:sort-order="list.state.sortOrder"
			:show-clear="hasFilters"
			:selectable="can('Attendance').submit || can('Attendance').cancel"
			empty-icon="lucide-clock"
			empty-message="No attendance matches these filters"
			mobile-aside="status"
			min-width="860px"
			@sort="list.toggleSort"
			@row-click="(row) => router.push(`/attendance/${encodeURIComponent(row.name)}`)"
			@clear-filters="list.clearFilters"
		>
			<template #cell-employee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }}</div>
				</div>
			</template>
			<template #cell-status="{ row }">
				<span class="flex items-center gap-2">
					<StatusBadge doctype="Attendance" :status="row.status" />
					<span v-if="row.docstatus !== 1" class="text-[12px] text-ch-ink-3">({{ docstatusLabel(row.docstatus) }})</span>
					<span
						v-if="row.status === 'Absent' && pendingLeaves[`${row.employee}|${row.attendance_date}`]"
						class="rounded-full bg-ch-blue-bg px-2 py-0.5 text-[11.5px] text-ch-blue-ink"
						:title="`${PENDING_LEAVE.label}: ${pendingLeaves[`${row.employee}|${row.attendance_date}`].name}`"
					>Leave pending</span>
				</span>
			</template>
		</DataTable>

		<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
	</template>

	<AttendanceRegister v-else :can-mark="can('Attendance').create" @mark="openMark" />

	<MarkAttendanceDialog v-model="markOpen" :employees="markEmployees" :range="markRange" @done="onMarked" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Button, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import EmployeeSearch from "@/components/EmployeeSearch.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DateFilter from "@/components/DateFilter.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import AttendanceRegister from "./AttendanceRegister.vue"
import MarkAttendanceDialog from "./MarkAttendanceDialog.vue"
import { api } from "@/data/api"
import { dateFilter, getGroupCounts, getList, useDocList, type Filter, type ListState } from "@/data/list"
import { loadMeta, selectOptions } from "@/data/meta"
import { can } from "@/data/permissions"
import { formatDate } from "@/utils/format"
import { getPendingLeaves, type PendingLeave } from "@/data/leave"
import { ATTENDANCE_SUMMARY_STATUSES, PENDING_LEAVE, PENDING_REQUEST, docstatusLabel, toneFor } from "@/utils/status"
import { getEmployeesWithPending } from "@/data/attendanceRequest"
import { readStorage, writeStorage } from "@/utils/storage"

const router = useRouter()
const route = useRoute()
loadMeta("Attendance")

const view = ref(route.query.view === "register" ? "register" : readStorage("centhr-attendance-view", "records"))
watch(view, (v) => writeStorage("centhr-attendance-view", v))

const PENDING_CHIPS = [
	{ value: "leave", label: "Pending leave", code: PENDING_LEAVE.code, tone: PENDING_LEAVE.tone },
	{ value: "request", label: "Pending attendance request", code: PENDING_REQUEST.code, tone: PENDING_REQUEST.tone },
]

const statusOptions = computed(() =>
	selectOptions("Attendance", "status").filter((s) => ATTENDANCE_SUMMARY_STATUSES.includes(s))
)

async function baseFilters(state: ListState): Promise<Filter[]> {
	const filters: Filter[] = []
	if (state.filters.pending === "leave" || state.filters.pending === "request") {
		// Pending items that overlap the date filter, or any pending item when there is none
		const { date_op: op, date_from: dateFrom, date_to: dateTo } = state.filters
		const from = op && op !== "<=" ? dateFrom : undefined
		const to = op === "between" ? dateTo : op === "=" || op === "<=" ? dateFrom : undefined
		const names = await getEmployeesWithPending(state.filters.pending, { from, to, company: state.filters.company })
		filters.push(["employee", "in", names.length ? names : [""]])
	}
	if (state.filters.employee_id) filters.push(["employee", "in", await findEmployees(state.filters.employee_id, state.filters.company)])
	for (const key of ["employee", "company", "department"]) {
		if (state.filters[key]) filters.push([key, "=", state.filters[key]])
	}
	if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
	const date = dateFilter("attendance_date", state.filters.date_op, state.filters.date_from, state.filters.date_to)
	if (date) filters.push(date)
	return filters
}

const list = useDocList({
	doctype: "Attendance",
	fields: [
		"name",
		"employee",
		"employee_name",
		"attendance_date",
		"status",
		"leave_type",
		"shift",
		"company",
		"docstatus",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "attendance_date", order: "desc" },
	buildFilters: async (state) => {
		const filters = await baseFilters(state)
		if (state.filters.status) filters.push(["status", "=", state.filters.status])
		return filters
	},
})

const statusCounts = ref<Record<string, number>>({})
async function loadCounts() {
	statusCounts.value = await baseFilters(list.state)
		.then((filters) => getGroupCounts("Attendance", "status", filters))
		.catch(() => ({}))
}
// The status chips filter the rows only, so their own counts ignore the status filter
watch(() => JSON.stringify({ ...list.state.filters, status: "" }), loadCounts, { immediate: true })

/** A picked suggestion filters on that one employee, shown in the Employee picker. */
function pickEmployee(employee: string) {
	list.state.filters = { ...list.state.filters, employee, employee_id: "" }
}

/**
 * Employees of the company (all companies when none is picked) whose name, ID or Employee Number
 * contains the text; Attendance itself has no Employee Number.
 */
async function findEmployees(text: string, company?: string) {
	const like = `%${text}%`
	const rows = await getList<{ name: string }>({
		doctype: "Employee",
		fields: ["name"],
		filters: company ? [["company", "=", company]] : [],
		or_filters: [
			["employee_name", "like", like],
			["name", "like", like],
			["employee_number", "like", like],
		],
		limit: 0,
	})
	// No match must show no attendance, not all of it
	return rows.length ? rows.map((r) => r.name) : [""]
}

const hasFilters = computed(
	() => !!list.state.search || Object.entries(list.state.filters).some(([k, v]) => k !== "status" && !!v)
)

// Absent rows whose leave is still waiting for approval (HRMS makes them On Leave once it is approved)
const pendingLeaves = ref<Record<string, PendingLeave>>({})
watch(
	() => list.rows.value,
	async (rows) => {
		const absent = (rows as { employee: string; attendance_date: string; status: string }[]).filter(
			(r) => r.status === "Absent"
		)
		if (!absent.length) return (pendingLeaves.value = {})
		const dates = absent.map((r) => r.attendance_date).sort()
		pendingLeaves.value = await getPendingLeaves(
			[...new Set(absent.map((r) => r.employee))],
			dates[0],
			dates[dates.length - 1]
		)
	}
)

const selected = ref<string[]>([])
watch(() => list.rows.value, () => (selected.value = []))
const bulkBusy = ref<string | null>(null)

async function bulk(action: "submit" | "cancel") {
	bulkBusy.value = action
	try {
		const failed = await api<string[]>("frappe.desk.doctype.bulk_update.bulk_update.submit_cancel_or_update_docs", {
			doctype: "Attendance",
			docnames: selected.value,
			action,
		})
		const done = selected.value.length - (failed?.length || 0)
		if (failed?.length) toast.warning(`${done} done, ${failed.length} could not be ${action === "submit" ? "submitted" : "cancelled"}`)
		else toast.success(`${done} record${done === 1 ? "" : "s"} ${action === "submit" ? "submitted" : "cancelled"}`)
		selected.value = []
		await Promise.all([list.reload(), loadCounts()])
	} catch {
		// Shown by the api helper
	} finally {
		bulkBusy.value = null
	}
}

const markOpen = ref(false)
const markEmployees = ref<string[]>([])
type MarkRange = { from: string; to: string; company?: string | null }
const markRange = ref<MarkRange | null>(null)
function openMark(employees: string[], range?: MarkRange) {
	markEmployees.value = employees
	markRange.value = range || null
	markOpen.value = true
}
watch(markOpen, (value) => {
	// The header button marks for one employee, with dates from that employee's company
	if (!value) markRange.value = null
})

// With a company filter, the date filter follows that company's payroll period
function setPeriodDate(key: "date_from" | "date_to", value: string) {
	list.state.filters.date_op = "between"
	list.state.filters[key] = value
}
function onMarked() {
	list.reload()
	loadCounts()
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{
		key: "attendance_date",
		label: "Date",
		width: "minmax(100px,1fr)",
		sortable: true,
		format: (v) => formatDate(v),
	},
	{ key: "status", label: "Status", width: "minmax(150px,1.4fr)", sortable: true },
	{ key: "leave_type", label: "Leave type", width: "minmax(100px,1fr)", hideOnMobile: true },
	{ key: "shift", label: "Shift", width: "minmax(90px,1fr)", hideOnMobile: true },
	{ key: "company", label: "Company", width: "minmax(110px,1.2fr)", sortable: true },
]
</script>
