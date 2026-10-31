<template>
	<PageHeader :crumbs="[{ label: 'Designation' }]">
		<template #actions>
			<Button
				v-if="can('Designation').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New designation"
				:route="{ name: 'DesignationNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search designations"
		noun="designation"
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
		empty-icon="lucide-briefcase"
		:empty-message="hasFilters ? 'No designations match this search' : 'No designations created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/designations/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-briefcase size-4" />
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
import { can, useReadableFields } from "@/data/permissions"

const router = useRouter()

const { ready, readable } = useReadableFields("Designation")

const list = useDocList({
	doctype: "Designation",
	fields: () => ["name", ...["description"].filter(readable)],
	ready,
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: () => [],
})

const hasFilters = computed(() => !!list.state.search)

// One grouped count covers every row; empty when the user cannot read Employee
const employees = ref<Record<string, number>>({})
getGroupCounts("Employee", "designation", [["status", "=", "Active"]]).then((c) => (employees.value = c)).catch(() => undefined)

const columns = computed<Column[]>(() => [
	{ key: "name", label: "Designation", width: "minmax(200px,1.6fr)", sortable: true },
	...(readable("description")
		? [
				{
					key: "description",
					label: "Description",
					width: "minmax(220px,2.4fr)",
					hideOnMobile: true,
					format: (v: any) => v || "—",
				} as Column,
			]
		: []),
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
