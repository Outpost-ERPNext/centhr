<template>
	<PageHeader :crumbs="[{ label: 'Department' }]">
		<template #actions>
			<Button
				v-if="can('Department').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New department"
				:route="{ name: 'DepartmentNew', query: list.state.filters.company ? { company: list.state.filters.company } : {} }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search departments"
		noun="department"
		@clear="list.clearFilters"
	>
		<FilterLink v-if="readable('company')" v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink
			v-if="readable('parent_department')"
			v-model="list.state.filters.parent_department"
			doctype="Department"
			:filters="{ is_group: 1 }"
			placeholder="Parent"
		/>
		<FilterSelect
			v-if="readable('is_group')"
			v-model="list.state.filters.is_group"
			:options="[
				{ label: 'Groups', value: '1' },
				{ label: 'Departments', value: '0' },
			]"
			placeholder="Type"
		/>
		<FilterSelect
			v-if="readable('disabled')"
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
		empty-icon="lucide-building-2"
		:empty-message="hasFilters ? 'No departments match these filters' : 'No departments created yet'"
		min-width="760px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/departments/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-department_name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span :class="row.is_group ? 'lucide-folder-tree' : 'lucide-building-2'" class="size-4" />
				</span>
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.department_name || row.name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }}</div>
				</div>
			</div>
		</template>
		<template #cell-disabled="{ row }">
			<StatusBadge :status="row.disabled ? 'Disabled' : 'Enabled'" :tone="row.disabled ? 'gray' : 'green'" />
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
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getGroupCounts, useDocList, type Filter } from "@/data/list"
import { can, useReadableFields } from "@/data/permissions"

const router = useRouter()

const { ready, readable } = useReadableFields("Department")
const FIELDS = ["department_name", "parent_department", "company", "is_group", "disabled"]

const list = useDocList({
	doctype: "Department",
	fields: () => ["name", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["department_name", "name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["company", "parent_department"]) {
			if (state.filters[key] && readable(key)) filters.push([key, "=", state.filters[key]])
		}
		for (const key of ["is_group", "disabled"]) {
			if (state.filters[key] && readable(key)) filters.push([key, "=", Number(state.filters[key])])
		}
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

// One grouped count covers every row; empty when the user cannot read Employee
const employees = ref<Record<string, number>>({})
getGroupCounts("Employee", "department", [["status", "=", "Active"]]).then((c) => (employees.value = c)).catch(() => undefined)

const columns = computed<Column[]>(() => [
	{ key: "department_name", label: "Department", width: "minmax(220px,2fr)", sortable: true },
	...(
		[
			{ key: "parent_department", label: "Parent", width: "minmax(150px,1.4fr)", sortable: true, hideOnMobile: true, format: (v: any) => v || "—" },
			{ key: "company", label: "Company", width: "minmax(150px,1.4fr)", sortable: true, hideOnMobile: true, format: (v: any) => v || "All companies" },
			{ key: "disabled", label: "Status", width: "minmax(90px,0.8fr)", sortable: true },
		] as Column[]
	).filter((c) => readable(c.key)),
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
