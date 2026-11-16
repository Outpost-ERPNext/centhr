<template>
	<PageHeader :crumbs="[{ label: '360 Setup' }]">
		<template #actions>
			<Button v-if="can('PMS 360 Degree').create" variant="solid" icon-left="lucide-plus" label="New 360 review" :route="{ name: 'Pms360New' }" />
		</template>
	</PageHeader>

	<FilterBar v-model:search="list.state.search" :total="list.total.value" :active="hasFilters" search-placeholder="Search" noun="review" @clear="list.clearFilters">
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.fiscal_year" doctype="Fiscal Year" placeholder="Fiscal year" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-orbit"
		:empty-message="hasFilters ? 'No 360 reviews match these filters' : 'No 360 review set up yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('PMS 360 Degree', row.name)!)"
		@clear-filters="list.clearFilters"
	/>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import Pager from "@/components/Pager.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "PMS 360 Degree",
	fields: ["name", "company", "fiscal_year", "quarter"],
	searchFields: ["name"],
	defaultSort: { field: "creation", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const field of ["company", "fiscal_year"]) {
			if (state.filters[field]) filters.push([field, "=", state.filters[field]])
		}
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns: Column[] = [
	{ key: "company", label: "Company", width: "minmax(200px,2fr)", sortable: true },
	{ key: "fiscal_year", label: "Fiscal year", width: "140px", sortable: true },
	{ key: "quarter", label: "Quarter", width: "110px", sortable: true },
]
</script>
