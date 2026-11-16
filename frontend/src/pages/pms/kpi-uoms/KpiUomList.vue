<template>
	<PageHeader :crumbs="[{ label: 'KPI UOM' }]">
		<template #actions>
			<Button v-if="can('KPI UOM').create" variant="solid" icon-left="lucide-plus" label="New unit" :route="{ name: 'KpiUomNew' }" />
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="!!list.state.search"
		search-placeholder="Search units"
		noun="unit"
		@clear="list.clearFilters"
	/>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="!!list.state.search"
		empty-icon="lucide-ruler"
		:empty-message="list.state.search ? 'No units match this search' : 'No units created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('KPI UOM', row.name)!)"
		@clear-filters="list.clearFilters"
	/>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import Pager from "@/components/Pager.vue"
import { useDocList } from "@/data/list"
import { can } from "@/data/permissions"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "KPI UOM",
	fields: ["name"],
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: () => [],
})

const columns: Column[] = [{ key: "name", label: "KPI UOM", width: "minmax(220px,1fr)", sortable: true }]
</script>
