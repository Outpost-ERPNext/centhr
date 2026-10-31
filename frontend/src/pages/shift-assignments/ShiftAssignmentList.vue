<template>
	<PageHeader :crumbs="[{ label: 'Shift Assignment' }]">
		<template #actions>
			<Button
				v-if="can('Shift Assignment Tool').write"
				icon-left="lucide-users-round"
				label="Assign in bulk"
				:route="{ name: 'ShiftAssignmentTool' }"
			/>
			<Button
				v-if="can('Shift Assignment').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New assignment"
				:route="{ name: 'ShiftAssignmentNew', query: newQuery }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="assignment"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.employee" doctype="Employee" placeholder="Employee" />
		<FilterLink v-model="list.state.filters.shift_type" doctype="Shift Type" placeholder="Shift" />
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterSelect
			v-if="readable('status')"
			v-model="list.state.filters.status"
			:options="selectOptions('Shift Assignment', 'status')"
			placeholder="Status"
		/>
		<FilterSelect
			v-model="list.state.filters.state"
			:options="[
				{ label: 'Draft', value: '0' },
				{ label: 'Submitted', value: '1' },
				{ label: 'Cancelled', value: '2' },
			]"
			placeholder="Document"
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
		empty-icon="lucide-calendar-clock"
		:empty-message="hasFilters ? 'No shift assignments match these filters' : 'No shift assignments created yet'"
		mobile-aside="docstatus"
		min-width="900px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/shift-assignments/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name || row.employee }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }} · {{ row.name }}</div>
			</div>
		</template>
		<template #cell-status="{ row }">
			<StatusBadge doctype="Shift Assignment" :status="row.status" />
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge :status="docstatusLabel(row.docstatus)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { loadMeta, selectOptions } from "@/data/meta"
import { can, useReadableFields } from "@/data/permissions"
import { formatDateShort } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()
loadMeta("Shift Assignment")

const { ready, readable } = useReadableFields("Shift Assignment")
const FIELDS = ["employee", "employee_name", "shift_type", "company", "start_date", "end_date", "status"]

const list = useDocList({
	doctype: "Shift Assignment",
	fields: () => ["name", "docstatus", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "start_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["employee", "shift_type", "company", "status"]) {
			if (state.filters[key] && readable(key)) filters.push([key, "=", state.filters[key]])
		}
		if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
		return filters
	},
})

/** Carries the employee, shift and company filters into a new assignment. */
const newQuery = computed(() => {
	const query: Record<string, string> = {}
	for (const key of ["employee", "shift_type", "company"]) if (list.state.filters[key]) query[key] = list.state.filters[key]
	return query
})
const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns = computed<Column[]>(() =>
	[
		{ key: "employee_name", label: "Employee", width: "minmax(220px,2.2fr)", sortable: true },
		{ key: "shift_type", label: "Shift", width: "minmax(130px,1.3fr)", sortable: true },
		{ key: "company", label: "Company", width: "minmax(130px,1.3fr)", sortable: true, hideOnMobile: true },
		{
			key: "start_date",
			label: "Period",
			width: "minmax(170px,1.5fr)",
			sortable: true,
			format: (_: any, row: Record<string, any>) =>
				`${formatDateShort(row.start_date)} – ${row.end_date ? formatDateShort(row.end_date) : "ongoing"}`,
		},
		{ key: "status", label: "Status", width: "minmax(90px,0.9fr)", sortable: true, hideOnMobile: true },
		{ key: "docstatus", label: "Document", width: "minmax(100px,0.9fr)", sortable: true },
	].filter((c) => c.key === "docstatus" || readable(c.key))
)
</script>
