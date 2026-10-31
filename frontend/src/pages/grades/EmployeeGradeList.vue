<template>
	<PageHeader :crumbs="[{ label: 'Grade' }]">
		<template #actions>
			<Button
				v-if="can('Employee Grade').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New grade"
				:route="{ name: 'EmployeeGradeNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search grades"
		noun="grade"
		@clear="list.clearFilters"
	>
		<FilterLink
			v-if="readable('default_salary_structure')"
			v-model="list.state.filters.default_salary_structure"
			doctype="Salary Structure"
			placeholder="Salary structure"
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
		empty-icon="lucide-award"
		:empty-message="hasFilters ? 'No grades match these filters' : 'No grades created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/grades/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-award size-4" />
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
import FilterLink from "@/components/FilterLink.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import { getGroupCounts, useDocList, type Filter } from "@/data/list"
import { can, useReadableFields } from "@/data/permissions"
import { formatCurrency } from "@/utils/format"

const router = useRouter()

const { ready, readable } = useReadableFields("Employee Grade")
const FIELDS = ["default_salary_structure", "default_base_pay", "currency"]

const list = useDocList({
	doctype: "Employee Grade",
	fields: () => ["name", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) =>
		state.filters.default_salary_structure && readable("default_salary_structure")
			? [["default_salary_structure", "=", state.filters.default_salary_structure] as Filter]
			: [],
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

// One grouped count covers every row; empty when the user cannot read Employee
const employees = ref<Record<string, number>>({})
getGroupCounts("Employee", "grade", [["status", "=", "Active"]]).then((c) => (employees.value = c)).catch(() => undefined)

const columns = computed<Column[]>(() => [
	{ key: "name", label: "Grade", width: "minmax(200px,2fr)", sortable: true },
	...(
		[
			{
				key: "default_salary_structure",
				label: "Default salary structure",
				width: "minmax(180px,1.8fr)",
				sortable: true,
				hideOnMobile: true,
				format: (v: any) => v || "—",
			},
			{
				key: "default_base_pay",
				label: "Default base pay",
				width: "minmax(130px,1.2fr)",
				align: "right",
				sortable: true,
				format: (v: any, row: Record<string, any>) => (v ? formatCurrency(v, row.currency) : "—"),
			},
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
