<template>
	<PageHeader :crumbs="[{ label: 'KPI Templates' }]">
		<template #actions>
			<template v-if="can('KPI Template').create">
				<Button icon-left="lucide-copy" label="Copy last month" class="hidden sm:inline-flex" @click="copyOpen = true" />
				<Button icon-left="lucide-users" label="For a department" @click="bulkOpen = true" />
				<Button variant="solid" icon-left="lucide-plus" label="New template" :route="{ name: 'KpiTemplateNew' }" />
			</template>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employees"
		noun="template"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.fiscal_year" doctype="Fiscal Year" placeholder="Fiscal year" />
		<FilterSelect v-model="list.state.filters.month" :options="MONTHS" placeholder="Month" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" :filters="{ is_group: 0 }" />
		<FilterSelect
			v-model="list.state.filters.docstatus"
			:options="[
				{ label: 'Draft', value: '0' },
				{ label: 'Submitted', value: '1' },
				{ label: 'Cancelled', value: '2' },
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
		empty-icon="lucide-clipboard-list"
		:empty-message="hasFilters ? 'No KPI Templates match these filters' : 'No KPI Templates created yet'"
		mobile-aside="docstatus"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('KPI Template', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.designation].filter(Boolean).join(" · ") }}</div>
			</div>
		</template>
		<template #cell-docstatus="{ row }">
			<StatusBadge doctype="docstatus" :status="docstatusLabel(row.docstatus)" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<KpiTemplateBulkDialog v-model:open="bulkOpen" @created="list.reload" />

	<Dialog v-model:open="copyOpen" title="Copy last month's templates">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Creates this month's KPI Templates as drafts, from the templates submitted last month. Employees who left, or who already have a
				template this month, are skipped. This also runs by itself on the 27th.
			</p>
			<LinkField v-model="copyCompany" doctype="Company" label="Company" required size="md" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="copyOpen = false" />
				<Button variant="solid" label="Copy" :disabled="!copyCompany" :loading="copying" @click="copy" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button, Dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import LinkField from "@/components/fields/LinkField.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import KpiTemplateBulkDialog from "./KpiTemplateBulkDialog.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { copyKpiTemplates, MONTHS } from "@/data/pms"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import { docstatusLabel } from "@/utils/status"

const router = useRouter()

const list = useDocList({
	doctype: "KPI Template",
	fields: ["name", "employee", "employee_name", "department", "designation", "fiscal_year", "month", "total_weight", "docstatus"],
	searchFields: ["employee_name", "employee"],
	defaultSort: { field: "creation", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const field of ["fiscal_year", "month", "department"]) {
			if (state.filters[field]) filters.push([field, "=", state.filters[field]])
		}
		if (state.filters.docstatus) filters.push(["docstatus", "=", Number(state.filters.docstatus)])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const bulkOpen = ref(false)
const copyOpen = ref(false)
const copyCompany = ref<string | null>(null)
const copying = ref(false)

async function copy() {
	copying.value = true
	try {
		const outcome = await copyKpiTemplates(copyCompany.value!)
		copyOpen.value = false
		toast.success(
			outcome.created.length
				? `${outcome.created.length} draft templates created for ${outcome.month}`
				: `Nothing to copy from ${outcome.source} to ${outcome.month}`
		)
		list.reload()
	} finally {
		copying.value = false
	}
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)", sortable: true },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "month", label: "Month", width: "130px", format: (_, row) => `${row.month} ${row.fiscal_year}` },
	{ key: "total_weight", label: "Weight", width: "90px", align: "right", hideOnMobile: true, format: (v) => formatNumber(v || 0) },
	{ key: "docstatus", label: "Status", width: "120px", sortable: true },
]
</script>
