<template>
	<PageHeader :crumbs="[{ label: 'Payroll Entry' }]">
		<template #actions>
			<Button
				v-if="can('Payroll Entry').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New payroll entry"
				:route="{ name: 'PayrollEntryNew', query: list.state.filters.company ? { company: list.state.filters.company } : {} }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search payroll entry ID"
		noun="payroll entry"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterSelect
			v-model="list.state.filters.payroll_frequency"
			:options="['Monthly', 'Fortnightly', 'Bimonthly', 'Weekly', 'Daily'].map((f) => ({ label: f, value: f }))"
			placeholder="Frequency"
		/>
		<FilterSelect
			v-model="list.state.filters.status"
			:options="['Draft', 'Submitted', 'Queued', 'Failed', 'Cancelled'].map((s) => ({ label: s, value: s }))"
			placeholder="Status"
		/>
		<PayrollCycleNav
			v-if="list.state.filters.company"
			:company="list.state.filters.company"
			allow-whole-year
			:from="list.state.filters.from"
			:to="list.state.filters.to"
			@update:from="list.state.filters.from = $event"
			@update:to="list.state.filters.to = $event"
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
		empty-icon="lucide-banknote"
		empty-message="No payroll entries match these filters"
		mobile-aside="status"
		min-width="900px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/payroll-processing/payroll-entries/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-start_date="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ cycleLabel(row.start_date, row.end_date) }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }} · posted {{ formatDateShort(row.posting_date) }}</div>
			</div>
		</template>
		<template #cell-salary_slips_created="{ row }">
			<span class="text-ch-ink-2">{{ slipStage(row) }}</span>
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Payroll Entry" :status="row.status" />
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
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { cycleLabel } from "@/data/payroll"
import { formatDateShort, formatNumber } from "@/utils/format"

const router = useRouter()

const list = useDocList({
	doctype: "Payroll Entry",
	fields: [
		"name",
		"company",
		"posting_date",
		"payroll_frequency",
		"start_date",
		"end_date",
		"number_of_employees",
		"salary_slips_created",
		"salary_slips_submitted",
		"status",
	],
	searchFields: ["name"],
	defaultSort: { field: "start_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["company", "payroll_frequency", "status"]) {
			if (state.filters[key]) filters.push([key, "=", state.filters[key]])
		}
		// Entries whose pay period falls inside the picked payroll month or year
		if (state.filters.company && state.filters.from) filters.push(["start_date", ">=", state.filters.from])
		if (state.filters.company && state.filters.to) filters.push(["end_date", "<=", state.filters.to])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

function slipStage(row: Record<string, any>) {
	if (row.salary_slips_submitted) return "Submitted"
	if (row.salary_slips_created) return "Created"
	return row.number_of_employees ? "Not created" : "—"
}

const columns: Column[] = [
	{ key: "start_date", label: "Pay period", width: "minmax(220px,2fr)", sortable: true },
	{ key: "company", label: "Company", width: "minmax(120px,1.3fr)", sortable: true },
	{ key: "payroll_frequency", label: "Frequency", width: "minmax(90px,1fr)", sortable: true },
	{
		key: "number_of_employees",
		label: "Employees",
		width: "90px",
		align: "right",
		sortable: true,
		format: (v) => formatNumber(v),
	},
	{ key: "salary_slips_created", label: "Salary slips", width: "minmax(100px,1fr)" },
	{ key: "status", label: "Status", width: "minmax(90px,1fr)", sortable: true },
]
</script>
