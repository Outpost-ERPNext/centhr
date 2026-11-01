<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="flex flex-wrap items-center gap-2">
			<div class="w-56">
				<FilterLink v-model="state.company" doctype="Company" placeholder="All companies" />
			</div>
			<PayrollCycleNav :company="state.company" :from="state.from" :to="state.to" @update:from="state.from = $event" @update:to="state.to = $event" />
			<Button class="ml-auto" icon-left="lucide-file-spreadsheet" label="Export to Excel" :loading="exporting" :disabled="!filtered.length" @click="exportRows" />
		</div>
		<slot name="toolbar" />
		<PayrollAuditPanel v-if="audit" :rows="rows" :period="state" :loading="loading" />
		<CollapsibleSection title="Summary" :storage-key="`summary`" :summary="`${formatNumber(rows.length)} employees`">
			<SalaryStatTiles v-model="state.tile" :tiles="TILES" :counts="tileCounts" :loading="loading" />
		</CollapsibleSection>
		<SegmentedTabs v-model="state.view" :tabs="STRUCTURE_VIEWS.map((v) => ({ label: v.label, value: v.key, count: viewCounts[v.key] }))" />
	</div>

	<FilterBar v-model:search="state.search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="employee" @clear="overview.clearFilters">
		<FilterLink v-model="state.employee" doctype="Employee" placeholder="Employee" :filters="companyFilter" />
		<FilterLink v-model="state.department" doctype="Department" placeholder="Department" :filters="companyFilter" />
		<FilterLink v-model="state.structure" doctype="Salary Structure" placeholder="Salary structure" :filters="companyFilter" />
	</FilterBar>

	<DataTable
		:columns="shownColumns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:sort-field="state.sort"
		:sort-order="state.order"
		:show-clear="hasFilters"
		empty-icon="lucide-users"
		empty-message="No employees match these filters"
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
			<RouterLink
				v-if="row.salary_structure"
				:to="routeFor('Salary Structure Assignment', row.assignment)!"
				class="flex min-w-0 items-center gap-1.5"
				:title="`Open assignment ${row.assignment}`"
				@click.stop
			>
				<span class="truncate rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] font-medium text-ch-ink-2 hover:text-ch-ink">{{ row.salary_structure }}</span>
				<StatusBadge v-if="row.structure_inactive" pill tone="red" status="Inactive" />
			</RouterLink>
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

	<Pager v-model:page="state.page" v-model:page-size="state.pageSize" :total="filtered.length" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import Pager from "@/components/Pager.vue"
import PayrollAuditPanel from "@/components/PayrollAuditPanel.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import SalaryStatTiles from "@/components/SalaryStatTiles.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { COLUMNS, STRUCTURE_VIEWS, TILES, exportSalaryOverview } from "@/data/salaryOverview"
import type { SalaryOverview } from "@/data/useSalaryOverview"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

/** Company and period pickers, summary tiles, structure chips, filters and the employee table of a salary overview page. */
const props = defineProps<{ overview: SalaryOverview; columns: Column[]; audit?: boolean }>()
defineSlots<{ toolbar?: () => any; actions?: (props: { row: Record<string, any> }) => any }>()

const router = useRouter()
// Top-level bindings, so the template reads them without .value
const { state, rows, loading, error, tileCounts, viewCounts, filtered, pageRows, hasFilters } = props.overview
const exporting = ref(false)

const companyFilter = computed(() => (state.company ? { company: state.company } : undefined))
// With every company listed, each row needs to say whose employee it is
const shownColumns = computed(() =>
	state.company ? props.columns : props.columns.flatMap((c) => (c.key === "employee_name" ? [c, COLUMNS.company] : [c]))
)

async function exportRows() {
	exporting.value = true
	try {
		await exportSalaryOverview(state.company, state, filtered.value.map((r) => r.name))
	} catch {
		// downloadFile already showed the server's message
	} finally {
		exporting.value = false
	}
}

const employeeRoute = (name: string) => routeFor("Employee", name)!
</script>
