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

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="salary slip"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" :filters="companyFilter" />
		<FilterLink
			v-model="list.state.filters.payroll_entry"
			doctype="Payroll Entry"
			placeholder="Payroll entry"
			:filters="companyFilter"
		/>
		<FilterSelect
			v-model="list.state.filters.status"
			:options="['Draft', 'Submitted', 'Withheld', 'Cancelled'].map((s) => ({ label: s, value: s }))"
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
		empty-icon="lucide-receipt"
		:empty-message="
			hasFilters ? 'No salary slips match these filters' : 'No salary slips yet. Submit a payroll entry or import them from Excel.'
		"
		mobile-aside="status"
		min-width="960px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/payroll-processing/salary-slips/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }}{{ row.designation ? ` · ${row.designation}` : "" }}</div>
			</div>
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Salary Slip" :status="row.status" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<SalarySlipImportDialog v-model:open="importOpen" @imported="list.reload" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
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
import SalarySlipImportDialog from "./SalarySlipImportDialog.vue"
import { useDocList, type Filter } from "@/data/list"
import { cycleLabel } from "@/data/payroll"
import { can } from "@/data/permissions"
import { formatCurrency, formatNumber } from "@/utils/format"

const router = useRouter()
const importOpen = ref(false)

const list = useDocList({
	doctype: "Salary Slip",
	fields: [
		"name",
		"employee",
		"employee_name",
		"designation",
		"company",
		"payroll_entry",
		"start_date",
		"end_date",
		"payment_days",
		"total_working_days",
		"currency",
		"gross_pay",
		"total_deduction",
		"net_pay",
		"status",
	],
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "start_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["company", "employee", "payroll_entry", "status"]) {
			if (state.filters[key]) filters.push([key, "=", state.filters[key]])
		}
		// Slips whose pay period falls inside the picked payroll month or year
		if (state.filters.company && state.filters.from) filters.push(["start_date", ">=", state.filters.from])
		if (state.filters.company && state.filters.to) filters.push(["end_date", "<=", state.filters.to])
		return filters
	},
})

/** The employee and payroll entry pickers only offer the selected company's records. */
const companyFilter = computed(() => (list.state.filters.company ? { company: list.state.filters.company } : undefined))
const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const money = (v: any, row: Record<string, any>) => formatCurrency(v, row.currency)

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)", sortable: true },
	{
		key: "start_date",
		label: "Pay period",
		width: "minmax(150px,1.4fr)",
		sortable: true,
		format: (_, row) => cycleLabel(row.start_date, row.end_date),
	},
	{
		key: "payment_days",
		label: "Paid days",
		width: "90px",
		align: "right",
		format: (v, row) => `${formatNumber(v)} / ${formatNumber(row.total_working_days)}`,
	},
	{ key: "gross_pay", label: "Gross", width: "minmax(100px,1fr)", align: "right", sortable: true, format: money },
	{ key: "total_deduction", label: "Deductions", width: "minmax(100px,1fr)", align: "right", sortable: true, format: money },
	{ key: "net_pay", label: "Net pay", width: "minmax(100px,1fr)", align: "right", sortable: true, format: money },
	{ key: "status", label: "Status", width: "minmax(90px,1fr)", sortable: true },
]
</script>
