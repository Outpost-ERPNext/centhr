<template>
	<PageHeader :crumbs="[{ label: 'Salary Structure' }]">
		<template #actions>
			<Button
				v-if="can('Salary Structure').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New structure"
				:route="{ name: 'SalaryStructureNew', query: list.state.filters.company ? { company: list.state.filters.company } : {} }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search structure"
		noun="structure"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterSelect v-model="list.state.filters.is_active" :options="['Yes', 'No']" placeholder="Active" />
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
		empty-icon="lucide-layers"
		empty-message="No salary structures match these filters"
		mobile-aside="docstatus"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('Salary Structure', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-1.5">
				<span class="truncate font-medium text-ch-ink">{{ row.name }}</span>
				<StatusBadge v-if="row.is_active === 'No'" pill tone="red" status="Inactive" />
			</div>
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge :status="docstatusLabel(row.docstatus)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getGroupCounts, useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { routeFor } from "@/utils/routes"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()

const list = useDocList({
	doctype: "Salary Structure",
	fields: ["name", "company", "payroll_frequency", "currency", "is_active", "docstatus"],
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["company", "is_active"]) if (state.filters[key]) filters.push([key, "=", state.filters[key]])
		if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

// One grouped count covers every row on the page
const assigned = ref<Record<string, number>>({})
getGroupCounts("Salary Structure Assignment", "salary_structure", [["docstatus", "=", 1]])
	.then((c) => (assigned.value = c))
	.catch(() => undefined)

const columns: Column[] = [
	{ key: "name", label: "Structure", width: "minmax(220px,2.2fr)", sortable: true },
	{ key: "company", label: "Company", width: "minmax(140px,1.4fr)", sortable: true },
	{ key: "payroll_frequency", label: "Frequency", width: "110px", sortable: true },
	{ key: "currency", label: "Currency", width: "90px", sortable: true },
	{ key: "assigned", label: "Assignments", width: "110px", align: "right", format: (_, row) => String(assigned.value[row.name] || 0) },
	{ key: "docstatus", label: "Status", width: "100px", sortable: true },
]
</script>
