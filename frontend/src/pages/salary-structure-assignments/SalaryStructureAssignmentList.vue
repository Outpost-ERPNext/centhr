<template>
	<PageHeader :crumbs="[{ label: 'Salary Structure Assignment' }]">
		<template #actions>
			<Button
				v-if="can('Salary Structure Assignment').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New assignment"
				:route="{ name: 'SalaryStructureAssignmentNew', query: newQuery }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="assignment"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" :filters="companyFilter" />
		<FilterLink
			v-model="list.state.filters.salary_structure"
			doctype="Salary Structure"
			placeholder="Salary structure"
			:filters="companyFilter"
		/>
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
		empty-icon="lucide-wallet"
		empty-message="No salary structure assignments match these filters"
		mobile-aside="docstatus"
		min-width="920px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/salary-structure-assignments/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }}{{ row.designation ? ` · ${row.designation}` : "" }}</div>
			</div>
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge :status="docstatusLabel(row.docstatus)" />
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
import { formatCurrency, formatDateShort } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()

const list = useDocList({
	doctype: "Salary Structure Assignment",
	fields: [
		"name",
		"employee",
		"employee_name",
		"designation",
		"company",
		"salary_structure",
		"from_date",
		"currency",
		"base",
		"variable",
		"docstatus",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "from_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["company", "employee", "salary_structure"]) {
			if (state.filters[key]) filters.push([key, "=", state.filters[key]])
		}
		if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
		return filters
	},
})

/** The employee and structure pickers only offer the selected company's records. */
const companyFilter = computed(() => (list.state.filters.company ? { company: list.state.filters.company } : undefined))

/** Carries the company and employee filters into a new assignment. */
const newQuery = computed(() => {
	const query: Record<string, string> = {}
	for (const key of ["employee", "company"]) if (list.state.filters[key]) query[key] = String(list.state.filters[key])
	return query
})
const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{ key: "salary_structure", label: "Salary structure", width: "minmax(140px,1.5fr)", sortable: true },
	{ key: "company", label: "Company", width: "minmax(110px,1.2fr)", sortable: true },
	{
		key: "base",
		label: "Base",
		width: "minmax(100px,1fr)",
		align: "right",
		sortable: true,
		format: (v, row) => formatCurrency(v, row.currency),
	},
	{
		key: "variable",
		label: "Variable",
		width: "minmax(90px,1fr)",
		align: "right",
		sortable: true,
		format: (v, row) => formatCurrency(v, row.currency),
	},
	{ key: "from_date", label: "From", width: "100px", sortable: true, format: (v) => formatDateShort(v) },
	{ key: "docstatus", label: "Status", width: "minmax(90px,1fr)", sortable: true },
]
</script>
