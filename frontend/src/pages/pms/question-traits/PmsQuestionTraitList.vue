<template>
	<PageHeader :crumbs="[{ label: 'Question Trait' }]">
		<template #actions>
			<Button v-if="can('PMS Question Trait').create" variant="solid" icon-left="lucide-plus" label="New trait" :route="{ name: 'PmsQuestionTraitNew' }" />
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="!!list.state.search"
		search-placeholder="Search traits"
		noun="trait"
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
		empty-icon="lucide-tags"
		:empty-message="list.state.search ? 'No traits match this search' : 'No traits created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('PMS Question Trait', row.name)!)"
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
	doctype: "PMS Question Trait",
	fields: ["name"],
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: () => [],
})

const columns: Column[] = [{ key: "name", label: "Question Trait", width: "minmax(220px,1fr)", sortable: true }]
</script>
