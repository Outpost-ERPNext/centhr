<template>
	<PageHeader :crumbs="[{ label: 'Attendance', route: '/attendance' }, { label: 'Attendance Request' }]">
		<template #actions>
			<Button
				v-if="can('Attendance Request').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New request"
				:route="{ name: 'AttendanceRequestNew', query: newQuery }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employee or ID"
		noun="request"
		@clear="list.clearFilters"
	>
		<FilterLink
			v-model="list.state.filters.employee"
			doctype="Employee"
			placeholder="Employee"
			:filters="list.state.filters.company ? { company: list.state.filters.company } : undefined"
		/>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" />
		<FilterSelect
			v-if="readable('reason')"
			v-model="list.state.filters.reason"
			:options="selectOptions('Attendance Request', 'reason').filter(Boolean)"
			placeholder="Reason"
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
		<DateFilter
			v-model:op="list.state.filters.date_op"
			v-model:from="list.state.filters.date_from"
			v-model:to="list.state.filters.date_to"
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
		empty-icon="lucide-calendar-plus"
		:empty-message="hasFilters ? 'No attendance requests match these filters' : 'No attendance requests yet'"
		mobile-aside="docstatus"
		min-width="900px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/attendance-requests/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name || row.employee }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }} · {{ row.name }}</div>
			</div>
		</template>
		<template #cell-reason="{ row }">
			<StatusBadge doctype="Attendance Request" :status="row.reason" />
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
import DateFilter from "@/components/DateFilter.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { loadMeta, selectOptions } from "@/data/meta"
import { can, useReadableFields } from "@/data/permissions"
import { formatDateShort } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()
loadMeta("Attendance Request")

const { ready, readable } = useReadableFields("Attendance Request")
const FIELDS = ["employee", "employee_name", "company", "department", "from_date", "to_date", "half_day", "reason"]

const list = useDocList({
	doctype: "Attendance Request",
	fields: () => ["name", "docstatus", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["employee_name", "employee", "name"],
	defaultSort: { field: "from_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const key of ["employee", "company", "department", "reason"]) {
			if (state.filters[key] && readable(key)) filters.push([key, "=", state.filters[key]])
		}
		if (state.filters.state) filters.push(["docstatus", "=", Number(state.filters.state)])
		// A request covers a period, so a date filter keeps the requests that overlap it
		const { date_op: op, date_from: from, date_to: to } = state.filters
		if (op && from) {
			if (op === "between" && to) filters.push(["from_date", "<=", to], ["to_date", ">=", from])
			else if (op === "=") filters.push(["from_date", "<=", from], ["to_date", ">=", from])
			else if (op === ">=" || op === "between") filters.push(["to_date", ">=", from])
			else if (op === "<=") filters.push(["from_date", "<=", from])
		}
		return filters
	},
})

/** Carries the employee and company filters into a new request. */
const newQuery = computed(() => {
	const query: Record<string, string> = {}
	for (const key of ["employee", "company"]) if (list.state.filters[key]) query[key] = list.state.filters[key]
	return query
})
const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns = computed<Column[]>(() =>
	[
		{ key: "employee_name", label: "Employee", width: "minmax(220px,2.2fr)", sortable: true },
		{
			key: "from_date",
			label: "Period",
			width: "minmax(170px,1.5fr)",
			sortable: true,
			format: (_: any, row: Record<string, any>) =>
				row.from_date === row.to_date
					? formatDateShort(row.from_date)
					: `${formatDateShort(row.from_date)} – ${formatDateShort(row.to_date)}`,
		},
		{ key: "half_day", label: "Half day", width: "90px", format: (v: any) => (v ? "Yes" : ""), hideOnMobile: true },
		{ key: "reason", label: "Reason", width: "minmax(130px,1fr)", sortable: true },
		{ key: "company", label: "Company", width: "minmax(130px,1.2fr)", sortable: true, hideOnMobile: true },
		{ key: "docstatus", label: "Document", width: "minmax(100px,0.9fr)", sortable: true },
	].filter((c) => c.key === "docstatus" || readable(c.key))
)
</script>
