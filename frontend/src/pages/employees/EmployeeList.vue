<template>
	<PageHeader :crumbs="[{ label: 'Employees' }]">
		<template #actions>
			<Button
				v-if="can('Employee').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New employee"
				:route="{ name: 'EmployeeNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search name or ID"
		noun="employee"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" />
		<FilterLink v-model="list.state.filters.designation" doctype="Designation" placeholder="Designation" />
		<FilterSelect
			v-model="list.state.filters.status"
			:options="selectOptions('Employee', 'status')"
			placeholder="Status"
		/>
		<FilterLink v-model="list.state.filters.grade" doctype="Employee Grade" placeholder="Grade" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-users"
		empty-message="No employees match these filters"
		mobile-aside="status"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/employees/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<Avatar :image="row.image || undefined" :label="row.employee_name" size="md" shape="circle" />
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.designation }}</div>
				</div>
			</div>
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Employee" :status="row.status" />
		</template>
	</DataTable>

	<Pager
		v-model:page="list.state.page"
		v-model:page-size="list.state.pageSize"
		:total="list.total.value"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Avatar, Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { loadMeta, selectOptions } from "@/data/meta"
import { can } from "@/data/permissions"
import { formatDate } from "@/utils/format"

const router = useRouter()
loadMeta("Employee")

const list = useDocList({
	doctype: "Employee",
	fields: [
		"name",
		"employee_name",
		"image",
		"designation",
		"company",
		"department",
		"grade",
		"status",
		"date_of_joining",
	],
	searchFields: ["employee_name", "name"],
	defaultSort: { field: "employee_name", order: "asc" },
	buildFilters: (state) =>
		(["company", "department", "designation", "status", "grade"] as const)
			.filter((key) => state.filters[key])
			.map((key) => [key, "=", state.filters[key]] as Filter),
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns: Column[] = [
	{ key: "employee_name", label: "Name", width: "minmax(200px,2.2fr)", sortable: true },
	{ key: "name", label: "ID", width: "minmax(110px,1.1fr)", sortable: true, class: "text-ch-ink-2" },
	{ key: "company", label: "Company", width: "minmax(120px,1.4fr)", sortable: true },
	{ key: "department", label: "Department", width: "minmax(120px,1.4fr)", sortable: true },
	{ key: "grade", label: "Grade", width: "minmax(60px,0.8fr)", sortable: true },
	{ key: "status", label: "Status", width: "minmax(90px,1fr)", sortable: true },
	{
		key: "date_of_joining",
		label: "Joined",
		width: "minmax(100px,1fr)",
		sortable: true,
		format: (v) => formatDate(v),
	},
]
</script>
