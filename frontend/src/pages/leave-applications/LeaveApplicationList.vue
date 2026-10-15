<template>
	<PageHeader :crumbs="[{ label: 'Leave Application' }]">
		<template #actions>
			<Button
				v-if="can('Leave Application').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New application"
				:route="{ name: 'LeaveApplicationNew', query: list.state.filters.employee ? { employee: list.state.filters.employee } : {} }"
			/>
		</template>
	</PageHeader>

	<div class="px-5 pt-3">
		<SegmentedTabs v-model="status" :tabs="statusTabs" />
	</div>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="application"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" />
		<FilterLink v-model="list.state.filters.leave_type" doctype="Leave Type" placeholder="Leave type" />
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<DateFilter
			v-model:op="list.state.filters.date_op"
			v-model:from="list.state.filters.date_from"
			v-model:to="list.state.filters.date_to"
			label="Date"
		/>
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-file-text"
		empty-message="No leave applications match these filters"
		mobile-aside="status"
		min-width="900px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/leave-applications/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }} · {{ row.employee }}</div>
			</div>
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Leave Application" :status="displayStatus(row)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import DateFilter from "@/components/DateFilter.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { dateFilter, getGroupCounts, useDocList, type Filter, type ListState } from "@/data/list"
import { can } from "@/data/permissions"
import { formatDate, formatNumber } from "@/utils/format"

const router = useRouter()

function baseFilters(state: ListState): Filter[] {
	const filters: Filter[] = []
	for (const key of ["employee", "leave_type", "company"]) {
		if (state.filters[key]) filters.push([key, "=", state.filters[key]])
	}
	const op = state.filters.date_op
	// "Between" matches any application that overlaps the range, as HR expects
	if (op === "between" && state.filters.date_from && state.filters.date_to) {
		filters.push(["from_date", "<=", state.filters.date_to], ["to_date", ">=", state.filters.date_from])
	} else {
		const f = dateFilter("from_date", op, state.filters.date_from)
		if (f) filters.push(f)
	}
	return filters
}

const list = useDocList({
	doctype: "Leave Application",
	fields: [
		"name",
		"employee",
		"employee_name",
		"leave_type",
		"from_date",
		"to_date",
		"total_leave_days",
		"status",
		"docstatus",
		"leave_approver_name",
		"leave_approver",
		"company",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "from_date", order: "desc" },
	buildFilters: (state) => {
		const filters = baseFilters(state)
		if (state.filters.status) filters.push(["status", "=", state.filters.status])
		return filters
	},
})

const status = computed({
	get: () => list.state.filters.status || "",
	set: (value) => (list.state.filters.status = value),
})

const counts = ref<Record<string, number>>({})
watch(
	() => JSON.stringify(baseFilters(list.state)),
	async () => {
		counts.value = await getGroupCounts("Leave Application", "status", baseFilters(list.state)).catch(() => ({}))
	},
	{ immediate: true }
)

const statusTabs = computed(() => {
	const total = Object.values(counts.value).reduce((a, b) => a + b, 0)
	return [
		{ label: "All", value: "", count: total },
		...["Open", "Approved", "Rejected", "Cancelled"].map((s) => ({ label: s, value: s, count: counts.value[s] || 0 })),
	]
})

const hasFilters = computed(
	() =>
		!!list.state.search ||
		Object.entries(list.state.filters).some(([key, value]) => key !== "status" && !!value)
)

/** A saved draft can carry Approved or Rejected before it is submitted. */
function displayStatus(row: Record<string, any>) {
	if (row.docstatus === 0 && row.status !== "Open") return `${row.status} (draft)`
	return row.status
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{ key: "leave_type", label: "Leave type", width: "minmax(110px,1.2fr)", sortable: true },
	{ key: "from_date", label: "From", width: "minmax(90px,1fr)", sortable: true, format: (v) => formatDate(v) },
	{ key: "to_date", label: "To", width: "minmax(90px,1fr)", sortable: true, format: (v) => formatDate(v) },
	{
		key: "total_leave_days",
		label: "Days",
		width: "60px",
		align: "right",
		sortable: true,
		format: (v) => formatNumber(v),
	},
	{ key: "status", label: "Status", width: "minmax(110px,1.1fr)", sortable: true },
	{ key: "leave_approver_name", label: "Approver", width: "minmax(110px,1.2fr)", hideOnMobile: true },
	{ key: "company", label: "Company", width: "minmax(110px,1.2fr)", sortable: true },
]
</script>
