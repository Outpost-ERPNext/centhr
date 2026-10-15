<template>
	<PageHeader :crumbs="[{ label: 'Employee Checkin' }]" />

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="check-in"
		@clear="list.clearFilters"
	>
		<FilterSelect
			v-model="list.state.filters.log_type"
			:options="[
				{ label: 'IN', value: 'IN' },
				{ label: 'OUT', value: 'OUT' },
			]"
			placeholder="Log type"
		/>
		<label
			v-if="canReadTime"
			class="inline-flex h-7 cursor-pointer select-none items-center gap-1.5 rounded-3 bg-ch-subtle px-2.5 text-[13px] text-ch-ink"
		>
			<input
				type="checkbox"
				class="size-3.5 cursor-pointer accent-[var(--ch-primary)]"
				:checked="list.state.filters.today === '1'"
				@change="toggleToday(($event.target as HTMLInputElement).checked)"
			/>
			Today
		</label>
		<DateFilter
			v-if="canReadTime && list.state.filters.today !== '1'"
			v-model:op="list.state.filters.date_op"
			v-model:from="list.state.filters.date_from"
			v-model:to="list.state.filters.date_to"
		/>
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" />
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-fingerprint"
		:empty-message="hasFilters ? 'No check-ins match these filters' : 'No check-ins logged yet'"
		mobile-aside="log_type"
		min-width="800px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/checkins/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<Avatar :label="row.employee_name || row.employee" size="md" shape="circle" />
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }}</div>
				</div>
			</div>
		</template>
		<template #cell-log_type="{ row }">
			<StatusBadge v-if="row.log_type" pill doctype="Employee Checkin" :status="row.log_type" />
			<span v-else class="text-ch-ink-4">—</span>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Avatar } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DateFilter from "@/components/DateFilter.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { getReadableFields } from "@/data/permissions"
import { formatDateTime, today } from "@/utils/format"

const router = useRouter()

/** `time` is a Datetime, so a date filter has to cover the whole day. */
function timeFilter(op: string | undefined, from: string | undefined, to: string | undefined): Filter | null {
	if (!op || !from) return null
	if (op === "=") return ["time", "between", [from, from]]
	if (op === "<=") return ["time", "<=", `${from} 23:59:59`]
	if (op === ">=") return ["time", ">=", from]
	return to ? ["time", "between", [from, to]] : ["time", ">=", from]
}

const FIELDS = [
	"name",
	"employee",
	"employee_name",
	"log_type",
	"time",
	"shift",
	"device_id",
	"attendance",
	"skip_auto_attendance",
	"creation",
]

// `time` is a permlevel 1 field: HRMS lets the Employee Self Service role list check-ins but not read their time
const canReadTime = ref(true)
const ready = getReadableFields("Employee Checkin").then((readable) => {
	// An empty answer means the check failed; the server still enforces the field permission
	canReadTime.value = !readable.length || readable.includes("time")
	if (!canReadTime.value && list.state.sortField === "time") list.state.sortField = "creation"
})

const list = useDocList({
	doctype: "Employee Checkin",
	fields: () => [...FIELDS.filter((f) => f !== "time" || canReadTime.value), "employee.company as company"],
	ready,
	searchFields: ["employee", "employee_name", "name"],
	defaultSort: { field: "time", order: "desc" },
	buildFilters: (state) => {
		const f = state.filters
		const filters: Filter[] = []
		if (f.log_type) filters.push(["log_type", "=", f.log_type])
		if (f.employee) filters.push(["employee", "=", f.employee])
		if (f.company) filters.push(["employee.company", "=", f.company])
		const date = !canReadTime.value
			? null
			: f.today === "1"
				? timeFilter("=", today(), undefined)
				: timeFilter(f.date_op, f.date_from, f.date_to)
		if (date) filters.push(date)
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

function toggleToday(on: boolean) {
	const { date_op, date_from, date_to, ...rest } = list.state.filters
	list.state.filters = on ? { ...rest, today: "1" } : (({ today: _, ...others }) => others)(rest)
}

const columns = computed<Column[]>(() => [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)", sortable: true },
	{ key: "log_type", label: "Log type", width: "110px", sortable: true },
	canReadTime.value
		? { key: "time", label: "Time", width: "minmax(170px,1.2fr)", sortable: true, format: (v) => formatDateTime(v) }
		: { key: "creation", label: "Logged", width: "minmax(170px,1.2fr)", sortable: true, format: (v) => formatDateTime(v) },
	{ key: "shift", label: "Shift", width: "minmax(140px,1fr)", sortable: true, format: (v) => v || "—" },
	{ key: "company", label: "Company", width: "minmax(150px,1.1fr)", format: (v) => v || "—", hideOnMobile: true },
])
</script>
