<template>
	<PageHeader :crumbs="[{ label: 'Salary Slip' }]">
		<template #actions>
			<Button
				v-if="can('Salary Slip').create"
				variant="solid"
				icon-left="lucide-upload"
				label="Import from Excel"
				@click="importOpen = true"
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
		search-placeholder="Search employee or slip"
		noun="salary slip"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" />
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" />
		<FilterLink v-model="list.state.filters.payroll_entry" doctype="Payroll Entry" placeholder="Payroll entry" />
		<DateFilter
			v-model:op="list.state.filters.date_op"
			v-model:from="list.state.filters.date_from"
			v-model:to="list.state.filters.date_to"
			label="Period"
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
		empty-icon="lucide-receipt"
		empty-message="No salary slips match these filters"
		mobile-aside="status"
		min-width="980px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('Salary Slip', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }} · {{ row.employee }}</div>
			</div>
		</template>
		<template #cell-start_date="{ row }">
			{{ formatDate(row.start_date) }} – {{ formatDate(row.end_date) }}
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Salary Slip" :status="row.status" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<SalarySlipImportDialog v-model:open="importOpen" @imported="refresh" />
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
import SalarySlipImportDialog from "./SalarySlipImportDialog.vue"
import { dateFilter, getGroupCounts, useDocList, type Filter, type ListState } from "@/data/list"
import { can } from "@/data/permissions"
import { formatCurrency, formatDate } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const STATUSES = ["Draft", "Submitted", "Withheld", "Cancelled"]

const router = useRouter()
const importOpen = ref(false)

function baseFilters(state: ListState): Filter[] {
	const filters: Filter[] = []
	for (const key of ["employee", "company", "department", "payroll_entry"]) {
		if (state.filters[key]) filters.push([key, "=", state.filters[key]])
	}
	const op = state.filters.date_op
	// "Between" matches any slip whose period overlaps the range
	if (op === "between" && state.filters.date_from && state.filters.date_to) {
		filters.push(["start_date", "<=", state.filters.date_to], ["end_date", ">=", state.filters.date_from])
	} else {
		const f = dateFilter("start_date", op, state.filters.date_from)
		if (f) filters.push(f)
	}
	return filters
}

const list = useDocList({
	doctype: "Salary Slip",
	fields: [
		"name",
		"employee",
		"employee_name",
		"department",
		"company",
		"currency",
		"start_date",
		"end_date",
		"posting_date",
		"payroll_entry",
		"gross_pay",
		"total_deduction",
		"net_pay",
		"status",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "start_date", order: "desc" },
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
async function loadCounts() {
	counts.value = await getGroupCounts("Salary Slip", "status", baseFilters(list.state)).catch(() => ({}))
}
watch(() => JSON.stringify(baseFilters(list.state)), loadCounts, { immediate: true })

function refresh() {
	list.reload()
	loadCounts()
}

const statusTabs = computed(() => {
	const total = Object.values(counts.value).reduce((a, b) => a + b, 0)
	return [{ label: "All", value: "", count: total }, ...STATUSES.map((s) => ({ label: s, value: s, count: counts.value[s] || 0 }))]
})

const hasFilters = computed(
	() => !!list.state.search || Object.entries(list.state.filters).some(([key, value]) => key !== "status" && !!value)
)

/** Formats an amount in the currency of its slip */
const money = (value: any, row: Record<string, any>) => formatCurrency(value, row.currency)

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{ key: "start_date", label: "Period", width: "minmax(170px,1.6fr)", sortable: true },
	{ key: "gross_pay", label: "Gross pay", width: "minmax(110px,1fr)", align: "right", sortable: true, format: money },
	{ key: "total_deduction", label: "Deductions", width: "minmax(110px,1fr)", align: "right", sortable: true, format: money, hideOnMobile: true },
	{ key: "net_pay", label: "Net pay", width: "minmax(110px,1fr)", align: "right", sortable: true, format: money },
	{ key: "status", label: "Status", width: "minmax(100px,1fr)", sortable: true },
	{ key: "department", label: "Department", width: "minmax(110px,1.2fr)", sortable: true, hideOnMobile: true },
	{ key: "company", label: "Company", width: "minmax(110px,1.2fr)", sortable: true },
]
</script>
