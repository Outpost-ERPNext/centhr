<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="flex flex-wrap items-center gap-2">
			<div class="w-56">
				<FilterLink :model-value="company" doctype="Company" placeholder="Company" @update:model-value="overview.setCompany" />
			</div>
			<PayrollCycleNav
				v-if="company"
				:company="company"
				:from="period.from"
				:to="period.to"
				@update:from="period.from = $event"
				@update:to="period.to = $event"
			/>
		</div>
		<slot name="toolbar" />
		<SalaryStatTiles v-model="tile" :tiles="TILES" :counts="tileCounts" :loading="loading" />
		<SegmentedTabs v-model="view" :tabs="STRUCTURE_VIEWS.map((v) => ({ label: v.label, value: v.key, count: viewCounts[v.key] }))" />
	</div>

	<FilterBar v-model:search="search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="employee" @clear="overview.clearFilters">
		<FilterSelect v-model="department" :options="distinct(rows, 'department')" placeholder="Department" />
		<FilterSelect v-model="structure" :options="distinct(rows, 'salary_structure')" placeholder="Structure" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:sort-field="sort.field"
		:sort-order="sort.order"
		:show-clear="hasFilters"
		empty-icon="lucide-users"
		:empty-message="company ? 'No employees match these filters' : 'Choose a company to see its employees'"
		mobile-aside="slip_status"
		min-width="1080px"
		@sort="overview.toggleSort"
		@row-click="(row) => router.push(employeeRoute(row.name))"
		@clear-filters="overview.clearFilters"
	>
		<template #cell-name="{ row }">
			<span class="font-medium text-ch-primary">{{ row.name }}</span>
		</template>
		<template #cell-salary_structure="{ row }">
			<div v-if="row.salary_structure" class="flex min-w-0 items-center gap-1.5">
				<span class="truncate rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] font-medium text-ch-ink-2">{{ row.salary_structure }}</span>
				<StatusBadge v-if="row.structure_inactive" pill tone="red" status="Inactive" />
			</div>
			<StatusBadge v-else tone="amber" status="Missing" />
		</template>
		<template #cell-slip_status="{ row }">
			<RouterLink v-if="row.salary_slip" :to="routeFor('Salary Slip', row.salary_slip)!" class="inline-flex" @click.stop>
				<StatusBadge pill doctype="Salary Slip" :status="row.slip_status" />
			</RouterLink>
			<StatusBadge v-else pill tone="gray" status="Pending" />
		</template>
		<template #cell-actions="{ row }">
			<div class="flex justify-end gap-1.5" @click.stop>
				<slot name="actions" :row="row" />
				<Button size="sm" icon-left="lucide-user" label="Profile" :route="employeeRoute(row.name)" />
			</div>
		</template>
	</DataTable>

	<Pager v-model:page="page" v-model:page-size="pageSize" :total="filtered.length" />
</template>

<script setup lang="ts">
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import SalaryStatTiles from "@/components/SalaryStatTiles.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { STRUCTURE_VIEWS, TILES, distinct } from "@/data/salaryOverview"
import type { SalaryOverview } from "@/data/useSalaryOverview"
import { routeFor } from "@/utils/routes"

/** Company and period pickers, stat tiles, structure chips and the employee table of a salary overview page. */
const props = defineProps<{ overview: SalaryOverview; columns: Column[] }>()
defineSlots<{ toolbar?: () => any; actions?: (props: { row: Record<string, any> }) => any }>()

const router = useRouter()
// Top-level refs, so the template reads them without .value
const {
	company,
	period,
	rows,
	loading,
	error,
	tile,
	view,
	search,
	department,
	structure,
	sort,
	page,
	pageSize,
	tileCounts,
	viewCounts,
	filtered,
	pageRows,
	hasFilters,
} = props.overview

const employeeRoute = (name: string) => routeFor("Employee", name)!
</script>
