<template>
	<PageHeader :crumbs="[{ label: 'KPI Result' }]" />

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employees"
		noun="result"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.fiscal_year" doctype="Fiscal Year" placeholder="Fiscal year" />
		<FilterSelect v-model="list.state.filters.month" :options="MONTHS" placeholder="Month" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" :filters="{ is_group: 0 }" />
		<FilterSelect
			v-model="list.state.filters.docstatus"
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
		empty-icon="lucide-chart-column"
		:empty-message="hasFilters ? 'No KPI Results match these filters' : 'No KPI Results yet. One is made when a KPI Template is submitted.'"
		mobile-aside="docstatus"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('KPI Result', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.designation].filter(Boolean).join(" · ") }}</div>
			</div>
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge doctype="docstatus" :status="docstatusLabel(row.docstatus)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { MONTHS } from "@/data/pms"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import { docstatusLabel } from "@/utils/status"

/** Every KPI Result the user may see, of any month. A result is made by submitting a KPI Template,
 * so there is nothing to create here; the KPI Dashboard shows one month with its counts. */
const router = useRouter()

const list = useDocList({
	doctype: "KPI Result",
	fields: ["name", "employee", "employee_name", "department", "designation", "fiscal_year", "month", "overall_score", "remark", "docstatus"],
	searchFields: ["employee_name", "employee"],
	defaultSort: { field: "creation", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const field of ["fiscal_year", "month", "department"]) {
			if (state.filters[field]) filters.push([field, "=", state.filters[field]])
		}
		if (state.filters.docstatus) filters.push(["docstatus", "=", Number(state.filters.docstatus)])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)", sortable: true },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "month", label: "Month", width: "120px", format: (_, row) => `${row.month} ${row.fiscal_year}` },
	{ key: "overall_score", label: "Score", width: "90px", align: "right", sortable: true, format: (v) => formatNumber(v || 0, 2) },
	{ key: "remark", label: "Remark", width: "minmax(130px,1fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "docstatus", label: "Status", width: "120px", sortable: true },
]
</script>
