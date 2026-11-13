<template>
	<PageHeader :crumbs="[{ label: 'Org Master', route: '/org-master' }, { label: 'Employment Type' }]">
		<template #actions>
			<Button
				v-if="can('Employment Type').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New employment type"
				:route="{ name: 'EmploymentTypeNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employment types"
		noun="employment type"
		@clear="list.clearFilters"
	/>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-id-card"
		:empty-message="hasFilters ? 'No employment types match this search' : 'No employment types created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/employment-types/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-id-card size-4" />
				</span>
				<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
			</div>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import { getGroupCounts, useDocList } from "@/data/list"
import { can } from "@/data/permissions"

const router = useRouter()

const list = useDocList({
	doctype: "Employment Type",
	fields: () => ["name"],
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: () => [],
})

const hasFilters = computed(() => !!list.state.search)

// One grouped count covers every row; empty when the user cannot read Employee
const employees = ref<Record<string, number>>({})
getGroupCounts("Employee", "employment_type", [["status", "=", "Active"]]).then((c) => (employees.value = c)).catch(() => undefined)

const columns = computed<Column[]>(() => [
	{ key: "name", label: "Employment type", width: "minmax(200px,3fr)", sortable: true },
	...(can("Employee").read
		? [
				{
					key: "employees",
					label: "Active employees",
					width: "minmax(110px,0.9fr)",
					align: "right",
					format: (_: any, row: Record<string, any>) => String(employees.value[row.name] || 0),
				} as Column,
			]
		: []),
])
</script>
