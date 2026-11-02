<template>
	<PageHeader :crumbs="[{ label: 'Salary Structure Assignment', route: '/salary-structure-assignments' }, { label: 'Salary Component' }]">
		<template #actions>
			<Button
				v-if="can('Salary Component').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New component"
				:route="{ name: 'SalaryComponentNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search component or abbreviation"
		noun="component"
		@clear="list.clearFilters"
	>
		<FilterSelect v-model="list.state.filters.type" :options="['Earning', 'Deduction']" placeholder="Type" />
		<FilterSelect
			v-model="list.state.filters.disabled"
			:options="[
				{ label: 'Enabled', value: '0' },
				{ label: 'Disabled', value: '1' },
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
		empty-icon="lucide-list-plus"
		empty-message="No salary components match these filters"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('Salary Component', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.salary_component_abbr }}</div>
			</div>
		</template>
		<template #cell-type="{ row }">
			<StatusBadge :tone="row.type === 'Earning' ? 'green' : 'red'" :status="row.type" />
		</template>
		<template #cell-disabled="{ row }">
			<StatusBadge :tone="row.disabled ? 'gray' : 'green'" :status="row.disabled ? 'Disabled' : 'Enabled'" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "Salary Component",
	fields: ["name", "salary_component_abbr", "type", "amount_based_on_formula", "formula", "amount", "depends_on_payment_days", "is_tax_applicable", "disabled"],
	searchFields: ["name", "salary_component_abbr"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		if (state.filters.type) filters.push(["type", "=", state.filters.type])
		if (state.filters.disabled) filters.push(["disabled", "=", Number(state.filters.disabled)])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))
const yesNo = (v: any) => (v ? "Yes" : "No")

const columns: Column[] = [
	{ key: "name", label: "Component", width: "minmax(200px,2fr)", sortable: true },
	{ key: "type", label: "Type", width: "110px", sortable: true },
	{
		key: "formula",
		label: "Amount",
		width: "minmax(160px,1.6fr)",
		format: (_, row) => (row.amount_based_on_formula ? row.formula || "Formula" : row.amount ? String(row.amount) : "From structure"),
	},
	{ key: "depends_on_payment_days", label: "Pro-rated", width: "100px", sortable: true, format: yesNo },
	{ key: "is_tax_applicable", label: "Taxable", width: "90px", sortable: true, format: yesNo },
	{ key: "disabled", label: "Status", width: "100px", sortable: true },
]
</script>
