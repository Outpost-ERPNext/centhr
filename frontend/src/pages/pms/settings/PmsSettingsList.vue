<template>
	<PageHeader :crumbs="[{ label: 'PMS Settings' }]">
		<template #actions>
			<Button v-if="can('PMS Settings').create" variant="solid" icon-left="lucide-plus" label="New settings" :route="{ name: 'PmsSettingsNew' }" />
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="!!list.state.search"
		search-placeholder="Search companies"
		noun="company"
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
		empty-icon="lucide-sliders-horizontal"
		:empty-message="list.state.search ? 'No company matches this search' : 'No company has PMS settings yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('PMS Settings', row.name)!)"
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
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "PMS Settings",
	fields: ["name", "company", "overall_kpi_weight", "overall__360_weight"],
	searchFields: ["company"],
	defaultSort: { field: "company", order: "asc" },
	buildFilters: () => [],
})

const percent = (value: any) => `${formatNumber(value || 0)}%`

const columns: Column[] = [
	{ key: "company", label: "Company", width: "minmax(220px,2fr)", sortable: true },
	{ key: "overall_kpi_weight", label: "KPI weight", width: "130px", align: "right", format: percent },
	{ key: "overall__360_weight", label: "360 weight", width: "130px", align: "right", format: percent },
]
</script>
