<template>
	<PageHeader :crumbs="[{ label: 'Leave Allocation' }]">
		<template #actions>
			<Button
				v-if="can('Leave Allocation').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New allocation"
				:route="{ name: 'LeaveAllocationNew', query: newQuery }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="allocation"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" />
		<FilterLink v-model="list.state.filters.leave_type" doctype="Leave Type" placeholder="Leave type" />
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterSelect
			v-model="list.state.filters.state"
			:options="[
				{ label: 'Draft', value: '0' },
				{ label: 'Submitted', value: '1' },
				{ label: 'Cancelled', value: '2' },
			]"
			placeholder="Status"
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
		empty-icon="lucide-calendar-plus"
		empty-message="No leave allocations match these filters"
		mobile-aside="docstatus"
		min-width="880px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/leave-allocations/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }} · {{ period(row) }}</div>
			</div>
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge :status="rowStatus(row)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { formatDateShort, formatNumber, parseDate } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()

const list = useDocList({
	doctype: "Leave Allocation",
	fields: [
		"name",
		"employee",
		"employee_name",
		"leave_type",
		"company",
		"from_date",
		"to_date",
		"new_leaves_allocated",
		"total_leaves_allocated",
		"docstatus",
		"expired",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "from_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["employee", "leave_type", "company"]) {
			if (state.filters[key]) filters.push([key, "=", state.filters[key]])
		}
		if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
		return filters
	},
})

/** Carries the employee and company filters into a new allocation. */
const newQuery = computed(() => {
	const query: Record<string, string> = {}
	for (const key of ["employee", "company"]) if (list.state.filters[key]) query[key] = String(list.state.filters[key])
	return query
})
const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

function period(row: Record<string, any>) {
	const from = parseDate(row.from_date)
	const to = parseDate(row.to_date)
	if (!from || !to) return ""
	return from.getFullYear() === to.getFullYear() ? String(from.getFullYear()) : `${from.getFullYear()}–${to.getFullYear()}`
}

function rowStatus(row: Record<string, any>) {
	if (row.docstatus === 1 && row.expired) return "Expired"
	return docstatusLabel(row.docstatus)
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{ key: "leave_type", label: "Leave type", width: "minmax(110px,1.2fr)", sortable: true },
	{ key: "company", label: "Company", width: "minmax(110px,1.2fr)", sortable: true },
	{
		key: "new_leaves_allocated",
		label: "New",
		width: "70px",
		align: "right",
		sortable: true,
		format: (v) => formatNumber(v),
	},
	{
		key: "total_leaves_allocated",
		label: "Total",
		width: "70px",
		align: "right",
		sortable: true,
		format: (v) => formatNumber(v),
	},
	{
		key: "from_date",
		label: "Validity",
		width: "minmax(170px,1.6fr)",
		sortable: true,
		format: (_, row) => `${formatDateShort(row.from_date)} – ${formatDateShort(row.to_date)}`,
	},
	{ key: "docstatus", label: "Status", width: "minmax(90px,1fr)", sortable: true },
]
</script>
